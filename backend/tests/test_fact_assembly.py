"""Tests for Stage 2a fact assembly.

Offline: the only networked dependencies are the wage clients
(oecd/bls.fetch_*), which we monkeypatch to return canned WageData. Numbeo is
mock (no network) and tax is pure, so both run for real here.
"""

import pytest

from backend.data_sources import bls, oecd, tax, wherenext, worldbank
from backend.models.ai_models import VisaRoute
from backend.models.fact_models import CostData
from backend.models.fact_models import WageData as SourceWageData
from backend.models.intake_models import ParsedProfile
from backend.models.output_models import CountryBundle
from backend.pipeline import fact_assembly


def _col(index=80.0, source="World Bank", is_fallback=False, monthly=None) -> CostData:
    return CostData(
        city="X", country="X", currency="USD",
        cost_of_living_index=index, monthly_cost_usd=monthly,
        source=source, is_mock=False, is_fallback=is_fallback,
    )


@pytest.fixture(autouse=True)
def _stub_worldbank(monkeypatch):
    """Keep assemble() offline+deterministic: World Bank resolves to a fixed
    live index unless a test overrides it. Mirrors the wage clients' stubbing."""
    monkeypatch.setattr(worldbank, "fetch_national_col", lambda c: _col())


def _profile(**kw) -> ParsedProfile:
    base = dict(
        citizenship="India",
        degree_field="Computer Science",
        career_stage="new_grad",
        country_a="US",
        country_b="Germany",
        user_context="I care most about long-term residency stability.",
    )
    base.update(kw)
    return ParsedProfile(**base)


def _stub_route(slug="us_h1b") -> VisaRoute:
    """The injected Stage-2b output (stubbed until Stage 2b is wired)."""
    return VisaRoute(
        visa_slug=slug,
        visa_name="AI-resolved name",
        eligibility_summary="You likely qualify.",
        employer_sponsorship_required=True,
        path_to_residency_years=6,
        key_constraint="Subject to annual cap.",
        routing_confidence="medium",
        source_url="https://example.gov/route",
        source_retrieved="2026-06-19",
    )


def _bls_wage(soc_code="15-1252", gross=132270.0) -> SourceWageData:
    return SourceWageData(
        country="US", currency="USD", gross_annual=gross, granularity="occupation",
        soc_code=soc_code, reference_period="2023", source="BLS", is_fallback=False,
    )


def _oecd_wage(country="Germany", currency="EUR", gross=54000.0) -> SourceWageData:
    return SourceWageData(
        country=country, currency=currency, gross_annual=gross,
        granularity="national_average", reference_period="2023", source="OECD",
        is_fallback=False,
    )


def test_us_known_field_uses_bls(monkeypatch):
    seen = {}

    def fake_bls(soc_code):
        seen["soc"] = soc_code
        return _bls_wage(soc_code=soc_code)

    monkeypatch.setattr(bls, "fetch_bls_wages", fake_bls)

    bundle = fact_assembly.assemble(_profile(degree_field="Computer Science"), "US", _stub_route())
    assert isinstance(bundle, CountryBundle)
    assert seen["soc"] == "15-1252"           # mapped from degree field
    assert bundle.wage.source == "BLS"
    assert bundle.wage.soc_code == "15-1252"
    assert "SOC" in bundle.wage.precision_note


def test_non_us_uses_oecd(monkeypatch):
    monkeypatch.setattr(oecd, "fetch_oecd_wages", lambda c: _oecd_wage(country=c))

    bundle = fact_assembly.assemble(_profile(), "Germany", _stub_route())
    assert bundle.wage.source == "OECD"
    assert bundle.wage.soc_code is None
    assert "National-average" in bundle.wage.precision_note


def test_us_unknown_field_falls_back_to_oecd(monkeypatch):
    called = {"bls": False}
    monkeypatch.setattr(bls, "fetch_bls_wages", lambda s: called.__setitem__("bls", True))
    monkeypatch.setattr(oecd, "fetch_oecd_wages", lambda c: _oecd_wage(country="US", currency="USD"))

    bundle = fact_assembly.assemble(_profile(degree_field="Underwater Basketweaving"), "US", _stub_route())
    assert called["bls"] is False             # no fabricated SOC, no BLS call
    assert bundle.wage.source == "OECD"
    assert bundle.wage.soc_code is None


def test_net_takehome_ppp_matches_formula(monkeypatch):
    monkeypatch.setattr(oecd, "fetch_oecd_wages", lambda c: _oecd_wage(country="Germany", gross=54000.0))
    monkeypatch.setattr(worldbank, "fetch_national_col", lambda c: _col(index=75.9))

    bundle = fact_assembly.assemble(_profile(), "Germany", _stub_route("zz_unknown"))
    expected_net = tax.compute_net_takehome(54000.0, "Germany").net_annual
    assert bundle.col.col_index == pytest.approx(75.9)
    assert bundle.net_takehome_ppp == pytest.approx(expected_net / (75.9 / 100))


