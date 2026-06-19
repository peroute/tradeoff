# Tradeoff — Project Plan

**USAII Global AI Hackathon 2026 · Challenge Brief 3, Direction A · Deadline: June 21, 11:59 PM ET**

---

## What This Is

A country-destination comparator for international students and recent grads. The user enters their citizenship, degree field, and two countries they're considering working in. The system synthesizes what working in each country would actually look like for someone with their exact profile — visa pathway, wages, cost of living, tax-adjusted take-home, immigration climate — then surfaces structured AI reasoning about the trade-offs.

No specific job offers required. The system builds the picture from market data. The differentiator is modeling real immigration constraints citizenship-by-citizenship, which most competing teams won't touch.

---

## Pipeline (Architecture B — locked)

```
1. Intake          (deterministic) — parse user profile
        ↓
2b. Route + Outlook (AI call #1)  — Gemini + Google Search
        ↓                            resolves visa route from official sources
2a. Fact Assembly  (deterministic) — wages (BLS/OECD), CoL (Numbeo), tax calc
        ↓                            enriches with visa_rules.json curated data
3.  Reasoning      (AI call #2)   — Gemini structured output, 7 typed insights
        ↓
    Validate       (deterministic) — 6 rules, SAFE_FALLBACK on any failure
        ↓
4.  Sacrifice Diff (deterministic) — 5-dimension cross-country comparison
        ↓
5.  Output         (dashboard)
```

**Two LLM calls only.** Everything else is deterministic. Stage 2b runs before 2a because the AI-resolved visa slug is needed for curated enrichment lookup.

---

## Country Scope (locked)

**Supported destinations:** US, UK, Canada, Australia, Germany, France

Any other destination: wage/CoL still rendered, visa flagged as "not yet modeled." Never fabricated.

---

## Data Sources

| Source | Type | Covers |
|---|---|---|
| OECD Data API (`sdmx.oecd.org`) | Live API, no key | National average wages, all 6 countries |
| BLS Public Data API (`api.bls.gov`) | Live API | US wages by occupation (SOC code), finer-grained |
| Numbeo Cost of Living API | Live API | City-level cost of living |
| `data/visa_rules.json` | Curated, cited, dated | Visa enrichment: lottery history, partner work rights, PR timeline, salary floor — for 6 known visa slugs |
| `data/official_source_registry.json` | Hardcoded | Approved government URLs per destination country — the only sources Stage 2b is allowed to extract from |
| `data/tax_rates.json` | Curated, cited | Income tax brackets + social contribution rates, all 6 countries |
| `data/field_soc_map.json` | Curated | Degree field → BLS SOC code |
| Gemini + Google Search grounding | Live AI call, Stage 2b only | Visa route resolution + immigration policy trends + career context |

**OECD vs BLS resolution gap:** US wages come from BLS (occupation-level). All other countries use OECD (national average). These are not measuring at the same resolution — this is disclosed on the dashboard via `PrecisionCaveat`.

---

## Visa Route Resolution (Stage 2b)

Routing is **fully AI-resolved** — no hardcoded citizenship → visa mapping table. Stage 2b's Gemini + Search call searches the approved official government sources for the destination country and identifies the applicable work visa path for the user's citizenship and degree field.

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

**Prompt constraints:** Only extract from approved source registry URLs. Do not state hard salary thresholds or PR timelines as facts — those are validated separately. Note uncertainty explicitly.

### Stage 3 — `WhatIfInsight` (Gemini, no search, structured output)

```json
{
  "scenario_type": "base | contingency | priority_match | synthesis",
  "fact_used": "exact dot-notation key from fact bundle",
  "context_used": "verbatim phrase from user_context",
  "connection": "shared vocabulary between fact_used and context_used",
  "consideration": "the non-obvious second-order implication",
  "confidence": "high | medium | low",
  "confidence_basis": "string",
  "next_action": "verb-led specific instruction"
}
```

