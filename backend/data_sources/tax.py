"""Curated tax-rate data layer.

Loads data/tax_rates.json (manually researched, cited, dated) and exposes:

  * compute_net_takehome(gross, country) -> TaxBreakdown for one destination, or
                                            None if that country isn't modeled

Design rules (CLAUDE.md / plan.md):
  - Tax is a HARD fact; never look it up via an LLM. The figure is computed
    deterministically from the curated brackets, in the destination's own
    currency (the same currency WageData carries, by design).
  - A 7th country (not in tax_rates.json) degrades gracefully: compute returns
    None and fact_assembly flags tax as "not yet modeled" instead of fabricating.
  - tax_rates.json brackets are min-inclusive / max-exclusive, national-currency.
    Social-contribution fields differ per country (no universal structure); we
    dispatch on the distinctive field names already present in the table.
"""

from __future__ import annotations

import json
from pathlib import Path

from backend.models.fact_models import TaxBreakdown

_DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def _load(filename: str) -> dict:
    path = _DATA_DIR / filename
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_load(filename: str) -> tuple[dict, bool]:
    try:
        return _load(filename), True
    except Exception:
        return {}, False


# Loaded once at import. visa_rules.is_loaded("tax_rates") owns the health report;
# _LOADED here is only for this module's own guard.
_TAX_RATES, _LOADED = _safe_load("tax_rates.json")


def _income_tax(gross: float, brackets: list[dict]) -> float:
    """Progressive marginal income tax over `brackets` (min-incl, max-excl)."""
    return sum(
        max(0.0, min(gross, b["max"]) - b["min"]) * b["rate"] for b in brackets
    )


def _social_contributions(gross: float, table: dict) -> float:
    """Mandatory employee social contributions for one country's tax table.

    Dispatches on the distinctive field names tax_rates.json uses per country:
      - US: Social Security + Medicare, flat on gross (JSON models no SS wage-base
        cap; the table `note` discloses the approximation).
      - UK: National Insurance on earnings above national_insurance_threshold.
      - Canada: CPP on earnings up to cpp_max_earnings.
      - Australia: Medicare levy, flat on gross.
      - Germany / France: combined social_contributions_rate, flat on gross.
    A country carrying none of these keys yields 0.0.
    """
    if "social_security_rate" in table or "medicare_rate" in table:
        rate = table.get("social_security_rate", 0.0) + table.get("medicare_rate", 0.0)
        return gross * rate
    if "national_insurance_rate" in table:
        threshold = table.get("national_insurance_threshold", 0.0)
        return max(0.0, gross - threshold) * table["national_insurance_rate"]
    if "cpp_rate" in table:
        cap = table.get("cpp_max_earnings", gross)
        return min(gross, cap) * table["cpp_rate"]
    if "medicare_levy_rate" in table:
        return gross * table["medicare_levy_rate"]
    if "social_contributions_rate" in table:
        return gross * table["social_contributions_rate"]
    return 0.0


def _lookup(country: str) -> tuple[str, dict] | None:
    """Case-insensitive match of `country` against tax_rates.json keys."""
    target = country.strip().lower()
    for key, table in _TAX_RATES.items():
        if key.strip().lower() == target:
            return key, table
    return None


def compute_net_takehome(gross_annual: float, country: str) -> TaxBreakdown | None:
    """Net annual take-home for `gross_annual` in `country`, or None if unmodeled.

    `country` is matched case-insensitively against the 6 locked countries in
    tax_rates.json (US, UK, Canada, Australia, Germany, France); a miss returns
    None so the caller can degrade gracefully. Figures stay in the country's
    national currency. A non-positive gross returns a zeroed breakdown (net =
    gross, effective_rate 0.0) rather than dividing by zero.
    """
    match = _lookup(country)
    if match is None:
        return None
    key, table = match
    currency = table["currency"]

    if gross_annual <= 0:
        return TaxBreakdown(
            country=key,
            currency=currency,
            gross_annual=gross_annual,
            income_tax=0.0,
            social_contributions=0.0,
            total_deductions=0.0,
            net_annual=gross_annual,
            effective_rate=0.0,
            source_url=table.get("source_url"),
            last_verified=table.get("last_verified"),
            note=table.get("note"),
        )

    income_tax = _income_tax(gross_annual, table.get("brackets", []))
    social = _social_contributions(gross_annual, table)
    total = income_tax + social

    return TaxBreakdown(
        country=key,
        currency=currency,
        gross_annual=gross_annual,
        income_tax=income_tax,
        social_contributions=social,
        total_deductions=total,
        net_annual=gross_annual - total,
        effective_rate=total / gross_annual,
        source_url=table.get("source_url"),
        last_verified=table.get("last_verified"),
        note=table.get("note"),
    )
