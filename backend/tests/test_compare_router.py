"""Tests for the stubbed POST /api/compare endpoint.

Offline: the endpoint returns a hardcoded payload, no data-source or LLM calls.
Exercises both the builder directly and the live FastAPI route via TestClient.
"""

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.models.ai_models import SafeFallback, WhatIfInsight
from backend.models.intake_models import CompareRequest
from backend.models.output_models import DashboardPayload
from backend.pipeline.sample_payload import STUB_NOTE, build_sample_payload

client = TestClient(app)


def _request(**kw) -> CompareRequest:
    base = dict(
        citizenship="India",
        degree_field="Computer Science",
        career_stage="new_grad",
        country_a="US",
        country_b="Germany",
        user_context="I care most about long-term residency stability.",
    )
    base.update(kw)
    return CompareRequest(**base)


def _valid_body() -> dict:
    return _request().model_dump()


def test_builder_returns_valid_payload():
    payload = build_sample_payload(_request())
    assert isinstance(payload, DashboardPayload)


def test_post_compare_returns_200_and_valid_schema():
    resp = client.post("/api/compare", json=_valid_body())
    assert resp.status_code == 200
    # Re-validates the JSON against the full schema.
    DashboardPayload.model_validate(resp.json())


def test_countries_echoed_from_request():
    payload = build_sample_payload(_request(country_a="Canada", country_b="France"))
    assert payload.bundle_a.country == "Canada"
    assert payload.bundle_b.country == "France"
    assert payload.sacrifice_map.net_takehome_ppp.dimension == "net_takehome_ppp"


def test_insight_structure_invariants():
    payload = build_sample_payload(_request())
    assert len(payload.insights) == 7
    fallbacks = [i for i in payload.insights if isinstance(i, SafeFallback)]
    insights = [i for i in payload.insights if isinstance(i, WhatIfInsight)]
    assert len(fallbacks) == 1
    assert len(insights) == 6


def test_sacrifice_map_has_all_five_dimensions():
    payload = build_sample_payload(_request())
    sm = payload.sacrifice_map
    for dim in (
        sm.net_takehome_ppp,
        sm.visa_stability_score,
        sm.pr_timeline_years,
        sm.lottery_risk,
        sm.partner_opportunity,
    ):
        assert dim.winner in ("a", "b", "tie")


def test_pipeline_meta_counts_self_consistent():
    payload = build_sample_payload(_request())
    meta = payload.pipeline_meta
    assert meta.insights_passed + meta.insights_withheld == len(payload.insights)
    assert meta.insights_passed == 6
    assert meta.insights_withheld == 1


def test_payload_self_labeled_as_stub():
    payload = build_sample_payload(_request())
    assert payload.pipeline_meta.fact_sources["note"] == STUB_NOTE


def test_net_takehome_ppp_is_internally_consistent():
    payload = build_sample_payload(_request())
    for bundle in (payload.bundle_a, payload.bundle_b):
        expected = bundle.tax.net_annual_local / (bundle.col.col_index / 100)
        assert bundle.net_takehome_ppp == pytest.approx(expected)


def test_unsupported_country_rejected_422():
    body = _valid_body()
    body["country_a"] = "Brazil"  # not in SupportedCountry
    resp = client.post("/api/compare", json=body)
    assert resp.status_code == 422


def test_missing_field_rejected_422():
    body = _valid_body()
    del body["user_context"]
    resp = client.post("/api/compare", json=body)
    assert resp.status_code == 422
