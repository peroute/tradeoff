"""Stage 3 — What-if reasoning (AI call #2) and the deterministic validator gate.

This module owns two things, in this order of importance:

1. ``validate_output()`` — the deterministic Responsible-AI gate. It is pure,
   dependency-free (stdlib only), and never calls a model. Every field of a
   Stage 3 result is checked against the *actual* fact bundle and the *actual*
   user intake. Any failure routes to ``SAFE_FALLBACK``; unvalidated model
   output is never returned to the caller. This is the keystone of the pitch.

2. ``generate_reasoning()`` — the Gemini call (gemini-2.5-flash) that produces a
   Stage 3 result via structured output (``response_schema``). It always runs
   its result through ``validate_output()`` before returning, so a caller that
   uses this function can never surface raw model text.

Stage 3 output contract (CLAUDE.md — match field names exactly):
    fact_used         str  — a real key from the fact bundle
    context_used      str  — something the user actually said in intake
    connection        str  — shares real vocabulary with fact_used AND context_used
    consideration     str  — the actual insight, not boilerplate
    confidence        str  — "high" | "medium" | "low"
    confidence_basis  str  — why this confidence level
    next_action       str  — a verb-led instruction

Key-convention note: the validator checks ``fact_used`` against the *flattened
keys the bundle actually emits*, so it is agnostic to whether a value key is
``min_salary`` or ``min_salary_eur`` (the two conventions in CLAUDE.md). It
validates against reality, not against the illustrative example.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable, get_args

from backend.models.ai_models import SafeFallback, ScenarioType, WhatIfInsight
from backend.models.output_models import CountryBundle

# ---------------------------------------------------------------------------
# Contract constants
# ---------------------------------------------------------------------------

MODEL_ID = "gemini-2.5-flash"  # Stage 3 model, per CLAUDE.md

REQUIRED_FIELDS = (
    "scenario_type",
    "fact_used",
    "context_used",
    "connection",
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
STAGE3_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "scenario_type": {"type": "string", "enum": sorted(VALID_SCENARIO_TYPES)},
        "fact_used": {"type": "string"},
        "context_used": {"type": "string"},
        "connection": {"type": "string"},
        "consideration": {"type": "string"},
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        "confidence_basis": {"type": "string"},
        "next_action": {"type": "string"},
    },
    "required": list(REQUIRED_FIELDS),
    "propertyOrdering": list(REQUIRED_FIELDS),
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
    "apply", "ask", "assess", "budget", "calculate", "check", "choose",
    "compare", "compile", "confirm", "consult", "contact", "convert", "cross-check",
    "document", "draft", "email", "estimate", "evaluate", "examine", "factor",
    "file", "gather", "identify", "list", "map", "measure", "model", "negotiate",
    "note", "obtain", "plan", "prioritize", "quantify", "rank", "reassess",
    "recalculate", "request", "research", "review", "schedule", "secure",
    "shortlist", "submit", "trace", "track", "validate", "verify", "weigh",
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
    "fact_used": None,
    "context_used": None,
    "connection": None,
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

    Both branch paths (``france_passeport_talent``) and leaf paths
    (``france_passeport_talent.min_salary``) are included, so ``fact_used`` may
    reference either a whole fact group or a specific field.
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


# ---------------------------------------------------------------------------
# The gate
# ---------------------------------------------------------------------------


def validate_output(
    output: Any,
    fact_bundle: dict[str, Any],
    raw_context: Any,
) -> ValidationResult:
    """Deterministically validate a Stage 3 result.

    Checks (any failure -> SAFE_FALLBACK):
      * schema:        all required fields present, confidence in the enum.
      * fact_used:     is a real flattened key of ``fact_bundle``.
      * context_used:  most of its content words appear in what the user said.
      * connection:    shares real vocabulary with BOTH fact_used and context_used.
      * consideration: long enough and not boilerplate.
      * next_action:   verb-led (first content word is an action verb).

    Returns a ``ValidationResult`` whose ``output`` is always safe to display.
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

    # Rule 6 (CLAUDE.md): scenario_type must be a real ScenarioType value.
    scenario_type = output.get("scenario_type")
    if not isinstance(scenario_type, str) or scenario_type not in VALID_SCENARIO_TYPES:
        failures.append(f"scenario_type not in ScenarioType: {scenario_type!r}")

    # If the shape is already broken, stop here — later checks assume strings.
    if failures:
        return ValidationResult(False, failures, build_safe_fallback(failures))

    fact_used = output["fact_used"]
    context_used = output["context_used"]
    connection = output["connection"]
    consideration = output["consideration"]
    next_action = output["next_action"]

    # --- fact_used is a real key -------------------------------------------
    real_keys = _flatten_keys(fact_bundle)
    if fact_used not in real_keys:
        failures.append(
            f"fact_used {fact_used!r} is not a real key in the fact bundle"
        )

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

    # --- connection shares vocab with BOTH ---------------------------------
    conn_tokens = set(_tokenize(connection))
    fact_vocab = _key_tokens(fact_used) if isinstance(fact_used, str) else set()
    fact_overlap = conn_tokens & fact_vocab
    ctx_overlap = conn_tokens & set(ctx_tokens)
    if len(fact_overlap) < _MIN_OVERLAP_TOKENS:
        failures.append("connection shares no vocabulary with fact_used")
    if len(ctx_overlap) < _MIN_OVERLAP_TOKENS:
        failures.append("connection shares no vocabulary with context_used")

    # --- consideration is a real insight -----------------------------------
    low_consideration = consideration.lower()
    if any(marker in low_consideration for marker in _BOILERPLATE_MARKERS):
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
    return ValidationResult(True, [], dict(output))


