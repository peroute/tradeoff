"""Manual runner for Stage 2b (immigration_outlook.fetch) — dev/QA only.

Hits Gemini live. Run from the repo root:

    python -m backend.scripts.run_stage2b
    python -m backend.scripts.run_stage2b --citizenship Nigeria --field "Mechanical Engineering" --a UK --b Canada

It does two things, in order:

  1. GROUNDING INSPECTION — replays Call #1 (Gemini + Google Search) directly so
     it can dump the *actual* grounding metadata: the search queries Gemini issued
     and the URLs it really retrieved. Each retrieved URL is flagged as in-registry
     or not. This is the ground truth that the self-reported `source_url` should be
     checked against (see the Stage 2b audit).

  2. STRUCTURED OUTPUT — runs the real fetch() end-to-end and pretty-prints the
     RouteAndOutlook, with a per-source check of the *claimed* source_url against
     the approved registry, so you can eyeball claim-vs-evidence drift.

This is a throwaway inspection tool, not a pytest test. It is intentionally noisy.
"""

from __future__ import annotations

import argparse
import json
import time

from google.genai import types
from google.genai import errors as genai_errors

from backend.config import settings
from backend.models.intake_models import ParsedProfile
from backend.pipeline import immigration_outlook as io


def _with_retry(fn, *, attempts: int = 5, base_delay: float = 6.0):
    """Call fn(), retrying on transient Gemini errors (503/429) with backoff.

    Grounded search calls are capacity-constrained and 503 intermittently;
    fetch() re-raises those as RuntimeError, so we retry on both.
    """
    for i in range(attempts):
        try:
            return fn()
        except (genai_errors.ServerError, genai_errors.ClientError, RuntimeError) as exc:
            msg = str(exc)
            transient = "503" in msg or "429" in msg or "UNAVAILABLE" in msg or "overloaded" in msg.lower()
            if not transient or i == attempts - 1:
                raise
            delay = base_delay * (2 ** i)
            print(f"  [transient error, retry {i + 1}/{attempts - 1} in {delay:.0f}s] {msg[:90]}")
            time.sleep(delay)

# ── tiny terminal helpers ────────────────────────────────────────────────────

def _rule(title: str) -> None:
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def _kv(label: str, value: object) -> None:
    print(f"  {label:<26} {value}")


# ── (1) grounding inspection ─────────────────────────────────────────────────

def inspect_grounding(profile: ParsedProfile) -> set[str]:
    """Replay Call #1 and dump the real grounding metadata.

    Returns the set of domains Gemini actually retrieved, so the structured-output
    pass can show the same verified/claimed/unapproved verdicts that fetch() uses
    internally. (fetch() runs its own Call #1, so the two grounding sets can differ
    slightly — this is an inspection tool, not a transactional record.)
    """
    _rule("CALL #1 - GROUNDING INSPECTION (what Gemini actually retrieved)")

    client = io._client()
    resp = _with_retry(lambda: client.models.generate_content(
        model=io.MODEL,
        contents=io._build_research_prompt(profile),
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
        ),
    ))

    approved = io._approved_domains(profile.country_a) | io._approved_domains(profile.country_b)
    grounded = io._extract_grounded_domains(resp)
    queries = io._extract_search_queries(resp)

    print(f"\n  Search queries Gemini issued ({len(queries)}):")
    for q in queries:
        _kv("-", q)

    # Per-chunk view: title + raw uri (usually a vertex redirect URL — that's the
    # audit gotcha) and whether its normalized domain landed in the registry.
    chunks = []
    try:
        chunks = resp.candidates[0].grounding_metadata.grounding_chunks or []
    except (AttributeError, IndexError, TypeError):
        pass

    print(f"\n  Sources actually retrieved ({len(chunks)}):")
    if not chunks:
        print("    (none reported)")
    for c in chunks:
        web = getattr(c, "web", None)
        uri = getattr(web, "uri", "") if web else ""
        title = getattr(web, "title", "") if web else ""
        dom = io._domain_of(uri)
        in_reg = any(dom == a or dom.endswith("." + a) for a in approved)
        flag = "IN-REGISTRY" if in_reg else "off-list/redirect"
        print(f"    [{flag:>17}] {title or '(no title)'}")
        print(f"                        {uri}")

    print(f"\n  Normalized grounded domains: {sorted(grounded) or '(none)'}")
    print("\n  --- raw research text returned by Call #1 ---\n")
    print((resp.text or "(empty)").strip())
    return grounded


