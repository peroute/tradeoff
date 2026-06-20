"""Stage 2b — visa route resolution + immigration outlook (2 LLM calls).

fetch(profile) -> RouteAndOutlook

────────────────────────────────────────────────────────────────────────────
IN PLAIN WORDS (read this first)
────────────────────────────────────────────────────────────────────────────
This file figures out, for two countries, (1) which work visa fits the user and
(2) what the immigration climate is like — using AI, but without letting the AI
invent facts or cite random websites. It works in three steps:

  Step 1 — ASK GEMINI TO RESEARCH (with live Google Search), one call per country
      We give Gemini the user's profile and ask it to look up the visa + climate
      for one country, basing its answer only on our trusted government sites
      (from official_source_registry.json). Queries are plain natural language —
      we do NOT inject "site:" boolean operators (that mangled the queries without
      reliably constraining grounding). It returns plain text. The "use only
      official sources" instruction is a *nudge*, not a lock — Gemini can still
      pull other sites, so we don't trust it blindly (see Step 3).

  Step 2 — ASK GEMINI TO TIDY IT INTO JSON (no search)
      A second call takes that messy text and reshapes it into a strict JSON
      shape (the RouteAndOutlook schema). No searching here — just formatting.

  Step 3 — CHECK THE SOURCES OURSELVES (plain Python, no AI)
      Gemini also hands back a list of the sites it *actually* opened during
      Step 1 (the "grounding metadata"). For every source Gemini claims it used,
      we ask two questions:
          a) Is this site on our trusted list?           (registry check)
          b) Did Gemini actually open it in Step 1?       (grounding check)
      - Yes to both  → "verified": keep the confidence as-is.
      - On the list but we can't confirm it opened it → "claimed": lower
        confidence one notch (high→medium, medium→low).
      - Not on the trusted list at all → "unapproved": force confidence to "low".
      We never swap in a nicer-looking URL to hide a problem — that would be
      faking a citation. We'd rather show low confidence honestly.

The point: the AI does the reading, but a dumb, predictable Python check decides
how much to trust each answer. That's the whole safety story.
────────────────────────────────────────────────────────────────────────────

Call #1 (once per country) — Gemini + Google Search grounding:
    Researches the applicable work visa and immigration climate for one country
    from approved government sources. Queries are plain natural language (no site:
    operators); the model is told to base its answer only on the official sources.
    The google_search tool has no hard domain allowlist, so this is steering, not
    enforcement — trust is enforced downstream (Call #2 source_url pinning + the
    verification below). Grounding metadata is captured as the model-independent
    record of which sources were actually retrieved; the real domain is read from
    grounding_chunks[].web.title, because .uri is an opaque vertexaisearch redirect
    that masks the true host.

Call #2 — Gemini, no search, response_schema=RouteAndOutlook, temperature=0:
    Structures the raw research text into the RouteAndOutlook schema.
    No search — just parsing what Call #1 found.

After Call #2 — deterministic source verification:
    Every source_url is cross-referenced against BOTH:
      (a) official_source_registry.json — is this an approved domain?
      (b) Call #1 grounding metadata    — was this domain actually retrieved?
    Three outcomes: verified / claimed-not-grounded / unapproved.
      - verified   → keep the model's stated confidence.
      - claimed    → in registry but not seen in grounding → confidence down one
                     notch (high→medium, medium→low).
      - unapproved → not in registry → confidence forced to "low".
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

# One-notch confidence downgrade, applied when a source is in the registry but
# could not be confirmed in the grounding metadata ("claimed" verdict).
_DOWNGRADE_ONE: dict[str, str] = {"high": "medium", "medium": "low", "low": "low"}


def _client():
    from google import genai
    return genai.Client(api_key=settings.gemini_api_key)


# ── Prompts ───────────────────────────────────────────────────────────────────

def _build_research_prompt(profile: ParsedProfile, country: str) -> str:
    """Call #1 prompt for ONE country — instructs Gemini to search approved sources.

    Stage 2b issues one grounded search per country (see fetch()), not a single
    combined two-country call. A combined call lets gemini-2.5-flash spend its
    whole search budget on the first country and then answer the second from
    parametric memory (ungrounded) — observed as a country grounding on zero
    sources. One call per country guarantees each country is actually searched.

    Queries are plain natural language — we deliberately do NOT ask the model to
    append `site:` boolean operators. Appending an OR-chain of site: filters to
    every query made gemini-2.5-flash's google_search rewriter mangle/truncate the
    queries (e.g. cut off at "(site:uscis.gov OR") without reliably constraining
    grounding. Source trust is enforced downstream instead: extraction is limited
    to the official sources by instruction, Call #2's source_url is pinned to the
    approved registry list, and deterministic verification confirms each against
    the grounding metadata.

    Note: profile.citizenship and profile.degree_field are user-supplied strings
    interpolated into the prompt. For a production system these would be
    sanitized; acceptable surface for a hackathon demo.
    """
    sources = ", ".join(_SOURCE_REGISTRY.get(country, []))

    return f"""You are a visa routing researcher helping a user evaluate working in {country}.

