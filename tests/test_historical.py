from datetime import datetime
from urllib.parse import parse_qs, urlparse

import pandas as pd
import pytest
import requests

from ftgo import FTMarketsError, get_historical_prices, get_multiple_historical_prices, get_multiple_historical_prices_dict
from ftgo.historical import PRICE_COLUMNS, _chunk_ranges, html_to_dataframe

from conftest import FakeResponse, price_row, prices_response

JAN_4 = price_row("Thursday, January 04, 2024", "182.15", "183.09", "180.88", "181.91", "71,983,570")
JAN_3 = price_row("Wednesday, January 03, 2024", "184.22", "185.88", "183.43", "184.25", "58,414,460")
JAN_2 = price_row("Tuesday, January 02, 2024", "1,187.15", "1,188.44", "1,183.89", "1,185.64", "82,488,674")


def request_range(url):
    query = parse_qs(urlparse(url).query)
    return (
        datetime.strptime(query["startDate"][0], "%Y/%m/%d"),
        datetime.strptime(query["endDate"][0], "%Y/%m/%d"),
    )


# --- html_to_dataframe -------------------------------------------------------

def test_parses_rows_sorted_by_date():
    df = html_to_dataframe(JAN_4 + JAN_3 + JAN_2)

    assert list(df.columns) == PRICE_COLUMNS
    assert list(df["date"]) == [pd.Timestamp("2024-01-02"), pd.Timestamp("2024-01-03"), pd.Timestamp("2024-01-04")]
    assert df.loc[0, "open"] == 1187.15  # thousands separators removed
    assert df.loc[2, "close"] == 181.91
    assert df["volume"].dtype == "int64"
    assert df.loc[2, "volume"] == 71983570


def test_empty_html_gives_empty_frame_with_columns():
    df = html_to_dataframe("")

    assert df.empty
    assert list(df.columns) == PRICE_COLUMNS


def test_missing_volume_is_na_not_zero():
    df = html_to_dataframe(JAN_3 + price_row("Thursday, January 04, 2024", "1", "2", "0.5", "1.5", "--"))

    assert df["volume"].dtype == "Int64"
    assert df.loc[0, "volume"] == 58414460
    assert pd.isna(df.loc[1, "volume"])


def test_missing_price_is_nan_and_row_is_kept():
    df = html_to_dataframe(price_row("Thursday, January 04, 2024", "--", "--", "--", "1.36", "0"))

    assert len(df) == 1
    assert pd.isna(df.loc[0, "open"])
    assert df.loc[0, "close"] == 1.36


def test_row_without_any_price_is_skipped():
    df = html_to_dataframe(JAN_3 + price_row("Thursday, January 04, 2024", "--", "--", "--", "--", "--"))

    assert list(df["date"]) == [pd.Timestamp("2024-01-03")]


def test_unrecognised_layout_raises():
    with pytest.raises(FTMarketsError):
        html_to_dataframe(price_row("04/01/2024", "1", "2", "0.5", "1.5", "10"))


# --- chunking ----------------------------------------------------------------

@pytest.mark.parametrize("start, end", [
    ("2024-01-01", "2024-01-31"),
    ("2024-01-31", "2024-01-31"),
    ("2014-01-31", "2024-01-31"),  # exactly one chunk
    ("2014-01-30", "2024-01-31"),  # one day past a chunk boundary
    ("2014-01-29", "2024-01-31"),
    ("1990-01-01", "2024-01-31"),
    ("2004-02-29", "2024-02-29"),
])
def test_chunks_cover_every_day_exactly_once(start, end):
    ranges = _chunk_ranges(datetime.fromisoformat(start), datetime.fromisoformat(end))

    assert ranges[0][1] == pd.Timestamp(end)
    assert ranges[-1][0] == pd.Timestamp(start)
    for (newer_start, _), (_, older_end) in zip(ranges, ranges[1:]):
        assert older_end == newer_start - pd.Timedelta(days=1)
    for chunk_start, chunk_end in ranges:
        assert chunk_start <= chunk_end
        assert (chunk_end - chunk_start).days <= 366 * 10


def test_short_range_is_a_single_request(scraper):
    scraper.add("get-historical-prices", prices_response(JAN_4, JAN_3, JAN_2))

    df = get_historical_prices("36276", "01012024", "31012024")

    assert len(df) == 3
    assert len(scraper.calls) == 1
    assert request_range(scraper.calls[0]) == (datetime(2024, 1, 1), datetime(2024, 1, 31))
    assert "symbol=36276" in scraper.calls[0]


