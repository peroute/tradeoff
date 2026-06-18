import httpx
import pytest

from backend.data_sources import bls


def test_build_series_id():
    assert bls._build_series_id("15-1252") == "OEUN000000000000015125204"


def test_build_series_id_invalid():
    with pytest.raises(ValueError):
        bls._build_series_id("abc")


def test_fetch_live_mocked(load_fixture, monkeypatch, fake_response):
    payload = load_fixture("bls_15-1252.json")
    monkeypatch.setattr(bls.httpx, "post", lambda *a, **k: fake_response(payload))

    w = bls.fetch_bls_wages("15-1252")
    assert w.source == "BLS"
    assert w.is_fallback is False
    assert w.granularity == "occupation"
    assert w.soc_code == "15-1252"
    assert w.currency == "USD"
    assert w.gross_annual == 148_100.0
    assert w.reference_period == "2025"


def test_fallback_on_bad_status(monkeypatch, fake_response):
    monkeypatch.setattr(
        bls.httpx, "post", lambda *a, **k: fake_response({"status": "REQUEST_NOT_PROCESSED"})
    )

    w = bls.fetch_bls_wages("15-1252")
    assert w.is_fallback is True
    assert w.source == "BLS (fallback)"
    assert w.gross_annual == bls._FALLBACK_WAGES["15-1252"]


def test_fallback_on_http_error(monkeypatch):
    def boom(*a, **k):
        raise httpx.ConnectError("no network")

    monkeypatch.setattr(bls.httpx, "post", boom)

    w = bls.fetch_bls_wages("19-3011")
    assert w.is_fallback is True
    assert w.gross_annual == bls._FALLBACK_WAGES["19-3011"]


def test_unknown_soc_fallback_default(monkeypatch):
    def boom(*a, **k):
        raise httpx.ConnectError("no network")

    monkeypatch.setattr(bls.httpx, "post", boom)

    w = bls.fetch_bls_wages("99-9999")  # valid 6-digit shape, no curated fallback
    assert w.is_fallback is True
    assert w.gross_annual == bls._FALLBACK_DEFAULT


@pytest.mark.live
def test_bls_live():
    w = bls.fetch_bls_wages("15-1252")
    assert w.is_fallback is False
    assert w.gross_annual > 0
    assert w.reference_period
