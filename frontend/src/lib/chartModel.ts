// toChartModel: reshapes the backend DashboardPayload into chart-ready datasets.
//
// Why this layer exists: the payload is already structured, but charts need
// two things the raw payload doesn't give you directly —
//   1. Normalization. A radar / diverging-bar comparing country A vs B needs
//      every sacrifice-map dimension on a common 0–1 "higher = better" scale.
//      Some dimensions are lower-is-better (PR timeline, lottery risk) and one
//      is categorical (partner work rights), so they must be transformed.
//   2. Currency safety. wage.gross_annual_local is in each country's *local*
//      currency, so A's and B's gross figures are NOT comparable on one axis.
//      The cross-country-comparable money figure is net_annual_usd (nominal,
//      converted to a common USD unit); cost of living lives on its own axis.
//
// All transforms are deterministic and unit-tested (chartModel.test.ts).

import type {
  CountryBundle,
  DashboardPayload,
  DimensionDiff,
  PartnerOpportunity,
} from '../types'

// ── Normalization helpers ───────────────────────────────────────────────────

/**
 * Share-of-total normalization for a two-way comparison.
 * Returns each value's share of the pair in [0, 1] (the pair sums to 1), with
 * direction baked in so 1 always means "better". Missing/degenerate inputs
 * yield nulls (radar should skip the spoke) or a 0.5/0.5 tie.
 */
function normalizePair(
  a: number | null,
  b: number | null,
  higherIsBetter: boolean,
): { a: number | null; b: number | null } {
  if (a === null && b === null) return { a: null, b: null }
  if (a === null) return { a: 0, b: 1 }
  if (b === null) return { a: 1, b: 0 }

  // Invert lower-is-better dimensions by comparing distance from the worse value.
  // Shift to keep shares non-negative when a raw value is 0 or negative.
  const va = higherIsBetter ? a : -a
  const vb = higherIsBetter ? b : -b
  const min = Math.min(va, vb)
  const offset = min < 0 ? -min : 0
  const sa = va + offset
  const sb = vb + offset
  const total = sa + sb
  if (total === 0) return { a: 0.5, b: 0.5 } // both equal (incl. both zero) → tie
  return { a: sa / total, b: sb / total }
}

/**
 * Magnitude normalization for axes read as raw size rather than "who wins"
 * (e.g. cost of living). The larger value maps to 1 (the rim), the other to its
 * proportional share of it, so the higher figure is always the maximal spoke and
 * the smaller one is shown to scale. Missing inputs yield null (skip the spoke).
 */
function normalizeMagnitude(
  a: number | null,
  b: number | null,
): { a: number | null; b: number | null } {
  if (a === null && b === null) return { a: null, b: null }
  const max = Math.max(a ?? 0, b ?? 0)
  if (max <= 0) return { a: a === null ? null : 0.5, b: b === null ? null : 0.5 }
  return { a: a === null ? null : a / max, b: b === null ? null : b / max }
}

const PARTNER_RANK: Record<PartnerOpportunity, number> = {
  full: 2,
  restricted: 1,
  none: 0,
}

function partnerRank(value: DimensionDiff['country_a_value']): number | null {
  if (typeof value !== 'string') return null
  return value in PARTNER_RANK ? PARTNER_RANK[value as PartnerOpportunity] : null
}

function asNumber(value: DimensionDiff['country_a_value']): number | null {
  return typeof value === 'number' ? value : null
}

// ── Chart-ready shapes ──────────────────────────────────────────────────────

/** One spoke of the A-vs-B comparison radar (or one group of a diverging bar). */
export interface ComparisonPoint {
  key: string // raw sacrifice_map dimension key
  label: string // human-readable axis label
  a: number | null // normalized 0–1, higher = better
  b: number | null
  aRaw: number | string | null // untouched value for tooltips
  bRaw: number | string | null
  winner: 'a' | 'b' | 'tie' | null
  note: string | null
}

/** Per-country income breakdown — local currency, NOT cross-country comparable. */
export interface IncomeBreakdown {
  country: string
  currency: string
  gross: number
  taxAmount: number
  netLocal: number
  effectiveRate: number
  colIndex: number | null
}

/** Cross-country comparable take-home in nominal USD. Safe to chart together. */
export interface NetComparisonPoint {
  country: string
  netUsd: number | null
}

export interface ChartModel {
  /** 5-dimension A-vs-B radar / diverging bar, all on a 0–1 "better" scale. */
  comparison: ComparisonPoint[]
  /** Side-by-side income waterfall inputs, each in its own currency. */
  incomeBreakdown: { a: IncomeBreakdown; b: IncomeBreakdown }
  /** Net take-home in a common USD unit — safe to compare across countries. */
  netComparison: NetComparisonPoint[]
  /** Visa stability gauges, already 0–1 from the backend. */
  visaStability: { a: number | null; b: number | null }
}

// dimension → (label, direction). Labels phrased so higher always reads "better".
const DIMENSIONS: Array<{
  key: keyof DashboardPayload['sacrifice_map']
  label: string
  higherIsBetter: boolean
  categorical?: boolean
  // magnitude axes show raw size (larger = rim), not a higher-is-better share.
  magnitude?: boolean
}> = [
  { key: 'net_takehome_usd', label: 'Take-home (USD)', higherIsBetter: true },
  { key: 'col_relative', label: 'Cost of living', higherIsBetter: true, magnitude: true },
  { key: 'visa_stability_score', label: 'Visa stability', higherIsBetter: true },
  { key: 'pr_timeline_years', label: 'PR speed', higherIsBetter: false },
  { key: 'lottery_risk', label: 'Lottery safety', higherIsBetter: false },
  { key: 'partner_opportunity', label: 'Partner work', higherIsBetter: true, categorical: true },
]

function buildIncome(bundle: CountryBundle): IncomeBreakdown {
  const gross = bundle.wage.gross_annual_local
  const netLocal = bundle.tax.net_annual_local
  return {
    country: bundle.country,
    currency: bundle.wage.currency,
    gross,
    taxAmount: Math.max(0, gross - netLocal),
    netLocal,
    effectiveRate: bundle.tax.effective_rate,
    colIndex: bundle.col.col_index,
  }
}

export function toChartModel(payload: DashboardPayload): ChartModel {
  const { sacrifice_map: sm, bundle_a, bundle_b } = payload

  const comparison: ComparisonPoint[] = DIMENSIONS.map(
    ({ key, label, higherIsBetter, categorical, magnitude }) => {
      const diff = sm[key]
      const aVal = categorical
        ? partnerRank(diff.country_a_value)
        : asNumber(diff.country_a_value)
      const bVal = categorical
        ? partnerRank(diff.country_b_value)
        : asNumber(diff.country_b_value)
      const norm = magnitude
        ? normalizeMagnitude(aVal, bVal)
        : normalizePair(aVal, bVal, higherIsBetter)
      return {
        key,
        label,
        a: norm.a,
        b: norm.b,
        aRaw: diff.country_a_value,
        bRaw: diff.country_b_value,
        winner: diff.winner,
        note: diff.note,
      }
    },
  )

  return {
    comparison,
    incomeBreakdown: { a: buildIncome(bundle_a), b: buildIncome(bundle_b) },
    netComparison: [
      { country: bundle_a.country, netUsd: bundle_a.net_annual_usd },
      { country: bundle_b.country, netUsd: bundle_b.net_annual_usd },
    ],
    visaStability: {
      a: asNumber(sm.visa_stability_score.country_a_value),
      b: asNumber(sm.visa_stability_score.country_b_value),
    },
  }
}