User profile:
- Citizenship: {profile.citizenship}
- Degree field: {profile.degree_field}
- Career stage: {profile.career_stage}

Your task: research and summarise the following for {country}. Use Google Search to find current information from the approved government sources listed below.

Official sources (base your answer ONLY on these): {sources}

SEARCH SCOPE — write clear, natural-language search queries. Do NOT add boolean "site:" operators to your queries. After searching, ground your answer only in the official sources above; ignore any result that is not from one of those sources. If the official sources do not answer a question, say so explicitly rather than substituting an unofficial source.

Find:

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


def _approved_url_list(country: str) -> str:
    """Bulleted approved-URL list for a country, for the Call #2 source allowlist."""
    urls = _SOURCE_REGISTRY.get(country, [])
    return "\n".join(f"  - {u}" for u in urls) or "  (none)"


def _build_structure_prompt(raw_research: str, country_a: str, country_b: str) -> str:
    """Call #2 prompt — structures raw research text into RouteAndOutlook JSON.

    source_url is constrained to the approved registry URLs for each country. The
    grounded research often mentions extra URLs (and the model sometimes invents a
    plausible government one); if such a URL reaches the output it fails the
    deterministic registry check and force-lows the confidence. Pinning source_url
    to the approved list at generation time keeps well-grounded answers from being
    penalised for an off-list citation, without any post-hoc URL substitution.
    """
    today = datetime.date.today().isoformat()
    return f"""You are a data structuring assistant. Below is research about work visa routes and immigration climate for {country_a} and {country_b}.

Structure this research into the required JSON format. Follow these rules exactly:

VISA SLUG FORMAT: lowercase, underscores, country prefix. Examples: "us_h1b", "de_eu_blue_card", "uk_skilled_worker", "ca_express_entry", "au_tss_482", "fr_talent_passport".

APPROVED SOURCE URLS — every source_url you output MUST be copied EXACTLY from the matching country's list below. Pick the single URL that best supports the field. Never output a URL that is not in these lists, never shorten or modify one, and never invent a new one — even if the research text cites another URL.
{country_a}:
{_approved_url_list(country_a)}
{country_b}:
{_approved_url_list(country_b)}

FIELDS:
- visa_slug: short machine-readable identifier as above
- visa_name: full human-readable name
- eligibility_summary: 1-2 sentences on who qualifies
- employer_sponsorship_required: true or false
- path_to_residency_years: integer if clearly stated in the research, otherwise null
- key_constraint: the single biggest risk or limitation for this specific user
- routing_confidence: "high" if one clear visa applies, "medium" if multiple options or uncertainty, "low" if the research was unclear
- source_url: the best-matching approved URL for this country, copied exactly from the list above
- source_retrieved: today's date "{today}"

For outlook fields:
- trend_direction: must be exactly "improving", "stable", or "restrictive"
- key_recent_change: the single most significant policy change in the last 12 months
- career_context: career demand outlook for this degree field in this country
- source_url: the best-matching approved URL for this country, copied exactly from the list above
- source_publish_date: approximate date the source was published, or "{today}" if unknown

Do not invent information not present in the research. Use null for optional fields that cannot be filled.

--- RESEARCH ---
{raw_research}
"""


# ── Grounding metadata extraction ─────────────────────────────────────────────

def _domain_from_title(title: str) -> str:
    """Pull a domain-like token out of a grounding chunk title.

    For the Gemini google_search tool, grounding_chunks[].web.title is typically
    the source's display domain (e.g. "make-it-in-germany.com"), while .uri is an
    opaque vertexaisearch redirect wrapper that hides the real domain. So the title
    is where the true source survives. Returns "" if no domain-like token is found
    (e.g. a prose page title with no domain).
    """
    m = re.search(r"\b([a-z0-9][a-z0-9\-]*(?:\.[a-z0-9\-]+)+)\b", (title or "").lower())
    return m.group(1).removeprefix("www.") if m else ""


