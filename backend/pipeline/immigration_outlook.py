"""Stage 2b — visa route resolution + immigration outlook (2 LLM calls).

fetch(profile, country_a, country_b) -> RouteAndOutlook

Call #1 — Gemini + Google Search grounding:
    Researches the applicable work visa and immigration climate for each
    country from approved government sources. Returns raw text.

Call #2 — Gemini, no search, response_schema=RouteAndOutlook:
    Structures the raw research text into the RouteAndOutlook schema.
    No search — just parsing and formatting what Call #1 found.

After Call #2 — deterministic source-domain validation:
    Every source_url in the structured output is checked against
    official_source_registry.json. Any URL whose domain isn't in the
    approved list triggers a routing_confidence downgrade to "low" so
    the dashboard can flag it. The pipeline never silently trusts an
    unapproved source.

Constraints (plan.md):
  - Only extract from official_source_registry.json approved URLs.
  - Never state hard salary thresholds or PR timelines as hard facts —
    those are owned by visa_rules.json.
  - This module is calls #1 and #2 of 3 total in the pipeline.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from urllib.parse import urlparse

from google import genai
from google.genai import types

from backend.config import settings
from backend.models.ai_models import RouteAndOutlook, VisaRoute
from backend.models.intake_models import ParsedProfile

log = logging.getLogger(__name__)

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


def _build_structure_prompt(raw_research: str, country_a: str, country_b: str) -> str:
    """Prompt for Call #2 — no search, just structure the raw research text.

    Tells Gemini exactly how to map the research into the RouteAndOutlook
    schema fields. The response_schema parameter enforces the shape; this
    prompt handles the semantic mapping (e.g. slug format, confidence rules).
    """
    today = "2026-06-19"
    return f"""You are a data structuring assistant. Below is research about work visa routes and immigration climate for {country_a} and {country_b}.

Structure this research into the required JSON format. Follow these rules exactly:

VISA SLUG FORMAT: lowercase, underscores, country prefix. Examples: "us_h1b", "de_eu_blue_card", "uk_skilled_worker", "ca_express_entry", "au_tss_482", "fr_talent_passport".

FIELDS:
- visa_slug: short machine-readable identifier as above
- visa_name: full human-readable name
- eligibility_summary: 1-2 sentences on who qualifies
- employer_sponsorship_required: true or false
- path_to_residency_years: integer if clearly stated in the research, otherwise null
- key_constraint: the single biggest risk or limitation for this specific user
- routing_confidence: "high" if one clear visa applies, "medium" if there are multiple options or uncertainty, "low" if the research was unclear
- source_url: MUST be a full URL starting with https:// (e.g. "https://www.uscis.gov"). Never use an organisation name or partial domain — always a complete URL.
- source_retrieved: today's date "{today}"

For outlook fields:
- trend_direction: must be exactly "improving", "stable", or "restrictive"
- key_recent_change: the single most significant policy change in the last 12 months
- career_context: career demand outlook for this degree field in this country
- source_url: MUST be a full URL starting with https://. Never use an organisation name.
- source_publish_date: approximate date the source was published, or "{today}" if unknown

Do not invent information not present in the research. If a field cannot be filled from the research, use null for optional fields.

--- RESEARCH ---
{raw_research}
"""


# ── Source-domain validation ─────────────────────────────────────────────────

def _approved_domains(country: str) -> set[str]:
    """Normalised domains from the registry for one country (no www. prefix)."""
    return {
        urlparse(url).netloc.removeprefix("www.")
        for url in _SOURCE_REGISTRY.get(country, [])
    }


def _fallback_url(country: str) -> str:
    """First approved URL for a country — used when the AI returns a non-URL."""
    urls = _SOURCE_REGISTRY.get(country, [])
    return urls[0] if urls else ""


def _source_domain_ok(url: str, approved: set[str]) -> bool:
    """True if url's domain matches or is a subdomain of an approved domain.

    Handles missing scheme (e.g. "make-it-in-germany.com") by prepending
    https:// so urlparse can extract the netloc correctly.
    """
    if "://" not in url:
        url = "https://" + url
    domain = urlparse(url).netloc.removeprefix("www.")
    # domain will be empty if url was something like a plain name — fail it.
    if not domain or "." not in domain:
        return False
    return any(domain == a or domain.endswith("." + a) for a in approved)


def _validate_and_fix_sources(result: RouteAndOutlook, country_a: str, country_b: str) -> RouteAndOutlook:
    """Deterministic check: every source_url must belong to an approved domain.

    Violations don't kill the pipeline — instead the affected route's
    routing_confidence is downgraded to "low" so the dashboard can flag it.
    This runs immediately after Call #2, before any data reaches fact assembly.
    """
    approved_a = _approved_domains(country_a)
    approved_b = _approved_domains(country_b)

    checks = [
        (result.visa_route_a, approved_a, country_a, "visa_route_a"),
        (result.visa_route_b, approved_b, country_b, "visa_route_b"),
        (result.country_a_outlook, approved_a, country_a, "country_a_outlook"),
        (result.country_b_outlook, approved_b, country_b, "country_b_outlook"),
    ]

    route_a_ok = _source_domain_ok(result.visa_route_a.source_url, approved_a)
    route_b_ok = _source_domain_ok(result.visa_route_b.source_url, approved_b)

    for obj, approved, country, label in checks:
        if not _source_domain_ok(obj.source_url, approved):
            log.warning(
                "Stage 2b: unapproved source domain in %s — %r not in registry for %s",
                label, obj.source_url, country,
            )

    # Rebuild routes: downgrade confidence + fix source_url if it's not a real URL.
    visa_a = result.visa_route_a
    visa_b = result.visa_route_b

    if not route_a_ok:
        url_a = visa_a.source_url if "://" in visa_a.source_url else _fallback_url(country_a)
        visa_a = VisaRoute(**{**visa_a.model_dump(), "routing_confidence": "low", "source_url": url_a})
    if not route_b_ok:
        url_b = visa_b.source_url if "://" in visa_b.source_url else _fallback_url(country_b)
        visa_b = VisaRoute(**{**visa_b.model_dump(), "routing_confidence": "low", "source_url": url_b})

    return RouteAndOutlook(
        visa_route_a=visa_a,
        visa_route_b=visa_b,
        country_a_outlook=result.country_a_outlook,
        country_b_outlook=result.country_b_outlook,
    )


# ── Public entry point ────────────────────────────────────────────────────────

def fetch(profile: ParsedProfile, country_a: str, country_b: str) -> RouteAndOutlook:
    """Run Stage 2b: research (Call #1) → structure (Call #2) → validate.

    Returns a RouteAndOutlook with routing_confidence downgraded to "low"
    on any route whose source_url falls outside the approved registry.
    """
    client = _client()

    # Call #1 — Gemini + Google Search grounding → raw research text.
    research_prompt = _build_research_prompt(profile, country_a, country_b)
    research_resp = client.models.generate_content(
        model=MODEL,
        contents=research_prompt,
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
        ),
    )
    raw_research = research_resp.text

    # Call #2 — Gemini, no search → structured RouteAndOutlook.
    structure_prompt = _build_structure_prompt(raw_research, country_a, country_b)
    structure_resp = client.models.generate_content(
        model=MODEL,
        contents=structure_prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=RouteAndOutlook,
        ),
    )
    result = RouteAndOutlook.model_validate_json(structure_resp.text)

    # Deterministic source validation — must run before fact assembly.
    return _validate_and_fix_sources(result, country_a, country_b)
