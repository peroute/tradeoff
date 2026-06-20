# Tradeoff — Project Plan

**USAII Global AI Hackathon 2026 · Challenge Brief 3, Direction A · Deadline: June 21, 11:59 PM ET**

---

## What This Is

A country-destination comparator for international students and recent grads. The user enters their citizenship, degree field, two countries they're considering, and optionally a specific city within each country (e.g. Austin vs New York within the US). The system synthesizes what working in each destination would actually look like for someone with their exact profile — visa pathway, wages, cost of living, tax-adjusted take-home, immigration climate — then surfaces structured AI reasoning about the trade-offs.

No specific job offers required. The system builds the picture from market data. The differentiator is modeling real immigration constraints citizenship-by-citizenship, which most competing teams won't touch.

---

## Pipeline (Architecture B — locked)

```
1. Intake           (deterministic) — parse user profile
        ↓
2b-1. Route + Outlook research (AI call #1) — Gemini + Google Search grounding
        ↓                                      RUN ONCE PER COUNTRY (×2)
        ↓                                      raw text from approved gov sources
2b-2. Route + Outlook structure (AI call #2) — Gemini, no search
        ↓                                       response_schema=RouteAndOutlook
2a. Fact Assembly   (deterministic) — wages (BLS/OECD), CoL (World Bank→WhereNext→Numbeo),
        ↓                             tax calc, visa_rules.json enrichment via AI-resolved slug
3.  Reasoning       (AI call #3)   — Gemini structured output, 7 typed insights
        ↓
    Validate        (deterministic) — 6 rules, SAFE_FALLBACK on any failure
        ↓
4.  Sacrifice Diff  (deterministic) — 5-dimension cross-country comparison
        ↓
5.  Output          (dashboard)
```

**Four LLM calls per comparison.** Stage 2b = 3 calls: Call #1 runs once per country (2 grounded research calls) + Call #2 structures the combined output (1 call). Stage 3 = 1 call: one Gemini call that receives all 7 required scenario types in the prompt and returns a JSON array of 7 insights; the validator then runs on each item individually so per-slot SAFE_FALLBACK still works. The Stage 2b per-country split was adopted June 20 — a single combined call let the model ground only the first country and answer the second from memory. Everything outside these 4 calls is deterministic. Stage 2b runs before 2a because the AI-resolved visa slug is needed for curated enrichment lookup.

---

## Country Scope (locked)

**Supported destinations:** US, UK, Canada, Australia, Germany, France

Any other destination: wage/CoL still rendered, visa flagged as "not yet modeled." Never fabricated.

---

## Data Sources

| Source | Type | Covers |
|---|---|---|
| OECD Data API (`sdmx.oecd.org`) | Live API, no key | National average wages + PPP conversion factors, all 6 countries |
| BLS Public Data API (`api.bls.gov`) | Live API | US wages by occupation (SOC code); national when no SOC match found |
| World Bank Open Data API (`api.worldbank.org`) | Live API, no key | National price-level index (PLI = PPP/XR × 100, US = 100), all 6 countries — **primary CoL source** |
| WhereNext (`getwherenext.com`, CC BY 4.0) | Live API, no key | National cost index (US = 100); aggregates World Bank ICP / Eurostat — **secondary CoL source** when World Bank unavailable |
| `data_sources/numbeo.py` (curated mock) | Curated, offline fallback | Curated national CoL indices (NYC = 100 shape); last-resort when both live CoL sources fail; flagged `is_mock=True` |
| `data/visa_rules.json` | Curated, cited, dated | Visa enrichment: lottery history, partner work rights, PR timeline, salary floor — for 6 known visa slugs |
| `data/official_source_registry.json` | Hardcoded | Approved government URLs per destination country — the only sources Stage 2b is allowed to extract from |
| `data/tax_rates.json` | Curated, cited | Income tax brackets + social contribution rates, all 6 countries |
| `data/field_soc_map.json` | Curated | Degree field → BLS SOC code |
| Gemini + Google Search grounding | Live AI call, Stage 2b only | Visa route resolution + immigration policy trends + career context |

**Resolution gaps (disclosed via `PrecisionCaveat` on dashboard):**
- Wages: US + known degree field → BLS occupation-level national wage (SOC code from `field_soc_map.json`). US + unknown field or any non-US country → OECD national average. Resolution is never equivalent across countries.
- CoL: World Bank national PLI (primary live) → WhereNext national index (secondary live) → Numbeo curated mock (last resort). All three sources are national-level — no city tier is available. Every bundle always tags `col_source: "national_ppp"`.

---

## Visa Route Resolution (Stage 2b)

