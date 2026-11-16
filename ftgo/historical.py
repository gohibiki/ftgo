"""
Historical data fetching functionality for ftgo.

This module provides functions to fetch and process historical price data
from FT Markets with support for OHLCV data and concurrent processing.
"""

import concurrent.futures
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode

import pandas as pd
from bs4 import BeautifulSoup

from .exceptions import FTMarketsError
from .session import BASE_URL, cached_get, invalidate

# Set up logging
logger = logging.getLogger(__name__)

PRICE_COLUMNS = ['date', 'open', 'high', 'low', 'close', 'volume']

_ROW_DATE_FORMATS = ('%A, %B %d, %Y', '%B %d, %Y')
_CHUNK_YEARS = 10  # Max years per API request (~12yr limit, use 10 for safety)


def _empty_prices() -> pd.DataFrame:
    """Empty price DataFrame with the standard columns."""
    return pd.DataFrame({
        'date': pd.Series(dtype='datetime64[ns]'),
        'open': pd.Series(dtype='float64'),
        'high': pd.Series(dtype='float64'),
        'low': pd.Series(dtype='float64'),
        'close': pd.Series(dtype='float64'),
        'volume': pd.Series(dtype='int64'),
    })


def _parse_date_arg(value: str, name: str) -> datetime:
    """Parse a DDMMYYYY argument, raising a clear ValueError if invalid."""
    try:
        return datetime.strptime(value, "%d%m%Y")
    except (TypeError, ValueError):
        raise ValueError(
            f"{name} must be a date string in DDMMYYYY format, got {value!r}"
        ) from None


def _parse_date_range(date_from: str, date_to: str) -> Tuple[datetime, datetime]:
    start_date = _parse_date_arg(date_from, "date_from")
    end_date = _parse_date_arg(date_to, "date_to")
    if start_date > end_date:
        raise ValueError(f"date_from ({date_from}) cannot be after date_to ({date_to})")
    return start_date, end_date


def fetch_historical_prices(xid: str, date_from: str, date_to: str) -> Dict[str, Any]:
    """
    Fetch historical price data from FT Markets API.

    Args:
        xid: The FT Markets XID
        date_from: Start date in DDMMYYYY format
        date_to: End date in DDMMYYYY format

    Returns:
        JSON response from the API

    Raises:
        FTMarketsError: If FT Markets does not answer with JSON
        requests.RequestException: On network errors or HTTP error statuses
    """
    start_date = _parse_date_arg(date_from, "date_from")
    end_date = _parse_date_arg(date_to, "date_to")

    query = urlencode({
        'startDate': start_date.strftime("%Y/%m/%d"),
        'endDate': end_date.strftime("%Y/%m/%d"),
        'symbol': xid,
    })
    url = f"{BASE_URL}/equities/ajax/get-historical-prices?{query}"

    response = cached_get(url)
    try:
        data = response.json()
    except ValueError as e:
        invalidate(url)
        raise FTMarketsError(
            f"FT Markets did not return JSON for XID {xid} ({date_from}-{date_to}); "
            "the request was rejected or the date range is too large"
        ) from e

    if not isinstance(data, dict):
        invalidate(url)
        raise FTMarketsError(f"Unexpected response from FT Markets for XID {xid}")

    return data


def _cell_text(cell) -> str:
    """Text of a table cell, preferring the first (long format) span."""
    span = cell.find('span')
    return (span if span is not None else cell).get_text().strip()


def _parse_row_date(text: str) -> Optional[datetime]:
    for fmt in _ROW_DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _parse_number(text: str) -> Optional[float]:
    try:
        return float(text.replace(',', ''))
    except ValueError:
        return None


def html_to_dataframe(html_content: str) -> pd.DataFrame:
    """
    Convert HTML response to a pandas DataFrame.

    Args:
        html_content: HTML content from the FT Markets API

    Returns:
        pandas.DataFrame with columns date, open, high, low, close, volume,
        sorted by date. Prices FT does not report are NaN. ``volume`` is int64,
        or nullable Int64 when FT does not report it for some rows.

    Raises:
        FTMarketsError: If the rows are not in the expected format
    """
    if not html_content:
        return _empty_prices()

    soup = BeautifulSoup(html_content, 'html.parser')

    records = []
    volumes = []
    candidate_rows = 0
    dated_rows = 0

    for row in soup.find_all('tr'):
        cells = row.find_all('td')
        if len(cells) < 6:
            continue
        candidate_rows += 1

        date_obj = _parse_row_date(_cell_text(cells[0]))
        if date_obj is None:
            continue
        dated_rows += 1

        prices = [_parse_number(cells[i].get_text().strip()) for i in range(1, 5)]
        if all(price is None for price in prices):
            continue

        volume = _parse_number(_cell_text(cells[5]))
        records.append([date_obj] + prices)
        volumes.append(None if volume is None else int(volume))

    if candidate_rows and not dated_rows:
        raise FTMarketsError(
            "Could not parse FT Markets historical price rows; "
            "the page layout may have changed"
        )

    skipped = candidate_rows - len(records)
    if skipped:
        logger.warning(f"Skipped {skipped} of {candidate_rows} price rows that could not be parsed")

    if not records:
        return _empty_prices()

    df = pd.DataFrame(records, columns=PRICE_COLUMNS[:5])
    df['date'] = pd.to_datetime(df['date'])
    for column in PRICE_COLUMNS[1:5]:
        df[column] = df[column].astype('float64')

    volume_values = pd.array(volumes, dtype='Int64')
    df['volume'] = volume_values if volume_values.isna().any() else volume_values.astype('int64')

    return df.sort_values('date').reset_index(drop=True)