**7 insights per request:** 2 base, 2 contingency, 2 priority_match, 1 synthesis.

**Prompt constraint:** `consideration` must state something NOT immediately obvious from the fact alone. "Make a second-order connection." Do not recommend which country to choose.

### `validate_output()` — 6 rules (in `reasoning_step.py`)

1. `fact_used` ∈ `_flatten_bundle_keys(bundle_a) ∪ _flatten_bundle_keys(bundle_b)`
2. `context_used` substring-matches `user_context`
3. `connection` shares vocabulary with both `fact_used` and `context_used`
4. `consideration` not in boilerplate phrases list
5. `next_action` first word is in imperative verb set
6. `scenario_type` ∈ `{"base", "contingency", "priority_match", "synthesis"}`

Any failure → `SafeFallback(type="safe_fallback", reason="rule_N_failed", slot_index=N)`. Never `None`. Always visible on dashboard.

`_flatten_bundle_keys()` is the single source of truth — used by both the prompt builder and the validator. They must never diverge.

---

## Sacrifice Diff — 5 Dimensions

| Dimension | Source |
|---|---|
| `net_takehome_ppp` | Gross wage → tax brackets → ÷ CoL index |
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
- **Precision caveat** disclosed on WagePanel: BLS (US, occupation-level) and OECD (other countries, national average) are not measuring at the same resolution.

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

// Response: DashboardPayload
// bundle_a, bundle_b, outlook_a, outlook_b, insights[], sacrifice_map, pipeline_meta
```

### `GET /api/visa/{country}` — curated enrichment for a destination country
### `GET /api/health` — `{"status": "ok", "visa_rules_loaded": true, ...}`

---

## 3-Day Build Plan

### Day 1 — June 18: Foundation + Data Layer
- Scaffold backend (FastAPI) + frontend (Vite + React + TypeScript + Tailwind)
- Author `visa_rules.json`, `official_source_registry.json`, `tax_rates.json`, `field_soc_map.json`
- Implement OECD, BLS, Numbeo API clients
- Implement `visa_rules.py`: `get_visa_rule()`, `merge_visa_facts()`, `compute_lottery_cumulative()`
- Implement `compute_net_takehome()` from tax bracket tables
- Implement `fact_assembly.py` (stubs for visa_route input — Stage 2b wired on Day 2)
- Stub `POST /api/compare` with hardcoded payload (frontend can start)
- Build `IntakePage`

### Day 2 — June 19: AI Pipeline + Validation
- Implement intake_models.py (CompareRequest) — unblock app boot
- Implement `immigration_outlook.py`: Stage 2b Gemini + Search, full `RouteAndOutlook` schema
- Implement `reasoning_step.py`: `_flatten_bundle_keys()`, `_build_prompt()`, `generate_insights()`, `validate_output()` (all 6 rules), `validate_batch()`
- Implement `sacrifice_diff.py`: 5 dimensions, `visa_stability_score` formula
- Implement `orchestrator.py`: wire all stages in correct order (2b → 2a parallel → 3 → validate → diff)
- End-to-end test: India / CS / US vs France → real data, 2 AI calls confirmed

### Day 3 — June 20–21: Dashboard + Polish + Submit
- Build all dashboard components (WagePanel, VisaPanel, OutlookCard, WhatIfList grouped by scenario_type, SacrificeMap)
- `HumanBoundaryBanner` pinned, always visible
- `SafeFallbackNotice` visible (not collapsible)
- `pipeline_meta` collapsible panel
- `LoadingPage` with named stage labels
- QA: SAFE_FALLBACK path, 7th-country graceful degradation, unknown citizenship no-crash
- Submit

---

## Tech Stack

**Backend:** Python 3.11+, FastAPI, Uvicorn, Pydantic v2, pydantic-settings, google-generativeai, httpx

**Frontend:** React 18, TypeScript, Vite, Tailwind CSS, React Router v6

**No LangChain. No MCP. No database. No ETL.**
