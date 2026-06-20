"""Manual audit runner for Stage 2a (fact_assembly.assemble) — dev/QA only.

Hits the live data-source APIs (OECD, BLS, World Bank, WhereNext). Run from the
repo root:

    python -m backend.scripts.run_fact_assembly
    python -m backend.scripts.run_fact_assembly --a UK --b Canada --field "Mechanical Engineering"

Why this exists
---------------
Every data source degrades gracefully: any live-call failure (network, non-200,
unexpected shape) is swallowed with `except Exception` and a curated fallback is
returned, flagged is_fallback=True. That's correct for production — but it means
from the outside you can't see WHETHER the live call succeeded or WHY it fell
back. This tool makes the raw request visible BEFORE the swallowing, so you can
audit the APIs yourself. For each country it prints three layers, in order:

  1. RAW API REQUESTS — the actual live HTTP request each source will make
     (URL, params, status, elapsed, raw body). This is the ground truth: it runs
     the SAME request the module runs, reusing the module's own URL constants, so
     it can't drift. Errors are printed, not swallowed.

  2. PARSED SOURCE RESULTS — the public fetch_*() result for each source plus a
     LIVE / FALLBACK verdict, so you can see what the module decided from the raw
     response above. Tax and visa enrichment are curated/offline (no HTTP).

  3. ASSEMBLED BUNDLE — the final CountryBundle from assemble(), as JSON.

Stage 2b (the AI visa route) is NOT run here. assemble() requires an injected
VisaRoute, so we stub one per country with the curated slug (override via
--slug-a / --slug-b) — enough to exercise the visa_rules.json enrichment lookup.

This is a throwaway inspection tool, not a pytest test. It is intentionally noisy.
"""

from __future__ import annotations

import argparse
import json
import sys
import time

import httpx

# Windows consoles default to cp1252, which chokes on chars like U+2011 that show
# up in API payloads. Force UTF-8 and never crash on a stray glyph.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from backend.config import settings
from backend.data_sources import bls, oecd, wherenext, worldbank
from backend.models.ai_models import VisaRoute
from backend.models.intake_models import ParsedProfile
from backend.pipeline import fact_assembly

# Curated default slug per supported country — exercises visa_rules.json enrichment.
_DEFAULT_SLUG: dict[str, str] = {
    "US": "us_h1b",
    "UK": "uk_skilled_worker",
    "Canada": "canada_express_entry",
    "Australia": "australia_tss_482",
    "Germany": "germany_fachkraeftezuwanderungsgesetz",
    "France": "france_passeport_talent",
}

_BODY_PREVIEW_CHARS = 1400  # raw response bodies are big; preview head only.


# ── tiny terminal helpers ────────────────────────────────────────────────────

def _rule(title: str) -> None:
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def _sub(title: str) -> None:
    print(f"\n  -- {title} " + "-" * max(0, 70 - len(title)))


def _kv(label: str, value: object) -> None:
    print(f"  {label:<26} {value}")


# ── (1) raw request inspection ───────────────────────────────────────────────

def _show_get(label: str, url: str, *, params: dict | None = None, headers: dict | None = None) -> None:
    """Run one GET exactly as the source module would, printing request+response.

    Best-effort: any error is printed (this is what the module silently swallows),
    never raised, so the audit always completes.
    """
    _sub(label)
    _kv("GET", url)
    if params:
        _kv("params", params)
    try:
        t0 = time.perf_counter()
        resp = httpx.get(url, params=params, headers=headers, timeout=oecd.TIMEOUT_SECONDS)
        elapsed = (time.perf_counter() - t0) * 1000
        _kv("status", f"{resp.status_code} {resp.reason_phrase}")
        _kv("elapsed", f"{elapsed:.0f} ms")
        _kv("final url", str(resp.url))
        _print_body(resp.text)
    except Exception as exc:  # noqa: BLE001 — mirror the module's swallow, but show it
        _kv("REQUEST FAILED", f"{type(exc).__name__}: {exc}")
        print("    -> module would swallow this and return a FALLBACK value.")


