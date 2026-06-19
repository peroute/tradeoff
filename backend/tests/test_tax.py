"""Tests for compute_net_takehome() over the curated tax_rates.json.

Fully offline — pure computation over JSON loaded at import, no mocking. Worked
examples below are hand-computed from the brackets in
backend/data/tax_rates.json (marginal, min-inclusive / max-exclusive).
"""

import pytest

from backend.data_sources import tax
from backend.models.fact_models import TaxBreakdown


def test_germany_worked_example():
    # 0-11604 @0; 11604-17006 @0.14 = 756.28; 17006-60000 @0.24 = 10318.56
    # social: 60000 * 0.2005 = 12030
    t = tax.compute_net_takehome(60000, "Germany")
    assert isinstance(t, TaxBreakdown)
    assert t.currency == "EUR"
    assert t.income_tax == pytest.approx(11074.84, abs=1e-2)
    assert t.social_contributions == pytest.approx(12030.0, abs=1e-2)
    assert t.net_annual == pytest.approx(36895.16, abs=1e-2)
    assert t.effective_rate == pytest.approx(0.3851, abs=1e-4)


def test_us_social_is_ss_plus_medicare():
    # income tax: 1160 + 4266 + 11627 = 17053; social: 0.0765 * 100000 = 7650
    t = tax.compute_net_takehome(100000, "US")
    assert t.income_tax == pytest.approx(17053.0, abs=1e-2)
    assert t.social_contributions == pytest.approx(7650.0, abs=1e-2)
    assert t.net_annual == pytest.approx(75297.0, abs=1e-2)


def test_uk_ni_threshold_applies():
    # gross above threshold: NI = (60000 - 12570) * 0.08 = 3794.4
    t = tax.compute_net_takehome(60000, "UK")
    assert t.social_contributions == pytest.approx(3794.4, abs=1e-2)
    assert t.income_tax == pytest.approx(11432.0, abs=1e-2)


def test_uk_below_ni_threshold_and_below_first_band():
    # £10k is under both the NI threshold (12570) and the first taxable band.
    t = tax.compute_net_takehome(10000, "UK")
    assert t.income_tax == pytest.approx(0.0, abs=1e-9)
    assert t.social_contributions == pytest.approx(0.0, abs=1e-9)
    assert t.net_annual == pytest.approx(10000.0, abs=1e-9)


def test_canada_cpp_is_capped():
    # CPP caps at cpp_max_earnings (68500): 68500 * 0.0595 = 4075.75, not on 100k
    t = tax.compute_net_takehome(100000, "Canada")
    assert t.social_contributions == pytest.approx(4075.75, abs=1e-2)
    assert t.income_tax == pytest.approx(17427.315, abs=1e-2)


def test_australia_medicare_levy():
    # levy: 80000 * 0.02 = 1600; income tax = 5092 + 11375 = 16467
    t = tax.compute_net_takehome(80000, "Australia")
    assert t.social_contributions == pytest.approx(1600.0, abs=1e-2)
    assert t.income_tax == pytest.approx(16467.0, abs=1e-2)


def test_france_combined_social_rate():
    # social: 50000 * 0.22 = 11000; income tax = 1925.33 + 6360.9 = 8286.23
    t = tax.compute_net_takehome(50000, "France")
    assert t.social_contributions == pytest.approx(11000.0, abs=1e-2)
    assert t.income_tax == pytest.approx(8286.23, abs=1e-2)


def test_progressive_not_flat_top_rate():
    # Germany €60k sits in the 24% band but must NOT be taxed 24% on the whole
    # amount — only the slice above 17006 is at 24%.
    t = tax.compute_net_takehome(60000, "Germany")
    assert t.income_tax < 60000 * 0.24


def test_income_below_first_taxable_band_is_zero_tax():
    # Germany first taxable band starts at 11604; €10k yields 0 income tax.
    t = tax.compute_net_takehome(10000, "Germany")
    assert t.income_tax == pytest.approx(0.0, abs=1e-9)


def test_identities_hold():
    t = tax.compute_net_takehome(75000, "US")
    assert t.total_deductions == pytest.approx(
        t.income_tax + t.social_contributions, abs=1e-9
    )
    assert t.net_annual == pytest.approx(t.gross_annual - t.total_deductions, abs=1e-9)
    assert t.effective_rate == pytest.approx(
        t.total_deductions / t.gross_annual, abs=1e-9
    )


def test_country_match_is_case_insensitive():
    assert tax.compute_net_takehome(60000, "germany") is not None
    assert tax.compute_net_takehome(60000, "  France  ") is not None


def test_unmodeled_country_returns_none():
    assert tax.compute_net_takehome(60000, "Brazil") is None


def test_zero_gross_is_zeroed_no_division_error():
    t = tax.compute_net_takehome(0, "US")
    assert t is not None
    assert t.income_tax == 0.0
    assert t.social_contributions == 0.0
    assert t.net_annual == 0.0
    assert t.effective_rate == 0.0


def test_negative_gross_is_zeroed():
    t = tax.compute_net_takehome(-5000, "France")
    assert t is not None
    assert t.total_deductions == 0.0
    assert t.net_annual == -5000
    assert t.effective_rate == 0.0


def test_provenance_copied_from_table():
    t = tax.compute_net_takehome(60000, "US")
    assert t.source_url and t.source_url.startswith("https://")
    assert t.last_verified == "2026-05-01"
    assert t.note and "state" in t.note.lower()
