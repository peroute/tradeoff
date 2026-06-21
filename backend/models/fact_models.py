from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, Field

# Still to implement (other tasks): CountryBundle


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class WageData(BaseModel):
    """Gross annual wage for one destination country.

    `currency` is ALWAYS the destination country's national currency so the
    figure can be fed straight into that country's tax brackets in
    tax_rates.json (which are also national-currency). Do not store USD-PPP
    here — that would break compute_net_takehome().

    `granularity` records the resolution gap the dashboard discloses via
    PrecisionCaveat: BLS gives US wages at occupation level; OECD gives every
    other country a single national average.
    """

    country: str
    currency: str
    gross_annual: float
    granularity: Literal["national_average", "occupation"]
    occupation: Optional[str] = None          # human label, occupation granularity only
    soc_code: Optional[str] = None            # BLS SOC, occupation granularity only
    reference_period: Optional[str] = None    # e.g. "2023"
    source: str                               # "OECD" | "BLS" | "OECD (fallback)" | "BLS (fallback)"
    source_url: Optional[str] = None
    is_fallback: bool = False                 # True when live API failed and curated value was used
    retrieved_at: str = Field(default_factory=_utc_now_iso)


class CostData(BaseModel):
    """City-level cost-of-living indices in Numbeo's schema (New York = 100 baseline).

    Field names mirror Numbeo's /api/indices payload so the mapping in
    numbeo.py is 1:1 with a real response.
    """

    city: str
    country: str
    currency: str
    cost_of_living_index: float               # Numbeo cpi_index (excludes rent)
    exchange_rate_to_usd: Optional[float] = None  # LCU per USD (World Bank PA.NUS.FCRF); None for sources that don't supply FX
    monthly_cost_usd: Optional[float] = None  # estimated monthly living cost USD (WhereNext); None for index-only sources
    rent_index: Optional[float] = None
    cost_of_living_plus_rent_index: Optional[float] = None
    groceries_index: Optional[float] = None
    restaurant_price_index: Optional[float] = None
    local_purchasing_power_index: Optional[float] = None
    source: str                               # "Numbeo (mock)"
    is_mock: bool = False                      # True: served from curated mock, not a live subscription
    is_fallback: bool = False                  # True: requested city unknown, generic default served
    retrieved_at: str = Field(default_factory=_utc_now_iso)


class TaxBreakdown(BaseModel):
    """Net take-home derived from one country's curated tax brackets.

    Produced by compute_net_takehome(gross_annual, country) over the curated
    tax_rates.json. All figures are in the destination country's national
    currency — the same currency WageData carries, by design, so the gross can be
    fed straight into the brackets. These are HARD facts (never LLM-looked-up); an
    unmodeled 7th country yields None rather than a fabricated figure.

    `note` carries the table's scope caveat (e.g. US = federal only, no state) so
    the dashboard can disclose what the deduction does and doesn't cover.
    """

    country: str
    currency: str
    gross_annual: float
    income_tax: float                         # progressive bracket total
    social_contributions: float               # SS+Medicare / NI / CPP / levy / combined, per country
    total_deductions: float                   # income_tax + social_contributions
    net_annual: float                         # gross_annual - total_deductions
    effective_rate: float                     # total_deductions / gross_annual (0.0 when gross <= 0)
    source_url: Optional[str] = None
    last_verified: Optional[str] = None       # YYYY-MM-DD, curated
    note: Optional[str] = None                # table scope caveat


class VisaRouteResolved(BaseModel):
    """One country's AI-resolved visa route — the parsed `visa_route_a`/`_b`
    object from Stage 2b's RouteAndOutlook (Gemini + Google Search grounding).

    AI-authoritative for ROUTING IDENTIFICATION ONLY (which visa applies, the
    eligibility narrative, routing confidence, and the source it was read from).
    It must NOT be trusted for hard numeric facts (salary floor, exact PR
    timeline) — those are validated against the curated visa_rules.json and
    merged in by merge_visa_facts(). See plan.md "Visa Route Resolution".
    """

    visa_slug: str                            # e.g. "us_h1b"; key to match curated rules
    visa_name: str
    eligibility_summary: str
    employer_sponsorship_required: bool
    path_to_residency_years: Optional[int] = None
    key_constraint: str
    routing_confidence: Literal["high", "medium", "low"]
    source_url: str
    source_retrieved: Optional[str] = None    # when the source page was read


class VisaFact(BaseModel):
    """Merged visa enrichment for one destination, consumed by sacrifice_diff
    and the reasoning fact bundle.

    Produced by merge_visa_facts(route, curated): AI route supplies the routing
    identity/confidence; curated visa_rules.json supplies the hard, dated, cited
    facts (curated WINS on conflict — the AI never states hard facts).

    `is_modeled` is False for unknown slugs / a 7th country: curated fields stay
    None and the dashboard flags the visa as "not yet modeled" rather than
    fabricating. `lottery_cumulative_3yr` is filled via compute_lottery_cumulative().
    """

    # identity / routing (from the AI route)
    country: str
    visa_slug: str
    visa_name: str
    routing_confidence: Literal["high", "medium", "low"]
    eligibility_summary: Optional[str] = None
    key_constraint: Optional[str] = None

    # hard curated facts (None when not modeled)
    min_salary: Optional[float] = None
    currency: Optional[str] = None
    employer_sponsorship_required: Optional[bool] = None
    can_switch_employer: Optional[bool] = None
    switch_conditions: Optional[str] = None
    path_to_pr_years: Optional[float] = None
    lottery_required: bool = False
    lottery_annual_rate: Optional[float] = None
    lottery_history: list[dict] = Field(default_factory=list)
    lottery_cumulative_3yr: Optional[float] = None
    partner_work_rights: Optional[Literal["full", "restricted", "none"]] = None
    partner_work_notes: Optional[str] = None

    # provenance + graceful degradation
    is_modeled: bool = False                  # True only when a curated rule matched the slug
    source_url: Optional[str] = None
    last_verified: Optional[str] = None       # YYYY-MM-DD, curated only