Routing is **fully AI-resolved** — no hardcoded citizenship → visa mapping table. Stage 2b's Gemini + Search call (one grounded call per country) searches the approved official government sources for the destination country and identifies the applicable work visa path for the user's citizenship and degree field. Call #1 uses plain natural-language queries — no `site:` boolean operators (they mangled the search-tool queries without reliably constraining grounding). Trust is enforced downstream instead: call #2 pins `source_url` to the approved registry list, and a deterministic verifier cross-checks every `source_url` against both the registry and call #1's grounding metadata (verified / claimed / unapproved → keep / down-one-notch / force-low). No URL is ever substituted.

`visa_rules.json` provides **enrichment only** for known visa slugs (lottery history, partner work rights, exact conditions). When the AI-resolved slug matches a key in `visa_rules.json`, the curated facts are merged in. When it doesn't, only the AI-extracted facts are used.

The `routing_confidence` field (high / medium / low) and `source_url` are always shown on the dashboard.

---

## AI Calls — Contracts

### Stage 2b — `RouteAndOutlook` (Gemini + Google Search grounding)

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

**Prompt constraints:** Only extract from approved source registry URLs; `source_url` is pinned to that registry list in call #2 and verified deterministically against the registry + grounding metadata. Do not state hard salary thresholds or PR timelines as facts — those are validated separately. Note uncertainty explicitly.

### Stage 3 — `WhatIfInsight` (Gemini, no search, structured output)

```json
{
  "scenario_type": "base | lottery_risk | extension_risk | employer_switch | partner_work | pr_timeline | priority_match | synthesis",
  "fact_used": "exact dot-notation key from fact bundle",
  "context_used": "verbatim phrase from user_context",
  "connection": "shared vocabulary between fact_used and context_used",
  "consideration": "the non-obvious second-order implication",
  "confidence": "high | medium | low",
  "confidence_basis": "string",
  "next_action": "verb-led specific instruction"
}
```

**7 insights per comparison, slot plan determined by `_slot_plan()` in `reasoning_step.py`:**

| Slot | `scenario_type` | Rule |
|---|---|---|
| 1–2 | `base` | fixed — always two base insights |
| 3–4 | dynamic contingency | `_contingency_scenarios()` picks the two most relevant granular risk types present in either bundle |
| 5–6 | `priority_match` | fixed — always two priority_match insights |
| 7 | `synthesis` | fixed — always one synthesis insight |

**Contingency priority order (highest to lowest):** `lottery_risk` > `partner_work` > `employer_switch` > `pr_timeline` > `extension_risk` (fallback — always eligible). The first two eligible scenario types from this list fill slots 3 and 4.

Stage 3 is **one Gemini call** that receives all 7 required scenario types in the prompt and returns a JSON array of 7 insights. The validator then runs on each item individually — per-slot SAFE_FALLBACK still works; only the failing slot is replaced.

**Prompt constraint:** `consideration` must state something NOT immediately obvious from the fact alone. Do not recommend which country to choose.

### `validate_output()` — 6 rules (in `reasoning_step.py`)

1. `fact_used` ∈ `_flatten_keys(bundle_a) ∪ _flatten_keys(bundle_b)` (via `_flatten_keys()` in `reasoning_step.py`)
2. `context_used` substring-matches `user_context`
3. `connection` shares vocabulary with both `fact_used` and `context_used`
4. `consideration` not in boilerplate phrases list
5. `next_action` first word is in imperative verb set
6. `scenario_type` ∈ `{"base", "lottery_risk", "extension_risk", "employer_switch", "partner_work", "pr_timeline", "priority_match", "synthesis"}`

Any failure → `SafeFallback(type="safe_fallback", reason="rule_N_failed", slot_index=N)`. Never `None`. Always visible on dashboard.

`_flatten_keys()` (in `reasoning_step.py`) is the single source of truth — used by both `build_prompt()` and `validate_output()`. They must never diverge.

---

## Sacrifice Diff — 5 Dimensions

| Dimension | Source |
|---|---|
| `net_takehome_ppp` | Gross wage → tax brackets → ÷ CoL index (city-level if available, OECD PPP otherwise) |
| `visa_stability_score` | Formula: base − trend_penalty − lottery_penalty (see below) |
| `pr_timeline_years` | `visa_rules.json` curated or AI-extracted |
| `lottery_risk` | `1 − lottery_cumulative_3yr`; null if no lottery |
| `partner_opportunity` | `full | restricted | none` from visa_rules.json |

**visa_stability_score formula** (documented inline in source for judges):
```
base = (0 if employer_sponsorship_required else 1)
       + (1 if can_switch_employer else 0)
       + max(0, (10 - path_to_pr_years) / 10)
trend_penalty  = 0.3 if trend_direction == "restrictive" else 0
lottery_penalty = (1 - lottery_cumulative_3yr) * 0.5 if lottery_required else 0
score = max(0.0, base - trend_penalty - lottery_penalty) / 2.5
```

This is the one place where AI-sourced signal (`trend_direction` from Stage 2b) combines with deterministic scoring.

---

## Responsible AI Commitments

