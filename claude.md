# Post-grad decision comparator — USAII Global AI Hackathon 2026

Challenge Brief 3, Direction A. Submission deadline June 21, 11:59 PM ET.

## What this is

A comparator for a single decision type: job offer vs. job offer, across countries. Not job vs. grad school — that was cut deliberately to keep one data domain instead of two. The differentiator is modeling real visa/residency constraints across countries, which most competing teams won't touch.

## Country scope (locked — do not add countries without updating this file)

US, UK, Canada, Australia, Germany, France. Chosen by actual international-student/grad enrollment volume, not arbitrary. Wage/cost-of-living comparisons work for any country via live APIs (see below) — only the curated visa-rules table is capped to these six. If a user enters a seventh country, the system should degrade gracefully (show wage/cost-of-living, flag visa specifics as "not yet modeled") rather than fabricate or silently fail.

## Architecture (locked — this is "architecture B," chosen over a 3-call chained version; do not collapse stages or add a third LLM call without discussing first)

```
Intake (deterministic)
  -> Fact assembly (deterministic: live APIs + ingested DB + curated table)
  -> Immigration outlook (AI call #1: Gemini + Google Search grounding, structured output)
  -> What-if reasoning (AI call #2: Gemini, reasoning_step.py)
  -> Validate (deterministic: reasoning_step.py validate_output(), routes failures to SAFE_FALLBACK)
  -> Sacrifice map diff (deterministic, cross-option comparison)
  -> Output (dashboard)
```

Only stages 2b and 3 call a model. This asymmetry is the answer to "why does this need AI" in the judging rubric — don't let it erode by routing intake, fact assembly, or the diff step through a model.

## Contracts — match these exactly, don't improvise field names

**Stage 3 output schema** (enforced via Gemini structured output / `response_schema`, gemini-2.5-flash):
```json
{
  "fact_used": "string — must be a real key from the fact bundle, e.g. france_passeport_talent.min_salary_eur",
  "context_used": "string — must be something the user actually said in intake",
  "connection": "string — must share real vocabulary with both fact_used and context_used",
  "consideration": "string — the actual insight, not generic boilerplate",
  "confidence": "high | medium | low",
  "confidence_basis": "string — why this confidence level",
  "next_action": "string — a real verb-led instruction, not vague advice"
}
```

**Stage 2b output schema** (Gemini + google_search tool, structured output):
```json
{
  "trend_summary": "string",
  "source_url": "string",
  "source_publish_date": "string",
  "confidence": "high | medium | low"
}
```

**`validate_output()`** (already built in `reasoning_step.py`) checks `fact_used` matches a real fact, `context_used` was actually said by the user, `connection` has real overlapping vocabulary with both, `consideration` isn't boilerplate, `next_action` is verb-led. Any failure -> `SAFE_FALLBACK`, never show unvalidated model output.

## Data sources — do not invent facts, do not call an LLM to "look up" a hard fact

| Source | Mechanism | Covers |
|---|---|---|
| OECD Data API (`sdmx.oecd.org`, SDMX REST, no key) | live call | wages/earnings, national/annual level, all 6 locked countries in one schema — primary wage source |
| BLS Public Data API (`api.bls.gov`) | live call, optional supplement | US wages by occupation/metro area, finer-grained than OECD for US only |
| Numbeo Cost of Living API | live call | cost of living, any city |
| USCIS H-1B Employer Data Hub + DOL OFLC LCA | quarterly bulk file, ingested into our own DB via a one-time ETL script | US sponsorship history |
| Curated visa-rule JSON (`data/visa_rules.json`) | manually researched, cited, dated | salary thresholds, employer-switch rules for the 6 locked countries |
| Gemini + Google Search grounding | live AI call, stage 2b only | immigration policy trend/outlook — soft information only, never hard facts |

Note: OECD's granularity is national/annual-average, coarser than BLS's occupation-and-metro detail. State this honestly in the dashboard rather than implying matched precision across countries — a US figure from BLS and a France figure from OECD aren't measuring at the same resolution.

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

Every entry needs a real `source_url` from the country's official immigration site and a `last_verified` date. Spot-check the two hardest-leaning facts (salary threshold, switch-employer rule) against the source link before submission — don't trust a drafted entry unverified, since this is the data the whole pitch depends on being real.

## Hard constraints

- No LangChain, no MCP — the brief's own kickoff Q&A says judges score justification, not architecture-by-name; both would add surface area with no judging benefit here.
- No third LLM call. If a new feature seems to need one, that's a signal to push it into the deterministic diff/output stage instead.
- Curated visa facts are never look-up targets for the search-grounded call — only the outlook/trend stage touches live search.
- The AI never states which option to choose. That's the human-in-the-loop boundary — keep it enforced in the output stage, not just mentioned in prose.

## Judging criteria map (for anyone touching a given stage — know what you're being scored on)

- Intake, fact assembly, validate, diff: Solution design (25%), Responsible AI (10%)
- Stage 2b (outlook): AI reasoning (30%), Impact & insight (15%)
- Stage 3 (what-if reasoning): AI reasoning (30%) — this is the core of the score
- Output/dashboard: Responsible AI (10%) — human-in-the-loop, decision moment must be visually labeled, not implicit