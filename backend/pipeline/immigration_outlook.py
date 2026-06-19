"""Stage 2b — AI call #1: visa route resolution + immigration outlook.

fetch(profile, country_a, country_b) -> RouteAndOutlook

Calls Gemini with Google Search grounding to:
  1. Identify the applicable work visa for each country given the user's
     citizenship and degree field (routing only — no hard facts).
  2. Summarise the current immigration climate and career context for each
     destination from official government sources.

Constraints (plan.md):
  - Only extract from official_source_registry.json approved URLs.
  - Never state hard salary thresholds or PR timelines as facts — those
    are validated separately via visa_rules.json.
  - Two LLM calls total in the pipeline; this is call #1.
"""

from __future__ import annotations

import json
from pathlib import Path

from google import genai
from google.genai import types

from backend.config import settings
from backend.models.ai_models import RouteAndOutlook
from backend.models.intake_models import ParsedProfile

_DATA_DIR = Path(__file__).resolve().parents[1] / "data"

# Approved government URLs per destination — the only sources Stage 2b
# is allowed to extract from (enforced via prompt constraint).
_SOURCE_REGISTRY: dict[str, list[str]] = json.loads(
    (_DATA_DIR / "official_source_registry.json").read_text(encoding="utf-8")
)

MODEL = "gemini-2.5-flash"


def _client() -> genai.Client:
    return genai.Client(api_key=settings.gemini_api_key)


def _build_research_prompt(
    profile: ParsedProfile,
    country_a: str,
    country_b: str,
) -> str:
    """Prompt for Call #1 — Gemini + Google Search grounding.

    Asks Gemini to research the applicable work visa and current immigration
    climate for each country. Instructs it to only extract from the approved
    government URLs in official_source_registry.json and never state hard
    numeric facts (salary floors, exact PR timelines).
    """
    sources_a = ", ".join(_SOURCE_REGISTRY.get(country_a, []))
    sources_b = ", ".join(_SOURCE_REGISTRY.get(country_b, []))

    return f"""You are a visa routing researcher. A user is deciding between working in {country_a} and {country_b}.

User profile:
- Citizenship: {profile.citizenship}
- Degree field: {profile.degree_field}
- Career stage: {profile.career_stage}

Your task: research and summarise the following for EACH country. Use Google Search to find current information from the approved sources listed below.

For {country_a} — only extract from: {sources_a}
For {country_b} — only extract from: {sources_b}

For each country, find:

1. VISA ROUTE
   - Which work visa applies to this user's citizenship and degree field?
   - What is the common short name/slug for this visa (e.g. "h1b", "skilled_worker", "eu_blue_card")?
   - Does it require employer sponsorship?
   - Is there an annual lottery or cap?
   - What is the key constraint or risk for this user specifically?
   - How confident are you in this routing: high / medium / low?
   - Which government URL did you extract this from?

2. IMMIGRATION CLIMATE
   - What is the current trend: improving, stable, or restrictive?
   - What is the most significant recent change to immigration policy in the last 12 months?
   - What is the career outlook for someone with a {profile.degree_field} degree?
   - Which government URL did you extract this from, and approximately when was it published?

IMPORTANT RULES:
- Do NOT state specific salary thresholds or exact PR timelines as hard facts — those will be verified separately.
- Only use the approved government sources listed above. Do not cite news articles, blogs, or unofficial sources.
- If you cannot find reliable information from the approved sources, say so explicitly — do not guess.
- Be concise. Each answer should be 2-3 sentences max.
"""