# ---------------------------------------------------------------------------
# Stage 3 generation (Gemini)
# ---------------------------------------------------------------------------


def build_prompt(fact_bundle: dict[str, Any], raw_context: Any, scenario_type: str) -> str:
    """Assemble the Stage 3 what-if prompt from real facts and real intake.

    The model is told to ground every field in the supplied material and to use
    only keys present in the bundle — the same things ``validate_output`` later
    enforces deterministically. ``scenario_type`` frames which what-if angle to
    reason about; the caller (not the model) owns it, so the prompt states it as
    a given rather than asking the model to choose.
    """
    real_keys = sorted(_flatten_keys(fact_bundle))
    keys_block = "\n".join(f"  - {k}" for k in real_keys)
    said = _normalize_context(raw_context)
    return (
        "You are the what-if reasoning step in a post-grad job-offer comparator.\n"
        "Surface ONE concrete consideration that connects a specific assembled "
        "fact to something the user actually told us. You never state which "
        "option to choose.\n\n"
        f"Reason specifically about the '{scenario_type}' scenario.\n\n"
        "Rules:\n"
        "  * fact_used MUST be exactly one of the keys listed below.\n"
        "  * context_used MUST be drawn from what the user said.\n"
        "  * connection MUST reuse real words from both.\n"
        "  * consideration MUST be a specific insight, not generic advice.\n"
        "  * next_action MUST start with an action verb.\n\n"
        f"Available fact keys:\n{keys_block}\n\n"
        f"What the user said:\n{said}\n"
    )


def generate_reasoning(
    fact_bundle: dict[str, Any],
    raw_context: Any,
    *,
    scenario_type: str,
    client: Any | None = None,
    model_id: str = MODEL_ID,
) -> ValidationResult:
    """Run the Stage 3 Gemini call and validate the result before returning.

    ``scenario_type`` is the what-if angle for this slot, owned by the caller so
    the pipeline can guarantee its fixed composition (e.g. 2 base, 2 contingency,
    2 priority_match, 1 synthesis). It is stamped authoritatively onto the parsed
    output before validation, so the model cannot drift it to an invalid value.

    The Gemini SDK (``google-genai``) is imported lazily so this module — and
    in particular ``validate_output`` — can be used and tested without the SDK
    or an API key installed. ``client`` may be injected (tests, reuse); when
    None a default ``genai.Client()`` is constructed (reads GEMINI_API_KEY /
    GOOGLE_API_KEY from the environment per the SDK's own resolution).

    The return value's ``output`` is always safe to display: validated model
    output, or SAFE_FALLBACK on any validation or call failure.
    """
    try:
        from google import genai
        from google.genai import types

        if client is None:
            client = genai.Client()

        response = client.models.generate_content(
            model=model_id,
            contents=build_prompt(fact_bundle, raw_context, scenario_type),
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
        return ValidationResult(False, [reason], build_safe_fallback([reason]))

    # The caller owns scenario_type — stamp it so the model can't drift it.
    if isinstance(parsed, dict):
        parsed["scenario_type"] = scenario_type

    return validate_output(parsed, fact_bundle, raw_context)


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
    """Produce the 7 Stage 3 insights, ready to drop into DashboardPayload.

    Orchestrator entry point. Builds the fact bundle once in the
    ``{"bundle_a": ..., "bundle_b": ...}`` shape that ``validate_output`` expects,
    runs one Gemini call per slot, and maps every result to the typed union so a
    failed slot surfaces as a SafeFallback rather than vanishing.
    """
    fact_bundle = {"bundle_a": bundle_a.model_dump(), "bundle_b": bundle_b.model_dump()}
    insights: list[WhatIfInsight | SafeFallback] = []
    for i, scenario_type in enumerate(_slot_plan(bundle_a, bundle_b)):
        result = generate_reasoning(
            fact_bundle,
            user_context,
            scenario_type=scenario_type,
            client=client,
            model_id=model_id,
        )
        insights.append(to_insight(result, i))
    return insights
