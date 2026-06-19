"""Numbeo cost-of-living client (CURATED FALLBACK, live-shaped).

Cost of living is now served live by worldbank.py (primary) and wherenext.py
(secondary). This module is the LAST-RESORT fallback used by
fact_assembly._to_col_data() only when BOTH live sources fail — it keeps the
offline demo alive and never presents a curated guess as a live reading.

Numbeo's API is a PAID subscription we don't hold. So this module serves
curated MOCK payloads shaped EXACTLY like Numbeo's /api/indices JSON, then runs
them through the same parser a live response would use. The returned CostData is
flagged `is_mock=True` and the dashboard surfaces that — we never present mock
numbers as a live reading.

Kept production-shaped on purpose:
  * NUMBEO_API_KEY is still read from settings.
  * _live_request() builds the real request (URL + key + query) exactly as it
    would fire against Numbeo. It is intentionally NOT called while mocked;
    going live later is a one-line switch in fetch_cost_of_living().

Index convention: New York = 100 baseline (Numbeo's own). Mock field names
(cpi_index, rent_index, ...) match Numbeo's response keys verbatim.
"""

from __future__ import annotations

from backend.config import settings
from backend.models.fact_models import CostData

NUMBEO_INDICES_URL = "https://www.numbeo.com/api/indices"

# Destination -> representative major city + national currency.
_COUNTRY_DEFAULT_CITY: dict[str, str] = {
    "US": "New York",
    "UK": "London",
    "Canada": "Toronto",
    "Australia": "Sydney",
    "Germany": "Berlin",
    "France": "Paris",
}
_COUNTRY_CURRENCY: dict[str, str] = {
    "US": "USD",
    "UK": "GBP",
    "Canada": "CAD",
    "Australia": "AUD",
    "Germany": "EUR",
    "France": "EUR",
}

# Curated MOCK responses, one per locked-country major city. Field names mirror
# Numbeo's /api/indices payload exactly (NYC = 100 baseline).
_MOCK_INDICES: dict[str, dict] = {
    "New York": {
        "name": "New York, NY, United States", "currency": "USD",
        "cpi_index": 100.0, "rent_index": 100.0, "cpi_and_rent_index": 100.0,
        "groceries_index": 100.0, "restaurant_price_index": 100.0,
        "purchasing_power_incl_rent_index": 100.0,
    },
    "London": {
        "name": "London, United Kingdom", "currency": "GBP",
        "cpi_index": 78.5, "rent_index": 75.2, "cpi_and_rent_index": 76.9,
        "groceries_index": 71.0, "restaurant_price_index": 74.6,
        "purchasing_power_incl_rent_index": 86.3,
    },
    "Toronto": {
        "name": "Toronto, Canada", "currency": "CAD",
        "cpi_index": 71.2, "rent_index": 61.0, "cpi_and_rent_index": 66.3,
        "groceries_index": 70.4, "restaurant_price_index": 66.1,
        "purchasing_power_incl_rent_index": 79.5,
    },
    "Sydney": {
        "name": "Sydney, Australia", "currency": "AUD",
        "cpi_index": 80.4, "rent_index": 66.8, "cpi_and_rent_index": 73.9,
        "groceries_index": 81.2, "restaurant_price_index": 76.0,
        "purchasing_power_incl_rent_index": 94.7,
    },
    "Berlin": {
        "name": "Berlin, Germany", "currency": "EUR",
        "cpi_index": 65.3, "rent_index": 51.4, "cpi_and_rent_index": 58.6,
        "groceries_index": 60.1, "restaurant_price_index": 61.2,
        "purchasing_power_incl_rent_index": 96.2,
    },
    "Paris": {
        "name": "Paris, France", "currency": "EUR",
        "cpi_index": 74.1, "rent_index": 59.3, "cpi_and_rent_index": 67.0,
        "groceries_index": 75.8, "restaurant_price_index": 74.2,
        "purchasing_power_incl_rent_index": 81.4,
    },
}


def fetch_cost_of_living(city: str, country: str) -> CostData:
    """Cost-of-living indices for `city` (Numbeo schema, NYC = 100).

    Always returns CostData with is_mock=True. If the city isn't in the mock
    set, falls back to the country's major city (is_fallback=True) so any of the
    six locked countries still resolves; an unknown country yields a neutral
    generic index.
    """
    # Prepared exactly as the live call would fire — intentionally unused while
    # mocked. Swap the two lines below to go live.
    _ = _live_request(city, country)

    raw, is_fallback = _lookup_mock(city, country)
    return _parse_indices(raw, city=city, country=country, is_fallback=is_fallback)


def _live_request(city: str, country: str) -> dict:
    """Build (NOT send) the real Numbeo request. Documents the live contract."""
    return {
        "url": NUMBEO_INDICES_URL,
        "params": {
            "api_key": settings.numbeo_api_key,
            "query": f"{city}, {country}",
        },
    }


def _lookup_mock(city: str, country: str) -> tuple[dict, bool]:
    if city in _MOCK_INDICES:
        return _MOCK_INDICES[city], False

    default_city = _COUNTRY_DEFAULT_CITY.get(country)
    if default_city and default_city in _MOCK_INDICES:
        # Requested city not modelled; use the country's major city as proxy.
        return _MOCK_INDICES[default_city], True

    # Unknown country: neutral generic index keeps the comparator alive.
    generic = {
        "name": f"{city}, {country}", "currency": _COUNTRY_CURRENCY.get(country, "USD"),
        "cpi_index": 60.0, "rent_index": 45.0, "cpi_and_rent_index": 52.0,
        "groceries_index": 58.0, "restaurant_price_index": 57.0,
        "purchasing_power_incl_rent_index": 70.0,
    }
    return generic, True


def _parse_indices(raw: dict, *, city: str, country: str, is_fallback: bool) -> CostData:
    """Map a Numbeo /api/indices payload (real shape) into CostData."""
    return CostData(
        city=city,
        country=country,
        currency=raw.get("currency", _COUNTRY_CURRENCY.get(country, "USD")),
        cost_of_living_index=raw["cpi_index"],
        rent_index=raw.get("rent_index"),
        cost_of_living_plus_rent_index=raw.get("cpi_and_rent_index"),
        groceries_index=raw.get("groceries_index"),
        restaurant_price_index=raw.get("restaurant_price_index"),
        local_purchasing_power_index=raw.get("purchasing_power_incl_rent_index"),
        source="Numbeo (mock)",
        is_mock=True,
        is_fallback=is_fallback,
    )
