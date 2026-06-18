"""BLS occupation-level wage client (US only).

Finer-grained than OECD: returns the US annual mean wage for a specific SOC
occupation code (from field_soc_map.json) rather than a national average. This
is the resolution gap disclosed on the dashboard via PrecisionCaveat.

LIVE PATH
---------
BLS Public Data API v2 (api.bls.gov), keyed by BLS_API_KEY from .env. We query
the OEWS (Occupational Employment & Wage Statistics) series for national annual
mean wage and read the latest year.

OEWS series ID layout (25 chars), built in _build_series_id():
    OE | U | N | 0000000 | 000000 | <6-digit SOC> | 04
    │    │   │   │          │        │               └─ datatype 04 = annual mean wage
    │    │   │   │          │        └─ occupation (SOC, dashes stripped)
    │    │   │   │          └─ industry 000000 = cross-industry
    │    │   │   └─ area 0000000 = national
    │    │   └─ areatype N = national
    │    └─ seasonal U = not seasonally adjusted
    └─ prefix OE = OEWS

FALLBACK PATH (documented, intentional)
---------------------------------------
Per the team decision, ANY failure of the live path (missing/invalid key,
network error, non-200, BLS "REQUEST_NOT_PROCESSED", unknown SOC, empty
series) degrades gracefully to a curated US annual mean wage flagged
`is_fallback=True` / source "BLS (fallback)". The dashboard surfaces the flag.
Fallback figures are BLS OEWS May-2023 national annual mean wages, rounded.
"""

from __future__ import annotations

import httpx

from backend.config import settings
from backend.models.fact_models import WageData

BLS_API_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
SOURCE_URL = "https://www.bls.gov/oes/"
TIMEOUT_SECONDS = 8.0
DATATYPE_ANNUAL_MEAN_WAGE = "04"

# Curated fallback: BLS OEWS (May 2023) national annual mean wage by SOC, rounded.
# Keys are the SOC codes used in data/field_soc_map.json.
_FALLBACK_WAGES: dict[str, float] = {
    "15-1252": 132_270.0,  # Software Developers
    "15-2051": 119_040.0,  # Data Scientists
    "17-2071": 111_910.0,  # Electrical Engineers
    "17-2141": 99_510.0,   # Mechanical Engineers
    "13-2051": 99_890.0,   # Financial Analysts
    "11-1021": 129_330.0,  # General & Operations Managers
    "17-2031": 106_950.0,  # Biomedical Engineers
    "17-2041": 118_780.0,  # Chemical Engineers
    "17-2051": 95_890.0,   # Civil Engineers
    "19-3011": 120_380.0,  # Economists
}
_FALLBACK_DEFAULT = 100_000.0  # unknown SOC, keep pipeline alive


def fetch_bls_wages(soc_code: str) -> WageData:
    """US annual mean wage for `soc_code` (e.g. "15-1252"), in USD.

    Always returns a WageData (country fixed to "US"). On any live-path failure,
    returns a curated fallback with is_fallback=True.
    """
    try:
        return _fetch_live(soc_code)
    except Exception:
        # Documented graceful degradation — see module docstring.
        return _fallback(soc_code)


def _build_series_id(soc_code: str) -> str:
    soc_digits = soc_code.replace("-", "")
    if len(soc_digits) != 6 or not soc_digits.isdigit():
        raise ValueError(f"unexpected SOC code: {soc_code!r}")
    return f"OEUN0000000000000{soc_digits}{DATATYPE_ANNUAL_MEAN_WAGE}"


def _fetch_live(soc_code: str) -> WageData:
    series_id = _build_series_id(soc_code)
    body: dict = {"seriesid": [series_id]}
    if settings.bls_api_key:
        # v2 (higher daily limit) requires a registration key; without one the
        # request still works against v1-equivalent limits but may be throttled.
        body["registrationkey"] = settings.bls_api_key

    resp = httpx.post(BLS_API_URL, json=body, timeout=TIMEOUT_SECONDS)
    resp.raise_for_status()
    payload = resp.json()

    if payload.get("status") != "REQUEST_SUCCEEDED":
        raise RuntimeError(f"BLS status: {payload.get('status')}")

    rows = payload["Results"]["series"][0]["data"]
    if not rows:
        raise RuntimeError("BLS returned empty series")

    latest = rows[0]  # BLS returns most-recent-first
    value = float(latest["value"])
    period = latest["year"]

    return WageData(
        country="US",
        currency="USD",
        gross_annual=value,
        granularity="occupation",
        occupation=None,
        soc_code=soc_code,
        reference_period=period,
        source="BLS",
        source_url=SOURCE_URL,
        is_fallback=False,
    )


def _fallback(soc_code: str) -> WageData:
    value = _FALLBACK_WAGES.get(soc_code, _FALLBACK_DEFAULT)
    return WageData(
        country="US",
        currency="USD",
        gross_annual=value,
        granularity="occupation",
        occupation=None,
        soc_code=soc_code,
        reference_period="2023",
        source="BLS (fallback)",
        source_url=SOURCE_URL,
        is_fallback=True,
    )
