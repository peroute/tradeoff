"""World Bank national cost-of-living client (PRIMARY cost-of-living source).

Cost of living used to be served only by numbeo.py, which is curated MOCK data
(Numbeo's API is paid). This module replaces that with a live, primary-source,
national price-level index from the World Bank Open Data API (free, no key).

PRICE-LEVEL INDEX
-----------------
There is no single World Bank "cost of living" indicator (the old
PA.NUS.PPPC.RF price-level ratio was archived). We derive the price-level index
ourselves from two live indicators:

    PLI = PA.NUS.PRVT.PP / PA.NUS.FCRF

  * PA.NUS.PRVT.PP — PPP conversion factor, household final consumption
    (local currency per international $). Household-consumption PPP tracks what
    people actually pay to live, which is what we want for cost of living.
  * PA.NUS.FCRF — official (market) exchange rate (local currency per US$).

Their ratio is the price level relative to the US. The US ratio is 1.0 by
construction (both indicators are 1.0 for the US), so we scale to a US = 100
index:  cost_of_living_index = PLI * 100. This keeps the same US = 100 baseline
the rest of the pipeline assumes for the cost-of-living comparison.

We also surface the raw exchange rate (PA.NUS.FCRF, LCU per US$) on the returned
CostData so fact_assembly can convert net take-home to nominal USD without a
second FX source.

LIVE PATH
---------
One GET per indicator against api.worldbank.org/v2, reading the most recent
non-null annual observation for the country.

FALLBACK PATH (documented, intentional)
---------------------------------------
Mirrors oecd.py/bls.py: ANY failure of the live path (network error, non-200,
empty/None series, unexpected shape) degrades gracefully to a curated index
flagged `is_fallback=True` / source "World Bank (fallback)". The dashboard
surfaces that flag — we never present a curated guess as a live reading. The
fallback figures below are the US = 100 indices computed from the World Bank's
own ~2024 values, rounded.
"""

from __future__ import annotations

import httpx

from backend.models.fact_models import CostData

WORLD_BANK_BASE = "https://api.worldbank.org/v2"
INDICATOR_PPP = "PA.NUS.PRVT.PP"   # household-consumption PPP conversion factor
INDICATOR_XR = "PA.NUS.FCRF"       # official exchange rate (LCU per US$)
SOURCE_URL = "https://data.worldbank.org/indicator/PA.NUS.PRVT.PP"
TIMEOUT_SECONDS = 8.0

# Supported destination -> World Bank ISO-3 + national currency.
_COUNTRY_META: dict[str, dict[str, str]] = {
    "US": {"iso3": "USA", "currency": "USD"},
    "UK": {"iso3": "GBR", "currency": "GBP"},
    "Canada": {"iso3": "CAN", "currency": "CAD"},
    "Australia": {"iso3": "AUS", "currency": "AUD"},
    "Germany": {"iso3": "DEU", "currency": "EUR"},
    "France": {"iso3": "FRA", "currency": "EUR"},
}

# Curated fallback: US = 100 price-level index from World Bank ~2024 values
# (PA.NUS.PRVT.PP / PA.NUS.FCRF * 100), rounded. Keeps a fallback close to live.
_FALLBACK_INDEX: dict[str, float] = {
    "US": 100.0,
    "UK": 87.3,
    "Canada": 90.6,
    "Australia": 94.2,
    "Germany": 75.9,
    "France": 77.6,
}

# Curated fallback exchange rate (LCU per US$), World Bank PA.NUS.FCRF ~2024
# period averages, rounded. Used only when the live FX read is unavailable so
# net-USD conversion (fact_assembly) still has a rate to work with.
_FALLBACK_XR: dict[str, float] = {
    "US": 1.0,
    "UK": 0.7824,
    "Canada": 1.3697,
    "Australia": 1.5163,
    "Germany": 0.9239,
    "France": 0.9239,
}


def fetch_national_col(country: str) -> CostData:
    """National price-level index (US = 100) for `country`.

    Always returns a CostData. On any live-path failure, returns a curated
    fallback with is_fallback=True. Unsupported countries get the fallback path
    with a neutral index so the comparator degrades gracefully rather than
    raising (mirrors the "7th country" graceful-degradation rule).
    """
    meta = _COUNTRY_META.get(country)

    if meta is not None:
        try:
            return _fetch_live(country, meta)
        except Exception:
            # Documented graceful degradation — see module docstring.
            pass

    return _fallback(country, meta)


def _fetch_live(country: str, meta: dict[str, str]) -> CostData:
    iso3 = meta["iso3"]
    ppp, _ = _fetch_indicator(iso3, INDICATOR_PPP)
    xr, _ = _fetch_indicator(iso3, INDICATOR_XR)
    if xr == 0:
        raise ValueError("World Bank exchange rate is zero")

    # PLI relative to the US (US PLI == 1.0 by construction) -> US = 100 index.
    index = (ppp / xr) * 100

    return CostData(
        city=country,                       # national figure; surfaced as col_source national_ppp
        country=country,
        currency=meta["currency"],
        cost_of_living_index=round(index, 1),
        exchange_rate_to_usd=round(xr, 6),  # LCU per US$ (US == 1.0 by construction)
        source="World Bank",
        is_mock=False,
        is_fallback=False,
    )


def _fetch_indicator(iso3: str, indicator: str) -> tuple[float, str]:
    """Latest (value, year) for one World Bank indicator + country. Raises on any
    unexpected shape so the caller falls back."""
    url = f"{WORLD_BANK_BASE}/country/{iso3}/indicator/{indicator}"
    params = {"format": "json", "per_page": "400", "date": "2015:2024"}

    resp = httpx.get(url, params=params, timeout=TIMEOUT_SECONDS)
    resp.raise_for_status()
    return _parse_latest_observation(resp.json())


def _parse_latest_observation(payload) -> tuple[float, str]:
    """Pull the latest (value, year) from a World Bank v2 response.

    Shape is [header, [rows]] where each row carries `date` and `value` (value is
    None for missing years). We pick the most recent year with a non-null value.
    """
    if not isinstance(payload, list) or len(payload) < 2 or not payload[1]:
        raise ValueError("unexpected World Bank payload shape")

    rows = payload[1]
    latest_value: float | None = None
    latest_year = ""
    for row in rows:
        value = row.get("value")
        year = row.get("date", "")
        if value is None:
            continue
        if latest_value is None or year > latest_year:
            latest_value = float(value)
            latest_year = year

    if latest_value is None:
        raise ValueError("no non-null observation in World Bank response")
    return latest_value, latest_year


def _fallback(country: str, meta: dict[str, str] | None) -> CostData:
    if meta is not None:
        currency = meta["currency"]
        index = _FALLBACK_INDEX[country]
        xr = _FALLBACK_XR[country]
    else:
        # Unsupported destination: keep the pipeline alive with a neutral index.
        currency = "USD"
        index = 70.0
        xr = 1.0

    return CostData(
        city=country,
        country=country,
        currency=currency,
        cost_of_living_index=index,
        exchange_rate_to_usd=xr,
        source="World Bank (fallback)",
        is_mock=False,
        is_fallback=True,
    )
