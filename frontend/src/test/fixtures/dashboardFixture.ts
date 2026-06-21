// TEST-ONLY fixture. A static DashboardPayload (US-vs-Germany) mirroring
// backend/pipeline/sample_payload.py, used solely by chart/component unit tests.
//
// This deliberately lives under src/test/ — NOT src/lib/ — so application code
// cannot import it. The dashboard must only ever render a live pipeline result;
// there is no canned fallback in the running app.

import type { DashboardPayload } from '../../types'

// Sample FX (LCU per USD), mirroring backend/pipeline/sample_payload.py.
const US_XR = 1.0
const DE_XR = 0.9239
const netUsd = (netLocal: number, xr: number) => Math.round((netLocal / xr) * 100) / 100

export const dashboardFixture: DashboardPayload = {
  bundle_a: {
    country: 'US',
    wage: {
      gross_annual_local: 132270,
      currency: 'USD',
      source: 'BLS',
      soc_code: '15-1252',
      precision_note: 'Occupation-level US wage (BLS OEWS) for SOC 15-1252.',
    },
    col: {
      city: 'New York',
      col_index: 100,
      exchange_rate_to_usd: US_XR,
      monthly_cost_usd: null,
      source: 'Numbeo',
      col_source: 'city',
      is_fallback: false,
      precision_note: null,
    },
    tax: {
      effective_rate: 0.2638,
      net_annual_local: 97364,
      notes: 'Federal income tax + FICA; state taxes not included.',
    },
    net_annual_usd: netUsd(97364, US_XR),
    visa_route: {
      visa_slug: 'us_h1b',
      visa_name: 'H-1B Specialty Occupation',
      eligibility_summary: "Bachelor's+ in a specialty field with a sponsoring employer.",
      employer_sponsorship_required: true,
      path_to_residency_years: 6,
      key_constraint: 'Annual lottery cap; selection is not guaranteed.',
      routing_confidence: 'high',
      source_url: 'https://www.uscis.gov/working-in-the-united-states/h-1b-specialty-occupations',
      source_retrieved: '2026-06-19',
    },
    visa_enrichment: {
      min_salary: 60000,
      currency: 'USD',
      can_switch_employer: true,
      switch_conditions: 'New employer must file a fresh H-1B petition (no re-lottery).',
      lottery_required: true,
      lottery_annual_rate: 0.14,
      lottery_history: [{ year: 2024, rate: 0.14 }],
      lottery_cumulative_3yr: 0.3639,
      partner_work_rights: 'restricted',
      partner_work_notes: 'H-4 dependents need an EAD; eligible only in limited cases.',
      last_verified: '2026-06-19',
      curated_source_url:
        'https://www.uscis.gov/working-in-the-united-states/h-1b-specialty-occupations',
    },
  },
  bundle_b: {
    country: 'Germany',
    wage: {
      gross_annual_local: 54000,
      currency: 'EUR',
      source: 'OECD',
      soc_code: null,
      precision_note: 'National-average wage (OECD); not occupation-specific.',
    },
    col: {
      city: 'Berlin',
      col_index: 65.3,
      exchange_rate_to_usd: DE_XR,
      monthly_cost_usd: null,
      source: 'Numbeo',
      col_source: 'city',
      is_fallback: false,
      precision_note: null,
    },
    tax: {
      effective_rate: 0.3168,
      net_annual_local: 36895,
      notes: 'Income tax + approximate employee social contributions.',
    },
    net_annual_usd: netUsd(36895, DE_XR),
    visa_route: {
      visa_slug: 'de_eu_blue_card',
      visa_name: 'EU Blue Card (Germany)',
      eligibility_summary: 'Recognised degree + a job offer above the salary threshold.',
      employer_sponsorship_required: false,
      path_to_residency_years: 4,
      key_constraint: 'Salary must meet the annual Blue Card threshold.',
      routing_confidence: 'medium',
      source_url: 'https://www.make-it-in-germany.com/en/visa-residence/types/eu-blue-card',
      source_retrieved: '2026-06-19',
    },
    visa_enrichment: {
      min_salary: 45300,
      currency: 'EUR',
      can_switch_employer: true,
      switch_conditions: 'Employer change in the first 12 months needs authority approval.',
      lottery_required: false,
      lottery_annual_rate: null,
      lottery_history: [],
      lottery_cumulative_3yr: null,
      partner_work_rights: 'full',
      partner_work_notes: 'Spouse gets unrestricted labour-market access.',
      last_verified: '2026-06-19',
      curated_source_url: 'https://www.make-it-in-germany.com/en/visa-residence/types/eu-blue-card',
    },
  },
  outlook_a: {
    trend_summary: 'US immigration policy has been broadly stable over the past year.',
    trend_direction: 'stable',
    key_recent_change: 'No major statutory change in the last 12 months.',
    career_context: 'Demand for skilled technical workers remains strong.',
    source_url: 'https://example.gov/immigration-outlook',
    source_publish_date: '2026-05-01',
    confidence: 'medium',
  },
  outlook_b: {
    trend_summary: 'Germany immigration policy has been broadly stable over the past year.',
    trend_direction: 'stable',
    key_recent_change: 'No major statutory change in the last 12 months.',
    career_context: 'Demand for skilled technical workers remains strong.',
    source_url: 'https://example.gov/immigration-outlook',
    source_publish_date: '2026-05-01',
    confidence: 'medium',
  },
  insights: [
    {
      type: 'insight',
      scenario_type: 'base',
      fact_a: 'bundle_a.net_takehome_ppp',
      fact_b: null,
      context_used: 'long-term residency stability',
      tradeoff:
        'The US net_takehome_ppp buys more day-to-day, but that take-home only lands while you hold the visa that underpins residency stability.',
      likely_outcome:
        'On an H-1B you most likely enjoy the higher take-home for the first few years, with the lottery and renewals still unresolved.',
      consideration:
        'The headline US take-home is contingent on clearing the H-1B lottery, so the nominal advantage overstates what is actually guaranteed.',
      confidence: 'high',
      confidence_basis: 'Wage and lottery rate are both curated facts.',
      next_action: 'Compare your offer salary against the H-1B prevailing-wage floor.',
    },
    {
      type: 'insight',
      scenario_type: 'base',
      fact_a: null,
      fact_b: 'bundle_b.net_takehome_ppp',
      context_used: 'long-term residency stability',
      tradeoff:
        "Germany's net_takehome_ppp is lower, but it arrives on a route whose residency stability is not gated by a lottery.",
      likely_outcome:
        'On the Blue Card you most likely keep a steadier, if smaller, take-home while the residency clock runs without a draw.',
      consideration:
        'The lower German take-home is near-certain rather than conditional, so a head-to-head with the US figure understates its reliability.',
      confidence: 'high',
      confidence_basis: 'Wage is curated; Blue Card has no lottery gate.',
      next_action: 'Budget against the German net take-home to test if the lower figure still meets your needs.',
    },
    {
      type: 'insight',
      scenario_type: 'lottery_risk',
      fact_a: 'bundle_a.visa_enrichment.lottery_cumulative_3yr',
      fact_b: 'bundle_b.visa_enrichment.lottery_required',
      context_used: 'long-term residency stability',
      tradeoff:
        'Choosing the US accepts lottery_cumulative_3yr odds for higher pay; choosing Germany, where no lottery is required, trades pay for a stability you can count on.',
      likely_outcome:
        'Over three H-1B cycles the more likely outcome is non-selection (~64%), whereas the Blue Card path has no draw to lose.',
      consideration:
        "The lottery converts the US's pay advantage into a coin-flip on stability, so the two options aren't on the same risk footing.",
      confidence: 'medium',
      confidence_basis: 'Three-cycle estimate assumes the current selection rate holds.',
      next_action: 'Draft a backup plan (O-1 or cap-exempt employer) before accepting a US offer.',
    },
    {
      type: 'insight',
      scenario_type: 'partner_work',
      fact_a: 'bundle_a.visa_enrichment.partner_work_rights',
      fact_b: 'bundle_b.visa_enrichment.partner_work_rights',
      context_used: 'long-term residency stability',
      tradeoff:
        "US partner_work_rights are restricted while Germany's are full, so the US pay premium is partly offset by a second income your household may have to forgo.",
      likely_outcome:
        'In the US your spouse most likely cannot work until an EAD is granted; in Germany they can work from arrival.',
      consideration:
        'Household stability, not just your salary, hinges on partner work rights — a factor the single-earner headline numbers hide.',
      confidence: 'high',
      confidence_basis: 'Partner work rights are curated for both routes.',
      next_action: "Confirm your partner's qualification recognition in Germany.",
    },
    {
      type: 'insight',
      scenario_type: 'priority_match',
      fact_a: 'bundle_a.visa_route.path_to_residency_years',
      fact_b: 'bundle_b.visa_route.path_to_residency_years',
      context_used: 'long-term residency stability',
      tradeoff:
        "The US path_to_residency_years (6) is longer than Germany's (4), so prioritising residency stability favours Germany at the cost of US earning power.",
      likely_outcome:
        'If stability is your real priority you most likely reach permanent status two years sooner in Germany, and without a lottery gate.',
      consideration:
        'The faster, lottery-free German timeline maps more directly onto a stability-first priority than the higher US salary does.',
      confidence: 'high',
      confidence_basis: 'PR timelines are curated for both routes.',
      next_action: 'Verify the German B1 language requirement for permanent settlement.',
    },
    {
      type: 'safe_fallback',
      reason: "next_action is not verb-led (starts with 'understanding')",
      slot_index: 5,
    },
    {
      type: 'insight',
      scenario_type: 'synthesis',
      fact_a: 'bundle_a.net_takehome_ppp',
      fact_b: 'bundle_b.visa_route.path_to_residency_years',
      context_used: 'long-term residency stability',
      tradeoff:
        "The sharpest tradeoff is US net_takehome_ppp against Germany's shorter path_to_residency_years: higher-but-uncertain purchasing power versus lower-but-near-certain residency.",
      likely_outcome:
        'The most likely real-world split is more money now in the US with a lottery hanging over it, versus steadier, sooner residency in Germany.',
      consideration:
        "The decision reduces to how you personally weight purchasing power against residency certainty — the numbers alone don't settle it.",
      confidence: 'medium',
      confidence_basis: 'Synthesis of curated facts; the trade-off weighting is yours.',
      next_action: 'Rank lottery risk against take-home for yourself before deciding.',
    },
  ],
  sacrifice_map: {
    net_takehome_usd: {
      dimension: 'net_takehome_usd',
      country_a_value: netUsd(97364, US_XR),
      country_b_value: netUsd(36895, DE_XR),
      delta: Math.round((netUsd(97364, US_XR) - netUsd(36895, DE_XR)) * 100) / 100,
      winner: 'a',
      note: 'Annual take-home converted to USD (nominal, market FX).',
    },
    col_relative: {
      dimension: 'col_relative',
      country_a_value: 100,
      country_b_value: 65.3,
      delta: -34.7,
      winner: 'b',
      note: 'Cost of living relative to Country A (A = 100; lower is cheaper).',
    },
    visa_stability_score: {
      dimension: 'visa_stability_score',
      country_a_value: 0.36,
      country_b_value: 0.9,
      delta: -0.54,
      winner: 'b',
      note: "Germany's no-lottery route is far more certain.",
    },
    pr_timeline_years: {
      dimension: 'pr_timeline_years',
      country_a_value: 6,
      country_b_value: 4,
      delta: 2,
      winner: 'b',
      note: 'Germany reaches permanent residency sooner.',
    },
    lottery_risk: {
      dimension: 'lottery_risk',
      country_a_value: 0.64,
      country_b_value: 0,
      delta: 0.64,
      winner: 'b',
      note: 'US H-1B carries a ~64% three-year non-selection risk.',
    },
    partner_opportunity: {
      dimension: 'partner_opportunity',
      country_a_value: 'restricted',
      country_b_value: 'full',
      delta: null,
      winner: 'b',
      note: 'Germany grants full partner work rights.',
    },
  },
  pipeline_meta: {
    ai_calls_made: 4,
    insights_passed: 6,
    insights_withheld: 1,
    routing_confidence_a: 'high',
    routing_confidence_b: 'medium',
    fact_sources: {
      wage: 'BLS / OECD',
      cost_of_living: 'Numbeo (mock)',
      tax: 'curated tax_rates.json',
      visa: 'curated visa_rules.json',
      note: 'TEST FIXTURE — not live data',
    },
  },
}
