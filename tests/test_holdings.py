import pandas as pd
import pytest

from ftgo import get_fund_breakdown, get_holdings
from ftgo.holdings import TOP_HOLDINGS_COLUMNS, parse_holdings_data

from conftest import FakeResponse

# Trimmed copy of the markup of an FT Markets holdings tearsheet.
HOLDINGS_PAGE = """
<html><body>
<h1 class="mod-tearsheet-overview__header__name mod-tearsheet-overview__header__name--large">Test S&amp;P 500 ETF</h1>
<h1 class="mod-tearsheet-overview__header__name mod-tearsheet-overview__header__name--small">Test S&amp;P 500 ETF</h1>

<div class="mod-app clearfix mod-asset-allocation mod-module"><div class="mod-module__content">
<div class="mod-asset-allocation__table"><table class="mod-ui-table mod-ui-table--colored">
<thead><tr><th>Type</th><th>% Net assets</th><th>% Short</th><th>% Long</th></tr></thead>
<tbody>
<tr><td><span style="border-color:#27757B; ">US stock</span></td><td>99.46%</td><td>0.00%</td><td>99.46%</td></tr>
<tr><td><span style="border-color:#94826B; ">Cash</span></td><td>0.06%</td><td>0.00%</td><td>0.06%</td></tr>
</tbody></table></div></div></div>

<div class="mod-app clearfix mod-weightings mod-module"><div class="mod-module__content">
<div class="mod-weightings__sectors__table"><table class="mod-ui-table mod-ui-table--colored">
<thead><th>Sector</th><th>% Net assets</th><th>Category average</th></thead>
<tbody>
<tr><td><span>Technology</span></td><td>38.21%</td><td>35.06%</td></tr>
<tr><td><span>Healthcare</span></td><td>10.25%</td><td>9.87%</td></tr>
</tbody></table></div>
<div class="mod-weightings__regions__table"><table class="mod-ui-table">
<thead><th>Sector</th><th>% Net assets</th><th>Category average</th></thead>
<tbody>
<tr class="mod-weightings__regions__table__row--colored"><td><span>Americas</span></td><td>99.51%</td><td>94.69%</td></tr>
<tr><td><span>United States</span></td><td>99.46%</td><td>94.54%</td></tr>
</tbody></table></div></div></div>

<div class="mod-app clearfix mod-top-ten mod-module"><div class="mod-module__content">
<table class="mod-ui-table mod-ui-table--colored">
<thead><tr><th colspan="4">Top 10 holdings as a per cent of portfolio</th></tr></thead>
<tbody><tr><td><span>52.53%</span></td><td><span>37.28%</span></td><td>0.00%</td><td>37.28%</td></tr>
<tr><th>Category average</th><th>% Net assets</th><th>% Short</th><th>% Long</th></tr></tbody></table>
<table class="mod-ui-table">
<thead><th>Company</th><th>1 year change</th><th>Portfolio weight</th><th>Long allocation</th></thead>
<tbody>
<tr><td class="mod-ui-table__cell--text"><a class="mod-ui-link" href="/data/equities/tearsheet/summary?s=AAPL:NSQ">Apple Inc.</a><br/><span class="mod-ui-table__cell__disclaimer">AAPL:NSQ</span></td><td><span class="mod-format--pos">+30.53%</span></td><td>7.70%</td><td><div style="width: 100%;"></div></td></tr>
<tr><td class="mod-ui-table__cell--text"><a class="mod-ui-link" href="/data/equities/tearsheet/summary?s=NVDA:NSQ">NVIDIA Corporation</a><br/><span class="mod-ui-table__cell__disclaimer">NVDA:NSQ</span></td><td><span class="mod-format--neg">-12.85%</span></td><td>7.58%</td><td><div style="width: 98%;"></div></td></tr>
<tr><td class="mod-ui-table__cell--text">Unlisted Treasury Note</td><td>--</td><td>1.10%</td><td><div style="width: 14%;"></div></td></tr>
<tr><td class="mod-ui-table__cell--text" colspan="100%">Per cent of portfolio in top 10 holdings: <strong>37.28%</strong></td></tr>
</tbody></table></div></div>
</body></html>
"""

FUND = "Test S&P 500 ETF"


def test_top_holdings_columns_hold_the_right_values():
    top = parse_holdings_data(HOLDINGS_PAGE)["top_holdings"]

    assert list(top.columns) == TOP_HOLDINGS_COLUMNS
    assert list(top["Holding"]) == ["Apple Inc.", "NVIDIA Corporation", "Unlisted Treasury Note"]
    assert list(top["1Y Change"]) == ["+30.53%", "-12.85%", "--"]
    assert list(top["Weight"]) == ["7.70%", "7.58%", "1.10%"]
    assert list(top["Symbol"][:2]) == ["AAPL:NSQ", "NVDA:NSQ"]
    assert pd.isna(top.loc[2, "Symbol"])  # None or NaN depending on the pandas version


def test_allocation_tables():
    data = parse_holdings_data(HOLDINGS_PAGE)

    assert data["asset_allocation"].to_dict("list") == {
        "Asset Class": ["US stock", "Cash"], FUND: ["99.46%", "0.06%"]
    }
    assert data["sector_weights"].to_dict("list") == {
        "Sector": ["Technology", "Healthcare"], FUND: ["38.21%", "10.25%"]
    }
    assert data["geographic_allocation"].to_dict("list") == {
        "Region": ["Americas", "United States"], FUND: ["99.51%", "99.46%"]
    }


def test_page_without_holdings_gives_empty_frames_with_columns():
    data = parse_holdings_data("<html><body><p>No holdings here</p></body></html>")

    assert all(df.empty for df in data.values())
    assert list(data["asset_allocation"].columns) == ["Asset Class", "Unknown Fund"]
    assert list(data["top_holdings"].columns) == TOP_HOLDINGS_COLUMNS


def test_get_holdings_single_type_and_all(scraper):
    scraper.add("tearsheet/holdings?s=258981", FakeResponse(text=HOLDINGS_PAGE))

    top = get_holdings("258981", "top_holdings")
    everything = get_holdings("258981")

    assert len(top) == 3
    assert isinstance(everything, tuple) and len(everything) == 4
    assert [list(df.columns)[0] for df in everything] == ["Asset Class", "Sector", "Region", "Holding"]
    assert len(scraper.calls) == 1  # second call served from cache


def test_get_fund_breakdown(scraper):
    scraper.add("tearsheet/holdings?s=258981", FakeResponse(text=HOLDINGS_PAGE))

    breakdown = get_fund_breakdown("258981")

    assert set(breakdown) == {"asset_allocation", "sector_weights", "geographic_allocation", "top_holdings"}


def test_unknown_xid_raises(scraper):
    scraper.add(
        "tearsheet/holdings",
        FakeResponse(text="search", url="https://markets.ft.com/data/search?query=nope&assetClass=ETF"),
    )

    with pytest.raises(ValueError, match="nope"):
        get_holdings("nope", "top_holdings")


def test_invalid_arguments_raise_before_any_request(scraper):
    with pytest.raises(ValueError):
        get_holdings("", "top_holdings")
    with pytest.raises(ValueError):
        get_holdings("258981", "everything")
    with pytest.raises(ValueError):
        get_fund_breakdown("")
    assert scraper.calls == []
