# Tradeoff

### Should I build my career in Country A or Country B? An immigration-aware decision comparator for international students and recent grads.

**USAII Global AI Hackathon 2026 · Challenge Brief 3, Direction A**

---

Every year millions of international students face the same high-stakes question after graduation: *which country should I actually build my life in?* The honest answer depends on something no salary chart captures — **whether the immigration system will even let you stay, on what terms, and for how long.** A $120k offer behind a visa lottery you have a 30% chance of winning is not comparable to an €70k role with a 5-year path to permanent residency. Existing tools compare salaries and cost of living. **None of them model the immigration reality, citizenship-by-citizenship.** That gap is the entire reason this project exists.

**Tradeoff** takes a user's citizenship, degree field, career stage, and two destination countries — *no job offer required* — and synthesizes what working in each place would actually look like for *their specific profile*: the applicable visa route, employer-sponsorship dependency, path to residency, lottery exposure, partner work rights, tax-adjusted take-home in PPP terms, and the current immigration-policy climate. Then it surfaces structured, source-grounded AI reasoning about the trade-offs — **and deliberately stops short of telling you what to do.** The decision stays human.

---

## Why this should score well

This section maps directly to the judging rubric.

### AI reasoning (30%) — the core of the score

The hard part of this problem is not fetching data; it's reasoning responsibly over messy, partially-knowable immigration information without hallucinating facts that could mislead someone's life decision. Our design treats that as a first-class engineering constraint:

- **A clean split between "soft" and "hard" knowledge.** The LLM is *only* allowed to reason about and retrieve soft information — visa-route resolution, policy trends, career context. Hard facts (salary floors, PR timelines, lottery odds) are **never** looked up by the model; they come from curated, cited, dated sources. The model is structurally prevented from being the source of a number that matters.
- **Grounded retrieval, then structured extraction — two sub-calls, for a reason.** Stage 2b runs Gemini with **Google Search grounding restricted to an all-listed registry of official government URLs**, then a second no-search call enforces a strict `response_schema`. We split these deliberately because Search grounding and structured JSON output can't be reliably combined in one SDK call — a justification-over-buzzwords choice, exactly what the brief asks judges to reward.
- **Second-order reasoning, not summary.** Stage 3 generates 7 typed "what-if" insights per comparison (`base`, `contingency`, `priority_match`, `synthesis`). Each insight must explicitly bind a **fact** from the data bundle to a **verbatim phrase from the user's own stated priorities**, and the `consideration` field is required to state something *not obvious from the fact alone*.
- **Every model output is validated before a human ever sees it.** A deterministic `validate_output()` enforces 6 rules — the cited fact must exist in the bundle, the user-context quote must be real, the connection must share vocabulary with both, the conclusion can't be boilerplate, the action must be imperative, the type must be in the allowed set. **Any failure routes to a visible `SAFE_FALLBACK` — unvalidated model output is never displayed.** The validator and the prompt builder share one source of truth (`_flatten_keys()` in `reasoning_step.py`) so they can't drift.

### Responsible AI (10%) — enforced in code, not just claimed

- **The AI never recommends a country.** This is the human-in-the-loop boundary, and it's enforced at the output layer, not just promised in prose. `HumanBoundaryBanner` is pinned and always visible.
- **Withheld reasoning is shown, not hidden.** When an insight fails validation, the user is told an analysis point was withheld because it couldn't be verified — silence would be the irresponsible choice.
- **Radical provenance.** Every curated fact carries a real `source_url` and `last_verified` date. Every visa route shows `routing_confidence`. Every wage/cost figure discloses its **resolution caveat** (e.g. US metro-level vs. national average) so users never over-trust a number that's coarser than it looks.

### Solution design (25%)

