"""
Profile and information data functionality for FTMarkets.

This module provides functions to fetch ETF/fund profile information,
key statistics, and investment details from FT Markets.
"""

import pandas as pd
from bs4 import BeautifulSoup
from typing import Dict
import logging

from .session import cached_get

# Set up logging
logger = logging.getLogger(__name__)


def fetch_profile_page(xid: str) -> str:
    """
    Fetch the profile/summary page HTML for a given XID from FT Markets.
    Uses cached session.
    """
    try:
        url = f"https://markets.ft.com/data/etfs/tearsheet/summary?s={xid}"
        response = cached_get(url)
        return response.text
    except Exception as e:
        logger.error(f"Failed to fetch profile page for XID {xid}: {e}")
        raise


def extract_profile_data(html_content: str) -> pd.DataFrame:
    """Extract profile and investment data from FT Markets ETF page HTML."""
    if not html_content:
        logger.warning("No HTML content provided")
        return pd.DataFrame(columns=['Field', 'Value'])

    try:
        soup = BeautifulSoup(html_content, 'html.parser')

        profile_section = soup.find('div', {'data-f2-app-id': 'mod-profile-and-investment-app'})

        if not profile_section:
            logger.warning("Profile and Investment section not found")
            return pd.DataFrame(columns=['Field', 'Value'])

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
                    value = ' '.join(value.split())
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
        xid: The FT Markets XID

    Returns:
        pandas.DataFrame with Field and Value columns
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
    """
    profile_df = get_fund_profile(xid)

    if profile_df.empty:
        return {}

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
    """
    profile_df = get_fund_profile(xid)

    if profile_df.empty:
        return pd.DataFrame(columns=['Field', 'Value'])

    matches = profile_df[profile_df['Field'].str.contains(search_term, case=False, na=False)]

    logger.info(f"Found {len(matches)} fields matching '{search_term}'")
    return matches


__all__ = [
    "get_fund_profile",
    "get_fund_stats",
    "get_available_fields",
    "search_profile_field"
]
