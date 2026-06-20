"""Temporary stub for POST /api/compare.

Returns a fully hardcoded, schema-valid DashboardPayload so the frontend can
build against the real response shape before Stage 2b + the orchestrator exist.
This is NOT live data: no LLM call, no data-source calls. The payload self-labels
as a sample via pipeline_meta.fact_sources so stubbed numbers are never mistaken
for a real reading. Delete this module (and restore the orchestrator call in
routers/compare.py) once run_pipeline() lands.

The example is a fixed US-vs-Germany comparison; only the two destination labels
are taken from the request so the response feels responsive to input.
"""

from __future__ import annotations

from backend.models.ai_models import (
    ImmigrationOutlook,
    SafeFallback,
    VisaRoute,
    WhatIfInsight,
)
from backend.models.intake_models import CompareRequest
from backend.models.output_models import (
    ColData,
    CountryBundle,
    DashboardPayload,
    DimensionDiff,
    PipelineMeta,
    SacrificeMap,
    TaxData,
    VisaEnrichment,
    WageData,
)

STUB_NOTE = "SAMPLE / stub payload — not live data"


def _ppp(net_annual_local: float, col_index: float) -> float:
    """Cost-of-living-adjusted take-home (NYC = 100 baseline)."""
    return net_annual_local / (col_index / 100)


def _bundle_a(country: str) -> CountryBundle:
    net = 97_364.0
    col_index = 100.0  # New York baseline
    return CountryBundle(
        country=country,
        wage=WageData(
            gross_annual_local=132_270.0,
            currency="USD",
            source="BLS",
            soc_code="15-1252",
            precision_note="Occupation-level US wage (BLS OEWS) for SOC 15-1252.",
        ),
        col=ColData(city="New York", col_index=col_index, monthly_cost_usd=None, source="Numbeo"),
        tax=TaxData(
            effective_rate=0.2638,
            net_annual_local=net,
            notes="Federal income tax + FICA; state taxes not included.",
        ),
        net_takehome_ppp=_ppp(net, col_index),
        visa_route=VisaRoute(
            visa_slug="us_h1b",
            visa_name="H-1B Specialty Occupation",
            eligibility_summary="Bachelor's+ in a specialty field with a sponsoring employer.",
            employer_sponsorship_required=True,
            path_to_residency_years=6,
            key_constraint="Annual lottery cap; selection is not guaranteed.",
            routing_confidence="high",
            source_url="https://www.uscis.gov/working-in-the-united-states/h-1b-specialty-occupations",
            source_retrieved="2026-06-19",
        ),
        visa_enrichment=VisaEnrichment(
            min_salary=60_000.0,
            currency="USD",
            can_switch_employer=True,
            switch_conditions="New employer must file a fresh H-1B petition (no re-lottery).",
            lottery_required=True,
            lottery_annual_rate=0.14,
            lottery_history=[{"year": 2024, "rate": 0.14}],
            lottery_cumulative_3yr=0.3639,
            partner_work_rights="restricted",
            partner_work_notes="H-4 dependents need an EAD; eligible only in limited cases.",
            last_verified="2026-06-19",
            curated_source_url="https://www.uscis.gov/working-in-the-united-states/h-1b-specialty-occupations",
        ),
    )


