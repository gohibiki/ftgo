"""
Holdings and allocation data functionality for FTMarkets.

This module provides functions to fetch ETF/fund holdings, asset allocation,
sector breakdown, and geographic allocation data from FT Markets.
"""

import cloudscraper
import pandas as pd
from bs4 import BeautifulSoup
from typing import Dict, Any, Tuple, Optional
from io import StringIO
import logging

# Set up logging
logger = logging.getLogger(__name__)

# Constants for holdings types
ASSET_ALLOCATION = "asset_allocation"
SECTOR_WEIGHTS = "sector_weights"  
GEOGRAPHIC_ALLOCATION = "geographic_allocation"
TOP_HOLDINGS = "top_holdings"
ALL_TYPES = "all"

# Valid holdings types for validation
VALID_HOLDINGS_TYPES = {ASSET_ALLOCATION, SECTOR_WEIGHTS, GEOGRAPHIC_ALLOCATION, TOP_HOLDINGS, ALL_TYPES}


def fetch_holdings_page(xid: str) -> str:
    """
    Fetch the holdings page HTML for a given XID from FT Markets.
    
    Args:
        xid: The FT Markets XID
        
    Returns:
        HTML content of the holdings page
        
    Raises:
        requests.exceptions.HTTPError: If the API request fails
    """
    scraper = cloudscraper.create_scraper(
        browser={
            'browser': 'chrome',
            'platform': 'windows',
            'desktop': True
        }
    )
    
    try:
        # Construct holdings URL using XID
        url = f"https://markets.ft.com/data/etfs/tearsheet/holdings?s={xid}"
        
        response = scraper.get(url)
        response.raise_for_status()
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
                # Rename the percentage column to fund name
                if len(df.columns) >= 2:
                    df = df.iloc[:, :2]  # Keep only first two columns
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
                # Rename the percentage column to fund name
                if len(df.columns) >= 2:
                    df = df.iloc[:, :2]  # Keep only first two columns
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
                # Rename the percentage column to fund name
                if len(df.columns) >= 2:
                    df = df.iloc[:, :2]  # Keep only first two columns
                    df.columns = ['Region', fund_name]
                    return df
    except Exception as e:
        logger.warning(f"Could not extract geographic allocation: {e}")
    
    return pd.DataFrame(columns=['Region', fund_name])


def extract_top_holdings(soup: BeautifulSoup) -> pd.DataFrame:
    """Extract top holdings data"""
    try:
        # Find all module content divs
        module_divs = soup.find_all('div', {'class': 'mod-module__content'})
        
        # Usually holdings are in the 3rd module (index 2)
        if len(module_divs) >= 3:
            holdings_html = str(module_divs[2]).replace('100%', '')  # Remove 100% text that breaks parsing
            df_list = pd.read_html(StringIO(holdings_html))
            
            # Usually the second table contains the holdings
            if len(df_list) >= 2:
                df = df_list[1]
                # Keep only first 3 columns and top 10 holdings
                if len(df.columns) >= 3:
                    df = df.iloc[:10, :3]
                    # Standardize column names
                    df.columns = ['Holding', 'Weight', 'Shares'] if len(df.columns) >= 3 else df.columns
                    return df
    except Exception as e:
        logger.warning(f"Could not extract top holdings: {e}")
    
    return pd.DataFrame(columns=['Holding', 'Weight', 'Shares'])


def parse_holdings_data(html_content: str) -> Dict[str, pd.DataFrame]:
    """
    Parse holdings data from HTML content into structured DataFrames.
    
    Args:
        html_content: Raw HTML content from FT Markets holdings page
        
    Returns:
        Dictionary containing DataFrames for different holdings types:
        - asset_allocation: Asset class breakdown
        - sector_weights: Sector allocation
        - geographic_allocation: Geographic allocation
        - top_holdings: Top holdings by weight
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Extract fund name
    fund_name = extract_fund_name(soup)
    
    # Extract all data types
    asset_allocation = extract_asset_allocation(soup, fund_name)
    sector_weights = extract_sector_weights(soup, fund_name)
    geographic_allocation = extract_geographic_allocation(soup, fund_name)
    top_holdings = extract_top_holdings(soup)
    
    return {
        ASSET_ALLOCATION: asset_allocation,
        SECTOR_WEIGHTS: sector_weights,
        GEOGRAPHIC_ALLOCATION: geographic_allocation,
        TOP_HOLDINGS: top_holdings
    }


def get_holdings(
    xid: str,
    holdings_type: str = "all"
) -> pd.DataFrame | Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Get holdings and allocation data for ETFs and funds from FT Markets.
    
    Args:
        xid: The FT Markets XID (use get_xid to find this)
        holdings_type: Type of holdings data to retrieve:
            - "asset_allocation": Breakdown by asset class (stocks, bonds, cash)
            - "sector_weights": Sector allocation
            - "geographic_allocation": Geographic allocation
            - "top_holdings": Top holdings by weight percentage
            - "all": All holdings data types as a tuple
            
    Returns:
        - pandas.DataFrame for specific holdings type
        - Tuple of DataFrames for "all": (asset_allocation, sector_weights, geographic_allocation, top_holdings)
        
    Raises:
        ValueError: If xid is missing or holdings_type is invalid
        
    Examples:
        >>> from ftmarkets import get_xid, get_holdings
        >>> xid = get_xid('SPY')
        >>> asset_allocation = get_holdings(xid, "asset_allocation")
        >>> print(asset_allocation)
        
        >>> # Get all data
        >>> all_data = get_holdings(xid, "all")
        >>> asset_alloc, sectors, regions, holdings = all_data
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
    """
    Get complete fund breakdown with all allocation data.
    
    Args:
        xid: The FT Markets XID
        
    Returns:
        Dictionary with all DataFrames:
        - 'asset_allocation': Asset class breakdown
        - 'sector_weights': Sector weights
        - 'geographic_allocation': Geographic distribution
        - 'top_holdings': Top 10 holdings
        
    Examples:
        >>> xid = get_xid('QQQ')
        >>> breakdown = get_fund_breakdown(xid)
        >>> print(breakdown['asset_allocation'])
        >>> print(breakdown['top_holdings'])
    """
    logger.info(f"Fetching complete fund breakdown for XID {xid}")
    
    html_content = fetch_holdings_page(xid)
    return parse_holdings_data(html_content)


# Update __all__ for exports
__all__ = [
    "get_holdings",
    "get_fund_breakdown",
    "ASSET_ALLOCATION",
    "SECTOR_WEIGHTS", 
    "GEOGRAPHIC_ALLOCATION",
    "TOP_HOLDINGS",
    "ALL_TYPES"
]