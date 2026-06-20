# Post-grad decision comparator — USAII Global AI Hackathon 2026

Challenge Brief 3, Direction A. Submission deadline June 21, 11:59 PM ET.

## What this is

A country-destination comparator for international students and recent grads. The user enters their citizenship, degree field, and two countries they're considering working in. No specific job offers required — the system builds the picture from market data. The differentiator is modeling real immigration constraints citizenship-by-citizenship, which most competing teams won't touch.

## Country scope (locked — do not add countries without updating this file)

US, UK, Canada, Australia, Germany, France. Chosen by actual international-student/grad enrollment volume, not arbitrary. Wage/cost-of-living comparisons work for any country via live APIs (see below) — only the curated visa-rules table is capped to these six.

**Scope enforcement (no in-prompt 7th-country degradation needed):** The 6-country scope is enforced in two layers, so an unsupported country can never reach the pipeline. (1) The intake UI offers only these six via a fixed dropdown. (2) `country_a`/`country_b` are typed as `SupportedCountry = Literal["US", "UK", "Canada", "Australia", "Germany", "France"]` on `CompareRequest` (the API boundary) and `ParsedProfile` in `intake_models.py` — so a 7th country is rejected with a `422` before Stage 2b runs. Stage 2b therefore assumes a valid, supported country and does not implement graceful degradation for unmodeled countries. If you ever widen scope, update the `Literal`, the dropdown, and the curated JSON tables together.

## Architecture (locked — "architecture B"; 4 LLM calls per comparison; do not add more without discussing first)

```
Intake (deterministic)
  -> Route + Outlook research (AI call #1: Gemini + Google Search grounding, raw text) — RUN ONCE PER COUNTRY (×2)
  -> Route + Outlook structure (AI call #2: Gemini no search, response_schema=RouteAndOutlook)
  -> Fact assembly (deterministic: live APIs + visa_rules.json enrichment using AI-resolved slug)
  -> What-if reasoning (AI call #3: Gemini no search, reasoning_step.py)
  -> Validate (deterministic: reasoning_step.py validate_output(), routes failures to SAFE_FALLBACK)
  -> Sacrifice map diff (deterministic, cross-option comparison)
  -> Output (dashboard)
```

Stage 2b is split into call #1 (research, with Google Search grounding) + call #2 (structure, no search) because Google Search grounding and structured JSON output cannot be reliably combined in one SDK call. This split was chosen on June 19 for reliability over the original single-call design.

**Call #1 runs once per country (updated June 20).** A single combined two-country research call let `gemini-2.5-flash` spend its whole search budget on the first country and answer the second from parametric memory (ungrounded) — we observed a country grounding on zero sources, then being force-lowed in verification. One grounded call per country guarantees each country is actually searched. So a comparison makes **3 Stage-2b calls** (2 research + 1 structure) and **4 LLM calls total** (+ Stage 3).

Call #1 query style (updated June 20): plain natural-language queries — we deliberately do NOT inject `site:` boolean operators. Appending an OR-chain of `site:` filters made the search-tool rewriter mangle/truncate queries without reliably constraining grounding. Trust is enforced downstream (call #2 `source_url` pinning + deterministic verification), not via query operators.

Call #2 takes the concatenated per-country research text and enforces the RouteAndOutlook schema via response_schema, `temperature=0`. Its `source_url` is **pinned to the approved registry list** (the prompt injects the allowlist and forbids inventing/modifying a URL) — this stopped the model fabricating off-registry citations that the verifier then had to force-low. The visa slug resolved in call #2 is required for the `visa_rules.json` enrichment lookup before fact assembly can run.

## Contracts — match these exactly, don't improvise field names

**Stage 2b output schema** (`RouteAndOutlook`, Gemini + Google Search grounding):
```json
{
  "visa_route_a": {
    "visa_slug": "us_h1b",
    "visa_name": "string",
    "eligibility_summary": "string",
    "employer_sponsorship_required": true,
    "path_to_residency_years": 6,
    "key_constraint": "string",
    "routing_confidence": "high | medium | low",
    "source_url": "string",
    "source_retrieved": "string"
  },
  "visa_route_b": { "..." },
  "country_a_outlook": {
    "trend_summary": "string",
    "trend_direction": "improving | stable | restrictive",
    "key_recent_change": "string",
    "career_context": "string",
    "source_url": "string",
    "source_publish_date": "string",
    "confidence": "high | medium | low"
  },
  "country_b_outlook": { "..." }
}
```

Prompt constraint: only extract from `official_source_registry.json` approved URLs. `source_url` is pinned to that registry list in call #2 and then cross-checked deterministically against BOTH the registry AND call #1 grounding metadata (verdicts: verified / claimed / unapproved → keep / down-one-notch / force-low). Do not state hard salary thresholds or PR timelines as facts — those are validated separately via `visa_rules.json`.

**Stage 3 output schema** (`WhatIfInsight`, Gemini no search, structured output, 7 insights per request: 2 base, 2 contingency, 2 priority_match, 1 synthesis — where "contingency" is a category filled by any of the granular risk scenario types below):
```json
{
  "scenario_type": "base | lottery_risk | extension_risk | employer_switch | partner_work | pr_timeline | priority_match | synthesis",
  "fact_used": "exact dot-notation key from fact bundle",
  "context_used": "verbatim phrase from user_context",
  "connection": "shared vocabulary between fact_used and context_used",
  "consideration": "the non-obvious second-order implication",
  "confidence": "high | medium | low",
  "confidence_basis": "string — why this confidence level",
  "next_action": "verb-led specific instruction"
}
```

