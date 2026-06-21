// TypeScript mirrors of the backend intake contract (backend/models/intake_models.py).

export type SupportedCountry = 'US' | 'UK' | 'Canada' | 'Australia' | 'Germany' | 'France'

export type CareerStage = 'new_grad' | 'early_career' | 'mid_career' | 'senior'

export interface CompareRequest {
  citizenship: string
  degree_field: string
  career_stage: CareerStage
  country_a: SupportedCountry
  country_b: SupportedCountry
  user_context: string
}

// ── Backend response contracts ─────────────────────────────────────────────
// Mirrors backend/models/output_models.py and backend/models/ai_models.py.
// Keep field names in lock-step with the Pydantic models — these are the API
// boundary. Gemini-sourced fields (VisaRoute, ImmigrationOutlook, WhatIfInsight)
// are intentionally qualitative; the numeric chart fuel lives in the
// deterministic CountryBundle + SacrificeMap.

export type ConfidenceLevel = 'high' | 'medium' | 'low'
export type TrendDirection = 'improving' | 'stable' | 'restrictive'
export type PartnerOpportunity = 'full' | 'restricted' | 'none'
export type ScenarioType =
  | 'base'
  | 'lottery_risk'
  | 'extension_risk'
  | 'employer_switch'
  | 'partner_work'
  | 'pr_timeline'
  | 'priority_match'
  | 'synthesis'

// --- Gemini Stage 2b output ---
export interface VisaRoute {
  visa_slug: string
  visa_name: string
  eligibility_summary: string
  employer_sponsorship_required: boolean
  path_to_residency_years: number | null
  key_constraint: string
  routing_confidence: ConfidenceLevel
  source_url: string
  source_retrieved: string
}

export interface ImmigrationOutlook {
  trend_summary: string
  trend_direction: TrendDirection
  key_recent_change: string
  career_context: string
  source_url: string
  source_publish_date: string
  confidence: ConfidenceLevel
}

// --- Gemini Stage 3 output (discriminated on `type`) ---
export interface WhatIfInsight {
  type: 'insight'
  scenario_type: ScenarioType
  fact_used: string
  context_used: string
  connection: string
  consideration: string
  confidence: ConfidenceLevel
  confidence_basis: string
  next_action: string
}

export interface SafeFallback {
  type: 'safe_fallback'
  reason: string
  slot_index: number
}

export type InsightOrFallback = WhatIfInsight | SafeFallback

// --- Deterministic fact layer ---
export interface VisaEnrichment {
  min_salary: number | null
  currency: string | null
  can_switch_employer: boolean | null
  switch_conditions: string | null
  lottery_required: boolean | null
  lottery_annual_rate: number | null
  lottery_history: Array<Record<string, unknown>> | null
  lottery_cumulative_3yr: number | null
  partner_work_rights: PartnerOpportunity | null
  partner_work_notes: string | null
  last_verified: string | null
  curated_source_url: string | null
}

export interface WageData {
  gross_annual_local: number
  currency: string
  source: 'BLS' | 'OECD'
  soc_code: string | null
  precision_note: string
}

export interface ColData {
  city: string | null
  col_index: number | null
  exchange_rate_to_usd: number | null
  monthly_cost_usd: number | null
  source: string
  col_source: 'city' | 'national_ppp'
  is_fallback: boolean
  precision_note: string | null
}

export interface TaxData {
  effective_rate: number
  net_annual_local: number
  notes: string | null
}

export interface CountryBundle {
  country: string
  wage: WageData
  col: ColData
  tax: TaxData
  net_annual_usd: number | null
  visa_route: VisaRoute
  visa_enrichment: VisaEnrichment | null
}

export type SacrificeDimension =
  | 'net_takehome_usd'
  | 'col_relative'
  | 'visa_stability_score'
  | 'pr_timeline_years'
  | 'lottery_risk'
  | 'partner_opportunity'

export interface DimensionDiff {
  dimension: string
  country_a_value: number | string | null
  country_b_value: number | string | null
  delta: number | null
  winner: 'a' | 'b' | 'tie' | null
  note: string | null
}

export interface SacrificeMap {
  net_takehome_usd: DimensionDiff
  col_relative: DimensionDiff
  visa_stability_score: DimensionDiff
  pr_timeline_years: DimensionDiff
  lottery_risk: DimensionDiff
  partner_opportunity: DimensionDiff
}

export interface PipelineMeta {
  ai_calls_made: number
  insights_passed: number
  insights_withheld: number
  routing_confidence_a: ConfidenceLevel
  routing_confidence_b: ConfidenceLevel
  fact_sources: Record<string, string>
}

export interface DashboardPayload {
  bundle_a: CountryBundle
  bundle_b: CountryBundle
  outlook_a: ImmigrationOutlook
  outlook_b: ImmigrationOutlook
  insights: InsightOrFallback[]
  sacrifice_map: SacrificeMap
  pipeline_meta: PipelineMeta
}

export const SUPPORTED_COUNTRIES: SupportedCountry[] = [
  'US',
  'UK',
  'Canada',
  'Australia',
  'Germany',
  'France',
]

// Passport-style code + full name per destination, used for the A/B path identity.
export const COUNTRY_META: Record<SupportedCountry, { code: string; name: string }> = {
  US: { code: 'US', name: 'United States' },
  UK: { code: 'GB', name: 'United Kingdom' },
  Canada: { code: 'CA', name: 'Canada' },
  Australia: { code: 'AU', name: 'Australia' },
  Germany: { code: 'DE', name: 'Germany' },
  France: { code: 'FR', name: 'France' },
}

export const CAREER_STAGES: { value: CareerStage; label: string }[] = [
  { value: 'new_grad', label: 'New grad' },
  { value: 'early_career', label: 'Early career' },
  { value: 'mid_career', label: 'Mid career' },
  { value: 'senior', label: 'Senior' },
]
