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

# Sample FX (LCU per USD) so the stub's net-USD figures are internally consistent.
_US_XR = 1.0
_DE_XR = 0.9239


def _net_usd(net_annual_local: float, xr: float) -> float:
    """Net take-home converted to nominal USD (market FX)."""
    return round(net_annual_local / xr, 2)


def _bundle_a(country: str) -> CountryBundle:
    net = 97_364.0
    col_index = 100.0  # US baseline
    return CountryBundle(
        country=country,
        wage=WageData(
            gross_annual_local=132_270.0,
            currency="USD",
            source="BLS",
            soc_code="15-1252",
            precision_note="Occupation-level US wage (BLS OEWS) for SOC 15-1252.",
        ),
        col=ColData(city="New York", col_index=col_index, exchange_rate_to_usd=_US_XR, monthly_cost_usd=None, source="Numbeo"),
        tax=TaxData(
            effective_rate=0.2638,
            net_annual_local=net,
            notes="Federal income tax + FICA; state taxes not included.",
        ),
        net_annual_usd=_net_usd(net, _US_XR),
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
        col=ColData(city="Berlin", col_index=col_index, exchange_rate_to_usd=_DE_XR, monthly_cost_usd=None, source="Numbeo"),
        tax=TaxData(
            effective_rate=0.3168,
            net_annual_local=net,
            notes="Income tax + approximate employee social contributions.",
        ),
        net_annual_usd=_net_usd(net, _DE_XR),
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
        # Slot 1 — base, country A only (scene-setting; fact_b empty).
        WhatIfInsight(
            scenario_type="base",
            fact_a="bundle_a.net_takehome_ppp",
            fact_b=None,
            context_used="long-term residency stability",
            tradeoff="The US net_takehome_ppp buys more day-to-day, but that take-home only lands while you hold the visa that underpins residency stability.",
            likely_outcome="On an H-1B you most likely enjoy the higher take-home for the first few years, with the lottery and renewals still unresolved.",
            consideration="The headline US take-home is contingent on clearing the H-1B lottery, so the nominal advantage overstates what is actually guaranteed.",
            confidence="high",
            confidence_basis="Wage and lottery rate are both curated facts.",
            next_action="Compare your offer salary against the H-1B prevailing-wage floor.",
        ),
        # Slot 2 — base, country B only (scene-setting; fact_a empty).
        WhatIfInsight(
            scenario_type="base",
            fact_a=None,
            fact_b="bundle_b.net_takehome_ppp",
            context_used="long-term residency stability",
            tradeoff="Germany's net_takehome_ppp is lower, but it arrives on a route whose residency stability is not gated by a lottery.",
            likely_outcome="On the Blue Card you most likely keep a steadier, if smaller, take-home while the residency clock runs without a draw.",
            consideration="The lower German take-home is near-certain rather than conditional, so comparing it head-to-head with the US figure understates its reliability.",
            confidence="high",
            confidence_basis="Wage is curated; Blue Card has no lottery gate.",
            next_action="Budget against the German net take-home to test if the lower figure still meets your needs.",
        ),
        # Slot 3 — lottery_risk, comparative.
        WhatIfInsight(
            scenario_type="lottery_risk",
            fact_a="bundle_a.visa_enrichment.lottery_cumulative_3yr",
            fact_b="bundle_b.visa_enrichment.lottery_required",
            context_used="long-term residency stability",
            tradeoff="Choosing the US accepts lottery_cumulative_3yr odds for higher pay; choosing Germany, where no lottery is required, trades pay for a stability you can count on.",
            likely_outcome="Over three H-1B cycles the more likely outcome is non-selection (~64%), whereas the Blue Card path has no draw to lose.",
            consideration="The lottery converts the US's pay advantage into a coin-flip on stability, so the two options aren't on the same risk footing.",
            confidence="medium",
            confidence_basis="Three-cycle estimate assumes the current selection rate holds.",
            next_action="Draft a backup plan (O-1 or cap-exempt employer) before accepting a US offer.",
        ),
        # Slot 4 — partner_work, comparative.
        WhatIfInsight(
            scenario_type="partner_work",
            fact_a="bundle_a.visa_enrichment.partner_work_rights",
            fact_b="bundle_b.visa_enrichment.partner_work_rights",
            context_used="long-term residency stability",
            tradeoff="US partner_work_rights are restricted while Germany's are full, so the US pay premium is partly offset by a second income your household may have to forgo.",
            likely_outcome="In the US your spouse most likely cannot work until an EAD is granted; in Germany they can work from arrival.",
            consideration="Household stability, not just your salary, hinges on partner work rights — a factor the single-earner headline numbers hide.",
            confidence="high",
            confidence_basis="Partner work rights are curated for both routes.",
            next_action="Confirm your partner's qualification recognition in Germany.",
        ),
        # Slot 5 — priority_match, comparative.
        WhatIfInsight(
            scenario_type="priority_match",
            fact_a="bundle_a.visa_route.path_to_residency_years",
            fact_b="bundle_b.visa_route.path_to_residency_years",
            context_used="long-term residency stability",
            tradeoff="The US path_to_residency_years (6) is longer than Germany's (4), so prioritising residency stability favours Germany at the cost of US earning power.",
            likely_outcome="If stability is your real priority you most likely reach permanent status two years sooner in Germany, and without a lottery gate.",
            consideration="The faster, lottery-free German timeline maps more directly onto a stability-first priority than the higher US salary does.",
            confidence="high",
            confidence_basis="PR timelines are curated for both routes.",
            next_action="Verify the German B1 language requirement for permanent settlement.",
        ),
        # Slot 6 — withheld (a real validation miss, kept to show the gate working).
        SafeFallback(
            reason="next_action is not verb-led (starts with 'understanding')",
            slot_index=5,
        ),
        # Slot 7 — synthesis, comparative (the decision moment).
        WhatIfInsight(
            scenario_type="synthesis",
            fact_a="bundle_a.net_takehome_ppp",
            fact_b="bundle_b.visa_route.path_to_residency_years",
            context_used="long-term residency stability",
            tradeoff="The sharpest tradeoff is US net_takehome_ppp against Germany's shorter path_to_residency_years: higher-but-uncertain purchasing power versus lower-but-near-certain residency.",
            likely_outcome="The most likely real-world split is more money now in the US with a lottery hanging over it, versus steadier, sooner residency in Germany.",
            consideration="The decision reduces to how you personally weight purchasing power against residency certainty — the numbers alone don't settle it.",
            confidence="medium",
            confidence_basis="Synthesis of curated facts; the trade-off weighting is yours.",
            next_action="Rank lottery risk against take-home for yourself before deciding.",
        ),
    ]


def _sacrifice_map(country_a: str, country_b: str) -> SacrificeMap:
    net_a_usd = _net_usd(97_364.0, _US_XR)
    net_b_usd = _net_usd(36_895.0, _DE_XR)
    return SacrificeMap(
        net_takehome_usd=DimensionDiff(
            dimension="net_takehome_usd",
            country_a_value=net_a_usd,
            country_b_value=net_b_usd,
            delta=round(net_a_usd - net_b_usd, 2),
            winner="a",
            note="Annual take-home converted to USD (nominal, market FX).",
        ),
        col_relative=DimensionDiff(
            dimension="col_relative",
            country_a_value=100.0,
            country_b_value=round(65.3 / 100.0 * 100, 1),
            delta=round(65.3 - 100.0, 1),
            winner="b",
            note="Cost of living relative to Country A (A = 100; lower is cheaper).",
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
