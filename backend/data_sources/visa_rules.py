"""Curated visa-rule data layer.

Loads data/visa_rules.json (manually researched, cited, dated) and exposes:

  * get_visa_rule(slug)            -> curated VisaFact for one visa slug, or None
  * merge_visa_facts(route, rule)  -> VisaFact merging the AI-resolved route with
                                      curated enrichment (curated WINS on conflict)
  * compute_lottery_cumulative(f)  -> cumulative selection probability over N cycles
  * list_country_visas(country)    -> all curated VisaFacts for a destination
  * is_loaded(name)                -> health-check for loaded curated data files

Design rules (CLAUDE.md / plan.md):
  - These are HARD facts; never look them up via an LLM.
  - The AI route identifies WHICH visa applies + confidence; the curated JSON owns
    the hard numbers. On conflict the curated value wins — the AI never states a
    hard fact as authoritative (validated separately).
  - Unknown slug / 7th country degrades gracefully (is_modeled=False, curated
    fields None) instead of fabricating.
"""

from __future__ import annotations

import json
from pathlib import Path

from backend.models.fact_models import VisaFact, VisaRouteResolved

_DATA_DIR = Path(__file__).resolve().parents[1] / "data"

# Curated files this layer can report on for the health endpoint. Only
# visa_rules is required by these functions; the others are loaded best-effort so
# /api/health can report their presence without a separate module.
_DATA_FILES: dict[str, str] = {
    "visa_rules": "visa_rules.json",
    "source_registry": "official_source_registry.json",
    "tax_rates": "tax_rates.json",
}


def _load(filename: str) -> dict:
    path = _DATA_DIR / filename
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_load(filename: str) -> tuple[dict, bool]:
    try:
        return _load(filename), True
    except Exception:
        return {}, False


# Loaded once at import. _LOADED records success/failure for is_loaded().
_VISA_RULES: dict[str, dict] = {}
_LOADED: dict[str, bool] = {}
for _key, _fname in _DATA_FILES.items():
    _data, _ok = _safe_load(_fname)
    _LOADED[_key] = _ok
    if _key == "visa_rules":
        _VISA_RULES = _data

DEFAULT_LOTTERY_CYCLES = 3


def is_loaded(name: str) -> bool:
    """True if the named curated data file loaded at import.

    `name` is one of: "visa_rules", "source_registry", "tax_rates".
    """
    return _LOADED.get(name, False)


def _rule_to_fact(slug: str, rule: dict) -> VisaFact:
    """Build a fully-populated, modeled VisaFact from one curated rule entry.

    routing_confidence defaults to "high" (curated baseline); merge_visa_facts()
    overwrites it with the AI route's confidence when a route is present.
    """
    fact = VisaFact(
        country=rule["country"],
        visa_slug=slug,
        visa_name=rule["visa_name"],
        routing_confidence="high",
        min_salary=rule.get("min_salary"),
        currency=rule.get("currency"),
        employer_sponsorship_required=rule.get("employer_sponsorship_required"),
        can_switch_employer=rule.get("can_switch_employer"),
        switch_conditions=rule.get("switch_conditions"),
        path_to_pr_years=rule.get("path_to_pr_years"),
        lottery_required=rule.get("lottery_required", False),
        lottery_annual_rate=rule.get("lottery_annual_rate"),
        lottery_history=rule.get("lottery_history", []),
        partner_work_rights=rule.get("partner_work_rights"),
        partner_work_notes=rule.get("partner_work_notes"),
        is_modeled=True,
        source_url=rule.get("source_url"),
        last_verified=rule.get("last_verified"),
    )
    fact.lottery_cumulative_3yr = compute_lottery_cumulative(fact)
    return fact


def get_visa_rule(slug: str) -> VisaFact | None:
    """Curated VisaFact for `slug` (e.g. "us_h1b"), or None if not modeled."""
    rule = _VISA_RULES.get(slug)
    if rule is None:
        return None
    return _rule_to_fact(slug, rule)


