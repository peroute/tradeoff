"""OECD average annual wage client.

Primary wage source for every country EXCEPT the US (the US is served at
occupation level by bls.py). Returns the national-average gross annual wage in
the country's own currency.

LIVE PATH
---------
Hits the OECD SDMX REST endpoint (sdmx.oecd.org, no API key) for the
AV_AN_WAGE dataflow and reads the most recent annual observation.

FALLBACK PATH (documented, intentional)
---------------------------------------
The OECD SDMX data-explorer dataflow IDs and dimension keys change between
catalogue versions, and the endpoint is occasionally unreachable. Per the
team decision, ANY failure of the live path (network error, non-200, schema
the parser doesn't recognise, empty series) degrades gracefully to a curated
national-average figure flagged `is_fallback=True` / source "OECD (fallback)".
The dashboard surfaces that flag — we never silently present a stale guess as
a live reading. The fallback values below are OECD-published ~2023 average
annual wages in national currency, rounded; they keep the demo working when
the live call doesn't return cleanly.
"""

from __future__ import annotations

import httpx

from backend.models.fact_models import WageData

OECD_BASE = "https://sdmx.oecd.org/public/rest/data"
OECD_DATAFLOW = "OECD.ELS.SAE,DSD_EARNINGS@AV_AN_WAGE,"
SOURCE_URL = "https://data.oecd.org/earnwage/average-wages.htm"
TIMEOUT_SECONDS = 8.0

# Supported destination -> OECD REF_AREA (ISO-3) + national currency.
_COUNTRY_META: dict[str, dict[str, str]] = {
    "US": {"iso3": "USA", "currency": "USD"},
    "UK": {"iso3": "GBR", "currency": "GBP"},
    "Canada": {"iso3": "CAN", "currency": "CAD"},
    "Australia": {"iso3": "AUS", "currency": "AUD"},
    "Germany": {"iso3": "DEU", "currency": "EUR"},
    "France": {"iso3": "FRA", "currency": "EUR"},
}

# Curated fallback: OECD 2024 average annual wages, national currency, rounded
# (mirrors the live AV_AN_WAGE national-currency series so a fallback reads close
# to a live value).
_FALLBACK_WAGES: dict[str, float] = {
    "US": 82_900.0,
    "UK": 44_800.0,
    "Canada": 83_100.0,
    "Australia": 101_500.0,
    "Germany": 50_300.0,
    "France": 44_900.0,
}


def fetch_oecd_wages(country: str) -> WageData:
    """National-average gross annual wage for `country`, in its own currency.

    Always returns a WageData. On any live-path failure, returns a curated
    fallback with is_fallback=True. Unsupported countries get the fallback path
    with a neutral USD figure so the comparator degrades gracefully rather than
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


def _fetch_live(country: str, meta: dict[str, str]) -> WageData:
    # Key: REF_AREA wildcarded on the remaining dimensions (blank = "all"), so
    # the response carries every UNIT_MEASURE/PRICE_BASE series for the country.
    # We request SDMX-JSON 2.0 ("series" layout) and select the national-currency
    # series in _parse_latest_observation().
    url = f"{OECD_BASE}/{OECD_DATAFLOW}/{meta['iso3']}......"
    params = {
        "startPeriod": "2019",
        "dimensionAtObservation": "TIME_PERIOD",
        "format": "jsondata",
    }
    headers = {"Accept": "application/vnd.sdmx.data+json"}

    resp = httpx.get(url, params=params, headers=headers, timeout=TIMEOUT_SECONDS)
    resp.raise_for_status()
    value, period = _parse_latest_observation(resp.json(), currency=meta["currency"])

    return WageData(
        country=country,
        currency=meta["currency"],
        gross_annual=value,
        granularity="national_average",
        reference_period=period,
        source="OECD",
        source_url=SOURCE_URL,
        is_fallback=False,
    )


def _parse_latest_observation(payload: dict, *, currency: str) -> tuple[float, str]:
    """Pull the latest (value, period) for the NATIONAL-CURRENCY series.

    The country response contains several series — USD_PPP plus the national
    currency, each in constant ("Q") and current ("V") price bases. We must
    pick the national-currency series (UNIT_MEASURE == `currency`) so the figure
    matches that country's tax brackets; among matches we prefer current prices
    ("V"). Raises on any unexpected shape so the caller falls back.
    """
    data = payload["data"]
    data_set = data["dataSets"][0]
    series = data_set["series"]

    # SDMX-JSON 2.0 nests structure under `structures` (list); 1.x used `structure`.
    structure = data.get("structures", [data.get("structure")])[0]
    series_dims = structure["dimensions"]["series"]
    dim_index = {d["id"]: i for i, d in enumerate(series_dims)}
    unit_pos = dim_index["UNIT_MEASURE"]
    price_pos = dim_index.get("PRICE_BASE")

    def unit_id(key_indices: list[int]) -> str:
        return series_dims[unit_pos]["values"][key_indices[unit_pos]]["id"]

    def price_id(key_indices: list[int]) -> str | None:
        if price_pos is None:
            return None
        return series_dims[price_pos]["values"][key_indices[price_pos]]["id"]

    chosen_key: str | None = None
    for key in series:
        indices = [int(x) for x in key.split(":")]
        if unit_id(indices) != currency:
            continue
        chosen_key = key
        if price_id(indices) == "V":  # current prices — preferred, stop early
            break

    if chosen_key is None:
        raise ValueError(f"no national-currency ({currency}) series in OECD response")

    observations: dict[str, list] = series[chosen_key]["observations"]
    obs_dim = structure["dimensions"]["observation"][0]
    time_values = [v["id"] for v in obs_dim["values"]]

    latest_idx = max(int(k) for k in observations.keys())
    value = float(observations[str(latest_idx)][0])
    period = time_values[latest_idx]
    return value, period


def _fallback(country: str, meta: dict[str, str] | None) -> WageData:
    if meta is not None:
        currency = meta["currency"]
        value = _FALLBACK_WAGES[country]
    else:
        # Unsupported destination: keep the pipeline alive with a neutral figure.
        currency = "USD"
        value = 50_000.0

    return WageData(
        country=country,
        currency=currency,
        gross_annual=value,
        granularity="national_average",
        reference_period="2023",
        source="OECD (fallback)",
        source_url=SOURCE_URL,
        is_fallback=True,
    )
