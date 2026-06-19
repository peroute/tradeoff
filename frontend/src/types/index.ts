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

// Full response typing lands with the dashboard task; loose for now.
export interface DashboardPayload {
  [key: string]: unknown
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