def _extract_grounded_domains(resp) -> set[str]:
    """Normalised domains Google Search actually retrieved in Call #1.

    The model-independent evidence of what was consulted. Two sources per chunk:
      - web.title — usually the real display domain (PRIMARY signal).
      - web.uri   — almost always a vertexaisearch.cloud.google.com redirect that
                    masks the real domain, so it's only used when it happens to be
                    a real, non-redirect host.
    Used as ground truth in source verification, never the model's self-reported
    source_url.
    """
    domains: set[str] = set()
    try:
        chunks = resp.candidates[0].grounding_metadata.grounding_chunks or []
    except (AttributeError, IndexError, TypeError):
        chunks = []

    for chunk in chunks:
        web = getattr(chunk, "web", None)
        if not web:
            continue
        title_domain = _domain_from_title(getattr(web, "title", "") or "")
        if title_domain:
            domains.add(title_domain)
        uri_domain = urlparse(getattr(web, "uri", "") or "").netloc.removeprefix("www.")
        if uri_domain and "vertexaisearch" not in uri_domain and "." in uri_domain:
            domains.add(uri_domain)
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

    def confidence_for(verdict: str, current: str) -> str:
        """Map a verification verdict onto a confidence level.

        verified   → keep the model's stated confidence (evidence backs the claim)
        claimed    → nudge down one notch (in registry, but retrieval unconfirmed)
        unapproved → "low" (source not trusted at all)
        """
        if verdict == "verified":
            return current
        if verdict == "claimed":
            return _DOWNGRADE_ONE.get(current, "low")
        return "low"

    def fix_route(route: VisaRoute, verdict: str) -> VisaRoute:
        new_conf = confidence_for(verdict, route.routing_confidence)
        if new_conf == route.routing_confidence:
            return route
        return VisaRoute(**{**route.model_dump(), "routing_confidence": new_conf})

    def fix_outlook(outlook: ImmigrationOutlook, verdict: str) -> ImmigrationOutlook:
        new_conf = confidence_for(verdict, outlook.confidence)
        if new_conf == outlook.confidence:
            return outlook
        return ImmigrationOutlook(**{**outlook.model_dump(), "confidence": new_conf})

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


# ── Call #1 (per-country grounded research) ───────────────────────────────────

def _research_country(client, profile: ParsedProfile, country: str):
    """Run one grounded Call #1 for a single country, returning the raw response.

    The full response is returned (not just the text) so callers can read the
    grounding metadata — chunks, domains, queries — from the exact call that
    produced the research, rather than replaying a second, divergent search.
    """
    from google.genai import types
    return client.models.generate_content(
        model=MODEL,
        contents=_build_research_prompt(profile, country),
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
        ),
    )


# ── Public entry point ────────────────────────────────────────────────────────

def fetch(profile: ParsedProfile, trace: dict | None = None) -> RouteAndOutlook:
    """Run Stage 2b: research (Call #1 ×2) → structure (Call #2) → verify sources.

    Call #1 runs once per country so each country gets its own search budget and
    is actually grounded (a single combined call let gemini-2.5-flash answer the
    second country from memory). The two raw research sections are concatenated
    and handed to the single Call #2 structuring pass.

    If ``trace`` is provided it is populated with the Call #1 grounding artifacts
    (per-country response, raw text, queries, grounded domains) and the combined
    research text — so a caller can inspect exactly what produced the JSON without
    issuing a second, divergent search. It is reset on entry so retries don't
    accumulate stale country entries.

    Raises RuntimeError on unrecoverable failure. The orchestrator catches
    this and routes to a SAFE_FALLBACK response — never a crash.
    """
    from google.genai import types

    country_a, country_b = profile.country_a, profile.country_b
    client = _client()

    if trace is not None:
        trace.clear()
        trace["countries"] = []

    # ── Call #1: one Gemini + Google Search grounding call per country ───────
    raw_sections: list[str] = []
    grounded_domains: set[str] = set()
    search_queries: list[str] = []
    for country in (country_a, country_b):
        try:
            resp = _research_country(client, profile, country)
        except Exception as exc:
            raise RuntimeError(f"Stage 2b Call #1 (search) failed for {country}: {exc}") from exc
        text = resp.text or ""
        if not text.strip():
            raise RuntimeError(f"Stage 2b Call #1 returned empty research text for {country}")
        domains = _extract_grounded_domains(resp)
        queries = _extract_search_queries(resp)
        raw_sections.append(f"### {country}\n\n{text.strip()}")
        grounded_domains |= domains
        search_queries.extend(queries)
        if trace is not None:
            trace["countries"].append({
                "country": country,
                "response": resp,
                "raw_text": text.strip(),
                "grounded_domains": domains,
                "search_queries": queries,
            })

    raw_research = "\n\n".join(raw_sections)
    log.info("Stage 2b grounded domains: %s", grounded_domains)
    log.info("Stage 2b search queries: %s", search_queries)

    if trace is not None:
        trace["raw_research"] = raw_research
        trace["grounded_domains"] = grounded_domains

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
