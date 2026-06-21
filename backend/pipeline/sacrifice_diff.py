"""Stage 4 — deterministic sacrifice diff.

compute(bundle_a, bundle_b, route_and_outlook) -> SacrificeMap

Converts two fully-assembled CountryBundles into 5 directly-comparable
dimension scores so the dashboard can show exactly what you gain and give up
in each country.

No LLM call here. The one place an AI-sourced signal enters is
visa_stability_score, where trend_direction (from Stage 2b) applies a penalty
for restrictive immigration climates. That link is documented inline.
"""

from __future__ import annotations

from backend.models.ai_models import ImmigrationOutlook, RouteAndOutlook
from backend.models.output_models import CountryBundle, DimensionDiff, SacrificeMap

# Ordering for the categorical partner_work_rights field (higher = better).
_PARTNER_RANK: dict[str, int] = {"full": 2, "restricted": 1, "none": 0}


def _winner_numeric(
    a: float | int | None,
    b: float | int | None,
    *,
    higher_is_better: bool,
) -> str | None:
    """Return "a", "b", or "tie"; None when either value is missing."""
    if a is None or b is None:
        return None
    if a == b:
        return "tie"
    better_a = (a > b) if higher_is_better else (a < b)
    return "a" if better_a else "b"


def _visa_stability_score(
    bundle: CountryBundle,
    outlook: ImmigrationOutlook,
) -> float:
    """0–1 stability score for one destination's visa route.

    Formula (plan.md — documented here so judges can audit it):
      base = (0 if employer_sponsorship_required else 1)
             + (1 if can_switch_employer else 0)
             + max(0, (10 - path_to_pr_years) / 10)
      trend_penalty   = 0.3 if trend_direction == "restrictive" else 0
      lottery_penalty = (1 - lottery_cumulative_3yr) * 0.5 if lottery_required else 0
      score = max(0.0, base - trend_penalty - lottery_penalty) / 2.5

    AI-sourced signal: trend_direction (Stage 2b ImmigrationOutlook) feeds
    trend_penalty only. All other inputs are curated hard facts.
    """
    route = bundle.visa_route
    enrichment = bundle.visa_enrichment

    pr_years = route.path_to_residency_years
    switch = enrichment.can_switch_employer if enrichment else None
    lottery_req = bool(enrichment.lottery_required) if enrichment else False
    lottery_cum = enrichment.lottery_cumulative_3yr if enrichment else None

    base = (
        (0.0 if route.employer_sponsorship_required else 1.0)
        + (1.0 if switch else 0.0)
        + (max(0.0, (10 - pr_years) / 10) if pr_years is not None else 0.0)
    )

    # AI-sourced signal — restrictive climate penalises stability.
    trend_penalty = 0.3 if outlook.trend_direction == "restrictive" else 0.0

    lottery_penalty = (
        (1.0 - lottery_cum) * 0.5
        if lottery_req and lottery_cum is not None
        else 0.0
    )

    return round(max(0.0, base - trend_penalty - lottery_penalty) / 2.5, 4)


def _lottery_risk(bundle: CountryBundle) -> float | None:
    """1 − lottery_cumulative_3yr, or None when there is no lottery."""
    enrichment = bundle.visa_enrichment
    if enrichment is None or not enrichment.lottery_required:
        return None
    cum = enrichment.lottery_cumulative_3yr
    return round(1.0 - cum, 4) if cum is not None else None


def _partner_diff(bundle_a: CountryBundle, bundle_b: CountryBundle) -> DimensionDiff:
    """Categorical diff for partner work rights (full > restricted > none)."""
    val_a = bundle_a.visa_enrichment.partner_work_rights if bundle_a.visa_enrichment else None
    val_b = bundle_b.visa_enrichment.partner_work_rights if bundle_b.visa_enrichment else None

    rank_a = _PARTNER_RANK.get(val_a, -1) if val_a else -1
    rank_b = _PARTNER_RANK.get(val_b, -1) if val_b else -1

    if val_a is None and val_b is None:
        winner = None
    elif val_a is None:
        winner = "b"
    elif val_b is None:
        winner = "a"
    elif rank_a > rank_b:
        winner = "a"
    elif rank_b > rank_a:
        winner = "b"
    else:
        winner = "tie"

    if val_a == val_b:
        note = "Both countries offer the same partner work rights."
    elif winner == "a":
        note = f"Country A offers {val_a} partner work rights vs {val_b or 'unknown'} for Country B."
    else:
        note = f"Country B offers {val_b} partner work rights vs {val_a or 'unknown'} for Country A."

    return DimensionDiff(
        dimension="partner_opportunity",
        country_a_value=val_a,
        country_b_value=val_b,
        delta=None,  # categorical — no numeric delta
        winner=winner,
        note=note,
    )


