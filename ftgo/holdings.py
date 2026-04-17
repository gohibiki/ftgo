"""
Holdings and allocation data functionality for FTMarkets.

This module provides functions to fetch ETF/fund holdings, asset allocation,
sector breakdown, and geographic allocation data from FT Markets.
"""

import pandas as pd
from bs4 import BeautifulSoup
from typing import Dict, Tuple
from io import StringIO
import logging

from .session import cached_get

# Set up logging
logger = logging.getLogger(__name__)

# Constants for holdings types
ASSET_ALLOCATION = "asset_allocation"
SECTOR_WEIGHTS = "sector_weights"
GEOGRAPHIC_ALLOCATION = "geographic_allocation"
TOP_HOLDINGS = "top_holdings"
ALL_TYPES = "all"

VALID_HOLDINGS_TYPES = {ASSET_ALLOCATION, SECTOR_WEIGHTS, GEOGRAPHIC_ALLOCATION, TOP_HOLDINGS, ALL_TYPES}


def fetch_holdings_page(xid: str) -> str:
    """
    Fetch the holdings page HTML for a given XID from FT Markets.
    Uses cached session.
    """
    try:
        url = f"https://markets.ft.com/data/etfs/tearsheet/holdings?s={xid}"
        response = cached_get(url)
        return response.text
    except Exception as e:
        logger.error(f"Failed to fetch holdings page for XID {xid}: {e}")
        raise


def extract_fund_name(soup: BeautifulSoup) -> str:
    """Extract fund name from the page"""
    try:
        name_element = soup.find('h1', {
            'class': 'mod-tearsheet-overview__header__name mod-tearsheet-overview__header__name--large'
        })
        if name_element:
            return name_element.get_text().strip()
    except Exception:
        pass
    return "Unknown Fund"


def extract_asset_allocation(soup: BeautifulSoup, fund_name: str) -> pd.DataFrame:
    """Extract asset allocation data"""
    try:
        allocation_div = soup.find('div', {'class': 'mod-asset-allocation__table'})
        if allocation_div:
            html_string = str(allocation_div)
            df_list = pd.read_html(StringIO(html_string))
            if df_list:
                df = df_list[0]
                if len(df.columns) >= 2:
                    df = df.iloc[:, :2]
                    df.columns = ['Asset Class', fund_name]
                    return df
    except Exception as e:
        logger.warning(f"Could not extract asset allocation: {e}")

    return pd.DataFrame(columns=['Asset Class', fund_name])


def extract_sector_weights(soup: BeautifulSoup, fund_name: str) -> pd.DataFrame:
    """Extract sector weights data"""
    try:
        sectors_div = soup.find('div', {'class': 'mod-weightings__sectors__table'})
        if sectors_div:
            html_string = str(sectors_div)
            df_list = pd.read_html(StringIO(html_string))
            if df_list:
                df = df_list[0]
                if len(df.columns) >= 2:
                    df = df.iloc[:, :2]
                    df.columns = ['Sector', fund_name]
                    return df
    except Exception as e:
        logger.warning(f"Could not extract sector weights: {e}")

    return pd.DataFrame(columns=['Sector', fund_name])


def extract_geographic_allocation(soup: BeautifulSoup, fund_name: str) -> pd.DataFrame:
    """Extract geographic allocation data"""
    try:
        geo_div = soup.find('div', {'class': 'mod-weightings__regions__table'})
        if geo_div:
            html_string = str(geo_div)
            df_list = pd.read_html(StringIO(html_string))
            if df_list:
                df = df_list[0]
                if len(df.columns) >= 2:
                    df = df.iloc[:, :2]
                    df.columns = ['Region', fund_name]
                    return df
    except Exception as e:
        logger.warning(f"Could not extract geographic allocation: {e}")

    return pd.DataFrame(columns=['Region', fund_name])


def extract_top_holdings(soup: BeautifulSoup) -> pd.DataFrame:
    """Extract top holdings data"""
    try:
        module_divs = soup.find_all('div', {'class': 'mod-module__content'})

        if len(module_divs) >= 3:
            holdings_html = str(module_divs[2]).replace('100%', '')
            df_list = pd.read_html(StringIO(holdings_html))

            if len(df_list) >= 2:
                df = df_list[1]
                if len(df.columns) >= 3:
                    df = df.iloc[:10, :3]
                    df.columns = ['Holding', 'Weight', 'Shares'] if len(df.columns) >= 3 else df.columns
                    return df
    except Exception as e:
        logger.warning(f"Could not extract top holdings: {e}")

    return pd.DataFrame(columns=['Holding', 'Weight', 'Shares'])


def parse_holdings_data(html_content: str) -> Dict[str, pd.DataFrame]:
    """Parse holdings data from HTML content into structured DataFrames."""
    soup = BeautifulSoup(html_content, 'html.parser')

    fund_name = extract_fund_name(soup)

    return {
        ASSET_ALLOCATION: extract_asset_allocation(soup, fund_name),
        SECTOR_WEIGHTS: extract_sector_weights(soup, fund_name),
        GEOGRAPHIC_ALLOCATION: extract_geographic_allocation(soup, fund_name),
        TOP_HOLDINGS: extract_top_holdings(soup)
    }


def get_holdings(
    xid: str,
    holdings_type: str = "all"
) -> pd.DataFrame | Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Get holdings and allocation data for ETFs and funds from FT Markets.

    Args:
        xid: The FT Markets XID
        holdings_type: Type of holdings data to retrieve

    Returns:
        - pandas.DataFrame for specific holdings type
        - Tuple of DataFrames for "all": (asset_allocation, sector_weights, geographic_allocation, top_holdings)
    """
    if not xid:
        raise ValueError("Missing required parameter: xid")

    if holdings_type not in VALID_HOLDINGS_TYPES:
        raise ValueError(
            f"Invalid holdings_type '{holdings_type}'. "
            f"Choose from: {', '.join(sorted(VALID_HOLDINGS_TYPES))}"
        )

    logger.info(f"Fetching holdings data for XID {xid}, type: {holdings_type}")

    try:
        html_content = fetch_holdings_page(xid)
        holdings_data = parse_holdings_data(html_content)

        if holdings_type == ALL_TYPES:
            return (
                holdings_data[ASSET_ALLOCATION],
                holdings_data[SECTOR_WEIGHTS],
                holdings_data[GEOGRAPHIC_ALLOCATION],
                holdings_data[TOP_HOLDINGS]
            )
        else:
            return holdings_data[holdings_type]

    except Exception as e:
        logger.error(f"Error retrieving holdings data: {e}")
        raise


def get_fund_breakdown(xid: str) -> Dict[str, pd.DataFrame]:
    """Get complete fund breakdown with all allocation data."""
    logger.info(f"Fetching complete fund breakdown for XID {xid}")

    html_content = fetch_holdings_page(xid)
    return parse_holdings_data(html_content)


__all__ = [
    "get_holdings",
    "get_fund_breakdown",
    "ASSET_ALLOCATION",
    "SECTOR_WEIGHTS",
    "GEOGRAPHIC_ALLOCATION",
    "TOP_HOLDINGS",
    "ALL_TYPES"
]
