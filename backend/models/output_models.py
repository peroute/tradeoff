from typing import Annotated, Literal, Union
from pydantic import BaseModel, Field

from backend.models.ai_models import (
    ConfidenceLevel,
    ImmigrationOutlook,
    SafeFallback,
    VisaRoute,
    WhatIfInsight,
)

PartnerOpportunity = Literal["full", "restricted", "none"]

# Discriminated union — serialization uses the `type` field to distinguish
InsightOrFallback = Annotated[
    Union[WhatIfInsight, SafeFallback],
    Field(discriminator="type"),
]


class VisaEnrichment(BaseModel):
    """Curated facts from visa_rules.json, merged in when visa_slug matches."""
    min_salary: float | None
    currency: str | None
    can_switch_employer: bool | None
    switch_conditions: str | None
    lottery_required: bool | None
    lottery_annual_rate: float | None
    lottery_history: list[dict] | None
    lottery_cumulative_3yr: float | None
    partner_work_rights: PartnerOpportunity | None
    partner_work_notes: str | None
    last_verified: str | None
    curated_source_url: str | None


class WageData(BaseModel):
    gross_annual_local: float
    currency: str
    source: Literal["BLS", "OECD"]
    soc_code: str | None = None
    precision_note: str


class ColData(BaseModel):
    city: str | None                          # None for national figures (col_source="national_ppp")
    col_index: float | None                   # US/NYC = 100 baseline
    monthly_cost_usd: float | None
    source: str = "World Bank"
    col_source: Literal["city", "national_ppp"] = "national_ppp"
    is_fallback: bool = False                 # True when both live sources failed and a curated value was used
    precision_note: str | None = None         # tier + provenance disclosure (parallels WageData.precision_note)


class TaxData(BaseModel):
    effective_rate: float
    net_annual_local: float
    notes: str | None = None


class CountryBundle(BaseModel):
    """Fully assembled data for one destination country."""
    country: str
    wage: WageData
    col: ColData
    tax: TaxData
    net_takehome_ppp: float | None
    visa_route: VisaRoute
    visa_enrichment: VisaEnrichment | None


class DimensionDiff(BaseModel):
    """One row in the sacrifice map — covers both countries for a single dimension."""
    dimension: str
    country_a_value: float | str | None
    country_b_value: float | str | None
    delta: float | None = None
    winner: Literal["a", "b", "tie"] | None = None
    note: str | None = None


class SacrificeMap(BaseModel):
    """5-dimension cross-country comparison (all deterministic)."""
    net_takehome_ppp: DimensionDiff
    visa_stability_score: DimensionDiff
    pr_timeline_years: DimensionDiff
    lottery_risk: DimensionDiff
    partner_opportunity: DimensionDiff


class PipelineMeta(BaseModel):
    """Transparency panel — shown as collapsible 'How this was built' section."""
    ai_calls_made: int
    insights_passed: int
    insights_withheld: int
    routing_confidence_a: ConfidenceLevel
    routing_confidence_b: ConfidenceLevel
    fact_sources: dict[str, str]


class DashboardPayload(BaseModel):
    """Full response from POST /api/compare."""
    bundle_a: CountryBundle
    bundle_b: CountryBundle
    outlook_a: ImmigrationOutlook
    outlook_b: ImmigrationOutlook
    insights: list[InsightOrFallback]
    sacrifice_map: SacrificeMap
    pipeline_meta: PipelineMeta