def _show_post(label: str, url: str, body: dict) -> None:
    """Run one POST exactly as bls would, printing request+response."""
    _sub(label)
    _kv("POST", url)
    # Don't echo the registration key.
    safe_body = {k: ("***" if k == "registrationkey" else v) for k, v in body.items()}
    _kv("body", json.dumps(safe_body))
    try:
        t0 = time.perf_counter()
        resp = httpx.post(url, json=body, timeout=bls.TIMEOUT_SECONDS)
        elapsed = (time.perf_counter() - t0) * 1000
        _kv("status", f"{resp.status_code} {resp.reason_phrase}")
        _kv("elapsed", f"{elapsed:.0f} ms")
        _print_body(resp.text)
    except Exception as exc:  # noqa: BLE001
        _kv("REQUEST FAILED", f"{type(exc).__name__}: {exc}")
        print("    -> module would swallow this and return a FALLBACK value.")


def _print_body(text: str) -> None:
    body = text or ""
    shown = body[:_BODY_PREVIEW_CHARS]
    print("    raw body (first %d chars):" % _BODY_PREVIEW_CHARS)
    print("    " + shown.replace("\n", "\n    "))
    if len(body) > _BODY_PREVIEW_CHARS:
        print(f"    ... [{len(body) - _BODY_PREVIEW_CHARS} more chars truncated]")


def print_raw_requests(profile: ParsedProfile, country: str) -> None:
    """Issue and display the live HTTP requests fact_assembly drives for `country`.

    Reuses each module's own URL constants / id builders so the requests match
    what assemble() actually issues. Wage routing mirrors fact_assembly._fetch_wage:
    US + known degree field -> BLS occupation; otherwise OECD national average.
    """
    _rule(f"[{country}] (1) RAW API REQUESTS — what the live calls actually return")

    # --- wage ---
    soc = fact_assembly._soc_for_field(profile.degree_field) if country == "US" else None
    if country == "US" and soc is not None:
        body: dict = {"seriesid": [bls._build_series_id(soc)]}
        if settings.bls_api_key:
            body["registrationkey"] = settings.bls_api_key
        _show_post(f"WAGE · BLS OEWS (SOC {soc}, occupation-level)", bls.BLS_API_URL, body)
    else:
        meta = oecd._COUNTRY_META.get(country)
        if meta is None:
            print("\n  WAGE · OECD: country not in OECD meta — assemble() will use a fallback wage.")
        else:
            url = f"{oecd.OECD_BASE}/{oecd.OECD_DATAFLOW}/{meta['iso3']}......"
            params = {"startPeriod": "2019", "dimensionAtObservation": "TIME_PERIOD", "format": "jsondata"}
            reason = "US, no SOC for degree field" if country == "US" else "non-US"
            _show_get(
                f"WAGE · OECD AV_AN_WAGE ({meta['iso3']}, national avg; {reason})",
                url, params=params, headers={"Accept": "application/vnd.sdmx.data+json"},
            )

    # --- cost of living: World Bank (primary, 2 indicators) then WhereNext (secondary) ---
    wb_meta = worldbank._COUNTRY_META.get(country)
    if wb_meta is None:
        print("\n  COL · World Bank: country not in meta — assemble() will use a fallback index.")
    else:
        iso3 = wb_meta["iso3"]
        wb_params = {"format": "json", "per_page": "400", "date": "2015:2024"}
        for indicator, what in ((worldbank.INDICATOR_PPP, "household PPP"), (worldbank.INDICATOR_XR, "exchange rate")):
            url = f"{worldbank.WORLD_BANK_BASE}/country/{iso3}/indicator/{indicator}"
            _show_get(f"COL · World Bank {indicator} ({what})", url, params=wb_params)

    _show_get(
        "COL · WhereNext /cost-of-living (secondary; used only if World Bank falls back)",
        wherenext.COST_OF_LIVING_ENDPOINT,
    )

    print("\n  NOTE  tax (tax_rates.json) and visa enrichment (visa_rules.json) are curated/offline — no HTTP.")


# ── (2) parsed source results ────────────────────────────────────────────────

def _verdict(is_fallback: bool) -> str:
    return "FALLBACK (live call failed/unavailable)" if is_fallback else "LIVE"


