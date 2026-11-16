import threading

import pytest
import requests

from ftgo import session
from ftgo.session import cached_get, clear_cache, fetch_tearsheet, get_scraper, set_cache_ttl

from conftest import FakeResponse

URL = "https://markets.ft.com/data/page"


def test_cache_hit_avoids_second_request(scraper):
    scraper.add("page", FakeResponse(text="one"))

    assert cached_get(URL).text == "one"
    assert cached_get(URL).text == "one"
    assert len(scraper.calls) == 1


def test_use_cache_false_always_requests(scraper):
    scraper.add("page", FakeResponse(text="one"))

    cached_get(URL, use_cache=False)
    cached_get(URL, use_cache=False)
    assert len(scraper.calls) == 2


def test_clear_cache_forces_refetch(scraper):
    scraper.add("page", FakeResponse(text="one"))

    cached_get(URL)
    clear_cache()
    cached_get(URL)
    assert len(scraper.calls) == 2


def test_zero_ttl_disables_cache(scraper):
    scraper.add("page", FakeResponse(text="one"))
    set_cache_ttl(0)

    cached_get(URL)
    cached_get(URL)
    assert len(scraper.calls) == 2


def test_negative_ttl_rejected():
    with pytest.raises(ValueError):
        set_cache_ttl(-1)


def test_expired_entries_are_evicted(scraper, monkeypatch):
    scraper.add("markets.ft.com", FakeResponse(text="x"))
    clock = [1000.0]
    monkeypatch.setattr(session.time, "monotonic", lambda: clock[0])

    cached_get(URL + "/old")
    clock[0] += session._CACHE_TTL + 1
    cached_get(URL + "/new")

    assert list(session._page_cache) == [URL + "/new"]


def test_cache_size_is_bounded(scraper, monkeypatch):
    scraper.add("markets.ft.com", FakeResponse(text="x"))
    monkeypatch.setattr(session, "_CACHE_MAX_ENTRIES", 3)

    for i in range(5):
        cached_get(f"{URL}/{i}")

    assert list(session._page_cache) == [f"{URL}/{i}" for i in (2, 3, 4)]


def test_retries_transient_status_then_succeeds(scraper):
    scraper.add("page", [FakeResponse(status_code=503), FakeResponse(text="ok")])

    assert cached_get(URL).text == "ok"
    assert len(scraper.calls) == 2


def test_retries_connection_error_then_raises(scraper):
    scraper.add("page", requests.ConnectionError("down"))

    with pytest.raises(requests.ConnectionError):
        cached_get(URL)
    assert len(scraper.calls) == session._MAX_ATTEMPTS


def test_persistent_server_error_raises_and_is_not_cached(scraper):
    scraper.add("page", FakeResponse(status_code=500))

    with pytest.raises(requests.HTTPError):
        cached_get(URL)
    assert len(scraper.calls) == session._MAX_ATTEMPTS
    assert URL not in session._page_cache


def test_client_error_is_not_retried(scraper):
    scraper.add("page", FakeResponse(status_code=404))

    with pytest.raises(requests.HTTPError):
        cached_get(URL)
    assert len(scraper.calls) == 1


def test_fetch_tearsheet_returns_html(scraper):
    scraper.add("tearsheet/holdings?s=123", FakeResponse(text="<html>ok</html>"))

    assert fetch_tearsheet("holdings", "123") == "<html>ok</html>"


def test_fetch_tearsheet_unknown_xid(scraper):
    scraper.add(
        "tearsheet/holdings",
        FakeResponse(text="search page", url="https://markets.ft.com/data/search?query=nope&assetClass=ETF"),
    )

    with pytest.raises(ValueError, match="nope"):
        fetch_tearsheet("holdings", "nope")


def test_each_thread_gets_its_own_scraper():
    scrapers = []

    def worker():
        scrapers.append((get_scraper(), get_scraper()))

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    (a1, a2), (b1, b2) = scrapers
    assert a1 is a2 and b1 is b2
    assert a1 is not b1
