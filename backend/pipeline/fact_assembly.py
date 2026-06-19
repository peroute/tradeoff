"""Stage 2a — deterministic fact assembly.

assemble(profile, country, visa_route) -> CountryBundle

This is the adapter where the data sources meet the dashboard wire shape. The
clients return rich internal fact_models types (WageData, CostData, TaxBreakdown,
VisaFact); CountryBundle wants trimmed DTOs (output_models WageData/ColData/
TaxData + ai_models VisaRoute + output_models VisaEnrichment). assemble() calls
the sources and maps the results.

No LLM call here (Stage 2b owns that). The AI-resolved `visa_route` is INJECTED:
Stage 2b is wired separately, so callers/tests supply the route. Wage routing is
the one branch: US with a known degree field uses occupation-level BLS; everything
else uses OECD national-average. Every source degrades gracefully (fallback flags
surfaced via precision_note), so assemble() never raises on a missing reading.
"""

from __future__ import annotations

import json
from pathlib import Path

from backend.data_sources import bls, numbeo, oecd, tax, visa_rules, wherenext, worldbank
from backend.models.ai_models import VisaRoute
from backend.models.fact_models import VisaFact
from backend.models.fact_models import WageData as SourceWageData
from backend.models.intake_models import ParsedProfile
from backend.models.output_models import (
    ColData,
    CountryBundle,
    TaxData,
    VisaEnrichment,
    WageData,
)

_DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def _load_soc_map() -> dict:
    try:
        return json.loads((_DATA_DIR / "field_soc_map.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


# Loaded once at import (curated, static).
_SOC_MAP = _load_soc_map()


def _soc_for_field(degree_field: str) -> str | None:
    """BLS SOC code for `degree_field` from field_soc_map.json, or None."""
    entry = _SOC_MAP.get(degree_field)
    return entry.get("bls_soc") if entry else None


def _to_wage_data(fm: SourceWageData) -> WageData:
    """Map a source WageData onto the trimmed output DTO + a precision note."""
    source = "BLS" if fm.source.startswith("BLS") else "OECD"
    if source == "BLS":
        note = f"Occupation-level US wage (BLS OEWS) for SOC {fm.soc_code}."
    else:
        note = "National-average wage (OECD); not occupation-specific."
    if fm.is_fallback:
        note += " Curated fallback used (live source unavailable)."
    return WageData(
        gross_annual_local=fm.gross_annual,
        currency=fm.currency,
        source=source,
        soc_code=fm.soc_code,
        precision_note=note,
    )


def _fetch_wage(profile: ParsedProfile, country: str) -> WageData:
    """US + known field -> occupation-level BLS; otherwise OECD national average."""
    if country == "US":
        soc = _soc_for_field(profile.degree_field)
        if soc is not None:
            return _to_wage_data(bls.fetch_bls_wages(soc))
    return _to_wage_data(oecd.fetch_oecd_wages(country))


def _to_col_data(country: str) -> ColData:
    """National cost-of-living index (US = 100), resolved across live sources.

    Resolution order (each degrades gracefully to the next):
      1. World Bank PPP price-level index — primary, live, primary-source.
      2. WhereNext national cost index — live secondary / cross-check.
      3. Curated static table (numbeo) — last-resort offline fallback, flagged.
    All three are national figures, so col_source is always "national_ppp"; a live
    *city* tier isn't available for the locked countries (see wherenext.py).
    """
    wb = worldbank.fetch_national_col(country)
    if not wb.is_fallback:
        return _col_data_from(
            wb,
            is_fallback=False,
            note="National price-level index (World Bank, PPP-based, US=100); not city-specific.",
        )

    wn = wherenext.fetch_national_col(country)
    if not wn.is_fallback:
        return _col_data_from(
            wn,
            is_fallback=False,
            note=(
                "National cost index (WhereNext, US=100; aggregates World Bank ICP / "
                "Eurostat). World Bank live source was unavailable."
            ),
        )

    # Both live sources failed — curated static fallback (NYC=100 proxy).
    default_city = numbeo._COUNTRY_DEFAULT_CITY.get(country, country)
    nb = numbeo.fetch_cost_of_living(default_city, country)
    return _col_data_from(
        nb,
        is_fallback=True,
        note="Curated fallback index (live cost-of-living sources unavailable).",
        source="Curated (fallback)",
    )


def _col_data_from(
    cd, *, is_fallback: bool, note: str, source: str | None = None
) -> ColData:
    """Map a source CostData onto the national ColData DTO."""
    return ColData(
        city=None,  # national figure, not city-specific
        col_index=cd.cost_of_living_index,
        monthly_cost_usd=cd.monthly_cost_usd,
        source=source or cd.source,
        col_source="national_ppp",
        is_fallback=is_fallback,
        precision_note=note,
    )


def _to_tax_data(gross_annual_local: float, country: str) -> TaxData:
    tb = tax.compute_net_takehome(gross_annual_local, country)
    if tb is None:
        # Safety net: the 6 locked countries are all modeled.
        return TaxData(
            effective_rate=0.0,
            net_annual_local=gross_annual_local,
            notes=f"Tax not modeled for {country}.",
        )
    return TaxData(
        effective_rate=tb.effective_rate,
        net_annual_local=tb.net_annual,
        notes=tb.note,
    )


def _to_visa_enrichment(vf: VisaFact | None) -> VisaEnrichment | None:
    """Curated VisaFact -> VisaEnrichment DTO, or None when the slug isn't modeled."""
    if vf is None:
        return None
    return VisaEnrichment(
        min_salary=vf.min_salary,
        currency=vf.currency,
        can_switch_employer=vf.can_switch_employer,
        switch_conditions=vf.switch_conditions,
        lottery_required=vf.lottery_required,
        lottery_annual_rate=vf.lottery_annual_rate,
        lottery_history=vf.lottery_history,
        lottery_cumulative_3yr=vf.lottery_cumulative_3yr,
        partner_work_rights=vf.partner_work_rights,
        partner_work_notes=vf.partner_work_notes,
        last_verified=vf.last_verified,
        curated_source_url=vf.source_url,
    )


def _net_takehome_ppp(net_annual_local: float, col_index: float | None) -> float | None:
    """Net take-home adjusted for cost of living (NYC=100 baseline)."""
    if col_index is None:
        return None
    return net_annual_local / (col_index / 100)


def assemble(
    profile: ParsedProfile, country: str, visa_route: VisaRoute
) -> CountryBundle:
    """Assemble one destination's CountryBundle from the data sources.

    `visa_route` is the AI-resolved route (Stage 2b output), injected by the
    caller. Wages route to BLS (US + known degree field) or OECD (otherwise);
    cost-of-living and tax come from the mock/curated layers; the curated visa
    enrichment is looked up by the route's slug (None when not modeled).
    """
    wage = _fetch_wage(profile, country)
    col = _to_col_data(country)
    tax_data = _to_tax_data(wage.gross_annual_local, country)
    enrichment = _to_visa_enrichment(visa_rules.get_visa_rule(visa_route.visa_slug))

    return CountryBundle(
        country=country,
        wage=wage,
        col=col,
        tax=tax_data,
        net_takehome_ppp=_net_takehome_ppp(tax_data.net_annual_local, col.col_index),
        visa_route=visa_route,
        visa_enrichment=enrichment,
    )