def _bundle_b(country: str) -> CountryBundle:
    net = 36_895.0
    col_index = 65.3  # Berlin
    return CountryBundle(
        country=country,
        wage=WageData(
            gross_annual_local=54_000.0,
            currency="EUR",
            source="OECD",
            soc_code=None,
            precision_note="National-average wage (OECD); not occupation-specific.",
        ),
        col=ColData(city="Berlin", col_index=col_index, monthly_cost_usd=None, source="Numbeo"),
        tax=TaxData(
            effective_rate=0.3168,
            net_annual_local=net,
            notes="Income tax + approximate employee social contributions.",
        ),
        net_takehome_ppp=_ppp(net, col_index),
        visa_route=VisaRoute(
            visa_slug="de_eu_blue_card",
            visa_name="EU Blue Card (Germany)",
            eligibility_summary="Recognised degree + a job offer above the salary threshold.",
            employer_sponsorship_required=False,
            path_to_residency_years=4,
            key_constraint="Salary must meet the annual Blue Card threshold.",
            routing_confidence="medium",
            source_url="https://www.make-it-in-germany.com/en/visa-residence/types/eu-blue-card",
            source_retrieved="2026-06-19",
        ),
        visa_enrichment=VisaEnrichment(
            min_salary=45_300.0,
            currency="EUR",
            can_switch_employer=True,
            switch_conditions="Employer change in the first 12 months needs authority approval.",
            lottery_required=False,
            lottery_annual_rate=None,
            lottery_history=[],
            lottery_cumulative_3yr=None,
            partner_work_rights="full",
            partner_work_notes="Spouse gets unrestricted labour-market access.",
            last_verified="2026-06-19",
            curated_source_url="https://www.make-it-in-germany.com/en/visa-residence/types/eu-blue-card",
        ),
    )


def _outlook(country: str) -> ImmigrationOutlook:
    return ImmigrationOutlook(
        trend_summary=f"{country} immigration policy has been broadly stable over the past year.",
        trend_direction="stable",
        key_recent_change="No major statutory change in the last 12 months.",
        career_context="Demand for skilled technical workers remains strong.",
        source_url="https://example.gov/immigration-outlook",
        source_publish_date="2026-05-01",
        confidence="medium",
    )


def _insights() -> list:
    return [
        WhatIfInsight(
            scenario_type="base",
            fact_used="bundle_a.net_takehome_ppp",
            context_used="long-term residency stability",
            connection="take-home and residency both depend on holding the visa",
            consideration="The higher US take-home is contingent on clearing the H-1B lottery, so the nominal gap overstates the guaranteed advantage.",
            confidence="high",
            confidence_basis="Lottery rate and wage are both curated facts.",
            next_action="Compare your offer salary against the H-1B prevailing-wage floor.",
        ),
        WhatIfInsight(
            scenario_type="base",
            fact_used="bundle_b.visa_enrichment.partner_work_rights",
            context_used="long-term residency stability",
            connection="partner work rights affect household stability",
            consideration="Germany's full partner work rights cut household income risk that the US H-4 restriction leaves exposed.",
            confidence="high",
            confidence_basis="Partner work rights are curated for both routes.",
            next_action="Confirm your partner's qualification recognition in Germany.",
        ),
        WhatIfInsight(
            scenario_type="lottery_risk",
            fact_used="bundle_a.visa_enrichment.lottery_cumulative_3yr",
            context_used="long-term residency stability",
            connection="cumulative lottery odds bound the stability of the US path",
            consideration="At ~36% over three cycles, the more likely outcome is non-selection, so a US plan needs a fallback route.",
            confidence="medium",
            confidence_basis="Three-cycle estimate assumes the current selection rate holds.",
            next_action="Draft a backup plan (O-1 or cap-exempt employer) before accepting a US offer.",
        ),
        WhatIfInsight(
            scenario_type="employer_switch",
            fact_used="bundle_b.visa_enrichment.switch_conditions",
            context_used="long-term residency stability",
            connection="employer-switch rules shape recovery if a job ends",
            consideration="A first-year job loss in Germany requires authority approval to switch, a constraint not obvious from the headline 'can switch employer'.",
            confidence="medium",
            confidence_basis="Switch conditions are curated but simplify case-by-case rules.",
            next_action="Ask the employer about probation length and Blue Card timing.",
        ),
        WhatIfInsight(
            scenario_type="priority_match",
            fact_used="bundle_b.visa_route.path_to_residency_years",
            context_used="long-term residency stability",
            connection="years-to-PR directly measures the stated residency priority",
            consideration="Germany's 4-year PR path beats the US 6-year baseline, and is not gated by a lottery — a better fit for a stability-first priority.",
            confidence="high",
            confidence_basis="PR timelines are curated for both routes.",
            next_action="Verify the German B1 language requirement for permanent settlement.",
        ),
        SafeFallback(
            reason="Generated insight failed validation (fact_used did not match a real fact key).",
            slot_index=5,
        ),
        WhatIfInsight(
            scenario_type="synthesis",
            fact_used="bundle_a.net_takehome_ppp",
            context_used="long-term residency stability",
            connection="weighing take-home against residency certainty",
            consideration="The decision reduces to higher-but-uncertain US purchasing power versus lower-but-near-certain German residency — which depends on your risk tolerance, not the numbers alone.",
            confidence="medium",
            confidence_basis="Synthesis of curated facts; the trade-off weighting is yours.",
            next_action="Rank lottery risk vs. take-home for yourself before deciding.",
        ),
    ]


