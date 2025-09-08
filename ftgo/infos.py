"""
Profile and information data functionality for FTMarkets.

This module provides functions to fetch ETF/fund profile information,
key statistics, and investment details from FT Markets.
"""

import cloudscraper
import pandas as pd
from bs4 import BeautifulSoup
from typing import Dict, Any, Optional
import logging

# Set up logging
logger = logging.getLogger(__name__)


def fetch_profile_page(xid: str) -> str:
    """
    Fetch the profile/summary page HTML for a given XID from FT Markets.
    
    Args:
        xid: The FT Markets XID
        
    Returns:
        HTML content of the profile page
        
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
        # Construct profile URL using XID
        url = f"https://markets.ft.com/data/etfs/tearsheet/summary?s={xid}"
        
        response = scraper.get(url)
        response.raise_for_status()
        return response.text
    except Exception as e:
        logger.error(f"Failed to fetch profile page for XID {xid}: {e}")
        raise


def extract_profile_data(html_content: str) -> pd.DataFrame:
    """
    Extract profile and investment data from FT Markets ETF page HTML.
    
    Args:
        html_content: Raw HTML content from FT Markets profile page
        
    Returns:
        pandas.DataFrame with Field and Value columns containing profile information
        
    Note:
        Returns empty DataFrame if no profile data is found
    """
    if not html_content:
        logger.warning("No HTML content provided")
        return pd.DataFrame(columns=['Field', 'Value'])
    
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Find the Profile and Investment section
        profile_section = soup.find('div', {'data-f2-app-id': 'mod-profile-and-investment-app'})
        
        if not profile_section:
            logger.warning("Profile and Investment section not found")
            return pd.DataFrame(columns=['Field', 'Value'])
        
        # Extract all table data
        data = []
        tables = profile_section.find_all('table')
        
        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                th = row.find('th')
                td = row.find('td')
                
                if th and td:
                    field = th.get_text(strip=True)
                    value = td.get_text(separator=' ', strip=True)
                    value = ' '.join(value.split())  # Clean whitespace
                    data.append({'Field': field, 'Value': value})
        
        logger.info(f"Extracted {len(data)} profile data points")
        return pd.DataFrame(data)
        
    except Exception as e:
        logger.error(f"Error extracting profile data: {e}")
        return pd.DataFrame(columns=['Field', 'Value'])


def get_fund_profile(xid: str) -> pd.DataFrame:
    """
    Get profile and investment information for ETFs and funds from FT Markets.
    
    Args:
        xid: The FT Markets XID (use get_xid to find this)
        
    Returns:
        pandas.DataFrame with Field and Value columns containing all available
        fund information including details, investment data, and statistics
        
    Raises:
        ValueError: If xid is missing
        requests.exceptions.HTTPError: If API request fails
        
    Examples:
        >>> from ftmarkets import get_xid, get_fund_profile
        >>> xid = get_xid('SPY')
        >>> profile = get_fund_profile(xid)
        >>> print(profile)
        
        >>> # Filter for specific information
        >>> fees = profile[profile['Field'].str.contains('fee', case=False)]
        >>> print(fees)
    """
    if not xid:
        raise ValueError("Missing required parameter: xid")
    
    logger.info(f"Fetching profile data for XID {xid}")
    
    try:
        html_content = fetch_profile_page(xid)
        profile_data = extract_profile_data(html_content)
        
        logger.info(f"Successfully retrieved profile data for XID {xid}")
        return profile_data
        
    except Exception as e:
        logger.error(f"Error retrieving profile data: {e}")
        raise


def get_fund_stats(xid: str) -> Dict[str, str]:
    """
    Get all fund profile data as a dictionary for easy access.
    
    Args:
        xid: The FT Markets XID
        
    Returns:
        Dictionary with all available fund fields and values
        
    Examples:
        >>> xid = get_xid('QQQ')
        >>> stats = get_fund_stats(xid)
        >>> 
        >>> # Access any available field safely
        >>> for field, value in stats.items():
        >>>     print(f"{field}: {value}")
        >>>
        >>> # Check if specific fields exist before using
        >>> inception = stats.get('Inception date', 'Not available')
        >>> fees = stats.get('Ongoing charge', 'Not available')
    """
    profile_df = get_fund_profile(xid)
    
    if profile_df.empty:
        return {}
    
    # Convert DataFrame to dictionary for easy access
    stats_dict = dict(zip(profile_df['Field'], profile_df['Value']))
    
    logger.info(f"Converted profile data to dictionary with {len(stats_dict)} fields")
    return stats_dict


def get_available_fields(xid: str) -> list:
    """
    Get list of all available profile fields for a fund.
    
    Args:
        xid: The FT Markets XID
        
    Returns:
        List of all field names available for this fund
        
    Examples:
        >>> xid = get_xid('SPY')
        >>> fields = get_available_fields(xid)
        >>> print("Available fields:")
        >>> for field in fields:
        >>>     print(f"  - {field}")
    """
    profile_df = get_fund_profile(xid)
    
    if profile_df.empty:
        return []
    
    field_list = profile_df['Field'].tolist()
    logger.info(f"Found {len(field_list)} available fields")
    return field_list


def search_profile_field(xid: str, search_term: str) -> pd.DataFrame:
    """
    Search for specific fields in the fund profile data.
    
    Args:
        xid: The FT Markets XID
        search_term: Term to search for in field names (case-insensitive)
        
    Returns:
        pandas.DataFrame with matching fields and values
        
    Examples:
        >>> xid = get_xid('SPY')
        >>> fees = search_profile_field(xid, 'fee')
        >>> inception = search_profile_field(xid, 'inception')
    """
    profile_df = get_fund_profile(xid)
    
    if profile_df.empty:
        return pd.DataFrame(columns=['Field', 'Value'])
    
    # Filter for fields containing the search term
    matches = profile_df[profile_df['Field'].str.contains(search_term, case=False, na=False)]
    
    logger.info(f"Found {len(matches)} fields matching '{search_term}'")
    return matches


# Export functions
__all__ = [
    "get_fund_profile",
    "get_fund_stats", 
    "get_available_fields",
    "search_profile_field"
]