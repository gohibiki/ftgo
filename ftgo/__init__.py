"""
ftgo - A Python library for fetching financial data from FT Markets

This library provides easy access to historical prices, ETF/fund holdings,
fund profiles and search functionality for financial instruments from
Financial Times Markets.
"""

from .exceptions import FTMarketsError
from .search import search_securities, get_xid
from .historical import get_historical_prices, get_multiple_historical_prices, get_multiple_historical_prices_dict
from .holdings import get_holdings, get_fund_breakdown
from .infos import get_fund_profile, get_fund_stats, get_available_fields, search_profile_field
from .session import clear_cache, set_cache_ttl

# Single source of truth for the version: pyproject.toml reads it from here.
__version__ = "2.0.0"
__author__ = "gohibiki"
__email__ = "gohibiki@protonmail.com"
__description__ = "A Python library for fetching financial data from FT Markets"

__all__ = [
    "FTMarketsError",
    "search_securities",
    "get_xid",
    "get_historical_prices",
    "get_multiple_historical_prices",
    "get_multiple_historical_prices_dict",
    "get_holdings",
    "get_fund_breakdown",
    "get_fund_profile",
    "get_fund_stats",
    "get_available_fields",
    "search_profile_field",
    "clear_cache",
    "set_cache_ttl"
]
