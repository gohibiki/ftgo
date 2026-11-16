import pytest

import ftgo
from ftgo import (
    FTMarketsError,
    get_available_fields,
    get_fund_profile,
    get_fund_stats,
    get_xid,
    search_profile_field,
    search_securities,
)
from ftgo.search import SEARCH_COLUMNS

from conftest import FakeResponse

PROFILE_PAGE = """
<html><body>
<div data-f2-app-id="mod-profile-and-investment-app">
<table><tbody>
<tr><th>Fund type</th><td>UIT</td></tr>
<tr><th>Investment style (stocks)</th><td><span>Market Cap: Large</span>
    <span>Investment Style: Blend</span></td></tr>
<tr><th>Ongoing charge</th><td>0.09%</td></tr>
</tbody></table>
<table><tbody><tr><th>Launch date</th><td>22 Jan 1993</td></tr></tbody></table>
</div>
</body></html>
"""

SEARCH_JSON = {"data": {"security": [
    {"xid": "36276", "name": "Apple Inc", "symbol": "AAPL:NSQ", "assetClass": "Equities",
     "url": "~/equities/tearsheet/summary?s=AAPL:NSQ"},
    {"xid": "72471517", "name": "Apple Inc", "symbol": "AAPL:MEX", "assetClass": "Equities",
     "url": "~/equities/tearsheet/summary?s=AAPL:MEX"},
]}}


# --- profile -------------------------------------------------------------------

def test_fund_profile(scraper):
    scraper.add("tearsheet/summary?s=258981", FakeResponse(text=PROFILE_PAGE))

    profile = get_fund_profile("258981")

    assert list(profile.columns) == ["Field", "Value"]
    assert profile.to_dict("list") == {
        "Field": ["Fund type", "Investment style (stocks)", "Ongoing charge", "Launch date"],
        "Value": ["UIT", "Market Cap: Large Investment Style: Blend", "0.09%", "22 Jan 1993"],
    }


def test_profile_helpers(scraper):
    scraper.add("tearsheet/summary?s=258981", FakeResponse(text=PROFILE_PAGE))

    assert get_fund_stats("258981")["Ongoing charge"] == "0.09%"
    assert get_available_fields("258981")[0] == "Fund type"
    assert search_profile_field("258981", "CHARGE").to_dict("records") == [
        {"Field": "Ongoing charge", "Value": "0.09%"}
    ]
    assert len(scraper.calls) == 1


def test_page_without_profile_gives_empty_results(scraper):
    scraper.add("tearsheet/summary", FakeResponse(text="<html><body>equity page</body></html>"))

    profile = get_fund_profile("36276")

    assert profile.empty and list(profile.columns) == ["Field", "Value"]
    assert get_fund_stats("36276") == {}
    assert get_available_fields("36276") == []
    assert search_profile_field("36276", "fee").empty


def test_profile_unknown_or_empty_xid(scraper):
    scraper.add("tearsheet/summary", FakeResponse(url="https://markets.ft.com/data/search?query=nope"))

    with pytest.raises(ValueError):
        get_fund_profile("nope")
    with pytest.raises(ValueError):
        get_fund_profile("")


# --- search --------------------------------------------------------------------

def test_search_securities(scraper):
    scraper.add("searchsecurities?query=Apple%20Inc", FakeResponse(json_data=SEARCH_JSON))

    df = search_securities("Apple Inc")

    assert list(df.columns) == SEARCH_COLUMNS
    assert list(df["xid"]) == ["36276", "72471517"]
    assert df.loc[0, "asset_class"] == "Equities"


def test_search_is_not_cached(scraper):
    scraper.add("searchsecurities", FakeResponse(json_data=SEARCH_JSON))

    search_securities("AAPL")
    search_securities("AAPL")
    assert len(scraper.calls) == 2


def test_get_xid_modes(scraper):
    scraper.add("searchsecurities", FakeResponse(json_data=SEARCH_JSON))

    assert get_xid("AAPL") == "36276"
    assert len(get_xid("AAPL", display_mode="all")) == 2


def test_get_xid_no_match(scraper):
    scraper.add("searchsecurities", FakeResponse(json_data={"data": {"security": []}}))

    with pytest.raises(ValueError, match="ZZZZ"):
        get_xid("ZZZZ")


def test_search_without_results_has_columns(scraper):
    scraper.add("searchsecurities", FakeResponse(json_data={"data": {}}))

    df = search_securities("ZZZZ")

    assert df.empty and list(df.columns) == SEARCH_COLUMNS


def test_search_non_json_response(scraper):
    scraper.add("searchsecurities", FakeResponse(text="<html>blocked</html>"))

    with pytest.raises(FTMarketsError):
        search_securities("AAPL")


def test_search_invalid_arguments_raise_before_any_request(scraper):
    with pytest.raises(ValueError):
        search_securities("")
    with pytest.raises(ValueError):
        get_xid("")
    with pytest.raises(ValueError):
        get_xid("AAPL", display_mode="last")
    assert scraper.calls == []


# --- package -------------------------------------------------------------------

def test_public_api_is_importable():
    for name in ftgo.__all__:
        assert hasattr(ftgo, name), name
