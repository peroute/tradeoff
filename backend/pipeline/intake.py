"""Stage 1 — Intake: validation and sanitization of the comparison request.

WHAT IT DOES
------------
parse_and_validate(request: CompareRequest) -> ParsedProfile

Takes the raw API request that arrived at POST /api/compare and returns a
clean ParsedProfile ready for the rest of the pipeline. It is the only place
in the codebase that touches raw user input before it flows into Gemini prompts
or data-source lookups — so correctness here protects every downstream stage.

HOW IT DOES IT
--------------
The function runs three layers of checks in order:

1. Business-rule guard — same-country rejection
   Pydantic enforces that country_a and country_b are both SupportedCountry
   literals, but it cannot enforce that they differ. We reject identical pairs
   here before any work is done.

2. Free-text sanitization (_sanitize)
   Three fields arrive as open strings from the user: citizenship, degree_field,
   and user_context. All three are later interpolated directly into Gemini prompts
   (Stage 2b and Stage 3). _sanitize strips characters and phrases that are
   commonly used in prompt-injection attacks: curly/square/angle braces,
   backslashes, and the phrases "ignore previous" and "system:". It also caps
   length (200 chars for short fields, 500 for user_context) to prevent
   oversized context payloads.

3. Degree-field normalization (_normalize_degree)
   degree_field is also used as a lookup key into field_soc_map.json, which maps
   degree labels to BLS SOC codes for US wage resolution. If the user typed
   "computer science" (lowercase), _normalize_degree maps it back to the
   canonical "Computer Science" key so the BLS lookup in fact_assembly.py
   succeeds. If the field is completely unrecognized (e.g. "Marine Biology"),
   it passes through sanitized — fact_assembly will miss the SOC code and fall
   back to OECD national wages, which is the documented degradation path.

4. Empty-after-sanitize rejection
   Edge case: a string made entirely of injection characters would sanitize down
   to an empty string. We explicitly reject that rather than letting an empty
   string propagate into prompts or lookups.

WHAT IT DOES NOT DO
-------------------
- It does not call any LLM or external API (zero I/O, runs in <1ms).
- It does not validate that citizenship is a real country — that's soft info
  used by Stage 2b (Gemini + Search grounding), not a lookup key.
- It does not re-validate SupportedCountry or CareerStage — Pydantic already
  enforces those as Literals at the API boundary; a 422 is returned before
  this function is ever called if those are wrong.

ERRORS
------
Raises ValueError with a descriptive message for any business-rule violation.
Pydantic ValidationError is raised upstream (by CompareRequest) for type
failures, never inside this function.
"""

import json
import re
from pathlib import Path

from backend.models.intake_models import CompareRequest, ParsedProfile

_FIELD_SOC_MAP_PATH = Path(__file__).parent.parent / "data" / "field_soc_map.json"
_KNOWN_FIELDS: set[str] = set(json.loads(_FIELD_SOC_MAP_PATH.read_text()).keys())

# Characters that could be used to escape/hijack a prompt template
_INJECTION_PATTERN = re.compile(r"[{}\[\]<>\\]|ignore\s+previous|system\s*:", re.IGNORECASE)


def _sanitize(value: str, max_len: int = 200) -> str:
    """Strip prompt-injection vectors and enforce length cap."""
    cleaned = _INJECTION_PATTERN.sub("", value).strip()
    return cleaned[:max_len]


def _normalize_degree(raw: str) -> str:
    """Return the canonical field_soc_map key if the input matches, else return sanitized raw."""
    # Exact match first
    if raw in _KNOWN_FIELDS:
        return raw
    # Case-insensitive fallback
    lower = raw.lower()
    for known in _KNOWN_FIELDS:
        if known.lower() == lower:
            return known
    return raw


def parse_and_validate(request: CompareRequest) -> ParsedProfile:
    """Validate business rules and sanitize free-text fields before they enter the pipeline."""
    if request.country_a == request.country_b:
        raise ValueError("country_a and country_b must be different countries.")

    citizenship = _sanitize(request.citizenship)
    degree_field = _normalize_degree(_sanitize(request.degree_field))
    user_context = _sanitize(request.user_context, max_len=500)

    if not citizenship:
        raise ValueError("citizenship must be a non-empty string.")
    if not degree_field:
        raise ValueError("degree_field must be a non-empty string.")
    if not user_context:
        raise ValueError("user_context must be a non-empty string.")

    return ParsedProfile(
        citizenship=citizenship,
        degree_field=degree_field,
        career_stage=request.career_stage,
        country_a=request.country_a,
        country_b=request.country_b,
        user_context=user_context,
    )
