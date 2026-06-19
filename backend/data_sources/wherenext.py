"""WhereNext national cost-of-living client (SECONDARY cost-of-living source).

Live cross-check / fallback for worldbank.py. WhereNext (getwherenext.com)
publishes a free, no-key, CC BY 4.0 national "Cost of Living Index" covering 95
countries. We read its national `cost_index` and normalize it to a US = 100
index so it shares the pipeline's baseline.

WhereNext is an AGGREGATOR (its own upstream is World Bank ICP, Eurostat, etc.),
so its citation names that provenance. We use ONLY the raw bulk dataset
(/api/data/cost-of-living). The `ai-*` endpoints return LLM-generated summaries
and are deliberately NOT used — this is a deterministic stage and hard facts are
never LLM-looked-up.

There is no live CITY tier here: WhereNext's city-prices dataset covers only ~51
mostly-European cities (no US/Canada/Australia city, no New York baseline), so it
can't serve city-level cost of living for the six locked countries. Both this and
worldbank.py are national; both map to col_source="national_ppp".

FALLBACK PATH (documented, intentional)
---------------------------------------
Mirrors oecd.py/bls.py/worldbank.py: any live-path failure degrades to a curated
US = 100 index flagged `is_fallback=True` / source "WhereNext (fallback)".
"""

from __future__ import annotations

import httpx

from backend.models.fact_models import CostData

WHERENEXT_BASE = "https://getwherenext.com/api/data"
COST_OF_LIVING_ENDPOINT = f"{WHERENEXT_BASE}/cost-of-living"
SOURCE_URL = "https://getwherenext.com/data/cost-of-living-2026"
# Surfaced provenance: WhereNext re-publishes institutional open data.
SOURCE_LABEL = "WhereNext (CC BY 4.0; aggregates World Bank ICP / Eurostat)"
TIMEOUT_SECONDS = 8.0
BASELINE_CODE = "US"  # WhereNext cost_index of the US, normalized to 100

# Supported destination -> WhereNext country_code (ISO-2) + national currency.
_COUNTRY_META: dict[str, dict[str, str]] = {
    "US": {"code": "US", "currency": "USD"},
    "UK": {"code": "GB", "currency": "GBP"},
    "Canada": {"code": "CA", "currency": "CAD"},
    "Australia": {"code": "AU", "currency": "AUD"},
    "Germany": {"code": "DE", "currency": "EUR"},
    "France": {"code": "FR", "currency": "EUR"},
}

# Curated fallback: WhereNext cost_index normalized to US = 100, plus its monthly
# USD estimate (rounded ~2026 values). Keeps a fallback close to live.
_FALLBACK: dict[str, dict[str, float]] = {
    "US": {"index": 100.0, "monthly_usd": 3000.0},
    "UK": {"index": 96.3, "monthly_usd": 2900.0},
    "Canada": {"index": 95.1, "monthly_usd": 2850.0},
    "Australia": {"index": 111.0, "monthly_usd": 3350.0},
    "Germany": {"index": 82.9, "monthly_usd": 2500.0},
    "France": {"index": 81.7, "monthly_usd": 2450.0},
}


def fetch_national_col(country: str) -> CostData:
    """National cost index (US = 100) for `country` from WhereNext.

    Always returns a CostData. On any live-path failure, returns a curated
    fallback with is_fallback=True. Unsupported countries get the fallback path
    with a neutral index (graceful degradation).
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
    resp = httpx.get(COST_OF_LIVING_ENDPOINT, timeout=TIMEOUT_SECONDS)
    resp.raise_for_status()
    by_code = _index_by_country_code(resp.json())

    row = by_code.get(meta["code"])
    baseline = by_code.get(BASELINE_CODE)
    if row is None or baseline is None:
        raise ValueError(f"WhereNext response missing {meta['code']} or US baseline")

    base_index = float(baseline["cost_index"])
    if base_index == 0:
        raise ValueError("WhereNext US baseline index is zero")

    # Normalize WhereNext's own scale to US = 100, matching the pipeline baseline.
    index = float(row["cost_index"]) / base_index * 100
    monthly = row.get("monthly_estimate_usd")

    return CostData(
        city=country,                       # national figure; col_source national_ppp
        country=country,
        currency=meta["currency"],
        cost_of_living_index=round(index, 1),
        monthly_cost_usd=float(monthly) if monthly is not None else None,
        source=SOURCE_LABEL,
        is_mock=False,
        is_fallback=False,
    )


def _index_by_country_code(payload) -> dict[str, dict]:
    """Map WhereNext /cost-of-living rows by country_code. Raises on bad shape."""
    if not isinstance(payload, dict) or "data" not in payload:
        raise ValueError("unexpected WhereNext payload shape")
    return {row["country_code"]: row for row in payload["data"]}


def _fallback(country: str, meta: dict[str, str] | None) -> CostData:
    if meta is not None:
        currency = meta["currency"]
        fb = _FALLBACK[country]
        index = fb["index"]
        monthly = fb["monthly_usd"]
    else:
        currency = "USD"
        index = 80.0
        monthly = None

    return CostData(
        city=country,
        country=country,
        currency=currency,
        cost_of_living_index=index,
        monthly_cost_usd=monthly,
        source="WhereNext (fallback)",
        is_mock=False,
        is_fallback=True,
    )
