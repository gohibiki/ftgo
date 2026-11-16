"""
Search functionality for the ftgo library.

This module provides functions to search for financial instruments
and retrieve their XIDs from FT Markets.
"""

import logging
from typing import Any, Dict, Union
from urllib.parse import quote

import pandas as pd

from .exceptions import FTMarketsError
from .session import BASE_URL, cached_get

# Set up logging
logger = logging.getLogger(__name__)

SEARCH_COLUMNS = ['xid', 'name', 'symbol', 'asset_class', 'url']
VALID_DISPLAY_MODES = ("first", "all")


def fetch_search_data(search_string: str) -> Dict[str, Any]:
    """
    Fetch search data for a given search string from FT Markets API.

    Args:
        search_string: The ticker symbol or name to search for

    Returns:
        JSON response from the API

    Raises:
        FTMarketsError: If FT Markets does not answer with JSON
        requests.RequestException: On network errors or HTTP error statuses
    """
    url = f"{BASE_URL}/searchapi/searchsecurities?query={quote(search_string, safe='')}"
    response = cached_get(url, use_cache=False)  # Don't cache searches

    try:
        data = response.json()
    except ValueError as e:
        raise FTMarketsError(f"FT Markets did not return JSON for search '{search_string}'") from e

    if not isinstance(data, dict):
        raise FTMarketsError(f"Unexpected search response from FT Markets for '{search_string}'")

    return data


def search_to_dataframe(json_data: Dict[str, Any]) -> pd.DataFrame:
    """
    Convert search JSON response to a pandas DataFrame.

    Args:
        json_data: JSON response from the FT Markets search API

    Returns:
        pandas.DataFrame with columns: xid, name, symbol, asset_class, url
    """
    data = json_data.get('data') if isinstance(json_data, dict) else None
    securities = data.get('security') if isinstance(data, dict) else None

    if not securities:
        logger.warning("No search data found in JSON response")
        return pd.DataFrame(columns=SEARCH_COLUMNS)

    processed_securities = [
        [
            security.get('xid'),
            security.get('name'),
            security.get('symbol'),
            security.get('assetClass'),
            security.get('url'),
        ]
        for security in securities
        if isinstance(security, dict)
    ]

    return pd.DataFrame(processed_securities, columns=SEARCH_COLUMNS)


def search_securities(query: str) -> pd.DataFrame:
    """
    Search for securities on FT Markets.

    Args:
        query: Search term for securities (ticker symbol or company name)

    Returns:
        pandas.DataFrame with search results containing:
        - xid: FT Markets identifier
        - name: Company/security name
        - symbol: Trading symbol
        - asset_class: Type of security (Equities, ETFs, etc.)
        - url: FT Markets URL path

    Raises:
        ValueError: If query is empty
    """
    if not query:
        raise ValueError("Query parameter cannot be empty")

    logger.info(f"Searching for securities with query: {query}")

    json_data = fetch_search_data(query)
    df = search_to_dataframe(json_data)

    logger.info(f"Found {len(df)} securities for query: {query}")
    return df


def get_xid(
    ticker: str,
    display_mode: str = "first"
) -> Union[str, pd.DataFrame]:
    """
    Get FT Markets XID for given ticker symbol.

    Args:
        ticker: Single ticker symbol
        display_mode: "first" to return first match XID, "all" to return all matches

    Returns:
        - If display_mode="first": String XID of first match
        - If display_mode="all": pandas.DataFrame with all search results

    Raises:
        ValueError: If parameters are invalid or no data is found
    """
    if not ticker:
        raise ValueError("Ticker parameter cannot be empty")

    if display_mode not in VALID_DISPLAY_MODES:
        raise ValueError("Invalid display_mode. Choose 'first' or 'all'.")

    df = search_securities(ticker)

    if df.empty:
        raise ValueError(f"No data found for ticker: {ticker}")

    if display_mode == "all":
        return df

    return df.iloc[0]['xid']
