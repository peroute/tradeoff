from typing import Literal
from pydantic import BaseModel

ConfidenceLevel = Literal["high", "medium", "low"]
TrendDirection = Literal["improving", "stable", "restrictive"]
ScenarioType = Literal[
    "base",            # baseline: what does working here actually look like for your profile
    "lottery_risk",    # what if you don't win the lottery (H-1B or equivalent)
    "extension_risk",  # what if your visa renewal is denied or not extended
    "employer_switch", # what if you want to change jobs mid-visa
    "partner_work",    # what your partner can and can't do in each country
    "pr_timeline",     # what if PR takes longer than expected or pathway changes
    "priority_match",  # how each country maps to what you said matters to you
    "synthesis",       # cross-country: where does the sharpest tradeoff actually sit
]


class VisaRoute(BaseModel):
    """AI-resolved visa path for one country (output of Stage 2b)."""
    visa_slug: str
    visa_name: str
    eligibility_summary: str
    employer_sponsorship_required: bool
    path_to_residency_years: int | None
    key_constraint: str
    routing_confidence: ConfidenceLevel
    source_url: str
    source_retrieved: str


class ImmigrationOutlook(BaseModel):
    """Immigration policy trend for one country (output of Stage 2b)."""
    trend_summary: str
    trend_direction: TrendDirection
    key_recent_change: str
    career_context: str
    source_url: str
    source_publish_date: str
    confidence: ConfidenceLevel


class RouteAndOutlook(BaseModel):
    """Combined output of Stage 2b — covers both countries in one Gemini call."""
    visa_route_a: VisaRoute
    visa_route_b: VisaRoute
    country_a_outlook: ImmigrationOutlook
    country_b_outlook: ImmigrationOutlook


class WhatIfInsight(BaseModel):
    """A validated AI-generated insight (output of Stage 3)."""
    type: Literal["insight"] = "insight"
    scenario_type: ScenarioType
    fact_used: str
    context_used: str
    connection: str
    consideration: str
    confidence: ConfidenceLevel
    confidence_basis: str
    next_action: str


class SafeFallback(BaseModel):
    """Replaces an insight that failed validation — always visible on dashboard."""
    type: Literal["safe_fallback"] = "safe_fallback"
    reason: str
    slot_index: int
