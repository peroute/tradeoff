"""Stage 2b — visa route resolution + immigration outlook (2 LLM calls).

fetch(profile) -> RouteAndOutlook

Call #1 — Gemini + Google Search grounding:
    Researches the applicable work visa and immigration climate for each
    country from approved government sources. Grounding metadata
    (grounding_chunks[].web.uri) is captured as the model-independent
    record of which URLs Google Search actually retrieved.

Call #2 — Gemini, no search, response_schema=RouteAndOutlook, temperature=0:
    Structures the raw research text into the RouteAndOutlook schema.
    No search — just parsing what Call #1 found.

After Call #2 — deterministic source verification:
    Every source_url is cross-referenced against BOTH:
      (a) official_source_registry.json — is this an approved domain?
      (b) Call #1 grounding metadata    — was this domain actually retrieved?
    Three outcomes: verified / claimed-not-grounded / unapproved.
    Unapproved → routing_confidence / confidence downgraded to "low".
    No URL substitution is ever performed — replacing an unverifiable URL
    with a different one fabricates a citation, harming the responsible-AI
    story.

Constraints (plan.md):
  - Only extract from official_source_registry.json approved URLs.
  - Never state hard salary thresholds or PR timelines as hard facts.
  - This module is calls #1 and #2 of 3 total in the pipeline.
"""

from __future__ import annotations

import datetime
import json
import logging
import re
from pathlib import Path
from urllib.parse import urlparse

from google import genai
from google.genai import types

from backend.config import settings
from backend.models.ai_models import ImmigrationOutlook, RouteAndOutlook, VisaRoute
from backend.models.intake_models import ParsedProfile

log = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parents[1] / "data"

_SOURCE_REGISTRY: dict[str, list[str]] = json.loads(
    (_DATA_DIR / "official_source_registry.json").read_text(encoding="utf-8")
)

MODEL = "gemini-2.5-flash"

# Country → visa slug prefix used in slug normalization.
# The slug is the key into visa_rules.json — format must match exactly.
_SLUG_PREFIX: dict[str, str] = {
    "US": "us", "UK": "uk", "Canada": "ca",
    "Australia": "au", "Germany": "de", "France": "fr",
}


def _client() -> genai.Client:
    return genai.Client(api_key=settings.gemini_api_key)


# ── Prompts ───────────────────────────────────────────────────────────────────

def _build_research_prompt(profile: ParsedProfile) -> str:
    """Call #1 prompt — instructs Gemini to search approved government sources.

    Note: profile.citizenship and profile.degree_field are user-supplied strings
    interpolated into the prompt. For a production system these would be
    sanitized; acceptable surface for a hackathon demo.
    """
    country_a, country_b = profile.country_a, profile.country_b
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
    """Call #2 prompt — structures raw research text into RouteAndOutlook JSON."""
    today = datetime.date.today().isoformat()
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
- routing_confidence: "high" if one clear visa applies, "medium" if multiple options or uncertainty, "low" if the research was unclear
- source_url: MUST be a full URL starting with https:// (e.g. "https://www.uscis.gov"). Never use an organisation name or partial domain.
- source_retrieved: today's date "{today}"

For outlook fields:
- trend_direction: must be exactly "improving", "stable", or "restrictive"
- key_recent_change: the single most significant policy change in the last 12 months
- career_context: career demand outlook for this degree field in this country
- source_url: MUST be a full URL starting with https://. Never use an organisation name.
- source_publish_date: approximate date the source was published, or "{today}" if unknown

Do not invent information not present in the research. Use null for optional fields that cannot be filled.