def _sacrifice_map(country_a: str, country_b: str) -> SacrificeMap:
    return SacrificeMap(
        net_takehome_ppp=DimensionDiff(
            dimension="net_takehome_ppp",
            country_a_value=_ppp(97_364.0, 100.0),
            country_b_value=_ppp(36_895.0, 65.3),
            delta=_ppp(97_364.0, 100.0) - _ppp(36_895.0, 65.3),
            winner="a",
            note="US leads on cost-of-living-adjusted take-home.",
        ),
        visa_stability_score=DimensionDiff(
            dimension="visa_stability_score",
            country_a_value=0.36,
            country_b_value=0.90,
            delta=-0.54,
            winner="b",
            note="Germany's no-lottery route is far more certain.",
        ),
        pr_timeline_years=DimensionDiff(
            dimension="pr_timeline_years",
            country_a_value=6,
            country_b_value=4,
            delta=2,
            winner="b",
            note="Germany reaches permanent residency sooner.",
        ),
        lottery_risk=DimensionDiff(
            dimension="lottery_risk",
            country_a_value=0.64,
            country_b_value=0.0,
            delta=0.64,
            winner="b",
            note="US H-1B carries a ~64% three-year non-selection risk.",
        ),
        partner_opportunity=DimensionDiff(
            dimension="partner_opportunity",
            country_a_value="restricted",
            country_b_value="full",
            delta=None,
            winner="b",
            note="Germany grants full partner work rights.",
        ),
    )


def build_sample_payload(request: CompareRequest) -> DashboardPayload:
    """Hardcoded, schema-valid DashboardPayload for the stubbed /api/compare.

    Fixed US-vs-Germany example; the request's two countries are stamped onto the
    bundles and sacrifice map so the response reflects the caller's inputs.
    """
    bundle_a = _bundle_a(request.country_a)
    bundle_b = _bundle_b(request.country_b)
    insights = _insights()
    return DashboardPayload(
        bundle_a=bundle_a,
        bundle_b=bundle_b,
        outlook_a=_outlook(request.country_a),
        outlook_b=_outlook(request.country_b),
        insights=insights,
        sacrifice_map=_sacrifice_map(request.country_a, request.country_b),
        pipeline_meta=PipelineMeta(
            ai_calls_made=2,
            insights_passed=sum(1 for i in insights if isinstance(i, WhatIfInsight)),
            insights_withheld=sum(1 for i in insights if isinstance(i, SafeFallback)),
            routing_confidence_a=bundle_a.visa_route.routing_confidence,
            routing_confidence_b=bundle_b.visa_route.routing_confidence,
            fact_sources={
                "wage": "BLS / OECD",
                "cost_of_living": "Numbeo (mock)",
                "tax": "curated tax_rates.json",
                "visa": "curated visa_rules.json",
                "note": STUB_NOTE,
            },
        ),
    )
