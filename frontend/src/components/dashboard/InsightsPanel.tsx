import type { InsightOrFallback, ScenarioType, WhatIfInsight, SafeFallback } from '../../types'
import { ConfidenceBadge } from './Badges'

interface InsightsPanelProps {
  insights: InsightOrFallback[]
  countryA: string
  countryB: string
}

const SCENARIO_LABEL: Record<ScenarioType, string> = {
  base: 'Base case',
  lottery_risk: 'Lottery risk',
  extension_risk: 'Extension risk',
  employer_switch: 'Switching employer',
  partner_work: 'Partner work',
  pr_timeline: 'Path to residency',
  priority_match: 'Your priority',
  synthesis: 'Synthesis',
}

function InsightCard({ insight }: { insight: WhatIfInsight }) {
  return (
    <li className="rounded-xl border border-line bg-surface-raised/60 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-mono text-[10px] font-semibold uppercase tracking-[0.16em] text-path-a">
          {SCENARIO_LABEL[insight.scenario_type] ?? insight.scenario_type}
        </span>
        <ConfidenceBadge level={insight.confidence} />
      </div>

      {/* The tradeoff — the structured gain-vs-sacrifice across both options. */}
      <p className="mt-3 text-[15px] font-medium leading-relaxed text-ink">{insight.tradeoff}</p>

      {/* Honest "what happens if" — the likely outcome, including unfavorable odds. */}
      <div className="mt-3 flex items-start gap-2 rounded-lg border border-line bg-paper/40 px-3 py-2">
        <span className="mt-0.5 font-mono text-[9px] font-semibold uppercase tracking-[0.16em] text-ink-muted">
          Likely
        </span>
        <p className="text-[13px] leading-snug text-ink">{insight.likely_outcome}</p>
      </div>

      {/* The non-obvious second-order implication. */}
      <p className="mt-3 text-[13px] leading-relaxed text-ink-muted">{insight.consideration}</p>

      {/* Grounding: each side is pinned to a real fact key + the user's own words. */}
      <div className="mt-3 flex flex-wrap gap-1.5">
        {insight.fact_a && (
          <span className="rounded-md bg-path-a/10 px-2 py-1 font-mono text-[10px] text-path-a">
            {countryA} · {insight.fact_a.replace(/^bundle_[ab]\./, '')}
          </span>
        )}
        {insight.fact_b && (
          <span className="rounded-md bg-path-b/10 px-2 py-1 font-mono text-[10px] text-path-b">
            {countryB} · {insight.fact_b.replace(/^bundle_[ab]\./, '')}
          </span>
        )}
      </div>

      <div className="mt-3 flex items-start gap-2 rounded-lg border border-path-a/20 bg-path-a/5 px-3 py-2">
        <svg
          width="14"
          height="14"
          viewBox="0 0 16 16"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.6"
          aria-hidden
          className="mt-0.5 shrink-0 text-path-a"
        >
          <path d="M3 8 H12 M8 4 L12 8 L8 12" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        <p className="text-[13px] leading-snug text-ink">{insight.next_action}</p>
      </div>

      <p className="mt-2 text-[11px] italic leading-snug text-ink-muted">
        Why this confidence: {insight.confidence_basis}
      </p>
    </li>
  )
}

function WithheldCard({ fallback: _fallback }: { fallback: SafeFallback }) {
  return (
    <li className="rounded-xl border border-dashed border-line bg-surface/40 p-4">
      <span className="font-mono text-[10px] font-semibold uppercase tracking-[0.16em] text-ink-muted">
        Insight withheld
      </span>
      <p className="mt-2 text-[11px] leading-snug text-ink-muted">
        We only show reasoning that passes validation against the real fact bundle, so we held this
        one back rather than guess.
      </p>
    </li>
  )
}

export default function InsightsPanel({ insights, countryA, countryB }: InsightsPanelProps) {
  const passed = insights.filter((i): i is WhatIfInsight => i.type === 'insight').length
  const withheld = insights.length - passed

  // Slots 0 and 1 are always the two single-country base cases (positional, so a withheld
  // base slot still lands here). The remaining comparative insights stay a vertical column.
  const baseItems = insights.slice(0, 2)
  const restItems = insights.slice(2)

  const renderItem = (item: InsightOrFallback, i: number) =>
    item.type === 'insight' ? (
      <InsightCard key={`insight-${i}`} insight={item} />
    ) : (
      <WithheldCard key={`fallback-${item.slot_index}-${i}`} fallback={item} />
    )

  return (
    <section
      aria-label="What-if reasoning"
      className="rounded-xl border border-line bg-surface p-5"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="font-display text-lg font-semibold text-ink">What this means for you</h2>
        <span className="font-mono text-[11px] text-ink-muted">
          {passed} shown{withheld > 0 ? ` · ${withheld} withheld` : ''}
        </span>
      </div>
      <p className="mt-1 text-sm text-ink-muted">
        Each weighs a {countryA} fact against the {countryB} fact, names the tradeoff, and shows the
        likely outcome — grounded in cited facts and your stated priorities.
      </p>

      {/* The two base cases — one per country — sit side-by-side on wide screens, stacked on mobile. */}
      <ul className="mt-4 grid gap-3 lg:grid-cols-2">{baseItems.map(renderItem)}</ul>

      {/* The comparative insights stay a single vertical column. */}
      <ul className="mt-3 space-y-3">{restItems.map((item, i) => renderItem(item, i + 2))}</ul>
    </section>
  )
}
