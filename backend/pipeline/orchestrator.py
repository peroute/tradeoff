"""Pipeline orchestrator — wires all stages together.

run_pipeline(request) -> DashboardPayload

Order: intake -> 2b (AI route+outlook) -> 2a (fact assembly x2 parallel)
       -> Stage 3 (AI reasoning, 7 slots) -> sacrifice_diff
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from backend.models.ai_models import WhatIfInsight
from backend.models.intake_models import CompareRequest
from backend.models.output_models import CountryBundle, DashboardPayload, PipelineMeta
from backend.pipeline import fact_assembly, immigration_outlook, sacrifice_diff
from backend.pipeline.intake import parse_and_validate
from backend.pipeline.reasoning_step import generate_insights

# 3 Stage-2b calls (2 per-country research + 1 structure) + 7 Stage-3 slots × 1 call each
_AI_CALLS_PER_RUN = 10


def run_pipeline(request: CompareRequest) -> DashboardPayload:
    """Run the full comparison pipeline end-to-end.

    Raises:
        ValueError   — intake rejected the request (same countries, bad field)
        RuntimeError — Stage 2b Gemini call failed unrecoverably
    All other stages degrade gracefully; Stage 3 failures surface as SafeFallbacks.
    """
    # ── Stage 1: intake ──────────────────────────────────────────────────────
    profile = parse_and_validate(request)

    # ── Stage 2b: AI visa routing + immigration outlook (3 Gemini calls) ─────
    route_and_outlook = immigration_outlook.fetch(profile)

    # ── Stage 2a: deterministic fact assembly, both countries in parallel ─────
    with ThreadPoolExecutor(max_workers=2) as pool:
        future_a = pool.submit(
            fact_assembly.assemble,
            profile, profile.country_a, route_and_outlook.visa_route_a,
        )
        future_b = pool.submit(
            fact_assembly.assemble,
            profile, profile.country_b, route_and_outlook.visa_route_b,
        )
        bundle_a: CountryBundle = future_a.result()
        bundle_b: CountryBundle = future_b.result()

    # ── Stage 3: AI what-if reasoning, 7 scenario slots ──────────────────────
    insights = generate_insights(bundle_a, bundle_b, profile.user_context)

    # ── Stage 4: deterministic sacrifice diff ─────────────────────────────────
    sacrifice_map = sacrifice_diff.compute(bundle_a, bundle_b, route_and_outlook)

    # ── Assemble and return ───────────────────────────────────────────────────
    insights_passed = sum(1 for i in insights if isinstance(i, WhatIfInsight))

    return DashboardPayload(
        bundle_a=bundle_a,
        bundle_b=bundle_b,
        outlook_a=route_and_outlook.country_a_outlook,
        outlook_b=route_and_outlook.country_b_outlook,
        insights=insights,
        sacrifice_map=sacrifice_map,
        pipeline_meta=PipelineMeta(
            ai_calls_made=_AI_CALLS_PER_RUN,
            insights_passed=insights_passed,
            insights_withheld=len(insights) - insights_passed,
            routing_confidence_a=route_and_outlook.visa_route_a.routing_confidence,
            routing_confidence_b=route_and_outlook.visa_route_b.routing_confidence,
            fact_sources={
                f"wage_{bundle_a.country}": bundle_a.wage.source,
                f"wage_{bundle_b.country}": bundle_b.wage.source,
                "cost_of_living": "Numbeo (mock)",
                "tax": "curated tax_rates.json",
                "visa_routing": "Gemini + Google Search (Stage 2b)",
                "visa_enrichment": "curated visa_rules.json",
            },
        ),
    )