--- RESEARCH ---
{raw_research}
"""


# ── Grounding metadata extraction ─────────────────────────────────────────────

def _extract_grounded_domains(resp) -> set[str]:
    """Normalised domains from Call #1 grounding metadata.

    grounding_chunks[].web.uri are the URLs Google Search actually retrieved —
    the only model-independent evidence of what was consulted. Used as ground
    truth in source verification (not the model's self-reported source_url).
    """
    domains: set[str] = set()
    try:
        chunks = resp.candidates[0].grounding_metadata.grounding_chunks or []
        for chunk in chunks:
            if chunk.web and chunk.web.uri:
                domain = urlparse(chunk.web.uri).netloc.removeprefix("www.")
                if domain:
                    domains.add(domain)
    except (AttributeError, IndexError, TypeError):
        pass
    return domains


def _extract_search_queries(resp) -> list[str]:
    """Search queries used in Call #1 — captured for pipeline_meta transparency."""
    try:
        return list(resp.candidates[0].grounding_metadata.web_search_queries or [])
    except (AttributeError, IndexError, TypeError):
        return []


# ── Source verification ───────────────────────────────────────────────────────

def _approved_domains(country: str) -> set[str]:
    return {
        urlparse(url).netloc.removeprefix("www.")
        for url in _SOURCE_REGISTRY.get(country, [])
    }


def _domain_of(url: str) -> str:
    """Normalised domain from a URL string; empty string if unparseable."""
    if "://" not in url:
        url = "https://" + url
    domain = urlparse(url).netloc.removeprefix("www.")
    return domain if "." in domain else ""


def _verify_source(url: str, approved: set[str], grounded: set[str]) -> str:
    """Return one of: 'verified', 'claimed', 'unapproved'.

    verified          — domain in registry AND in grounding metadata
    claimed           — domain in registry but NOT found in grounding metadata
                        (model may have used it; we can't confirm from evidence)
    unapproved        — domain not in registry at all
    """
    domain = _domain_of(url)
    if not domain:
        return "unapproved"

    in_registry = any(domain == a or domain.endswith("." + a) for a in approved)
    if not in_registry:
        return "unapproved"

    in_grounding = any(
        domain == g or domain.endswith("." + g) or g.endswith("." + domain)
        for g in grounded
    )
    return "verified" if in_grounding else "claimed"


def _validate_sources(
    result: RouteAndOutlook,
    country_a: str,
    country_b: str,
    grounded_domains: set[str],
) -> RouteAndOutlook:
    """Cross-reference every source_url against the registry AND grounding metadata.

    Unapproved sources → routing_confidence / confidence downgraded to "low".
    No URL substitution is performed — we never replace an unverifiable URL
    with a different approved-looking one, as that fabricates a citation.
    """
    approved_a = _approved_domains(country_a)
    approved_b = _approved_domains(country_b)

    def check(url: str, approved: set[str], label: str) -> str:
        verdict = _verify_source(url, approved, grounded_domains)
        if verdict == "unapproved":
            log.warning("Stage 2b unapproved source in %s: %r", label, url)
        elif verdict == "claimed":
            log.info("Stage 2b claimed-not-grounded in %s: %r", label, url)
        return verdict

    v_route_a   = check(result.visa_route_a.source_url,      approved_a, "visa_route_a")
    v_route_b   = check(result.visa_route_b.source_url,      approved_b, "visa_route_b")
    v_outlook_a = check(result.country_a_outlook.source_url, approved_a, "country_a_outlook")
    v_outlook_b = check(result.country_b_outlook.source_url, approved_b, "country_b_outlook")

    def fix_route(route: VisaRoute, verdict: str) -> VisaRoute:
        if verdict == "unapproved":
            return VisaRoute(**{**route.model_dump(), "routing_confidence": "low"})
        return route

    def fix_outlook(outlook: ImmigrationOutlook, verdict: str) -> ImmigrationOutlook:
        if verdict == "unapproved":
            return ImmigrationOutlook(**{**outlook.model_dump(), "confidence": "low"})
        return outlook

    return RouteAndOutlook(
        visa_route_a=fix_route(result.visa_route_a, v_route_a),
        visa_route_b=fix_route(result.visa_route_b, v_route_b),
        country_a_outlook=fix_outlook(result.country_a_outlook, v_outlook_a),
        country_b_outlook=fix_outlook(result.country_b_outlook, v_outlook_b),
    )


# ── Slug normalization ────────────────────────────────────────────────────────

def _normalize_slug(slug: str, country: str) -> str:
    """Normalize visa slug to lowercase_underscore with country prefix.

    The slug is the key into visa_rules.json enrichment lookup — a malformed
    slug silently misses curated facts with no error. We enforce format here.
    """
    prefix = _SLUG_PREFIX.get(country, country.lower())
    normalized = re.sub(r"[\s\-]+", "_", slug.strip().lower())
    if not normalized.startswith(prefix + "_"):
        normalized = f"{prefix}_{normalized}"
    return normalized


# ── Public entry point ────────────────────────────────────────────────────────

def fetch(profile: ParsedProfile) -> RouteAndOutlook:
    """Run Stage 2b: research (Call #1) → structure (Call #2) → verify sources.

    Raises RuntimeError on unrecoverable failure. The orchestrator catches
    this and routes to a SAFE_FALLBACK response — never a crash.
    """
    country_a, country_b = profile.country_a, profile.country_b
    client = _client()

    # ── Call #1: Gemini + Google Search grounding → raw research text ────────
    try:
        research_resp = client.models.generate_content(
            model=MODEL,
            contents=_build_research_prompt(profile),
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
            ),
        )
    except Exception as exc:
        raise RuntimeError(f"Stage 2b Call #1 (search) failed: {exc}") from exc

    raw_research = research_resp.text or ""
    if not raw_research.strip():
        raise RuntimeError("Stage 2b Call #1 returned empty research text")

    grounded_domains = _extract_grounded_domains(research_resp)
    search_queries = _extract_search_queries(research_resp)
    log.info("Stage 2b grounded domains: %s", grounded_domains)
    log.info("Stage 2b search queries: %s", search_queries)

    # ── Call #2: Gemini, no search, temperature=0 → structured output ────────
    try:
        structure_resp = client.models.generate_content(
            model=MODEL,
            contents=_build_structure_prompt(raw_research, country_a, country_b),
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=RouteAndOutlook,
                temperature=0.0,
            ),
        )
    except Exception as exc:
        raise RuntimeError(f"Stage 2b Call #2 (structure) failed: {exc}") from exc

    try:
        result = RouteAndOutlook.model_validate_json(structure_resp.text or "")
    except Exception as exc:
        raise RuntimeError(f"Stage 2b Call #2 returned invalid JSON: {exc}") from exc

    # Normalize slugs before enrichment lookup — format must match visa_rules.json keys.
    result = RouteAndOutlook(
        visa_route_a=VisaRoute(**{
            **result.visa_route_a.model_dump(),
            "visa_slug": _normalize_slug(result.visa_route_a.visa_slug, country_a),
        }),
        visa_route_b=VisaRoute(**{
            **result.visa_route_b.model_dump(),
            "visa_slug": _normalize_slug(result.visa_route_b.visa_slug, country_b),
        }),
        country_a_outlook=result.country_a_outlook,
        country_b_outlook=result.country_b_outlook,
    )

    # Deterministic source verification — anchored to Call #1 grounding metadata.
    return _validate_sources(result, country_a, country_b, grounded_domains)
