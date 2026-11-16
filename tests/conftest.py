"""Shared test helpers: a fake scraper so unit tests never touch the network."""

import pytest
import requests

from ftgo import session


class FakeResponse:
    def __init__(self, text="", json_data=None, status_code=200, url="https://markets.ft.com/data/x"):
        self.text = text
        self.status_code = status_code
        self.url = url
        self._json_data = json_data

    def json(self):
        if self._json_data is None:
            raise ValueError("response is not JSON")
        return self._json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} error")


class FakeScraper:
    """Answers GET requests from routes matched by URL substring.

    A route result may be a FakeResponse, an exception to raise, a callable
    taking the URL, or a list of those consumed one per request.
    """

    def __init__(self):
        self.routes = []
        self.calls = []

    def add(self, url_part, result):
        self.routes.append((url_part, result))

    def get(self, url, timeout=None):
        self.calls.append(url)
        for url_part, result in self.routes:
            if url_part in url:
                if isinstance(result, list):
                    result = result.pop(0) if len(result) > 1 else result[0]
                if callable(result):
                    result = result(url)
                if isinstance(result, Exception):
                    raise result
                return result
        raise AssertionError(f"Unexpected request: {url}")


@pytest.fixture
def scraper(monkeypatch):
    """Replace the HTTP session with a FakeScraper and isolate cache state."""
    fake = FakeScraper()
    monkeypatch.setattr(session, "get_scraper", lambda: fake)
    monkeypatch.setattr(session, "_RETRY_BACKOFF", 0)
    monkeypatch.setattr(session, "_CACHE_TTL", 3600.0)
    session.clear_cache()
    yield fake
    session.clear_cache()


def price_row(date_text, open_, high, low, close, volume):
    """One historical price row, in the markup FT Markets returns."""
    return (
        '<tr><td class="mod-ui-table__cell--text">'
        f'<span class="mod-ui-hide-small-below">{date_text}</span>'
        '<span class="mod-ui-hide-medium-above">short date</span></td>'
        f'<td>{open_}</td><td>{high}</td><td>{low}</td><td>{close}</td>'
        f'<td><span class="mod-ui-hide-small-below">{volume}</span>'
        '<span class="mod-ui-hide-medium-above">1.00m</span></td></tr>'
    )


def prices_response(*rows):
    return FakeResponse(json_data={"data": {}, "html": "".join(rows)})
