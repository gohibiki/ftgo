"""
Shared HTTP session and caching for the ftgo library.

Provides one cloudscraper session per thread, retries for transient failures,
and a small bounded TTL cache to avoid redundant HTTP requests.
"""

import logging
import threading
import time
from collections import OrderedDict
from typing import Any, Tuple
from urllib.parse import quote

import cloudscraper
import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://markets.ft.com/data"

# requests sessions are not guaranteed thread-safe, so each thread gets its own.
_thread_local = threading.local()

# Page cache: {url: (monotonic timestamp, response)}, oldest entry first.
_page_cache: "OrderedDict[str, Tuple[float, Any]]" = OrderedDict()
_cache_lock = threading.Lock()
_CACHE_TTL = 3600.0  # 1 hour
_CACHE_MAX_ENTRIES = 256

_REQUEST_TIMEOUT = 30  # seconds
_MAX_ATTEMPTS = 3
_RETRY_BACKOFF = 1.0  # seconds, doubled after each failed attempt
_RETRY_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


def get_scraper():
    """Get or create the cloudscraper session for the current thread."""
    scraper = getattr(_thread_local, "scraper", None)
    if scraper is None:
        scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'desktop': True
            }
        )
        _thread_local.scraper = scraper
    return scraper


def _fetch(url: str):
    """GET a URL, retrying transient network errors and 429/5xx responses."""
    scraper = get_scraper()

    for attempt in range(1, _MAX_ATTEMPTS + 1):
        last_attempt = attempt == _MAX_ATTEMPTS
        try:
            response = scraper.get(url, timeout=_REQUEST_TIMEOUT)
        except (requests.ConnectionError, requests.Timeout) as e:
            if last_attempt:
                raise
            reason = repr(e)
        else:
            if last_attempt or response.status_code not in _RETRY_STATUS_CODES:
                response.raise_for_status()
                return response
            reason = f"HTTP {response.status_code}"

        delay = _RETRY_BACKOFF * 2 ** (attempt - 1)
        logger.warning(
            f"Request failed ({reason}), retrying in {delay:.1f}s "
            f"(attempt {attempt}/{_MAX_ATTEMPTS}): {url[:80]}"
        )
        time.sleep(delay)

    raise AssertionError("unreachable")  # pragma: no cover


def cached_get(url: str, use_cache: bool = True):
    """
    GET request with optional caching.

    Args:
        url: URL to fetch
        use_cache: Whether to use the cache (default True)

    Returns:
        Response object

    Raises:
        requests.RequestException: On network errors or HTTP error statuses
    """
    if use_cache:
        with _cache_lock:
            entry = _page_cache.get(url)
            if entry is not None:
                cached_time, cached_response = entry
                if time.monotonic() - cached_time < _CACHE_TTL:
                    logger.debug(f"Cache hit for {url[:80]}")
                    return cached_response
                del _page_cache[url]

    response = _fetch(url)

    if use_cache:
        now = time.monotonic()
        with _cache_lock:
            expired = [u for u, (t, _) in _page_cache.items() if now - t >= _CACHE_TTL]
            for u in expired:
                del _page_cache[u]
            _page_cache.pop(url, None)
            _page_cache[url] = (now, response)
            while len(_page_cache) > _CACHE_MAX_ENTRIES:
                _page_cache.popitem(last=False)

    return response


def invalidate(url: str) -> None:
    """Remove a single URL from the cache, if present."""
    with _cache_lock:
        _page_cache.pop(url, None)


def fetch_tearsheet(page: str, xid: str) -> str:
    """
    Fetch a tearsheet page (e.g. "holdings" or "summary") as HTML.

    FT redirects to the right asset class for the XID, and to its search page
    when the XID is unknown.

    Raises:
        ValueError: If FT Markets does not recognise the XID
    """
    url = f"{BASE_URL}/etfs/tearsheet/{page}?s={quote(str(xid), safe='')}"
    response = cached_get(url)

    if "/data/search" in (getattr(response, "url", None) or ""):
        raise ValueError(f"FT Markets does not recognise XID '{xid}'")

    return response.text


def clear_cache() -> None:
    """Clear the page cache."""
    with _cache_lock:
        _page_cache.clear()


def set_cache_ttl(ttl_seconds: float) -> None:
    """Set the cache TTL in seconds. Use 0 to disable caching."""
    global _CACHE_TTL
    if ttl_seconds < 0:
        raise ValueError("ttl_seconds cannot be negative")
    _CACHE_TTL = float(ttl_seconds)