Prompt constraint: `consideration` must state something NOT immediately obvious from the fact alone. Do not recommend which country to choose.

**`validate_output()`** (already built in `reasoning_step.py`) enforces 6 rules:
1. `fact_used` ∈ `_flatten_bundle_keys(bundle_a) ∪ _flatten_bundle_keys(bundle_b)`
2. `context_used` substring-matches `user_context`
3. `connection` shares vocabulary with both `fact_used` and `context_used`
4. `consideration` not in boilerplate phrases list
5. `next_action` first word is in imperative verb set
6. `scenario_type` ∈ `{"base", "lottery_risk", "extension_risk", "employer_switch", "partner_work", "pr_timeline", "priority_match", "synthesis"}` (the `ScenarioType` literal in `ai_models.py` is the source of truth)

Any failure → `SAFE_FALLBACK`, never show unvalidated model output.

`_flatten_bundle_keys()` is the single source of truth — used by both the prompt builder and the validator. They must never diverge.

## Data sources — do not invent facts, do not call an LLM to "look up" a hard fact

| Source | Mechanism | Covers |
|---|---|---|
| OECD Data API (`sdmx.oecd.org`, SDMX REST, no key) | live call | wages/earnings + PPP conversion factors, national/annual level, all 6 locked countries |
| BLS Public Data API (`api.bls.gov`) | live call | US wages by occupation (SOC code); metro-area (MSA) wages when a US city is provided |
| `data/cost_of_living.json` | curated, cited, dated | CoL index (Numbeo scale, NYC=100) for ~20 major cities across the 6 countries; OECD PPP used as national-level fallback when city not in table or no city provided |
| `data/visa_rules.json` | curated, cited, dated | enrichment for known visa slugs: lottery history, partner work rights, PR timeline, salary floor |
| `data/official_source_registry.json` | hardcoded | approved government URLs per destination country — the only sources Stage 2b is allowed to extract from |
| `data/tax_rates.json` | curated, cited | income tax brackets + social contribution rates, all 6 countries |
| `data/field_soc_map.json` | curated | degree field → BLS SOC code |
| Gemini + Google Search grounding | live AI call, Stage 2b only | visa route resolution + immigration policy trends + career context — soft information only, never hard facts |

Resolution gaps (disclosed via `PrecisionCaveat` on dashboard):
- Wages: US city provided → BLS metro-area. US no city → BLS national. Non-US → OECD national average. Not the same resolution across countries.
- CoL: city in `cost_of_living.json` → city-level index. Otherwise → OECD PPP national. Each fact bundle tags `col_source: "city" | "national_ppp"` so the dashboard shows the right caveat.
- Non-US wage data is always national — providing a city for UK/Canada/etc. improves CoL precision only, not wage precision.

No database. No ETL.

## Curated visa JSON schema

```json
{
  "<country>_<visa_name_slug>": {
    "country": "string",
    "visa_name": "string",
    "min_salary": "number",
    "currency": "string",
    "employer_sponsorship_required": "boolean",
    "can_switch_employer": "boolean",
    "switch_conditions": "string",
    "path_to_pr_years": "number",
    "source_url": "string",
    "last_verified": "YYYY-MM-DD"
  }
}
```

Every entry needs a real `source_url` from the country's official immigration site and a `last_verified` date. Spot-check the two hardest-leaning facts (salary threshold, switch-employer rule) against the source link before submission.

## Cost of living JSON schema

```json
{
  "<city_slug>": {
    "city": "string",
    "country": "string",
    "col_index": 100,
    "source_url": "string",
    "last_verified": "YYYY-MM-DD"
  }
}
```

Index is on the Numbeo scale (NYC = 100). Values are read manually from Numbeo's public city pages (no API key needed for reading the website) and committed as static data. When a user-provided city slug is not found here, `cost_of_living.py` falls back to OECD PPP for the country and sets `col_source = "national_ppp"`.

## Hard constraints

- No LangChain, no MCP — the brief's own kickoff Q&A says judges score justification, not architecture-by-name; both would add surface area with no judging benefit here.
- Four LLM calls per comparison (Stage 2b = 3: one grounded research call PER COUNTRY [2] + one structuring call [1]; Stage 3 = 1). Updated June 20 from the original 3-call design: the per-country split was required because a single combined research call left the second country ungrounded. Do not add more without discussing first.
- Curated visa facts are never look-up targets for the search-grounded call — only the outlook/trend stage touches live search.
- The AI never states which option to choose. That's the human-in-the-loop boundary — keep it enforced in the output stage, not just mentioned in prose. `HumanBoundaryBanner` must be pinned, always visible, contrasting background.

## Judging criteria map (for anyone touching a given stage — know what you're being scored on)

- Intake, fact assembly, validate, diff: Solution design (25%), Responsible AI (10%)
- Stage 2b (Route + Outlook): AI reasoning (30%), Impact & insight (15%)
- Stage 3 (what-if reasoning): AI reasoning (30%) — this is the core of the score
- Output/dashboard: Responsible AI (10%) — human-in-the-loop, decision moment must be visually labeled, not implicit
