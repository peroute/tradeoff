"""Stage 3 reasoning_step — single-call refactor + scenario_type plumbing.

All offline: validate_output is pure stdlib+pydantic and never calls a model.
Tests that exercise generate_insights inject a fake google.genai SDK (via
fake_genai fixture) so the stamping path runs without the real SDK or API key.
"""

import sys
import types as pytypes

import pytest

from backend.models.ai_models import SafeFallback, ScenarioType, WhatIfInsight
from backend.pipeline import reasoning_step
from backend.pipeline.reasoning_step import (
    VALID_SCENARIO_TYPES,
    ValidationResult,
    _contingency_scenarios,
    _slot_plan,
    generate_insights,
    to_insight,
    validate_output,
)
from backend.pipeline.sample_payload import _bundle_a, _bundle_b

# Granular risk types the two "contingency" slots may resolve to.
_RISK_TYPES = {"lottery_risk", "extension_risk", "employer_switch", "partner_work", "pr_timeline"}

# Fact bundle keyed bundle_a/bundle_b so fact_a/fact_b match the real convention
# (mirrors backend/pipeline/sample_payload.py).
FACT_BUNDLE = {
    "bundle_a": {
        "net_annual_usd": 97364.0,
        "visa_route": {"path_to_residency_years": 6},
    },
    "bundle_b": {
        "net_annual_usd": 56500.0,
        "visa_route": {"path_to_residency_years": 4},
    },
}

USER_CONTEXT = "I care about long-term residency stability for my family"


def _valid_output(**overrides):
    """A well-formed comparative Stage 3 output that clears every validator rule.

    Cites a fact from BOTH bundles, so it passes the default ``("a", "b")``
    coverage demand as well as the single-side base demands.
    """
    out = {
        "scenario_type": "pr_timeline",
        "fact_a": "bundle_a.visa_route.path_to_residency_years",
        "fact_b": "bundle_b.visa_route.path_to_residency_years",
        "context_used": "long-term residency stability",
        "tradeoff": (
            "The longer residency timeline in country A trades years of stability "
            "away against country B"
        ),
        "likely_outcome": "You most likely reach residency status later on the longer path",
        "consideration": (
            "The six-year residency path delays family settlement more than the "
            "nominal figure suggests"
        ),
        "confidence": "high",
        "confidence_basis": "PR timeline is a curated fact",
        "next_action": "Verify the residency timeline with the official source",
    }
    out.update(overrides)
    return out


def test_valid_scenario_types_match_model():
    """The validator's allowed set is derived from the model — single source."""
    assert VALID_SCENARIO_TYPES == frozenset(
        ScenarioType.__args__  # type: ignore[attr-defined]
    )
    assert "contingency" not in VALID_SCENARIO_TYPES  # the value that 500'd


def test_validate_output_passes_with_valid_scenario_type():
    result = validate_output(_valid_output(), FACT_BUNDLE, USER_CONTEXT)
    assert result.passed, result.failures


def test_passing_output_constructs_a_whatifinsight():
    """Keystone: a passing result can build the real model — the bug is closed."""
    result = validate_output(_valid_output(), FACT_BUNDLE, USER_CONTEXT)
    assert result.passed
    insight = WhatIfInsight(**result.output)
    assert insight.scenario_type == "pr_timeline"
    assert insight.type == "insight"


def test_base_slot_single_country_passes():
    """A base slot only needs its one side; the empty side normalizes to None."""
    out = _valid_output(scenario_type="base", fact_b="")
    result = validate_output(out, FACT_BUNDLE, USER_CONTEXT, required_sides=("a",))
    assert result.passed, result.failures
    assert result.output["fact_a"] == "bundle_a.visa_route.path_to_residency_years"
    assert result.output["fact_b"] is None


def test_comparative_slot_requires_both_facts():
    """A comparative slot missing fact_b is withheld — coverage is enforced."""
    out = _valid_output(fact_b="")
    result = validate_output(out, FACT_BUNDLE, USER_CONTEXT, required_sides=("a", "b"))
    assert not result.passed
    assert any("fact_b is required" in f for f in result.failures)


def test_fact_a_wrong_namespace_is_rejected():
    """A fact_a that points into bundle_b is not a valid country-A fact."""
    out = _valid_output(fact_a="bundle_b.visa_route.path_to_residency_years")
    result = validate_output(out, FACT_BUNDLE, USER_CONTEXT, required_sides=("a", "b"))
    assert not result.passed
    assert any("bundle_a.* key" in f for f in result.failures)


def test_tradeoff_must_share_vocab_with_both_facts():
    """tradeoff that ignores the facts' vocabulary fails the grounding rule."""
    out = _valid_output(tradeoff="generic statement about your situation overall here")
    result = validate_output(out, FACT_BUNDLE, USER_CONTEXT, required_sides=("a", "b"))
    assert not result.passed
    assert any("tradeoff shares no vocabulary" in f for f in result.failures)


def test_validate_output_rejects_invalid_scenario_type():
    """'contingency' — the exact value that caused the /api/compare 500."""
    result = validate_output(
        _valid_output(scenario_type="contingency"), FACT_BUNDLE, USER_CONTEXT
    )
    assert not result.passed
    assert any("scenario_type" in f for f in result.failures)
    assert result.output["is_fallback"] is True


def test_validate_output_rejects_missing_scenario_type():
    out = _valid_output()
    del out["scenario_type"]
    result = validate_output(out, FACT_BUNDLE, USER_CONTEXT)
    assert not result.passed
    assert any("scenario_type" in f for f in result.failures)