def _chunk_ranges(start_date: datetime, end_date: datetime) -> List[Tuple[pd.Timestamp, pd.Timestamp]]:
    """
    Split an inclusive date range into chunks the API accepts, newest first.

    Chunks do not overlap and together cover every day of the range.
    """
    start = pd.Timestamp(start_date)
    chunk_end = pd.Timestamp(end_date)

    ranges = []
    while chunk_end >= start:
        chunk_start = max(start, chunk_end - pd.DateOffset(years=_CHUNK_YEARS))
        ranges.append((chunk_start, chunk_end))
        chunk_end = chunk_start - pd.Timedelta(days=1)

    return ranges


def _fetch_single_chunk(xid: str, date_from: str, date_to: str) -> pd.DataFrame:
    """Fetch a single chunk of historical data (within API limits)."""
    json_data = fetch_historical_prices(xid, date_from, date_to)
    return html_to_dataframe(json_data.get('html') or '')


def get_historical_prices(xid: str, date_from: str, date_to: str) -> pd.DataFrame:
    """
    Get historical price data for a security with full OHLCV data.
    Automatically splits large date ranges into chunks to work around
    the API's ~12 year per-request limit.

    Args:
        xid: The FT Markets XID
        date_from: Start date in DDMMYYYY format
        date_to: End date in DDMMYYYY format

    Returns:
        pandas.DataFrame with OHLCV data covering the full requested range.
        The DataFrame is empty (with the standard columns) when FT Markets has
        no prices for the range, which is also what it reports for an unknown XID.

    Raises:
        ValueError: If the XID is empty or the dates are invalid
        FTMarketsError: If FT Markets returns an unexpected response
        requests.RequestException: On network errors or HTTP error statuses
    """
    if not xid:
        raise ValueError("XID cannot be empty")

    start_date, end_date = _parse_date_range(date_from, date_to)
    ranges = _chunk_ranges(start_date, end_date)

    logger.info(
        f"Fetching historical data for XID {xid} from {date_from} to {date_to} "
        f"({len(ranges)} request(s))"
    )

    chunks = []
    for chunk_start, chunk_end in ranges:
        df = _fetch_single_chunk(
            xid, chunk_start.strftime("%d%m%Y"), chunk_end.strftime("%d%m%Y")
        )
        if not df.empty:
            chunks.append(df)

    if not chunks:
        logger.warning(f"No data retrieved for XID {xid}")
        return _empty_prices()

    combined = chunks[0] if len(chunks) == 1 else pd.concat(chunks, ignore_index=True)
    combined = combined.drop_duplicates(subset=['date']).sort_values('date').reset_index(drop=True)

    logger.info(f"Successfully retrieved {len(combined)} data points for XID {xid}")
    return combined


def get_multiple_historical_prices_dict(
    xids: List[str],
    date_from: str,
    date_to: str,
    max_workers: int = 3
) -> Dict[str, pd.DataFrame]:
    """
    Get historical data for multiple securities concurrently, returned as a dict.

    Securities that fail to download or have no data are logged and left out
    of the result, so compare its keys with ``xids`` to detect them.

    Args:
        xids: List of FT Markets XIDs
        date_from: Start date in DDMMYYYY format
        date_to: End date in DDMMYYYY format
        max_workers: Max concurrent threads (default 3)

    Returns:
        Dict mapping xid -> DataFrame with OHLCV data, in the order of ``xids``

    Raises:
        ValueError: If the XIDs list is empty or the dates are invalid
    """
    if not xids:
        raise ValueError("XIDs list cannot be empty")

    # Validate once up front so a bad date fails loudly instead of per security
    _parse_date_range(date_from, date_to)

    unique_xids = list(dict.fromkeys(xids))
    logger.info(f"Fetching data for {len(unique_xids)} securities")

    fetched = {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_xid = {
            executor.submit(get_historical_prices, xid, date_from, date_to): xid
            for xid in unique_xids
        }

        for future in concurrent.futures.as_completed(future_to_xid):
            xid = future_to_xid[future]
            try:
                result = future.result()
            except Exception as e:
                logger.error(f"Error fetching data for XID {xid}: {e}")
                continue
            if not result.empty:
                fetched[xid] = result

    logger.info(f"Successfully retrieved data for {len(fetched)}/{len(unique_xids)} securities")
    return {xid: fetched[xid] for xid in unique_xids if xid in fetched}


def get_multiple_historical_prices(
    xids: List[str],
    date_from: str,
    date_to: str,
    max_workers: int = 3
) -> pd.DataFrame:
    """
    Get historical data for multiple securities concurrently.

    Securities that fail to download or have no data are logged and left out
    of the result.

    Args:
        xids: List of FT Markets XIDs
        date_from: Start date in DDMMYYYY format
        date_to: End date in DDMMYYYY format
        max_workers: Max concurrent threads (default 3)

    Returns:
        pandas.DataFrame in long format with columns xid, date, open, high,
        low, close, volume, ordered by the position of the xid in ``xids``
        and then by date

    Raises:
        ValueError: If the XIDs list is empty or the dates are invalid
    """
    results = get_multiple_historical_prices_dict(xids, date_from, date_to, max_workers)

    if not results:
        logger.warning("No data retrieved for any securities")
        empty = _empty_prices()
        empty.insert(0, 'xid', pd.Series(dtype='object'))
        return empty

    frames = []
    for xid, df in results.items():
        df = df.copy()
        df.insert(0, 'xid', xid)
        frames.append(df)

    return pd.concat(frames, axis=0, ignore_index=True)