def test_first_day_is_requested_when_it_falls_just_past_a_chunk_boundary(scraper):
    def respond(url):
        start, end = request_range(url)
        if start <= datetime(2014, 1, 30) <= end:
            return prices_response(price_row("Thursday, January 30, 2014", "1", "2", "0.5", "1.5", "10"))
        return prices_response(JAN_4)

    scraper.add("get-historical-prices", respond)

    df = get_historical_prices("36276", "30012014", "31012024")

    assert len(scraper.calls) == 2
    assert df["date"].min() == pd.Timestamp("2014-01-30")
    assert df["date"].is_monotonic_increasing


def test_no_data_gives_empty_frame_with_columns(scraper):
    scraper.add("get-historical-prices", prices_response())

    df = get_historical_prices("36276", "06012024", "07012024")

    assert df.empty
    assert list(df.columns) == PRICE_COLUMNS


# --- failures are raised, not swallowed ----------------------------------------

def test_http_error_is_raised(scraper):
    scraper.add("get-historical-prices", FakeResponse(status_code=403))

    with pytest.raises(requests.HTTPError):
        get_historical_prices("36276", "01012024", "31012024")


def test_failed_chunk_fails_the_whole_request(scraper):
    scraper.add("get-historical-prices", [prices_response(JAN_4), FakeResponse(status_code=404)])

    with pytest.raises(requests.HTTPError):
        get_historical_prices("36276", "01012000", "31012024")


def test_non_json_response_raises_and_is_not_cached(scraper):
    scraper.add("get-historical-prices", [FakeResponse(text="<html>rejected</html>"), prices_response(JAN_4)])

    with pytest.raises(FTMarketsError):
        get_historical_prices("36276", "01012024", "31012024")

    assert len(get_historical_prices("36276", "01012024", "31012024")) == 1


@pytest.mark.parametrize("xid, date_from, date_to", [
    ("", "01012024", "31012024"),
    ("36276", "2024-01-01", "31012024"),
    ("36276", "01012024", "31132024"),
    ("36276", "31012024", "01012024"),
    ("36276", None, "31012024"),
])
def test_invalid_arguments_raise_before_any_request(scraper, xid, date_from, date_to):
    with pytest.raises(ValueError):
        get_historical_prices(xid, date_from, date_to)
    assert scraper.calls == []


# --- multiple securities -------------------------------------------------------

def test_multiple_prices_are_labelled_by_xid_in_input_order(scraper):
    scraper.add("symbol=AAA", prices_response(JAN_3, JAN_2))
    scraper.add("symbol=BBB", prices_response(JAN_4))

    df = get_multiple_historical_prices(["BBB", "AAA"], "01012024", "31012024")

    assert list(df.columns) == ["xid"] + PRICE_COLUMNS
    assert list(df["xid"]) == ["BBB", "AAA", "AAA"]
    assert list(df["date"]) == [pd.Timestamp("2024-01-04"), pd.Timestamp("2024-01-02"), pd.Timestamp("2024-01-03")]


def test_multiple_prices_dict_skips_failed_and_empty_securities(scraper):
    scraper.add("symbol=GOOD", prices_response(JAN_4))
    scraper.add("symbol=EMPTY", prices_response())
    scraper.add("symbol=BROKEN", FakeResponse(status_code=404))

    result = get_multiple_historical_prices_dict(["BROKEN", "GOOD", "EMPTY", "GOOD"], "01012024", "31012024")

    assert list(result) == ["GOOD"]
    assert len(result["GOOD"]) == 1


def test_multiple_prices_with_no_data_has_columns(scraper):
    scraper.add("get-historical-prices", prices_response())

    df = get_multiple_historical_prices(["AAA"], "01012024", "31012024")

    assert df.empty
    assert list(df.columns) == ["xid"] + PRICE_COLUMNS


@pytest.mark.parametrize("func", [get_multiple_historical_prices, get_multiple_historical_prices_dict])
def test_multiple_prices_validate_arguments(scraper, func):
    with pytest.raises(ValueError):
        func([], "01012024", "31012024")
    with pytest.raises(ValueError):
        func(["AAA"], "bad-date", "31012024")
    assert scraper.calls == []
