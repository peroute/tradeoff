"""Stage 3 reasoning_step — scenario_type plumbing (issue #36).

All offline: validate_output is pure stdlib+pydantic and never calls a model.
The generate_reasoning test injects a fake google.genai SDK so the stamping
path runs without the real SDK or an API key.
"""

import sys
import types as pytypes

import pytest

from backend.models.ai_models import ScenarioType, WhatIfInsight
from backend.pipeline.reasoning_step import (
    VALID_SCENARIO_TYPES,
    generate_reasoning,
    validate_output,
)

# Fact bundle keyed bundle_a/bundle_b so fact_used matches the real convention
# (mirrors backend/pipeline/sample_payload.py).
FACT_BUNDLE = {
    "bundle_a": {
        "net_takehome_ppp": 97364.0,
        "visa_route": {"path_to_residency_years": 6},
    },
    "bundle_b": {
        "net_takehome_ppp": 56500.0,
        "visa_route": {"path_to_residency_years": 4},
    },
}

USER_CONTEXT = "I care about long-term residency stability for my family"


def _valid_output(**overrides):
    """A well-formed Stage 3 output that clears every validator rule."""
    out = {
        "scenario_type": "pr_timeline",
        "fact_used": "bundle_a.visa_route.path_to_residency_years",
        "context_used": "long-term residency stability",
        "connection": "residency timeline shapes long-term stability",
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
    """Inject a minimal google.genai SDK so generate_reasoning runs offline.

    Returns a setter: call with the dict the fake 'model' should return.
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


def test_generate_reasoning_stamps_scenario_type(fake_genai):
    """The caller owns scenario_type — it's stamped even if the model omits it."""
    model_out = _valid_output()
    del model_out["scenario_type"]  # model returns nothing for it
    fake_genai(model_out)

    result = generate_reasoning(FACT_BUNDLE, USER_CONTEXT, scenario_type="base")
    assert result.passed, result.failures
    assert result.output["scenario_type"] == "base"


def test_generate_reasoning_overrides_model_scenario_type(fake_genai):
    """A bad value from the model can't survive — caller's value wins."""
    fake_genai(_valid_output(scenario_type="contingency"))

    result = generate_reasoning(FACT_BUNDLE, USER_CONTEXT, scenario_type="synthesis")
    assert result.passed, result.failures
    assert result.output["scenario_type"] == "synthesis"