A locked, justified pipeline — **exactly 4 LLM calls, everything else deterministic** (Stage 2b = 3: two per-country grounded research calls + one structuring call; Stage 3 = 1: one call returns all 7 insights as a JSON array; the validator runs per-item so per-slot SAFE_FALLBACK still works) — with no database, no ETL, no LangChain, no MCP (deliberately: the brief's own Q&A says judges score justification, not architecture-by-name). Scope is enforced in two layers (a fixed dropdown and a `Literal` type at the API boundary), so an unsupported country is rejected with a `422` before any AI runs, rather than being handled by fragile in-prompt degradation.

### Impact & insight (15%)

The differentiator is the immigration modeling most competing teams won't attempt. Comparing two job markets is commodity; comparing two *immigration futures* for *a specific nationality* — lottery exposure, employer lock-in, partner work rights, residency timelines — is the insight that actually changes a decision.

---

## How it works

```
Intake (deterministic — parse + validate profile)
   │
   ├─▶ AI calls #1a/#1b  Route + Outlook research (×2, once per country)
   │                     Gemini + Google Search grounding, allow-listed gov URLs, raw text
   ├─▶ AI call #2        Route + Outlook structure
   │                     Gemini, no search, response_schema=RouteAndOutlook, temperature=0
   │
   ├─▶ Fact assembly (deterministic)
   │   World Bank/WhereNext/Numbeo CoL · OECD/BLS wages · tax · visa-rules enrichment
   │
   ├─▶ AI call #3        What-if reasoning — one call, 7 insights returned as JSON array
   │                     Gemini structured output · validator runs per item
   ├─▶ Validate (deterministic, per item)  6 rules → per-slot SAFE_FALLBACK on any failure
   │
   ├─▶ Sacrifice-map diff (deterministic)  5-dimension cross-country comparison
   │
   └─▶ Dashboard
```

**Soft vs. hard knowledge** is the load-bearing idea: the live AI call (Stage 2b) touches only routes, trends, and context; curated, cited tables own every hard number.

| Knowledge | Owner | Examples |
|---|---|---|
| **Soft** (model-reasoned, search-grounded) | Gemini + allow-listed gov sources | visa route resolution, policy trend direction, career context |
| **Hard** (never model-sourced) | OECD/BLS live APIs + curated cited JSON | wages, PPP, tax, salary floors, PR timelines, lottery history, partner rights |

**Supported destinations:** US, UK, Canada, Australia, Germany, France — chosen by real international-student enrollment volume.

**Tech stack:** Python 3.11+, FastAPI, Pydantic v2, google-generativeai · React 18, TypeScript, Vite, Tailwind CSS.

---

## Run it locally

Two processes: backend on `:8000`, frontend on `:5173`.

> The frontend runs end-to-end with **no API keys** — `POST /api/compare` currently returns a schema-valid, self-labeled **sample payload** while the orchestrator is being wired. The live pipeline (all stages connected) requires both a `GEMINI_API_KEY` and the completed `orchestrator.py`.

### Backend

From the project root (`tradeoff/`):

```bash
python -m venv .venv
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# macOS / Linux:  source .venv/bin/activate

pip install -r backend/requirements.txt

cp .env.example .env        # Windows: copy .env.example .env
# edit .env → set GEMINI_API_KEY (NUMBEO_API_KEY / BLS_API_KEY optional)

uvicorn backend.main:app --reload --port 8000
```

API: **http://localhost:8000** · interactive docs: **http://localhost:8000/docs**

### Frontend

```bash
cd frontend
npm install      # first run only
npm run dev
```

App: **http://localhost:5173** (calls the backend at `http://localhost:8000`; override with `VITE_API_BASE_URL`).

---

## API

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/compare` | Run a comparison → `DashboardPayload` |
| `GET`  | `/api/visa/{country}` | Curated visa enrichment for a destination |
| `GET`  | `/api/health` | Health + curated-data-load status |

Example `POST /api/compare` body:

```json
{
  "citizenship": "India",
  "degree_field": "Computer Science",
  "career_stage": "new_grad",
  "country_a": "US",
  "country_b": "France",
  "user_context": "I care most about long-term residency stability and not being tied to one employer. My partner is also looking for work."
}
```

`career_stage` ∈ `new_grad | early_career | mid_career | senior`. `country_a` / `country_b` must be one of the six supported destinations (enforced as a `Literal` at the API boundary — anything else is a `422`).

---

## Data sources

| Source | Mechanism | Covers |
|---|---|---|
| OECD Data API (`sdmx.oecd.org`) | live, no key | national wages + PPP conversion, all 6 countries |
| BLS Public Data API (`api.bls.gov`) | live | US wages by occupation (SOC); metro-area when a US city is given |
| World Bank Open Data API (`api.worldbank.org`) | live, no key | national price-level index (US = 100) — **primary CoL source** |
| WhereNext (`getwherenext.com`, CC BY 4.0) | live, no key | national cost index (US = 100) — secondary CoL source when World Bank unavailable |
| `data_sources/numbeo.py` (curated mock) | curated, offline fallback | national CoL indices; last resort when both live CoL sources fail; flagged on dashboard |
| `data/visa_rules.json` | curated, cited, dated | lottery history, partner work rights, PR timeline, salary floor |
| `data/official_source_registry.json` | hardcoded | the **only** government URLs Stage 2b may extract from |
| `data/tax_rates.json` | curated, cited | income tax + social contribution rates, all 6 countries |
| `data/field_soc_map.json` | curated | degree field → BLS SOC code |
| Gemini + Google Search grounding | live AI, Stage 2b only | visa-route resolution, policy trends, career context — soft info only |

---

## Tests

```bash
pytest backend/tests        # backend (repo root, venv active)
cd frontend && npm test     # frontend
```

---

## Project structure

```
tradeoff/
├── backend/
│   ├── main.py              FastAPI app + CORS
│   ├── config.py            env-driven settings
│   ├── routers/             compare · visa · health
│   ├── pipeline/            intake · immigration_outlook (2b) · reasoning_step (3)
│   │                        fact_assembly · sacrifice_diff · orchestrator
│   ├── data_sources/        oecd · bls · worldbank · wherenext · numbeo · tax · visa_rules
│   ├── models/              Pydantic schemas (intake · fact · ai · output)
│   ├── data/                curated cited JSON
│   └── tests/
├── frontend/                Vite · React · TS · Tailwind
│   └── src/                 pages/ · components/ · hooks/ · lib/
├── plan.md                  full design doc
├── CLAUDE.md                build constraints + judging map
└── .env.example
```

---

## Design docs

The full pipeline contracts, validation rules, and data policy live in [`plan.md`](./plan.md) and [`CLAUDE.md`](./CLAUDE.md).
