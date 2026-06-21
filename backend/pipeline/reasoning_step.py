"""Stage 3 — What-if reasoning (single Gemini call) and the deterministic validator gate.

This module owns two things, in this order of importance:

1. ``validate_output()`` — the deterministic Responsible-AI gate. It is pure,
   dependency-free (stdlib only), and never calls a model. Every field of a
   Stage 3 result is checked against the *actual* fact bundle and the *actual*
   user intake. Any failure routes to ``SAFE_FALLBACK``; unvalidated model
   output is never returned to the caller. This is the keystone of the pitch.

2. ``generate_insights()`` — makes ONE Gemini call (gemini-2.5-flash) that returns
   all 7 insights as a JSON array, then runs ``validate_output()`` on each item
   individually. Per-slot ``SAFE_FALLBACK`` routing is preserved; a single call
   failure yields 7 SafeFallback items so the dashboard always receives exactly 7.

Stage 3 output contract (CLAUDE.md — match field names exactly):
    fact_a            str|None — a real ``bundle_a.*`` key (the country-A fact)
    fact_b            str|None — a real ``bundle_b.*`` key (the country-B fact)
    context_used      str  — something the user actually said in intake
    tradeoff          str  — "gain X but sacrifice Y"; shares vocab with the facts AND context
    likely_outcome    str  — the honest "what happens if" result (esp. risk slots)
    consideration     str  — the non-obvious second-order implication, not boilerplate
    confidence        str  — "high" | "medium" | "low"
    confidence_basis  str  — why this confidence level
    next_action       str  — a verb-led instruction

Coverage rule: each slot declares which sides it must cite. The two ``base``
slots are single-country (slot 1 → fact_a only, slot 2 → fact_b only); every
other slot is comparative and must cite a real fact from BOTH bundles, so an
insight can never collapse onto one country.

Key-convention note: the validator checks ``fact_a``/``fact_b`` against the
*flattened keys the bundle actually emits* (namespaced ``bundle_a.*`` /
``bundle_b.*``), so it is agnostic to whether a value key is ``min_salary`` or
``min_salary_eur``. It validates against reality, not against the example.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable, get_args

from backend.config import settings
from backend.models.ai_models import SafeFallback, ScenarioType, WhatIfInsight
from backend.models.output_models import CountryBundle

# ---------------------------------------------------------------------------
# Contract constants
# ---------------------------------------------------------------------------

MODEL_ID = "gemini-2.5-flash"  # Stage 3 model, per CLAUDE.md

# Always-present prose fields, checked for presence + string-ness. fact_a/fact_b
# are validated separately (per-slot coverage) because which side is required
# depends on the slot, so they are intentionally NOT in this set.
REQUIRED_FIELDS = (
    "scenario_type",
    "context_used",
    "tradeoff",
    "likely_outcome",
    "consideration",
    "confidence",
    "confidence_basis",
    "next_action",
)

VALID_CONFIDENCE = frozenset({"high", "medium", "low"})

# Single source of truth: the scenario taxonomy lives on the WhatIfInsight model
# (ai_models.ScenarioType). Deriving the set here — rather than re-listing it —
# means a stray value (the kind that caused the /api/compare 500) can never pass
# the validator. pydantic is a core dep, so the validator stays SDK-free.
VALID_SCENARIO_TYPES = frozenset(get_args(ScenarioType))

# JSON Schema for Gemini structured output (response_schema). Kept as a plain
# dict so it has no SDK dependency and can be reused by tests.
# The outer array wraps 7 per-insight objects so the single Stage-3 call returns
# all insights at once.
# Field order the model emits per object. fact_a/fact_b are emitted as "" when a
# single-country (base) slot does not use that side; the validator treats an
# empty string as "absent" and normalizes it to None before the model is built.
_SCHEMA_FIELD_ORDER = (
    "scenario_type",
    "fact_a",
    "fact_b",
    "context_used",
    "tradeoff",
    "likely_outcome",
    "consideration",
    "confidence",
    "confidence_basis",
    "next_action",
)

STAGE3_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "scenario_type": {"type": "string", "enum": sorted(VALID_SCENARIO_TYPES)},
            "fact_a": {"type": "string"},
            "fact_b": {"type": "string"},
            "context_used": {"type": "string"},
            "tradeoff": {"type": "string"},
            "likely_outcome": {"type": "string"},
            "consideration": {"type": "string"},
            "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
            "confidence_basis": {"type": "string"},
            "next_action": {"type": "string"},
        },
        "required": list(_SCHEMA_FIELD_ORDER),
        "propertyOrdering": list(_SCHEMA_FIELD_ORDER),
    },
    "minItems": 7,
    "maxItems": 7,
}

# ---------------------------------------------------------------------------
# Validator tuning
# ---------------------------------------------------------------------------

# Minimum number of shared content tokens required to claim a real overlap.
_MIN_OVERLAP_TOKENS = 1

# Fraction of context_used's content tokens that must appear in what the user
# actually said, for context_used to count as "something the user said".
_CONTEXT_RECALL_THRESHOLD = 0.5

# consideration must clear this many content tokens to not read as a stub.
_MIN_CONSIDERATION_TOKENS = 4

# tradeoff and likely_outcome must each clear this many content tokens.
_MIN_TRADEOFF_TOKENS = 4
_MIN_OUTCOME_TOKENS = 3

# Phrases that mark generic boilerplate rather than a real insight. Matched as
# substrings against the lowercased consideration.
_BOILERPLATE_MARKERS = (
    "it depends",
    "there are many factors",
    "consider all factors",
    "do your research",
    "weigh the pros and cons",
    "ultimately the choice is yours",
    "every situation is different",
    "this is an important decision",
    "carefully consider",
    "as an ai",
    "i cannot provide",
    "it is important to note",
    "there is no right answer",
)

# Verb-led check: a curated set of imperative action verbs relevant to this
# domain. Kept explicit (no POS tagger dependency) so the check is deterministic
# and inspectable. The first content word of next_action must be in this set.
_ACTION_VERBS = frozenset({
    "analyze", "anticipate", "apply", "ask", "assess", "budget", "calculate",
    "check", "clarify", "choose", "compare", "compile", "confirm", "consult",
    "contact", "convert", "cross-check", "define", "determine", "develop",
    "document", "draft", "email", "engage", "ensure", "establish", "estimate",
    "evaluate", "examine", "explore", "factor", "file", "flag", "gather",
    "identify", "investigate", "list", "map", "measure", "model", "monitor",
    "negotiate", "note", "obtain", "outline", "plan", "prepare", "prioritize",
    "pursue", "quantify", "rank", "reassess", "recalculate", "request",
    "research", "review", "schedule", "secure", "seek", "shortlist", "study",
    "submit", "trace", "track", "validate", "verify", "weigh",
})

# Stopwords removed before any vocabulary-overlap comparison. Deliberately small
# and generic — content words carry the overlap signal.
_STOPWORDS = frozenset({
    "a", "an", "the", "and", "or", "but", "if", "then", "than", "so", "as",
    "of", "to", "in", "on", "at", "by", "for", "with", "about", "from", "into",
    "is", "are", "was", "were", "be", "been", "being", "am", "do", "does",
    "did", "has", "have", "had", "will", "would", "can", "could", "should",
    "may", "might", "must", "shall", "this", "that", "these", "those", "it",
    "its", "your", "you", "their", "they", "them", "we", "our", "us", "i",
    "my", "me", "he", "she", "his", "her", "which", "who", "whom", "what",
    "when", "where", "why", "how", "not", "no", "yes", "more", "most", "less",
    "very", "much", "many", "some", "any", "all", "both", "each", "per",
    "between", "across", "over", "under", "out", "up", "down", "there", "here",
})

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9\-']*")


# ---------------------------------------------------------------------------
# Result + fallback types
# ---------------------------------------------------------------------------


@dataclass
class ValidationResult:
    """Outcome of validating a Stage 3 result.

    ``output`` is always safe to display: it is the original model output when
    ``passed`` is True, and ``SAFE_FALLBACK`` (annotated with the reasons) when
    ``passed`` is False. Callers should render ``output`` and never the raw
    model result directly.
    """

    passed: bool
    failures: list[str] = field(default_factory=list)
    output: dict[str, Any] = field(default_factory=dict)


# Canonical safe fallback. Shown verbatim (with a reason attached) whenever the
# model output fails any check. It deliberately does not recommend an option —
# the AI never states which choice to make (human-in-the-loop boundary).
SAFE_FALLBACK: dict[str, Any] = {
    "fact_a": None,
    "fact_b": None,
    "context_used": None,
    "tradeoff": None,
    "likely_outcome": None,
    "consideration": (
        "We could not generate a verified what-if insight for this comparison. "
        "Review the assembled facts and visa rules directly, and treat this "
        "section as incomplete rather than as guidance."
    ),
    "confidence": "low",
    "confidence_basis": "Automated validation did not pass; no insight is asserted.",
    "next_action": "Review the fact table and visa rules side by side yourself.",
    "is_fallback": True,
    "fallback_reasons": [],
}


def build_safe_fallback(reasons: Iterable[str]) -> dict[str, Any]:
    """Return a fresh SAFE_FALLBACK copy annotated with why it triggered."""
    fallback = dict(SAFE_FALLBACK)
    fallback["fallback_reasons"] = list(reasons)
    return fallback


# ---------------------------------------------------------------------------
# Tokenizing / overlap helpers (pure)
# ---------------------------------------------------------------------------


def _tokenize(text: Any) -> list[str]:
    """Lowercase content tokens with stopwords removed. Non-str -> []."""
    if not isinstance(text, str):
        return []
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOPWORDS]


def _flatten_keys(bundle: Any, prefix: str = "") -> set[str]:
    """Flatten a nested fact bundle into the set of dotted leaf+branch keys.

    Both branch paths (``bundle_a.visa_route``) and leaf paths
    (``bundle_a.visa_route.path_to_residency_years``) are included, so
    ``fact_a``/``fact_b`` may reference either a whole fact group or a field.
    """
    keys: set[str] = set()
    if isinstance(bundle, dict):
        for k, v in bundle.items():
            path = f"{prefix}.{k}" if prefix else str(k)
            keys.add(path)
            keys |= _flatten_keys(v, path)
    return keys


def _key_tokens(dotted_key: str) -> set[str]:
    """Content tokens drawn from a dotted fact key, e.g.
    ``france_passeport_talent.min_salary`` -> {france, passeport, talent, min, salary}.
    """
    return {t for t in _TOKEN_RE.findall(dotted_key.lower()) if t not in _STOPWORDS}


def _normalize_context(raw_context: Any) -> str:
    """Join raw intake utterances into one searchable string."""
    if isinstance(raw_context, str):
        return raw_context
    if isinstance(raw_context, (list, tuple)):
        return " ".join(str(x) for x in raw_context)
    if isinstance(raw_context, dict):
        return " ".join(str(v) for v in raw_context.values())
    return ""


# Prose fields a user reads, where a stray generic "Country A/B" must be rewritten
# to the real destination name. fact_a/fact_b are deliberately excluded — those are
# the bundle_a.*/bundle_b.* key contract the validator checks, not human prose.
_RELABEL_FIELDS = (
    "tradeoff",
    "likely_outcome",
    "consideration",
    "next_action",
    "confidence_basis",
    "context_used",
)

# Matches "Country A"/"country a" and the possessive "Country A's" (the \b after
# the letter sits before the apostrophe, so the "'s" is preserved).
_COUNTRY_A_RE = re.compile(r"\bcountry\s+a\b", re.IGNORECASE)
_COUNTRY_B_RE = re.compile(r"\bcountry\s+b\b", re.IGNORECASE)


def _relabel_countries(item: Any, country_a: str, country_b: str) -> Any:
    """Deterministically rewrite generic "Country A/B" prose to real names.

    Belt-and-suspenders for the prompt instruction: the model is told to use real
    names, but at temperature it occasionally slips. This guarantees no user-facing
    "Country A"/"Country B" survives, regardless of model behaviour. Mutates and
    returns ``item`` (a parsed insight dict); non-dicts pass through untouched.
    """
    if not isinstance(item, dict):
        return item
    for f in _RELABEL_FIELDS:
        v = item.get(f)
        if isinstance(v, str) and ("country a" in v.lower() or "country b" in v.lower()):
            v = _COUNTRY_A_RE.sub(country_a, v)
            item[f] = _COUNTRY_B_RE.sub(country_b, v)
    return item


# ---------------------------------------------------------------------------
# The gate
# ---------------------------------------------------------------------------


def _present(value: Any) -> bool:
    """A fact side counts as present only if it is a non-empty string."""
    return isinstance(value, str) and value.strip() != ""


def validate_output(
    output: Any,
    fact_bundle: dict[str, Any],
    raw_context: Any,
    required_sides: tuple[str, ...] = ("a", "b"),
) -> ValidationResult:
    """Deterministically validate a Stage 3 result.

    ``required_sides`` is the slot's coverage demand: ``("a",)`` / ``("b",)`` for
    the single-country base slots, ``("a", "b")`` for every comparative slot.

    Checks (any failure -> SAFE_FALLBACK):
      * schema:        required prose fields present, confidence in the enum,
                       scenario_type a real ScenarioType value.
      * coverage:      every required side is present; each present fact_a/fact_b
                       is a real flattened key in the correct bundle namespace.
      * context_used:  most of its content words appear in what the user said.
      * tradeoff:      shares real vocabulary with context AND with each present
                       fact's key tokens; long enough to be a real comparison.
      * likely_outcome:long enough and not boilerplate.
      * consideration: long enough and not boilerplate.
      * next_action:   verb-led (first content word is an action verb).

    On success the returned ``output`` has empty fact sides normalized to None,
    so it can be splatted straight into ``WhatIfInsight``.
    """
    failures: list[str] = []

    # --- schema completeness ------------------------------------------------
    if not isinstance(output, dict):
        return ValidationResult(False, ["output is not an object"],
                                build_safe_fallback(["output is not an object"]))

    missing = [f for f in REQUIRED_FIELDS if f not in output]
    if missing:
        failures.append(f"missing required fields: {', '.join(missing)}")
    non_string = [
        f for f in REQUIRED_FIELDS
        if f in output and not isinstance(output[f], str)
    ]
    if non_string:
        failures.append(f"non-string fields: {', '.join(non_string)}")

    if isinstance(output.get("confidence"), str):
        if output["confidence"].strip().lower() not in VALID_CONFIDENCE:
            failures.append(
                f"confidence not in {{high, medium, low}}: {output['confidence']!r}"
            )

    # scenario_type must be a real ScenarioType value (CLAUDE.md rule).
    scenario_type = output.get("scenario_type")
    if not isinstance(scenario_type, str) or scenario_type not in VALID_SCENARIO_TYPES:
        failures.append(f"scenario_type not in ScenarioType: {scenario_type!r}")

    # If the shape is already broken, stop here — later checks assume strings.
    if failures:
        return ValidationResult(False, failures, build_safe_fallback(failures))

    fact_a = output.get("fact_a")
    fact_b = output.get("fact_b")
    context_used = output["context_used"]
    tradeoff = output["tradeoff"]
    likely_outcome = output["likely_outcome"]
    consideration = output["consideration"]
    next_action = output["next_action"]

    # --- coverage + fact validity ------------------------------------------
    real_keys = _flatten_keys(fact_bundle)
    present_a, present_b = _present(fact_a), _present(fact_b)

    if "a" in required_sides and not present_a:
        failures.append("fact_a is required for this slot but missing")
    if "b" in required_sides and not present_b:
        failures.append("fact_b is required for this slot but missing")

    if present_a and (fact_a not in real_keys or not fact_a.startswith("bundle_a.")):
        failures.append(f"fact_a {fact_a!r} is not a real bundle_a.* key")
    if present_b and (fact_b not in real_keys or not fact_b.startswith("bundle_b.")):
        failures.append(f"fact_b {fact_b!r} is not a real bundle_b.* key")

    # --- context_used was actually said ------------------------------------
    said = set(_tokenize(_normalize_context(raw_context)))
    ctx_tokens = _tokenize(context_used)
    if not ctx_tokens:
        failures.append("context_used has no content words")
    else:
        recalled = sum(1 for t in ctx_tokens if t in said)
        if recalled / len(ctx_tokens) < _CONTEXT_RECALL_THRESHOLD:
            failures.append(
                "context_used is not grounded in what the user said "
                f"({recalled}/{len(ctx_tokens)} content words match)"
            )

    # --- tradeoff is grounded in the fact(s) it compares -------------------
    # Context relevance is already enforced via context_used (rule above); here
    # we only require the comparison to be anchored in the real fact key(s), so a
    # tradeoff can never be asserted about a fact it doesn't actually reference.
    trade_tokens = set(_tokenize(tradeoff))
    if len(_tokenize(tradeoff)) < _MIN_TRADEOFF_TOKENS:
        failures.append("tradeoff is too thin to be a real comparison")
    if present_a and len(trade_tokens & _key_tokens(fact_a)) < _MIN_OVERLAP_TOKENS:
        failures.append("tradeoff shares no vocabulary with fact_a")
    if present_b and len(trade_tokens & _key_tokens(fact_b)) < _MIN_OVERLAP_TOKENS:
        failures.append("tradeoff shares no vocabulary with fact_b")

    # --- likely_outcome is a real "what happens if" ------------------------
    if any(m in likely_outcome.lower() for m in _BOILERPLATE_MARKERS):
        failures.append("likely_outcome reads as boilerplate")
    if len(_tokenize(likely_outcome)) < _MIN_OUTCOME_TOKENS:
        failures.append("likely_outcome is too thin to model an outcome")

    # --- consideration is a real insight -----------------------------------
    if any(marker in consideration.lower() for marker in _BOILERPLATE_MARKERS):
        failures.append("consideration reads as boilerplate")
    if len(_tokenize(consideration)) < _MIN_CONSIDERATION_TOKENS:
        failures.append("consideration is too thin to be a real insight")

    # --- next_action is verb-led -------------------------------------------
    action_tokens = _tokenize(next_action)
    if not action_tokens:
        failures.append("next_action has no content words")
    elif action_tokens[0] not in _ACTION_VERBS:
        failures.append(
            f"next_action is not verb-led (starts with {action_tokens[0]!r})"
        )

    if failures:
        return ValidationResult(False, failures, build_safe_fallback(failures))

    # Normalize empty fact sides to None so the dict splats cleanly into the model.
    normalized = dict(output)
    normalized["fact_a"] = fact_a if present_a else None
    normalized["fact_b"] = fact_b if present_b else None
    return ValidationResult(True, [], normalized)


# ---------------------------------------------------------------------------
# Stage 3 generation (Gemini)
# ---------------------------------------------------------------------------


def build_prompt(
    fact_bundle: dict[str, Any], raw_context: Any, slot_plan: list[str]
) -> str:
    """Assemble the Stage 3 what-if prompt that requests all 7 insights at once.

    ``slot_plan`` is the ordered list of 7 scenario types produced by
    ``_slot_plan()``. The prompt injects this list — together with each slot's
    coverage demand — so the model knows exactly what to produce, in which order,
    and which country/countries each slot must cite. The caller re-derives the
    same coverage and stamps the authoritative scenario_type before validating.
    """
    real_keys = _flatten_keys(fact_bundle)
    a_keys = sorted(k for k in real_keys if k.startswith("bundle_a."))
    b_keys = sorted(k for k in real_keys if k.startswith("bundle_b."))
    a_block = "\n".join(f"  - {k}" for k in a_keys)
    b_block = "\n".join(f"  - {k}" for k in b_keys)
    said = _normalize_context(raw_context)

    # Real destination names so the model writes prose about (e.g.) "France" and
    # "Australia" instead of the generic "Country A" / "Country B". The fact_a/
    # fact_b key namespaces stay generic (bundle_a.* / bundle_b.*) — that is the
    # validator's contract — but every human-facing string uses the real name.
    country_a = (fact_bundle.get("bundle_a") or {}).get("country", "Country A")
    country_b = (fact_bundle.get("bundle_b") or {}).get("country", "Country B")

    coverages = _slot_coverages(slot_plan)
    slot_lines = []
    for i, (st, sides) in enumerate(zip(slot_plan, coverages)):
        if sides == ("a",):
            cover = f"use ONE {country_a} fact in fact_a; leave fact_b empty"
        elif sides == ("b",):
            cover = f"use ONE {country_b} fact in fact_b; leave fact_a empty"
        else:
            cover = f"use ONE {country_a} fact in fact_a AND ONE {country_b} fact in fact_b"
        slot_lines.append(f"  {i + 1}. {st} — {cover}")
    slots_block = "\n".join(slot_lines)

    return (
        "You are the what-if reasoning step in a post-grad job-offer comparator.\n"
        f"The two destinations being compared are {country_a} (Country A) and "
        f"{country_b} (Country B).\n"
        "Surface SEVEN concrete considerations, one per scenario slot below. Most "
        f"slots are COMPARATIVE: they weigh a {country_a} fact against a {country_b} "
        "fact and name the real tradeoff (what you gain versus what you give up). "
        "You never state which option to choose.\n\n"
        "Return a JSON array of exactly 7 objects in this exact slot order. The "
        "'scenario_type' of object N must match slot N, and each slot dictates which "
        "country/countries you must cite:\n"
        f"{slots_block}\n\n"
        "Rules (apply to every object):\n"
        f"  * In every prose field (tradeoff, likely_outcome, consideration, "
        f"next_action, confidence_basis) refer to each country by its real name — "
        f"{country_a} or {country_b}. NEVER write \"Country A\" or \"Country B\".\n"
        f"  * fact_a (when used) MUST be copied verbatim from the {country_a} key list below.\n"
        f"  * fact_b (when used) MUST be copied verbatim from the {country_b} key list below.\n"
        "  * NEVER invent, guess, or modify a key, and NEVER assume the two countries "
        "expose the same keys — the lists below can differ (e.g. one country may have "
        "no visa_enrichment.* keys). If a key is not in the list, you may not cite it; "
        "pick a different listed key for that country instead.\n"
        "  * For an unused side, return an empty string \"\".\n"
        "  * context_used MUST be drawn verbatim from what the user said.\n"
        "  * tradeoff MUST reuse real words from the fact key(s) AND from context_used, "
        "and state the gain-versus-sacrifice explicitly.\n"
        "  * likely_outcome MUST state the probable real-world result honestly — "
        "including unfavorable odds — not a reassurance.\n"
        "  * consideration MUST be a non-obvious second-order implication, not generic advice.\n"
        "  * next_action MUST start with an action verb.\n\n"
        f"{country_a} fact keys (bundle_a.*):\n{a_block}\n\n"
        f"{country_b} fact keys (bundle_b.*):\n{b_block}\n\n"
        f"What the user said:\n{said}\n"
    )


# ---------------------------------------------------------------------------
# Stage 3 orchestration: 7-insight composition + typed-union mapping
# ---------------------------------------------------------------------------

# The request always yields 7 insights in this composition (CLAUDE.md):
#   2 base · 2 contingency · 2 priority_match · 1 synthesis
# "contingency" is a category, not a ScenarioType value — the two contingency
# slots are filled by _contingency_scenarios() from the granular risk types.
_FIXED_SLOTS_HEAD = ("base", "base")
_FIXED_SLOTS_TAIL = ("priority_match", "priority_match", "synthesis")

# Priority order for resolving the two contingency slots. Each entry pairs a
# granular ScenarioType with a predicate over the two bundles; the most relevant
# come first. extension_risk has no dedicated curated field, so it is the generic
# fallback that keeps the list long enough to always yield two distinct values.
def _has_lottery(b: CountryBundle) -> bool:
    return bool(b.visa_enrichment and b.visa_enrichment.lottery_required)


def _restricted_partner(b: CountryBundle) -> bool:
    return bool(
        b.visa_enrichment
        and b.visa_enrichment.partner_work_rights in {"restricted", "none"}
    )


def _switch_constrained(b: CountryBundle) -> bool:
    return bool(b.visa_enrichment and b.visa_enrichment.can_switch_employer is False)


def _has_pr_timeline(b: CountryBundle) -> bool:
    return b.visa_route.path_to_residency_years is not None


# (scenario_type, predicate) in descending relevance. extension_risk is always
# eligible so the filtered list never falls below two entries.
_CONTINGENCY_PRIORITY: tuple[tuple[str, Any], ...] = (
    ("lottery_risk", lambda a, b: _has_lottery(a) or _has_lottery(b)),
    ("partner_work", lambda a, b: _restricted_partner(a) or _restricted_partner(b)),
    ("employer_switch", lambda a, b: _switch_constrained(a) or _switch_constrained(b)),
    ("pr_timeline", lambda a, b: _has_pr_timeline(a) or _has_pr_timeline(b)),
    ("extension_risk", lambda a, b: True),
)


def _contingency_scenarios(bundle_a: CountryBundle, bundle_b: CountryBundle) -> list[str]:
    """Pick the two most relevant contingency scenarios for this comparison.

    Deterministic: walk the priority list, keep scenarios whose signal is present
    in either bundle, then pad from the remaining priority order so exactly two
    distinct granular risk types are always returned.
    """
    relevant = [st for st, pred in _CONTINGENCY_PRIORITY if pred(bundle_a, bundle_b)]
    chosen = relevant[:2]
    if len(chosen) < 2:
        for st, _ in _CONTINGENCY_PRIORITY:
            if st not in chosen:
                chosen.append(st)
            if len(chosen) == 2:
                break
    return chosen


def _slot_plan(bundle_a: CountryBundle, bundle_b: CountryBundle) -> list[str]:
    """The 7 scenario_type slots in order, with contingency slots resolved."""
    c1, c2 = _contingency_scenarios(bundle_a, bundle_b)
    return [*_FIXED_SLOTS_HEAD, c1, c2, *_FIXED_SLOTS_TAIL]


def _slot_coverages(slot_plan: list[str]) -> list[tuple[str, ...]]:
    """Per-slot fact-coverage demand, aligned 1:1 with ``slot_plan``.

    The two scene-setting ``base`` slots are single-country — the first cites
    country A (``("a",)``), the second country B (``("b",)``) — so both countries
    always appear even before the comparative slots. Every non-base slot is
    comparative and must cite a fact from BOTH bundles (``("a", "b")``).
    """
    coverages: list[tuple[str, ...]] = []
    base_seen = 0
    for st in slot_plan:
        if st == "base":
            coverages.append(("a",) if base_seen == 0 else ("b",))
            base_seen += 1
        else:
            coverages.append(("a", "b"))
    return coverages


def to_insight(
    result: ValidationResult, slot_index: int
) -> WhatIfInsight | SafeFallback:
    """Map an internal ValidationResult to the typed DashboardPayload union.

    A passing result becomes a WhatIfInsight; a failure becomes a SafeFallback
    carrying the validator's reasons and the slot it replaced. (The failed
    result's ``output`` is the SAFE_FALLBACK dict, whose shape differs from the
    SafeFallback model — hence this translation rather than a direct splat.)
    """
    if result.passed:
        return WhatIfInsight(**result.output)
    reason = "; ".join(result.failures) or "validation failed"
    return SafeFallback(reason=reason, slot_index=slot_index)


def generate_insights(
    bundle_a: CountryBundle,
    bundle_b: CountryBundle,
    user_context: Any,
    *,
    client: Any | None = None,
    model_id: str = MODEL_ID,
) -> list[WhatIfInsight | SafeFallback]:
    """Produce the 7 Stage 3 insights with a single Gemini call.

    Makes one ``client.models.generate_content()`` call that returns all 7
    insights as a JSON array, then runs ``validate_output()`` on each item
    individually so per-slot ``SAFE_FALLBACK`` routing is preserved.

    Failure modes:
    - Top-level Gemini call fails (network, auth, parse) → 7 SafeFallback items.
    - Response parses but is not a list → 7 SafeFallback items.
    - Response has fewer than 7 items → missing slots filled with SafeFallback.
    - Individual item fails validation → that slot becomes SafeFallback.

    The caller always receives exactly 7 items.
    """
    slot_plan = _slot_plan(bundle_a, bundle_b)
    coverages = _slot_coverages(slot_plan)
    fact_bundle = {"bundle_a": bundle_a.model_dump(), "bundle_b": bundle_b.model_dump()}
    country_a = bundle_a.country or "Country A"
    country_b = bundle_b.country or "Country B"

    try:
        from google import genai
        from google.genai import types

        if client is None:
            client = genai.Client(api_key=settings.gemini_api_key)

        response = client.models.generate_content(
            model=model_id,
            contents=build_prompt(fact_bundle, user_context, slot_plan),
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=STAGE3_RESPONSE_SCHEMA,
                temperature=0.2,
            ),
        )
        parsed = getattr(response, "parsed", None)
        if parsed is None:
            import json
            parsed = json.loads(response.text)
    except Exception as exc:  # SDK missing, network, parse, auth — all fall back.
        reason = f"Stage 3 generation failed: {type(exc).__name__}: {exc}"
        return [SafeFallback(reason=reason, slot_index=i) for i in range(len(slot_plan))]

    if not isinstance(parsed, list):
        reason = "Stage 3 response was not a JSON array"
        return [SafeFallback(reason=reason, slot_index=i) for i in range(len(slot_plan))]

    insights: list[WhatIfInsight | SafeFallback] = []
    for i, scenario_type in enumerate(slot_plan):
        if i < len(parsed):
            item = parsed[i]
            # The caller owns scenario_type — stamp it so the model can't drift it.
            if isinstance(item, dict):
                item["scenario_type"] = scenario_type
            # Guarantee no generic "Country A/B" reaches the user, even if the model
            # ignored the prompt instruction for this slot.
            item = _relabel_countries(item, country_a, country_b)
            result = validate_output(item, fact_bundle, user_context, coverages[i])
        else:
            result = ValidationResult(
                False,
                ["slot missing from Stage 3 response"],
                build_safe_fallback(["slot missing from Stage 3 response"]),
            )
        insights.append(to_insight(result, i))
    return insights
