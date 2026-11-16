"""
Holdings and allocation data functionality for ftgo.

This module provides functions to fetch ETF/fund holdings, asset allocation,
sector breakdown, and geographic allocation data from FT Markets.
"""

import logging
from typing import Dict, Tuple, Union

import pandas as pd
from bs4 import BeautifulSoup

from .session import fetch_tearsheet

# Set up logging
logger = logging.getLogger(__name__)

# Constants for holdings types
ASSET_ALLOCATION = "asset_allocation"
SECTOR_WEIGHTS = "sector_weights"
GEOGRAPHIC_ALLOCATION = "geographic_allocation"
TOP_HOLDINGS = "top_holdings"
ALL_TYPES = "all"

VALID_HOLDINGS_TYPES = {ASSET_ALLOCATION, SECTOR_WEIGHTS, GEOGRAPHIC_ALLOCATION, TOP_HOLDINGS, ALL_TYPES}

TOP_HOLDINGS_COLUMNS = ['Holding', 'Symbol', '1Y Change', 'Weight']


def fetch_holdings_page(xid: str) -> str:
    """
    Fetch the holdings page HTML for a given XID from FT Markets.
    Uses cached session.

    Raises:
        ValueError: If FT Markets does not recognise the XID
    """
    try:
        return fetch_tearsheet("holdings", xid)
    except Exception as e:
        logger.error(f"Failed to fetch holdings page for XID {xid}: {e}")
        raise


def extract_fund_name(soup: BeautifulSoup) -> str:
    """Extract fund name from the page"""
    name_element = soup.find('h1', class_='mod-tearsheet-overview__header__name')
    if name_element:
        name = name_element.get_text().strip()
        if name:
            return name
    return "Unknown Fund"


def _extract_weight_table(
    soup: BeautifulSoup, container_class: str, label: str, fund_name: str
) -> pd.DataFrame:
    """Read the label and '% Net assets' columns of an allocation table."""
    columns = [label, fund_name]

    container = soup.find('div', class_=container_class)
    table = container.find('table') if container else None
    if table is None:
        return pd.DataFrame(columns=columns)

    records = []
    for row in table.find_all('tr'):
        cells = row.find_all('td')
        if len(cells) >= 2:
            records.append([cells[0].get_text(strip=True), cells[1].get_text(strip=True)])

    if not records:
        logger.warning(f"No rows found in the {label.lower()} table")

    return pd.DataFrame(records, columns=columns)


def extract_asset_allocation(soup: BeautifulSoup, fund_name: str) -> pd.DataFrame:
    """Extract asset allocation data"""
    return _extract_weight_table(soup, 'mod-asset-allocation__table', 'Asset Class', fund_name)


def extract_sector_weights(soup: BeautifulSoup, fund_name: str) -> pd.DataFrame:
    """Extract sector weights data"""
    return _extract_weight_table(soup, 'mod-weightings__sectors__table', 'Sector', fund_name)


def extract_geographic_allocation(soup: BeautifulSoup, fund_name: str) -> pd.DataFrame:
    """Extract geographic allocation data"""
    return _extract_weight_table(soup, 'mod-weightings__regions__table', 'Region', fund_name)


def extract_top_holdings(soup: BeautifulSoup) -> pd.DataFrame:
    """
    Extract top holdings data.

    Returns:
        pandas.DataFrame with columns Holding (name), Symbol (FT symbol,
        missing when the holding is not listed), 1Y Change and Weight
        (portfolio weight)
    """
    section = soup.find('div', class_='mod-top-ten')
    if section is None:
        return pd.DataFrame(columns=TOP_HOLDINGS_COLUMNS)

    # The section also holds a summary table; the holdings table is the one
    # with a "Company" header.
    table = None
    for candidate in section.find_all('table'):
        headers = [th.get_text(strip=True).lower() for th in candidate.find_all('th')]
        if 'company' in headers:
            table = candidate
            break

    if table is None:
        logger.warning("Top holdings table not found; the page layout may have changed")
        return pd.DataFrame(columns=TOP_HOLDINGS_COLUMNS)

    records = []
    for row in table.find_all('tr'):
        cells = row.find_all('td')
        if len(cells) < 3:  # header and "per cent of portfolio" footer rows
            continue

        name_cell = cells[0]
        symbol_element = name_cell.find('span', class_='mod-ui-table__cell__disclaimer')
        symbol = symbol_element.get_text(strip=True) if symbol_element else None

        name_parts = list(name_cell.stripped_strings)
        if symbol and name_parts and name_parts[-1] == symbol:
            name_parts = name_parts[:-1]

        records.append([
            ' '.join(name_parts),
            symbol or None,
            cells[1].get_text(strip=True),
            cells[2].get_text(strip=True),
        ])

    return pd.DataFrame(records, columns=TOP_HOLDINGS_COLUMNS)


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
) -> Union[pd.DataFrame, Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]]:
    """
    Get holdings and allocation data for ETFs and funds from FT Markets.

    Args:
        xid: The FT Markets XID
        holdings_type: Type of holdings data to retrieve

    Returns:
        - pandas.DataFrame for specific holdings type
        - Tuple of DataFrames for "all": (asset_allocation, sector_weights, geographic_allocation, top_holdings)

        A DataFrame is empty when FT Markets has no such data for the security.

    Raises:
        ValueError: If a parameter is invalid or FT Markets does not recognise the XID
        requests.RequestException: On network errors or HTTP error statuses
    """
    if not xid:
        raise ValueError("Missing required parameter: xid")

    if holdings_type not in VALID_HOLDINGS_TYPES:
        raise ValueError(
            f"Invalid holdings_type '{holdings_type}'. "
            f"Choose from: {', '.join(sorted(VALID_HOLDINGS_TYPES))}"
        )

    logger.info(f"Fetching holdings data for XID {xid}, type: {holdings_type}")

    holdings_data = parse_holdings_data(fetch_holdings_page(xid))

    if holdings_type == ALL_TYPES:
        return (
            holdings_data[ASSET_ALLOCATION],
            holdings_data[SECTOR_WEIGHTS],
            holdings_data[GEOGRAPHIC_ALLOCATION],
            holdings_data[TOP_HOLDINGS]
        )

    return holdings_data[holdings_type]


def get_fund_breakdown(xid: str) -> Dict[str, pd.DataFrame]:
    """Get complete fund breakdown with all allocation data."""
    if not xid:
        raise ValueError("Missing required parameter: xid")

    logger.info(f"Fetching complete fund breakdown for XID {xid}")

    return parse_holdings_data(fetch_holdings_page(xid))


__all__ = [
    "get_holdings",
    "get_fund_breakdown",
    "ASSET_ALLOCATION",
    "SECTOR_WEIGHTS",
    "GEOGRAPHIC_ALLOCATION",
    "TOP_HOLDINGS",
    "ALL_TYPES"
]
