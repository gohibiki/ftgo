"""
Search functionality for FTMarkets library.

This module provides functions to search for financial instruments
and retrieve their XIDs from FT Markets.
"""

import pandas as pd
from urllib.parse import quote
from typing import Dict, Any, Union
import logging

from .session import cached_get

# Set up logging
logger = logging.getLogger(__name__)


def fetch_search_data(search_string: str) -> Dict[str, Any]:
    """
    Fetch search data for a given search string from FT Markets API.

    Args:
        search_string: The ticker symbol or name to search for

    Returns:
        JSON response from the API
    """
    try:
        url = f"https://markets.ft.com/data/searchapi/searchsecurities?query={quote(search_string)}"
        response = cached_get(url, use_cache=False)  # Don't cache searches
        return response.json()
    except Exception as e:
        logger.error(f"Failed to fetch search data for {search_string}: {e}")
        raise


def search_to_dataframe(json_data: Dict[str, Any]) -> pd.DataFrame:
    """
    Convert search JSON response to a pandas DataFrame.

    Args:
        json_data: JSON response from the FT Markets search API

    Returns:
        pandas.DataFrame with columns: xid, name, symbol, asset_class, url
    """
    if 'data' not in json_data or 'security' not in json_data['data']:
        logger.warning("No search data found in JSON response")
        return pd.DataFrame()

    try:
        securities = json_data['data']['security']

        processed_securities = []
        for security in securities:
            processed_securities.append({
                'xid': security.get('xid'),
                'name': security.get('name'),
                'symbol': security.get('symbol'),
                'asset_class': security.get('assetClass'),
                'url': security.get('url')
            })

        return pd.DataFrame(processed_securities)

    except (KeyError, IndexError) as e:
        logger.error(f"Error processing search JSON data: {e}")
        return pd.DataFrame()


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

    df = search_securities(ticker)

    if df.empty:
        raise ValueError(f"No data found for ticker: {ticker}")

    if display_mode == "all":
        return df
    elif display_mode == "first":
        return df.iloc[0]['xid']
    else:
        raise ValueError("Invalid display_mode. Choose 'first' or 'all'.")