@pytest.fixture
def fake_genai(monkeypatch):
    """Inject a minimal google.genai SDK so generate_insights runs offline.

    Returns a setter: call with the list of 7 dicts the fake model should return.
    """
    holder: dict = {}

    class _FakeResp:
        def __init__(self, parsed):
            self.parsed = parsed

    class _FakeModels:
        def generate_content(self, **kwargs):
            return _FakeResp(holder["parsed"])

    class _FakeClient:
        def __init__(self, **kwargs):
            self.models = _FakeModels()

    genai_mod = pytypes.ModuleType("google.genai")
    genai_mod.Client = _FakeClient
    types_mod = pytypes.ModuleType("google.genai.types")
    types_mod.GenerateContentConfig = lambda **kw: None
    genai_mod.types = types_mod

    monkeypatch.setitem(sys.modules, "google.genai", genai_mod)
    monkeypatch.setitem(sys.modules, "google.genai.types", types_mod)

    def _set(parsed):
        holder["parsed"] = parsed

    return _set


def test_generate_insights_stamps_scenario_type(fake_genai):
    """Caller stamps scenario_type — model omitting it still yields the right type."""
    plan = _slot_plan(BUNDLE_A, BUNDLE_B)
    # Model returns items without scenario_type; stamping must supply it.
    items = []
    for _ in plan:
        item = _valid_output()
        del item["scenario_type"]
        items.append(item)
    fake_genai(items)

    insights = generate_insights(BUNDLE_A, BUNDLE_B, USER_CONTEXT)

    assert len(insights) == 7
    for i, item in enumerate(insights):
        if isinstance(item, WhatIfInsight):
            assert item.scenario_type == plan[i]


def test_generate_insights_overrides_model_scenario_type(fake_genai):
    """A bad scenario_type from the model can't survive — caller's slot value wins."""
    plan = _slot_plan(BUNDLE_A, BUNDLE_B)
    # Model returns "contingency" for every slot (invalid); stamping must replace it.
    fake_genai([_valid_output(scenario_type="contingency") for _ in plan])

    insights = generate_insights(BUNDLE_A, BUNDLE_B, USER_CONTEXT)

    assert len(insights) == 7
    for i, item in enumerate(insights):
        if isinstance(item, WhatIfInsight):
            assert item.scenario_type == plan[i]


# ---------------------------------------------------------------------------
# 1->7 expansion + typed-union mapping (issue #38)
# ---------------------------------------------------------------------------

# Sample comparison: US H-1B (lottery + restricted partner) vs Germany Blue Card
# (no lottery, full partner). Reused across the expansion tests.
BUNDLE_A = _bundle_a("US")
BUNDLE_B = _bundle_b("Germany")


def test_contingency_scenarios_pick_relevant_risks():
    """US lottery + restricted partner → lottery_risk and partner_work lead."""
    chosen = _contingency_scenarios(BUNDLE_A, BUNDLE_B)
    assert chosen == ["lottery_risk", "partner_work"]


def test_contingency_scenarios_pad_to_two_when_no_signals():
    """A bundle with no curated risk signals still yields two distinct types."""
    neutered = BUNDLE_B.model_copy(
        update={
            "visa_enrichment": None,
            "visa_route": BUNDLE_B.visa_route.model_copy(
                update={"path_to_residency_years": None}
            ),
        }
    )
    chosen = _contingency_scenarios(neutered, neutered)
    assert len(chosen) == 2
    assert len(set(chosen)) == 2
    assert set(chosen) <= _RISK_TYPES


def test_slot_plan_composition():
    """7 slots: 2 base, 2 contingency (granular), 2 priority_match, 1 synthesis."""
    plan = _slot_plan(BUNDLE_A, BUNDLE_B)
    assert len(plan) == 7
    assert plan.count("base") == 2
    assert plan.count("priority_match") == 2
    assert plan.count("synthesis") == 1
    assert plan[2] in _RISK_TYPES and plan[3] in _RISK_TYPES
    assert plan[2] != plan[3]


def test_to_insight_maps_passed_to_whatifinsight():
    result = ValidationResult(True, [], _valid_output())
    insight = to_insight(result, 0)
    assert isinstance(insight, WhatIfInsight)
    assert insight.type == "insight"
    assert insight.scenario_type == "pr_timeline"


def test_to_insight_maps_failure_to_safefallback():
    result = ValidationResult(False, ["fact_a bad", "tradeoff thin"], {})
    fallback = to_insight(result, 3)
    assert isinstance(fallback, SafeFallback)
    assert fallback.type == "safe_fallback"
    assert fallback.slot_index == 3
    assert "fact_a bad" in fallback.reason


def test_generate_insights_returns_seven_typed_union(fake_genai):
    """Single Gemini call end-to-end: synthesis slot fails validation → SafeFallback."""
    plan = _slot_plan(BUNDLE_A, BUNDLE_B)
    # Slot 6 (synthesis) has a fact_a not in the real bundle → validation fails.
    items = []
    for i, _ in enumerate(plan):
        if i == 6:
            items.append(_valid_output(fact_a="bundle_a.nonexistent.key"))
        else:
            items.append(_valid_output())
    fake_genai(items)

    insights = generate_insights(BUNDLE_A, BUNDLE_B, USER_CONTEXT)

    assert len(insights) == 7
    assert sum(isinstance(i, WhatIfInsight) for i in insights) == 6
    fallbacks = [i for i in insights if isinstance(i, SafeFallback)]
    assert len(fallbacks) == 1
    assert fallbacks[0].slot_index == 6  # synthesis is the last slot
    # Each WhatIfInsight carries the scenario_type its slot demanded.
    for i, item in enumerate(insights):
        if isinstance(item, WhatIfInsight):
            assert item.scenario_type == plan[i]
    # Every element serializes with its discriminator.
    for item in insights:
        assert item.model_dump()["type"] in {"insight", "safe_fallback"}