def test_tax_mapping_matches_compute(monkeypatch):
    monkeypatch.setattr(oecd, "fetch_oecd_wages", lambda c: _oecd_wage(country="France", currency="EUR", gross=50000.0))

    bundle = fact_assembly.assemble(_profile(), "France", _stub_route("zz_unknown"))
    tb = tax.compute_net_takehome(50000.0, "France")
    assert bundle.tax.effective_rate == pytest.approx(tb.effective_rate)
    assert bundle.tax.net_annual_local == pytest.approx(tb.net_annual)


def test_col_primary_uses_world_bank(monkeypatch):
    monkeypatch.setattr(oecd, "fetch_oecd_wages", lambda c: _oecd_wage(country="Canada", currency="CAD"))
    monkeypatch.setattr(worldbank, "fetch_national_col", lambda c: _col(index=90.6))

    bundle = fact_assembly.assemble(_profile(), "Canada", _stub_route("zz_unknown"))
    assert bundle.col.city is None                       # national figure, not city-specific
    assert bundle.col.col_index == pytest.approx(90.6)
    assert bundle.col.source == "World Bank"
    assert bundle.col.col_source == "national_ppp"
    assert bundle.col.is_fallback is False


def test_col_falls_back_to_wherenext_when_world_bank_unavailable(monkeypatch):
    monkeypatch.setattr(oecd, "fetch_oecd_wages", lambda c: _oecd_wage(country="Germany"))
    monkeypatch.setattr(worldbank, "fetch_national_col", lambda c: _col(index=99, source="World Bank (fallback)", is_fallback=True))
    monkeypatch.setattr(wherenext, "fetch_national_col", lambda c: _col(index=82.9, source=wherenext.SOURCE_LABEL, monthly=2500.0))

    bundle = fact_assembly.assemble(_profile(), "Germany", _stub_route("zz_unknown"))
    assert bundle.col.col_index == pytest.approx(82.9)
    assert "WhereNext" in bundle.col.source
    assert bundle.col.monthly_cost_usd == pytest.approx(2500.0)
    assert bundle.col.col_source == "national_ppp"
    assert bundle.col.is_fallback is False               # WhereNext is a live source


def test_col_curated_fallback_when_both_live_sources_fail(monkeypatch):
    monkeypatch.setattr(oecd, "fetch_oecd_wages", lambda c: _oecd_wage(country="Canada", currency="CAD"))
    monkeypatch.setattr(worldbank, "fetch_national_col", lambda c: _col(source="World Bank (fallback)", is_fallback=True))
    monkeypatch.setattr(wherenext, "fetch_national_col", lambda c: _col(source="WhereNext (fallback)", is_fallback=True))

    bundle = fact_assembly.assemble(_profile(), "Canada", _stub_route("zz_unknown"))
    assert bundle.col.is_fallback is True
    assert bundle.col.source == "Curated (fallback)"
    assert bundle.col.col_index == pytest.approx(71.2)   # numbeo Toronto cpi, curated proxy
    assert bundle.col.col_source == "national_ppp"


def test_visa_enrichment_populated_for_modeled_slug(monkeypatch):
    monkeypatch.setattr(bls, "fetch_bls_wages", lambda s: _bls_wage(soc_code=s))

    bundle = fact_assembly.assemble(_profile(), "US", _stub_route("us_h1b"))
    assert bundle.visa_enrichment is not None
    assert bundle.visa_enrichment.min_salary == 60000
    assert bundle.visa_enrichment.curated_source_url


def test_visa_enrichment_none_for_unmodeled_slug(monkeypatch):
    monkeypatch.setattr(oecd, "fetch_oecd_wages", lambda c: _oecd_wage(country="Germany"))

    bundle = fact_assembly.assemble(_profile(), "Germany", _stub_route("zz_unknown"))
    assert bundle.visa_enrichment is None


def test_visa_route_passed_through(monkeypatch):
    monkeypatch.setattr(oecd, "fetch_oecd_wages", lambda c: _oecd_wage(country="UK", currency="GBP"))

    route = _stub_route("zz_unknown")
    bundle = fact_assembly.assemble(_profile(), "UK", route)
    assert bundle.visa_route is route


def test_fallback_wage_noted_in_precision_note(monkeypatch):
    fallback = SourceWageData(
        country="Germany", currency="EUR", gross_annual=54000.0,
        granularity="national_average", source="OECD (fallback)", is_fallback=True,
    )
    monkeypatch.setattr(oecd, "fetch_oecd_wages", lambda c: fallback)

    bundle = fact_assembly.assemble(_profile(), "Germany", _stub_route("zz_unknown"))
    assert bundle.wage.source == "OECD"               # suffix stripped for the Literal
    assert "fallback" in bundle.wage.precision_note.lower()
