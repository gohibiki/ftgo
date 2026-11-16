"""Tests against the live FT Markets site.

Deselected by default; run them with ``pytest -m integration``. They catch
changes to FT's pages that the offline tests cannot see.
"""

import pandas as pd
import pytest

import ftgo
from ftgo.historical import PRICE_COLUMNS
from ftgo.holdings import TOP_HOLDINGS_COLUMNS

pytestmark = pytest.mark.integration

AAPL = "36276"
SPY = "258981"


def test_search_finds_apple():
    assert ftgo.get_xid("AAPL") == AAPL


def test_historical_prices():
    df = ftgo.get_historical_prices(AAPL, "01012024", "31012024")

    assert list(df.columns) == PRICE_COLUMNS
    assert len(df) == 21  # trading days in January 2024
    assert df["date"].min() == pd.Timestamp("2024-01-02")
    assert (df["high"] >= df["low"]).all()
    assert (df["volume"] > 0).all()


def test_historical_prices_across_chunk_boundary():
    df = ftgo.get_historical_prices(AAPL, "30012014", "31012024")

    assert df["date"].min() == pd.Timestamp("2014-01-30")
    assert df["date"].max() == pd.Timestamp("2024-01-31")
    assert df["date"].is_unique and df["date"].is_monotonic_increasing


def test_unknown_xid_has_no_prices():
    assert ftgo.get_historical_prices("notanxid", "01012024", "31012024").empty


def test_multiple_historical_prices():
    df = ftgo.get_multiple_historical_prices([AAPL, SPY], "01012024", "31012024")

    assert df.groupby("xid", sort=False).size().to_dict() == {AAPL: 21, SPY: 21}


def test_holdings():
    breakdown = ftgo.get_fund_breakdown(SPY)

    for key in ("asset_allocation", "sector_weights", "geographic_allocation"):
        assert not breakdown[key].empty, key

    top = breakdown["top_holdings"]
    assert list(top.columns) == TOP_HOLDINGS_COLUMNS
    assert len(top) == 10
    weights = top["Weight"].str.rstrip("%").astype(float)
    assert weights.is_monotonic_decreasing  # the weight column really is the weight
    assert weights.sum() < 100


def test_holdings_unknown_xid():
    with pytest.raises(ValueError):
        ftgo.get_holdings("notanxid", "top_holdings")


def test_fund_profile():
    stats = ftgo.get_fund_stats(SPY)

    assert len(stats) > 5
    assert "Fund type" in stats
