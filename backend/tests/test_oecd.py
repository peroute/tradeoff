import httpx
import pytest

from backend.data_sources import oecd


def test_parse_selects_national_currency(load_fixture):
    """The GBR response carries both USD_PPP and GBP series with different
    values — the parser must return the national-currency (GBP) one."""
    payload = load_fixture("oecd_gbr.json")

    value, period = oecd._parse_latest_observation(payload, currency="GBP")
    assert round(value) == 44806
    assert period == "2024"

    ppp, _ = oecd._parse_latest_observation(payload, currency="USD_PPP")
    assert round(ppp) == 63691
    assert value != ppp  # proves we don't just grab the first series


def test_parse_raises_when_currency_absent(load_fixture):
    payload = load_fixture("oecd_gbr.json")
    with pytest.raises(ValueError):
        oecd._parse_latest_observation(payload, currency="JPY")


def test_fetch_live_path_mocked(load_fixture, monkeypatch, fake_response):
    payload = load_fixture("oecd_gbr.json")
    monkeypatch.setattr(oecd.httpx, "get", lambda *a, **k: fake_response(payload))

    w = oecd.fetch_oecd_wages("UK")
    assert w.source == "OECD"
    assert w.is_fallback is False
    assert w.currency == "GBP"
    assert round(w.gross_annual) == 44806
    assert w.granularity == "national_average"
    assert w.reference_period == "2024"


def test_fallback_on_http_error(monkeypatch):
    def boom(*a, **k):
        raise httpx.ConnectError("no network")

    monkeypatch.setattr(oecd.httpx, "get", boom)

    w = oecd.fetch_oecd_wages("France")
    assert w.is_fallback is True
    assert w.source == "OECD (fallback)"
    assert w.currency == "EUR"
    assert w.gross_annual == oecd._FALLBACK_WAGES["France"]


def test_fallback_on_unparseable_payload(monkeypatch, fake_response):
    # 200 OK but a shape the parser can't read -> graceful fallback, not a crash.
    monkeypatch.setattr(oecd.httpx, "get", lambda *a, **k: fake_response({"data": {}}))

    w = oecd.fetch_oecd_wages("Germany")
    assert w.is_fallback is True
    assert w.gross_annual == oecd._FALLBACK_WAGES["Germany"]


def test_unsupported_country_falls_back():
    w = oecd.fetch_oecd_wages("Brazil")
    assert w.is_fallback is True
    assert w.currency == "USD"
    assert w.gross_annual == 50_000.0


@pytest.mark.live
def test_oecd_live_all_countries():
    expected_currency = {
        "US": "USD", "UK": "GBP", "Canada": "CAD",
        "Australia": "AUD", "Germany": "EUR", "France": "EUR",
    }
    for country, currency in expected_currency.items():
        w = oecd.fetch_oecd_wages(country)
        assert w.is_fallback is False, f"{country} unexpectedly fell back"
        assert w.currency == currency
        assert w.gross_annual > 0
        assert w.reference_period
