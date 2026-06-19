import pytest

from backend.data_sources import visa_rules
from backend.models.fact_models import VisaFact, VisaRouteResolved


def _route(slug="us_h1b", **kw):
    base = dict(
        visa_slug=slug,
        visa_name="AI-resolved name",
        eligibility_summary="You likely qualify.",
        employer_sponsorship_required=True,
        path_to_residency_years=6,
        key_constraint="Subject to annual cap.",
        routing_confidence="medium",
        source_url="https://example.gov/route",
        source_retrieved="2026-06-18",
    )
    base.update(kw)
    return VisaRouteResolved(**base)


def test_get_visa_rule_modeled():
    f = visa_rules.get_visa_rule("us_h1b")
    assert isinstance(f, VisaFact)
    assert f.is_modeled is True
    assert f.country == "US"
    assert f.min_salary == 60000
    assert f.lottery_required is True
    assert f.lottery_cumulative_3yr == pytest.approx(0.3639, abs=1e-4)
    assert f.source_url and f.last_verified


def test_get_visa_rule_unknown_returns_none():
    assert visa_rules.get_visa_rule("does_not_exist") is None


def test_compute_lottery_cumulative_h1b():
    f = visa_rules.get_visa_rule("us_h1b")
    assert visa_rules.compute_lottery_cumulative(f) == pytest.approx(0.3639, abs=1e-4)


def test_compute_lottery_cumulative_single_cycle_is_annual_rate():
    f = visa_rules.get_visa_rule("us_h1b")
    assert visa_rules.compute_lottery_cumulative(f, cycles=1) == pytest.approx(0.14, abs=1e-4)


def test_compute_lottery_cumulative_none_when_no_lottery():
    f = visa_rules.get_visa_rule("uk_skilled_worker")
    assert f.lottery_required is False
    assert visa_rules.compute_lottery_cumulative(f) is None


def test_compute_lottery_cumulative_history_mean_fallback():
    # No annual rate, but history present -> mean of [0.2, 0.4] = 0.3
    f = VisaFact(
        country="X", visa_slug="x", visa_name="X", routing_confidence="low",
        lottery_required=True, lottery_annual_rate=None,
        lottery_history=[{"year": 2023, "rate": 0.2}, {"year": 2024, "rate": 0.4}],
    )
    expected = 1.0 - (1.0 - 0.3) ** 3
    assert visa_rules.compute_lottery_cumulative(f) == pytest.approx(round(expected, 4), abs=1e-4)


def test_merge_with_curated_keeps_hard_facts_takes_ai_routing():
    curated = visa_rules.get_visa_rule("us_h1b")
    merged = visa_rules.merge_visa_facts(_route("us_h1b", routing_confidence="low"), curated)
    assert merged.is_modeled is True
    # curated hard facts win
    assert merged.min_salary == 60000
    assert merged.can_switch_employer is True
    assert merged.lottery_cumulative_3yr == pytest.approx(0.3639, abs=1e-4)
    # AI route supplies routing + narrative
    assert merged.routing_confidence == "low"
    assert merged.eligibility_summary == "You likely qualify."
    assert merged.key_constraint == "Subject to annual cap."


def test_merge_without_curated_degrades_gracefully():
    merged = visa_rules.merge_visa_facts(_route("japan_engineer"), None)
    assert merged.is_modeled is False
    assert merged.visa_slug == "japan_engineer"
    assert merged.min_salary is None
    assert merged.lottery_required is False
    # AI route fields still present
    assert merged.employer_sponsorship_required is True
    assert merged.path_to_pr_years == 6
    assert merged.routing_confidence == "medium"


def test_list_country_visas():
    us = visa_rules.list_country_visas("US")
    assert us and all(f.country == "US" for f in us)
    assert visa_rules.list_country_visas("Japan") == []


def test_is_loaded():
    assert visa_rules.is_loaded("visa_rules") is True
    assert visa_rules.is_loaded("nonexistent") is False
