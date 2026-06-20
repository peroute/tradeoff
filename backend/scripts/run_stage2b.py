"""Manual runner for Stage 2b (immigration_outlook.fetch) — dev/QA only.

Hits Gemini live. Run from the repo root:

    python -m backend.scripts.run_stage2b
    python -m backend.scripts.run_stage2b --citizenship Nigeria --field "Mechanical Engineering" --a UK --b Canada

It runs fetch() exactly once (passing a trace dict that fetch() fills with its
Call #1 grounding artifacts), then prints two things, in order:

  1. GROUNDING INSPECTION — the *actual* grounding metadata captured during that
     run: the search queries Gemini issued and the URLs it really retrieved, each
     flagged as in-registry or not. Because it comes from the same run, this is the
     true ground truth that the self-reported `source_url` is checked against — no
     second, divergent replay search.

  2. STRUCTURED OUTPUT — the RouteAndOutlook from the same fetch(), with a
     per-source check of the *claimed* source_url against the approved registry and
     the run's grounding set, so you can eyeball claim-vs-evidence drift.

This is a throwaway inspection tool, not a pytest test. It is intentionally noisy.
"""

from __future__ import annotations

import argparse
import json
import sys
import time

from google.genai import errors as genai_errors

# Windows consoles default to cp1252, which chokes on chars like U+2011 (non-breaking
# hyphen) that show up in model output. Force UTF-8 and never crash on a stray glyph.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

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

def print_grounding(trace: dict) -> None:
    """Dump the Call #1 grounding metadata captured during the single fetch() run.

    Reads from the ``trace`` fetch() populated, so what's shown here is the exact
    research (queries, retrieved sources, raw text) that produced the JSON below —
    not a second, divergent replay search.
    """
    _rule("CALL #1 - GROUNDING INSPECTION (what Gemini actually retrieved)")

    for entry in trace.get("countries", []):
        country = entry["country"]
        resp = entry["response"]
        grounded = entry["grounded_domains"]
        queries = entry["search_queries"]
        approved = io._approved_domains(country)

        print(f"\n  ── {country} ──")
        print(f"\n  Search queries Gemini issued ({len(queries)}):")
        for q in queries:
            _kv("-", q)

        # Per-chunk view: title + raw uri (usually a vertex redirect URL — that's
        # the audit gotcha) and whether its normalized domain landed in registry.
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
            # Real domain lives in the title; the uri is a vertexaisearch redirect.
            dom = io._domain_from_title(title) or io._domain_of(uri)
            in_reg = bool(dom) and any(dom == a or dom.endswith("." + a) for a in approved)
            flag = "IN-REGISTRY" if in_reg else "off-list"
            print(f"    [{flag:>11}] {dom or '(unknown)':<28} {title or '(no title)'}")

        print(f"\n  Normalized grounded domains: {sorted(grounded) or '(none)'}")
        print(f"\n  --- raw research text that produced the JSON ({country}) ---\n")
        print(entry["raw_text"] or "(empty)")


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


def print_structured(result, profile: ParsedProfile, grounded: set[str]) -> None:
    _rule("STRUCTURED OUTPUT - fetch() end-to-end (Call #1 + #2 + verification)")

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
        help="suppress the grounding-inspection printout (grounding is captured "
             "during the single fetch() run regardless, so this saves no API calls)",
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

    # One fetch() run produces both the structured result and (via trace) the
    # Call #1 grounding artifacts — so the inspection below reflects the exact
    # research that produced the JSON, with no second divergent search.
    trace: dict = {}
    result = _with_retry(lambda: io.fetch(profile, trace=trace))

    if not args.skip_grounding:
        print_grounding(trace)

    print_structured(result, profile, trace.get("grounded_domains", set()))


if __name__ == "__main__":
    main()