def list_country_visas(country: str) -> list[VisaFact]:
    """All curated VisaFacts whose country matches `country` (case-insensitive).

    Empty list for an unmodeled country — the router turns that into
    {"modeled": False}.
    """
    target = country.strip().lower()
    return [
        _rule_to_fact(slug, rule)
        for slug, rule in _VISA_RULES.items()
        if rule.get("country", "").strip().lower() == target
    ]


def merge_visa_facts(route: VisaRouteResolved, curated: VisaFact | None) -> VisaFact:
    """Merge the AI-resolved route with curated enrichment into one VisaFact.

    Conflict policy: curated (dated, cited) WINS on every hard fact; the AI route
    supplies routing identity, confidence, and the soft narrative fields. When
    `curated` is None (unknown slug / 7th country) the result is flagged
    is_modeled=False with hard fields left None — only the AI route is reflected,
    so the dashboard can show "not yet modeled" without fabricating.

    Note: VisaRouteResolved carries no country; for the modeled path country comes
    from the curated rule. On the unmodeled path country is left "" — fact_assembly
    already knows the destination and should stamp it.
    """
    if curated is not None:
        # Curated hard facts retained; AI supplies routing identity + narrative.
        return VisaFact(
            country=curated.country,
            visa_slug=route.visa_slug or curated.visa_slug,
            visa_name=route.visa_name or curated.visa_name,
            routing_confidence=route.routing_confidence,
            eligibility_summary=route.eligibility_summary,
            key_constraint=route.key_constraint,
            min_salary=curated.min_salary,
            currency=curated.currency,
            employer_sponsorship_required=curated.employer_sponsorship_required,
            can_switch_employer=curated.can_switch_employer,
            switch_conditions=curated.switch_conditions,
            path_to_pr_years=curated.path_to_pr_years,
            lottery_required=curated.lottery_required,
            lottery_annual_rate=curated.lottery_annual_rate,
            lottery_history=curated.lottery_history,
            lottery_cumulative_3yr=curated.lottery_cumulative_3yr,
            partner_work_rights=curated.partner_work_rights,
            partner_work_notes=curated.partner_work_notes,
            is_modeled=True,
            source_url=curated.source_url,
            last_verified=curated.last_verified,
        )

    # Unmodeled: only AI route fields, hard facts stay None.
    return VisaFact(
        country="",
        visa_slug=route.visa_slug,
        visa_name=route.visa_name,
        routing_confidence=route.routing_confidence,
        eligibility_summary=route.eligibility_summary,
        key_constraint=route.key_constraint,
        employer_sponsorship_required=route.employer_sponsorship_required,
        path_to_pr_years=route.path_to_residency_years,
        is_modeled=False,
        source_url=route.source_url,
    )


def compute_lottery_cumulative(
    visa_fact: VisaFact, cycles: int = DEFAULT_LOTTERY_CYCLES
) -> float | None:
    """Cumulative selection probability across `cycles` annual lottery attempts.

    P(selected at least once) = 1 - (1 - r)**cycles, where r is the per-cycle
    selection rate. Returns None when the visa has no lottery (e.g. UK Skilled
    Worker). Feeds the sacrifice-diff stability formula and
    lottery_risk = 1 - lottery_cumulative_3yr.

    Rate source: lottery_annual_rate; if absent, the mean of lottery_history
    rates. None if neither is usable or cycles < 1.
    """
    if not visa_fact.lottery_required or cycles < 1:
        return None

    rate = visa_fact.lottery_annual_rate
    if rate is None:
        history_rates = [
            h["rate"] for h in visa_fact.lottery_history if h.get("rate") is not None
        ]
        if not history_rates:
            return None
        rate = sum(history_rates) / len(history_rates)

    rate = min(max(rate, 0.0), 1.0)
    cumulative = 1.0 - (1.0 - rate) ** cycles
    return round(min(max(cumulative, 0.0), 1.0), 4)