def print_parsed_sources(profile: ParsedProfile, country: str) -> None:
    """Call the public fetch_*() functions and show their mapped result + verdict."""
    _rule(f"[{country}] (2) PARSED SOURCE RESULTS — what each module decided")

    # Wage (same routing as assemble()).
    soc = fact_assembly._soc_for_field(profile.degree_field) if country == "US" else None
    if country == "US" and soc is not None:
        wage = bls.fetch_bls_wages(soc)
    else:
        wage = oecd.fetch_oecd_wages(country)
    _sub("WAGE")
    _kv("source", wage.source)
    _kv("verdict", _verdict(wage.is_fallback))
    _kv("gross_annual", f"{wage.gross_annual:,.0f} {wage.currency}")
    _kv("granularity", wage.granularity)
    _kv("reference_period", wage.reference_period)
    _kv("soc_code", wage.soc_code)

    # Cost of living — show the full resolution chain (primary then secondary).
    wb = worldbank.fetch_national_col(country)
    _sub("COL · World Bank (primary)")
    _kv("verdict", _verdict(wb.is_fallback))
    _kv("index (US=100)", wb.cost_of_living_index)
    if wb.is_fallback:
        wn = wherenext.fetch_national_col(country)
        _sub("COL · WhereNext (secondary — World Bank fell back)")
        _kv("verdict", _verdict(wn.is_fallback))
        _kv("index (US=100)", wn.cost_of_living_index)
        _kv("monthly_cost_usd", wn.monthly_cost_usd)
        if wn.is_fallback:
            print("    -> both live sources fell back; assemble() uses the curated numbeo proxy.")


# ── (3) assembled bundle ─────────────────────────────────────────────────────

def _stub_route(country: str, slug: str) -> VisaRoute:
    """Stand-in for the Stage-2b route (not run here). Slug drives visa enrichment."""
    return VisaRoute(
        visa_slug=slug,
        visa_name=f"[stub route for {country}]",
        eligibility_summary="(stubbed — Stage 2b not run in this audit)",
        employer_sponsorship_required=True,
        path_to_residency_years=None,
        key_constraint="(stubbed)",
        routing_confidence="low",
        source_url="https://example.gov/stub",
        source_retrieved="2026-06-20",
    )


def print_bundle(profile: ParsedProfile, country: str, slug: str) -> None:
    _rule(f"[{country}] (3) ASSEMBLED BUNDLE — fact_assembly.assemble() output")
    _kv("injected visa_slug", slug)
    bundle = fact_assembly.assemble(profile, country, _stub_route(country, slug))
    print()
    print(json.dumps(bundle.model_dump(), indent=2, ensure_ascii=False, default=str))


# ── entry point ──────────────────────────────────────────────────────────────

def main() -> None:
    p = argparse.ArgumentParser(description="Live audit runner for Stage 2a fact assembly.")
    p.add_argument("--citizenship", default="India")
    p.add_argument("--field", default="Computer Science", help="degree field")
    p.add_argument(
        "--stage", default="new_grad",
        choices=["new_grad", "early_career", "mid_career", "senior"],
    )
    p.add_argument("--a", default="US", help="country_a")
    p.add_argument("--b", default="Germany", help="country_b")
    p.add_argument("--slug-a", default=None, help="injected visa slug for country_a (default: curated)")
    p.add_argument("--slug-b", default=None, help="injected visa slug for country_b (default: curated)")
    p.add_argument(
        "--context",
        default="I care most about long-term residency stability and not being tied to one employer.",
    )
    args = p.parse_args()

    profile = ParsedProfile(
        citizenship=args.citizenship,
        degree_field=args.field,
        career_stage=args.stage,
        country_a=args.a,
        country_b=args.b,
        user_context=args.context,
    )

    _rule("INPUT PROFILE")
    for k, v in profile.model_dump().items():
        _kv(k, v)
    if not settings.bls_api_key:
        print("\n  (BLS_API_KEY not set — BLS POST runs key-less at v1-equivalent limits.)")

    for country, slug_override in ((args.a, args.slug_a), (args.b, args.slug_b)):
        slug = slug_override or _DEFAULT_SLUG.get(country, "zz_unknown")
        print_raw_requests(profile, country)
        print_parsed_sources(profile, country)
        print_bundle(profile, country, slug)


if __name__ == "__main__":
    main()
