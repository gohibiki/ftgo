"""
Shared session and caching for FTMarkets library.

Provides a singleton cloudscraper session and a simple TTL cache
to avoid redundant HTTP requests.
"""

import cloudscraper
import time
import logging

logger = logging.getLogger(__name__)

# Singleton scraper session
_scraper = None

# Page cache: {url: (timestamp, content)}
_page_cache = {}
_CACHE_TTL = 3600  # 1 hour


def get_scraper():
    """Get or create the shared cloudscraper session."""
    global _scraper
    if _scraper is None:
        _scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'desktop': True
            }
        )
    return _scraper


def cached_get(url, use_cache=True):
    """
    GET request with optional caching.

    Args:
        url: URL to fetch
        use_cache: Whether to use the cache (default True)

    Returns:
        Response object
    """
    now = time.time()

    if use_cache and url in _page_cache:
        cached_time, cached_response = _page_cache[url]
        if now - cached_time < _CACHE_TTL:
            logger.debug(f"Cache hit for {url[:80]}")
            return cached_response

    scraper = get_scraper()
    response = scraper.get(url)
    response.raise_for_status()

    if use_cache:
        _page_cache[url] = (now, response)

    return response


def clear_cache():
    """Clear the page cache."""
    global _page_cache
    _page_cache = {}


def set_cache_ttl(ttl_seconds):
    """Set the cache TTL in seconds."""
    global _CACHE_TTL
    _CACHE_TTL = ttl_seconds
