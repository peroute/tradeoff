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