def compute(
    bundle_a: CountryBundle,
    bundle_b: CountryBundle,
    route_and_outlook: RouteAndOutlook,
) -> SacrificeMap:
    """Build the 5-dimension sacrifice map from two assembled CountryBundles.

    Called by the orchestrator after Stage 3 validation. All math is
    deterministic and traceable to cited sources except trend_direction
    (Stage 2b AI call), which is labelled in _visa_stability_score.
    """
    # ── 1. net_takehome_usd ─────────────────────────────────────────────────
    net_a = bundle_a.net_annual_usd
    net_b = bundle_b.net_annual_usd
    net_delta = round(net_a - net_b, 2) if net_a is not None and net_b is not None else None

    # ── 1b. col_relative (Country A = 100 baseline) ─────────────────────────
    col_a = bundle_a.col.col_index
    col_b = bundle_b.col.col_index
    if col_a and col_b:
        col_rel_a: float | None = 100.0
        col_rel_b: float | None = round(col_b / col_a * 100, 1)
        col_rel_delta: float | None = round(col_rel_b - 100.0, 1)
        # Lower cost of living is better; A is the fixed 100 baseline.
        col_winner = _winner_numeric(col_rel_a, col_rel_b, higher_is_better=False)
    else:
        col_rel_a = 100.0 if col_a else None
        col_rel_b = None
        col_rel_delta = None
        col_winner = None

    # ── 2. visa_stability_score ──────────────────────────────────────────────
    score_a = _visa_stability_score(bundle_a, route_and_outlook.country_a_outlook)
    score_b = _visa_stability_score(bundle_b, route_and_outlook.country_b_outlook)

    # ── 3. pr_timeline_years ─────────────────────────────────────────────────
    pr_a = bundle_a.visa_route.path_to_residency_years
    pr_b = bundle_b.visa_route.path_to_residency_years
    pr_delta = (pr_a - pr_b) if pr_a is not None and pr_b is not None else None

    # ── 4. lottery_risk ──────────────────────────────────────────────────────
    risk_a = _lottery_risk(bundle_a)
    risk_b = _lottery_risk(bundle_b)
    risk_delta = round(risk_a - risk_b, 4) if risk_a is not None and risk_b is not None else None

    # When one country has no lottery its risk is effectively 0 — it wins.
    if risk_a is None and risk_b is not None:
        lottery_winner: str | None = "a"
    elif risk_b is None and risk_a is not None:
        lottery_winner = "b"
    elif risk_a is None and risk_b is None:
        lottery_winner = "tie"
    else:
        lottery_winner = _winner_numeric(risk_a, risk_b, higher_is_better=False)

    return SacrificeMap(
        net_takehome_usd=DimensionDiff(
            dimension="net_takehome_usd",
            country_a_value=round(net_a, 2) if net_a is not None else None,
            country_b_value=round(net_b, 2) if net_b is not None else None,
            delta=net_delta,
            winner=_winner_numeric(net_a, net_b, higher_is_better=True),
            note="Annual take-home converted to USD (nominal, market FX).",
        ),
        col_relative=DimensionDiff(
            dimension="col_relative",
            country_a_value=col_rel_a,
            country_b_value=col_rel_b,
            delta=col_rel_delta,
            winner=col_winner,
            note="Cost of living relative to Country A (A = 100; lower is cheaper).",
        ),
        visa_stability_score=DimensionDiff(
            dimension="visa_stability_score",
            country_a_value=score_a,
            country_b_value=score_b,
            delta=round(score_a - score_b, 4),
            winner=_winner_numeric(score_a, score_b, higher_is_better=True),
            note="0–1 score: employer sponsorship, job switching, PR timeline, immigration trend, lottery risk.",
        ),
        pr_timeline_years=DimensionDiff(
            dimension="pr_timeline_years",
            country_a_value=pr_a,
            country_b_value=pr_b,
            delta=pr_delta,
            winner=_winner_numeric(pr_a, pr_b, higher_is_better=False),
            note="Years to permanent residency (lower is better).",
        ),
        lottery_risk=DimensionDiff(
            dimension="lottery_risk",
            country_a_value=risk_a,
            country_b_value=risk_b,
            delta=risk_delta,
            winner=lottery_winner,
            note="Probability of non-selection across 3 annual lottery cycles (null = no lottery, treated as zero risk).",
        ),
        partner_opportunity=_partner_diff(bundle_a, bundle_b),
    )