- **AI never recommends which country to choose.** `HumanBoundaryBanner` is pinned at the bottom of the dashboard, always visible, contrasting background: *"These insights are for your consideration. No recommendation is made. You decide."*
- **SAFE_FALLBACK is visible, not hidden.** Any insight that fails validation shows `SafeFallbackNotice`: *"One analysis point was withheld because it could not be verified against source data."*
- **`pipeline_meta` panel** (collapsible "How this was built") shows: number of AI calls made, which facts came from which source, how many insights passed vs. were withheld, `routing_confidence` per country.
- **Every curated fact has a `source_url` and `last_verified` date**, visible on the VisaPanel.
- **Precision caveat** disclosed on WagePanel and CoLPanel: wage resolution (BLS metro vs OECD national) and CoL resolution (city index vs national PPP) vary per destination and are always labeled. `col_source` tag in the fact bundle drives which caveat is shown.

---

## API

### `POST /api/compare`
```json
// Request
{
  "citizenship": "India",
  "degree_field": "Computer Science",
  "career_stage": "new_grad",
  "country_a": "US",
  "country_b": "France",
  "user_context": "I care most about long-term residency stability and not being tied to one employer. My partner is also looking for work."
}
// career_stage ∈ new_grad | early_career | mid_career | senior
// country_a / country_b must be one of the six supported destinations (Literal enforced at API boundary — 422 otherwise)
// Note: no city_a / city_b — all wage and CoL data is national-level for all destinations

// Response: DashboardPayload
// bundle_a, bundle_b, outlook_a, outlook_b, insights[], sacrifice_map, pipeline_meta
```

### `GET /api/visa/{country}` — curated enrichment for a destination country
### `GET /api/health` — `{"status": "ok", "visa_rules_loaded": true, ...}`

---

## Current Status (June 20)

### Done

**Backend — all pipeline stages built and tested:**
- ✓ `pipeline/intake.py` — Stage 1: parse, sanitize, normalize, validate
- ✓ `pipeline/immigration_outlook.py` — Stage 2b: per-country grounded research (Call #1 ×2) + structured output (Call #2) + deterministic source verification
- ✓ `pipeline/fact_assembly.py` — Stage 2a: wages (BLS/OECD), CoL (World Bank→WhereNext→Numbeo), tax calc, visa enrichment lookup
- ✓ `pipeline/reasoning_step.py` — Stage 3: `generate_insights()` (7 slots, one Gemini call per slot), `validate_output()` (6 rules), `build_prompt()`, `to_insight()`, `_slot_plan()`, `_contingency_scenarios()`, `_flatten_keys()`
- ✓ `pipeline/sacrifice_diff.py` — Stage 4: 5-dimension sacrifice map with `visa_stability_score` formula
- ✓ `data_sources/` — oecd, bls, worldbank, wherenext, numbeo, tax, visa_rules (all with graceful fallback)
- ✓ `models/` — all Pydantic schemas: intake_models, ai_models, fact_models, output_models
- ✓ `data/` — visa_rules.json, tax_rates.json, field_soc_map.json, official_source_registry.json
- ✓ `routers/` — health, visa, compare (compare still uses sample stub — see below)
- ✓ Tests for all pipeline stages and data sources

**Frontend — intake and loading complete; dashboard partial:**
- ✓ `IntakePage` — full form: profile, country picker, priorities, submit + loading overlay
- ✓ `LoadingPage` / `GeneratingScreen` — animated path convergence, pipeline stage messaging
- ✓ Dashboard components built: `SacrificeMap`, `WagePanel`, `VisaPanel`, `OutlookCard`, `WhatIfList`, `WhatIfCard`, `HumanBoundaryBanner`, `ConfidenceChip`, `PrecisionCaveat`, `SafeFallbackNotice`, `SourceCitation`, `NotModeledBadge`
- ✓ `DashboardPage` — partial: currently mounts only `SacrificeMap` + `WagePanel`

### Remaining (submission-blocking)

1. **`pipeline/orchestrator.py`** — `run_pipeline(request) -> DashboardPayload` needs to be implemented. Wire order: intake → 2b (per-country research ×2 + structure) → 2a (fact assembly ×2) → reasoning (7 slots) → sacrifice_diff. The file currently contains only a comment stub.
2. **`routers/compare.py`** — replace `build_sample_payload()` call with `run_pipeline()` once orchestrator lands.
3. **`DashboardPage.tsx`** — mount the remaining built components: `VisaPanel`, `OutlookCard`, `WhatIfList` (with `HumanBoundaryBanner` pinned, `SafeFallbackNotice` visible, `pipeline_meta` collapsible panel).

---

## Tech Stack

**Backend:** Python 3.11+, FastAPI, Uvicorn, Pydantic v2, pydantic-settings, google-generativeai, httpx

**Frontend:** React 18, TypeScript, Vite, Tailwind CSS, React Router v6

**No LangChain. No MCP. No database. No ETL.**
