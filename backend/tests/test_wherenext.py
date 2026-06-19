import httpx
import pytest

from backend.data_sources import wherenext


def test_fetch_live_normalizes_to_us_100(load_fixture, monkeypatch, fake_response):
    payload = load_fixture("wherenext_cost_of_living.json")
    monkeypatch.setattr(wherenext.httpx, "get", lambda *a, **k: fake_response(payload))

    cd = wherenext.fetch_national_col("Germany")
    assert cd.is_fallback is False
    assert "WhereNext" in cd.source
    assert cd.currency == "EUR"
    assert cd.cost_of_living_index == pytest.approx(82.9, abs=0.1)  # 68/82*100
    assert cd.monthly_cost_usd == pytest.approx(2500.0)


def test_us_is_100(load_fixture, monkeypatch, fake_response):
    payload = load_fixture("wherenext_cost_of_living.json")
    monkeypatch.setattr(wherenext.httpx, "get", lambda *a, **k: fake_response(payload))

    cd = wherenext.fetch_national_col("US")
    assert cd.cost_of_living_index == pytest.approx(100.0)


def test_only_raw_bulk_endpoint_used(load_fixture, monkeypatch, fake_response):
    """Hard facts must never come from WhereNext's LLM-backed ai-* endpoints."""
    payload = load_fixture("wherenext_cost_of_living.json")
    seen = {}

    def capture(url, *a, **k):
        seen["url"] = url
        return fake_response(payload)

    monkeypatch.setattr(wherenext.httpx, "get", capture)
    wherenext.fetch_national_col("France")
    assert seen["url"] == wherenext.COST_OF_LIVING_ENDPOINT
    assert "ai-" not in seen["url"]


def test_fallback_on_http_error(monkeypatch):
    def boom(*a, **k):
        raise httpx.ConnectError("no network")

    monkeypatch.setattr(wherenext.httpx, "get", boom)

    cd = wherenext.fetch_national_col("Canada")
    assert cd.is_fallback is True
    assert cd.source == "WhereNext (fallback)"
    assert cd.currency == "CAD"
    assert cd.cost_of_living_index == wherenext._FALLBACK["Canada"]["index"]


def test_fallback_on_bad_shape(monkeypatch, fake_response):
    monkeypatch.setattr(wherenext.httpx, "get", lambda *a, **k: fake_response({"nope": []}))

    cd = wherenext.fetch_national_col("UK")
    assert cd.is_fallback is True
    assert cd.cost_of_living_index == wherenext._FALLBACK["UK"]["index"]


def test_unsupported_country_falls_back():
    cd = wherenext.fetch_national_col("Japan")
    assert cd.is_fallback is True
    assert cd.currency == "USD"
    assert cd.cost_of_living_index == 80.0


@pytest.mark.live
def test_wherenext_live_all_countries():
    for country in ("US", "UK", "Canada", "Australia", "Germany", "France"):
        cd = wherenext.fetch_national_col(country)
        assert cd.is_fallback is False, f"{country} unexpectedly fell back"
        assert cd.cost_of_living_index > 0
