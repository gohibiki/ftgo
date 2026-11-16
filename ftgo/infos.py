"""
Profile and information data functionality for ftgo.

This module provides functions to fetch ETF/fund profile information,
key statistics, and investment details from FT Markets.
"""

import logging
from typing import Dict, List

import pandas as pd
from bs4 import BeautifulSoup

from .session import fetch_tearsheet

# Set up logging
logger = logging.getLogger(__name__)

PROFILE_COLUMNS = ['Field', 'Value']


def fetch_profile_page(xid: str) -> str:
    """
    Fetch the profile/summary page HTML for a given XID from FT Markets.
    Uses cached session.

    Raises:
        ValueError: If FT Markets does not recognise the XID
    """
    try:
        return fetch_tearsheet("summary", xid)
    except Exception as e:
        logger.error(f"Failed to fetch profile page for XID {xid}: {e}")
        raise


def extract_profile_data(html_content: str) -> pd.DataFrame:
    """Extract profile and investment data from FT Markets ETF page HTML."""
    if not html_content:
        logger.warning("No HTML content provided")
        return pd.DataFrame(columns=PROFILE_COLUMNS)

    soup = BeautifulSoup(html_content, 'html.parser')

    profile_section = soup.find('div', {'data-f2-app-id': 'mod-profile-and-investment-app'})

    if not profile_section:
        logger.warning("Profile and Investment section not found")
        return pd.DataFrame(columns=PROFILE_COLUMNS)

    data = []
    for table in profile_section.find_all('table'):
        for row in table.find_all('tr'):
            th = row.find('th')
            td = row.find('td')

            if th and td:
                field = th.get_text(strip=True)
                value = ' '.join(td.get_text(separator=' ', strip=True).split())
                data.append([field, value])

    logger.info(f"Extracted {len(data)} profile data points")
    return pd.DataFrame(data, columns=PROFILE_COLUMNS)


def get_fund_profile(xid: str) -> pd.DataFrame:
    """
    Get profile and investment information for ETFs and funds from FT Markets.

    Args:
        xid: The FT Markets XID

    Returns:
        pandas.DataFrame with Field and Value columns, empty when FT Markets
        has no profile for the security (e.g. for equities)

    Raises:
        ValueError: If the XID is empty or FT Markets does not recognise it
        requests.RequestException: On network errors or HTTP error statuses
    """
    if not xid:
        raise ValueError("Missing required parameter: xid")

    logger.info(f"Fetching profile data for XID {xid}")

    return extract_profile_data(fetch_profile_page(xid))


def get_fund_stats(xid: str) -> Dict[str, str]:
    """
    Get all fund profile data as a dictionary for easy access.

    Args:
        xid: The FT Markets XID

    Returns:
        Dictionary with all available fund fields and values
    """
    profile_df = get_fund_profile(xid)

    return dict(zip(profile_df['Field'], profile_df['Value']))


def get_available_fields(xid: str) -> List[str]:
    """
    Get list of all available profile fields for a fund.

    Args:
        xid: The FT Markets XID

    Returns:
        List of all field names available for this fund
    """
    return get_fund_profile(xid)['Field'].tolist()


def search_profile_field(xid: str, search_term: str) -> pd.DataFrame:
    """
    Search for specific fields in the fund profile data.

    Args:
        xid: The FT Markets XID
        search_term: Text to search for in field names (case-insensitive)

    Returns:
        pandas.DataFrame with matching fields and values
    """
    profile_df = get_fund_profile(xid)

    if profile_df.empty:
        return profile_df

    matches = profile_df[profile_df['Field'].str.contains(search_term, case=False, na=False)]

    logger.info(f"Found {len(matches)} fields matching '{search_term}'")
    return matches.reset_index(drop=True)


__all__ = [
    "get_fund_profile",
    "get_fund_stats",
    "get_available_fields",
    "search_profile_field"
]