# ── (2) structured output ────────────────────────────────────────────────────

_VERDICT_LABEL = {
    "verified": "VERIFIED  (in registry + grounded)",
    "claimed": "CLAIMED   (in registry, NOT grounded <- unconfirmed)",
    "unapproved": "UNAPPROVED (not in registry <- downgraded)",
}


def _print_route(label: str, route, country: str, grounded: set[str]) -> None:
    verdict = io._verify_source(route.source_url, io._approved_domains(country), grounded)
    print(f"\n  {label} ({country})")
    _kv("visa_slug", route.visa_slug)
    _kv("visa_name", route.visa_name)
    _kv("eligibility_summary", route.eligibility_summary)
    _kv("employer_sponsorship", route.employer_sponsorship_required)
    _kv("path_to_residency_years", route.path_to_residency_years)
    _kv("key_constraint", route.key_constraint)
    _kv("routing_confidence", route.routing_confidence)
    _kv("source_url", route.source_url)
    _kv("  -> source verdict", _VERDICT_LABEL.get(verdict, verdict))


def _print_outlook(label: str, outlook, country: str, grounded: set[str]) -> None:
    verdict = io._verify_source(outlook.source_url, io._approved_domains(country), grounded)
    print(f"\n  {label} ({country})")
    _kv("trend_direction", outlook.trend_direction)
    _kv("trend_summary", outlook.trend_summary)
    _kv("key_recent_change", outlook.key_recent_change)
    _kv("career_context", outlook.career_context)
    _kv("confidence", outlook.confidence)
    _kv("source_url", outlook.source_url)
    _kv("  -> source verdict", _VERDICT_LABEL.get(verdict, verdict))


def run_fetch(profile: ParsedProfile, grounded: set[str]) -> None:
    _rule("STRUCTURED OUTPUT - fetch() end-to-end (Call #1 + #2 + verification)")
    result = _with_retry(lambda: io.fetch(profile))

    _print_route("visa_route_a", result.visa_route_a, profile.country_a, grounded)
    _print_route("visa_route_b", result.visa_route_b, profile.country_b, grounded)
    _print_outlook("country_a_outlook", result.country_a_outlook, profile.country_a, grounded)
    _print_outlook("country_b_outlook", result.country_b_outlook, profile.country_b, grounded)

    _rule("RAW JSON")
    print(json.dumps(result.model_dump(), indent=2, ensure_ascii=False))


# ── entry point ──────────────────────────────────────────────────────────────

def main() -> None:
    p = argparse.ArgumentParser(description="Live runner for Stage 2b (hits Gemini).")
    p.add_argument("--citizenship", default="India")
    p.add_argument("--field", default="Computer Science", help="degree field")
    p.add_argument(
        "--stage",
        default="new_grad",
        choices=["new_grad", "early_career", "mid_career", "senior"],
    )
    p.add_argument("--a", default="US", help="country_a")
    p.add_argument("--b", default="Germany", help="country_b")
    p.add_argument(
        "--context",
        default="I care most about long-term residency stability and not being tied to one employer.",
    )
    p.add_argument(
        "--skip-grounding",
        action="store_true",
        help="skip the grounding-inspection call (saves one Gemini call)",
    )
    args = p.parse_args()

    if not settings.gemini_api_key:
        raise SystemExit("GEMINI_API_KEY is not set — populate .env before running.")

    profile = ParsedProfile(
        citizenship=args.citizenship,
        degree_field=args.field,
        career_stage=args.stage,
        country_a=args.a,
        country_b=args.b,
        user_context=args.context,
    )

    _rule("INPUT PROFILE")
    for k, v in profile.model_dump().items():
        _kv(k, v)

    grounded: set[str] = set()
    if not args.skip_grounding:
        grounded = inspect_grounding(profile)
    run_fetch(profile, grounded)


if __name__ == "__main__":
    main()
