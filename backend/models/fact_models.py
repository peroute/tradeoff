from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, Field

# Still to implement (other tasks): CountryBundle, VisaFact, VisaRouteResolved


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class WageData(BaseModel):
    """Gross annual wage for one destination country.

    `currency` is ALWAYS the destination country's national currency so the
    figure can be fed straight into that country's tax brackets in
    tax_rates.json (which are also national-currency). Do not store USD-PPP
    here — that would break compute_net_takehome().

    `granularity` records the resolution gap the dashboard discloses via
    PrecisionCaveat: BLS gives US wages at occupation level; OECD gives every
    other country a single national average.
    """

    country: str
    currency: str
    gross_annual: float
    granularity: Literal["national_average", "occupation"]
    occupation: Optional[str] = None          # human label, occupation granularity only
    soc_code: Optional[str] = None            # BLS SOC, occupation granularity only
    reference_period: Optional[str] = None    # e.g. "2023"
    source: str                               # "OECD" | "BLS" | "OECD (fallback)" | "BLS (fallback)"
    source_url: Optional[str] = None
    is_fallback: bool = False                 # True when live API failed and curated value was used
    retrieved_at: str = Field(default_factory=_utc_now_iso)


class CostData(BaseModel):
    """City-level cost-of-living indices in Numbeo's schema (New York = 100 baseline).

    Field names mirror Numbeo's /api/indices payload so the mapping in
    numbeo.py is 1:1 with a real response.
    """

    city: str
    country: str
    currency: str
    cost_of_living_index: float               # Numbeo cpi_index (excludes rent)
    rent_index: Optional[float] = None
    cost_of_living_plus_rent_index: Optional[float] = None
    groceries_index: Optional[float] = None
    restaurant_price_index: Optional[float] = None
    local_purchasing_power_index: Optional[float] = None
    source: str                               # "Numbeo (mock)"
    is_mock: bool = False                      # True: served from curated mock, not a live subscription
    is_fallback: bool = False                  # True: requested city unknown, generic default served
    retrieved_at: str = Field(default_factory=_utc_now_iso)
