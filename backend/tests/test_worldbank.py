import httpx
import pytest

from backend.data_sources import worldbank


def _dispatch_get(ppp_payload, xr_payload, fake_response):
    """Emulate the World Bank single-country endpoint: filter the multi-country
    fixture down to the iso3 in the URL and pick the indicator by URL."""
    def fake_get(url, params=None, **kwargs):
        iso = url.split("/country/")[1].split("/")[0]
        indicator = url.rsplit("/indicator/", 1)[1]
        src = ppp_payload if indicator == worldbank.INDICATOR_PPP else xr_payload
        rows = [r for r in src[1] if r["countryiso3code"] == iso]
        return fake_response([src[0], rows])
    return fake_get


def test_parse_picks_latest_nonnull():
    payload = [
        {"page": 1},
        [
            {"countryiso3code": "GBR", "date": "2024", "value": 0.6827},
            {"countryiso3code": "GBR", "date": "2023", "value": 0.6700},
            {"countryiso3code": "GBR", "date": "2025", "value": None},  # ignored
        ],
    ]
    value, year = worldbank._parse_latest_observation(payload)
    assert value == pytest.approx(0.6827)
    assert year == "2024"


def test_parse_raises_on_empty():
    with pytest.raises(ValueError):
        worldbank._parse_latest_observation([{"page": 1}, []])


def test_fetch_live_index_uk(load_fixture, monkeypatch, fake_response):
    ppp = load_fixture("worldbank_ppp_privcons.json")
    xr = load_fixture("worldbank_exchange_rate.json")
    monkeypatch.setattr(worldbank.httpx, "get", _dispatch_get(ppp, xr, fake_response))

    cd = worldbank.fetch_national_col("UK")
    assert cd.source == "World Bank"
    assert cd.is_fallback is False
    assert cd.currency == "GBP"
    assert cd.cost_of_living_index == pytest.approx(87.3, abs=0.1)  # 0.6827/0.7824*100


def test_us_baseline_is_100(load_fixture, monkeypatch, fake_response):
    ppp = load_fixture("worldbank_ppp_privcons.json")
    xr = load_fixture("worldbank_exchange_rate.json")
    monkeypatch.setattr(worldbank.httpx, "get", _dispatch_get(ppp, xr, fake_response))

    cd = worldbank.fetch_national_col("US")
    assert cd.cost_of_living_index == pytest.approx(100.0, abs=0.1)


def test_fallback_on_http_error(monkeypatch):
    def boom(*a, **k):
        raise httpx.ConnectError("no network")

    monkeypatch.setattr(worldbank.httpx, "get", boom)

    cd = worldbank.fetch_national_col("Germany")
    assert cd.is_fallback is True
    assert cd.source == "World Bank (fallback)"
    assert cd.currency == "EUR"
    assert cd.cost_of_living_index == worldbank._FALLBACK_INDEX["Germany"]


def test_fallback_on_unparseable_payload(monkeypatch, fake_response):
    monkeypatch.setattr(worldbank.httpx, "get", lambda *a, **k: fake_response({"bad": "shape"}))

    cd = worldbank.fetch_national_col("France")
    assert cd.is_fallback is True
    assert cd.cost_of_living_index == worldbank._FALLBACK_INDEX["France"]


def test_unsupported_country_falls_back():
    cd = worldbank.fetch_national_col("Brazil")
    assert cd.is_fallback is True
    assert cd.currency == "USD"
    assert cd.cost_of_living_index == 70.0


@pytest.mark.live
def test_worldbank_live_all_countries():
    for country in ("US", "UK", "Canada", "Australia", "Germany", "France"):
        cd = worldbank.fetch_national_col(country)
        assert cd.is_fallback is False, f"{country} unexpectedly fell back"
        assert cd.cost_of_living_index > 0
