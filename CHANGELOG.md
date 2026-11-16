# Changelog

## 2.0.0

### Breaking changes

- `get_holdings(..., "top_holdings")` now returns the columns `Holding`, `Symbol`, `1Y Change` and `Weight`. Previously the columns were `Holding`, `Weight` and `Shares`, where `Weight` actually held the 1-year price change and `Shares` held the portfolio weight.
- `get_multiple_historical_prices` now returns a leading `xid` column, ordered by the input list and then by date. Previously the rows of different securities could not be told apart.
- `get_historical_prices` now raises when a request fails (network error, HTTP error, rejected request) instead of returning an empty DataFrame. A failed chunk of a long date range fails the whole call instead of leaving a silent gap.
- `get_holdings`, `get_fund_breakdown` and `get_fund_profile` raise `ValueError` for an XID that FT Markets does not recognise.
- Volume that FT Markets does not report is now missing (`<NA>`, nullable `Int64` column) instead of `0`. Prices it does not report are `NaN` instead of dropping the row.
- Python 3.9 or newer is required. Earlier 1.x releases declared support for Python 3.7 but could not be imported before Python 3.10.
- The broken `ftgo-demo` console script was removed.

### Fixed

- Long date ranges no longer drop the first requested day when it falls one day past a 10-year chunk boundary.
- Holdings tables no longer come back empty on installs without `lxml` or `html5lib`; they are parsed with BeautifulSoup, which is already a dependency.
- Invalid dates and a `date_from` after `date_to` raise a clear `ValueError` before any request is made.

### Added

- `FTMarketsError`, raised when FT Markets answers in an unexpected format.
- Requests time out after 30 seconds and are retried on connection errors and 429/5xx responses.
- Each thread uses its own HTTP session, and the response cache is bounded and evicts expired entries.
- Empty results keep their column names.
- An offline test suite, plus live tests run with `pytest -m integration`. The publish workflow now runs the tests first.

## 1.3.0

- Cache historical price responses via the shared session cache.

## 1.2.0

- Automatic chunking of large date ranges in `get_historical_prices`.
