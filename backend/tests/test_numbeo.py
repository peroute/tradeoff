from backend.data_sources import numbeo


def test_known_city():
    d = numbeo.fetch_cost_of_living("Paris", "France")
    assert d.cost_of_living_index == 74.1
    assert d.is_mock is True
    assert d.is_fallback is False
    assert d.currency == "EUR"
    assert d.local_purchasing_power_index == 81.4


def test_country_default_fallback():
    # City not modelled, but France's major city (Paris) is the proxy.
    d = numbeo.fetch_cost_of_living("Lyon", "France")
    assert d.is_mock is True
    assert d.is_fallback is True
    assert d.city == "Lyon"
    assert d.cost_of_living_index == 74.1  # proxied from Paris


def test_unknown_country_generic():
    d = numbeo.fetch_cost_of_living("Tokyo", "Japan")
    assert d.is_mock is True
    assert d.is_fallback is True
    assert d.cost_of_living_index == 60.0
    assert d.currency == "USD"


def test_live_request_uses_api_key_and_is_not_sent(monkeypatch):
    monkeypatch.setattr(numbeo.settings, "numbeo_api_key", "test-key-123")
    req = numbeo._live_request("Paris", "France")
    assert req["url"] == numbeo.NUMBEO_INDICES_URL
    assert req["params"]["api_key"] == "test-key-123"
    assert req["params"]["query"] == "Paris, France"
