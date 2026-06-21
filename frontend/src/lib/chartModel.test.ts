import { describe, it, expect } from 'vitest'

import { toChartModel } from './chartModel'
import type { DashboardPayload, DimensionDiff } from '../types'

function diff(
  dimension: string,
  a: DimensionDiff['country_a_value'],
  b: DimensionDiff['country_b_value'],
  winner: DimensionDiff['winner'] = null,
): DimensionDiff {
  return { dimension, country_a_value: a, country_b_value: b, delta: null, winner, note: 'n' }
}

function payload(overrides: Partial<DashboardPayload> = {}): DashboardPayload {
  const route = {
    visa_slug: 's',
    visa_name: 'n',
    eligibility_summary: 'e',
    employer_sponsorship_required: true,
    path_to_residency_years: 5,
    key_constraint: 'k',
    routing_confidence: 'high' as const,
    source_url: 'u',
    source_retrieved: 'd',
  }
  const bundle = (country: string, gross: number, net: number, usd: number) => ({
    country,
    wage: { gross_annual_local: gross, currency: 'USD', source: 'BLS' as const, soc_code: null, precision_note: '' },
    col: { city: null, col_index: 100, exchange_rate_to_usd: 1, monthly_cost_usd: null, source: 'WB', col_source: 'national_ppp' as const, is_fallback: false, precision_note: null },
    tax: { effective_rate: (gross - net) / gross, net_annual_local: net, notes: null },
    net_annual_usd: usd,
    visa_route: route,
    visa_enrichment: null,
  })
  return {
    bundle_a: bundle('US', 100000, 70000, 70000),
    bundle_b: bundle('UK', 80000, 60000, 50000),
    outlook_a: {} as never,
    outlook_b: {} as never,
    insights: [],
    sacrifice_map: {
      net_takehome_usd: diff('net_takehome_usd', 70000, 50000, 'a'),
      col_relative: diff('col_relative', 100, 80, 'b'),
      visa_stability_score: diff('visa_stability_score', 0.8, 0.4, 'a'),
      pr_timeline_years: diff('pr_timeline_years', 6, 3, 'b'),
      lottery_risk: diff('lottery_risk', 0.5, 0.0, 'b'),
      partner_opportunity: diff('partner_opportunity', 'full', 'none', 'a'),
    },
    pipeline_meta: {} as never,
    ...overrides,
  }
}

describe('toChartModel', () => {
  it('normalizes higher-is-better dimensions to shares summing to 1', () => {
    const { comparison } = toChartModel(payload())
    const net = comparison.find((c) => c.key === 'net_takehome_usd')!
    expect(net.a! + net.b!).toBeCloseTo(1)
    expect(net.a).toBeGreaterThan(net.b!) // 70k vs 50k → A leads
    expect(net.aRaw).toBe(70000) // raw value preserved for tooltips
  })

  it('renders all six comparison spokes incl. cost of living', () => {
    const { comparison } = toChartModel(payload())
    expect(comparison.map((c) => c.key)).toEqual([
      'net_takehome_usd',
      'col_relative',
      'visa_stability_score',
      'pr_timeline_years',
      'lottery_risk',
      'partner_opportunity',
    ])
  })

  it('puts the cheaper country further out on the cost-of-living axis (lower cost = better)', () => {
    const { comparison } = toChartModel(payload())
    const col = comparison.find((c) => c.key === 'col_relative')!
    // A = 100, B = 80 → B is cheaper → B is further out; shares sum to 1
    expect(col.b).toBeGreaterThan(col.a!)
    expect(col.a! + col.b!).toBeCloseTo(1)
    expect(col.aRaw).toBe(100) // raw values preserved for tooltips
    expect(col.bRaw).toBe(80)
  })

  it('inverts lower-is-better dimensions so the smaller raw value scores higher', () => {
    const { comparison } = toChartModel(payload())
    const pr = comparison.find((c) => c.key === 'pr_timeline_years')!
    expect(pr.b).toBeGreaterThan(pr.a!) // 3yr (B) beats 6yr (A)
    expect(pr.a! + pr.b!).toBeCloseTo(1)
  })

  it('ranks the categorical partner dimension (full > restricted > none)', () => {
    const { comparison } = toChartModel(payload())
    const partner = comparison.find((c) => c.key === 'partner_opportunity')!
    expect(partner.a).toBe(1) // full vs none
    expect(partner.b).toBe(0)
  })

  it('treats equal values (incl. both zero) as a 0.5/0.5 tie', () => {
    const p = payload()
    p.sacrifice_map.lottery_risk = diff('lottery_risk', 0, 0, 'tie')
    const lottery = toChartModel(p).comparison.find((c) => c.key === 'lottery_risk')!
    expect(lottery.a).toBe(0.5)
    expect(lottery.b).toBe(0.5)
  })

  it('skips a spoke when both raw values are null', () => {
    const p = payload()
    p.sacrifice_map.lottery_risk = diff('lottery_risk', null, null)
    const lottery = toChartModel(p).comparison.find((c) => c.key === 'lottery_risk')!
    expect(lottery.a).toBeNull()
    expect(lottery.b).toBeNull()
  })

  it('exposes net_annual_usd (not gross) as the cross-country comparable figure', () => {
    const { netComparison, incomeBreakdown } = toChartModel(payload())
    expect(netComparison).toEqual([
      { country: 'US', netUsd: 70000 },
      { country: 'UK', netUsd: 50000 },
    ])
    // gross stays in local currency on the per-country breakdown only
    expect(incomeBreakdown.a.gross).toBe(100000)
    expect(incomeBreakdown.a.taxAmount).toBe(30000)
  })
})
