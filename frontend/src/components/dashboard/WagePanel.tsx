import {
  Bar,
  BarChart,
  Cell,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  type TooltipContentProps,
} from 'recharts'

import type { ChartModel, IncomeBreakdown } from '../../lib/chartModel'
import { AXIS_TICK, COLOR_A, COLOR_B, COLOR_MUTED, GRID_STROKE, TOOLTIP_STYLE } from '../../lib/chartTheme'
import { formatCurrency } from '../../lib/formatters'

interface WagePanelProps {
  model: ChartModel
  countryA: string
  countryB: string
}

// ── Block A: per-country gross breakdown (local currency, NOT comparable) ─────
function GrossBar({ income, accent }: { income: IncomeBreakdown; accent: string }) {
  const data = [
    {
      name: income.country,
      netLocal: income.netLocal,
      taxAmount: income.taxAmount,
      currency: income.currency,
    },
  ]

  const tooltip = ({ active, payload }: TooltipContentProps) => {
    if (!active || !payload?.length) return null
    return (
      <div style={TOOLTIP_STYLE}>
        {payload.map((p) => (
          <div key={String(p.dataKey)} style={{ color: p.color }}>
            {p.dataKey === 'netLocal' ? 'Take-home' : 'Tax & contributions'}:{' '}
            {formatCurrency(Number(p.value), income.currency)}
          </div>
        ))}
      </div>
    )
  }

  return (
    <div>
      <div className="flex items-baseline justify-between">
        <span className="text-sm font-medium text-ink">{income.country}</span>
        <span className="font-mono text-xs text-ink-muted">
          {(income.effectiveRate * 100).toFixed(1)}% effective tax · {income.currency}
        </span>
      </div>
      <div className="mt-1 h-12 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical" margin={{ top: 4, right: 8, bottom: 4, left: 8 }}>
            <XAxis type="number" hide />
            <YAxis type="category" dataKey="name" hide />
            <Tooltip content={tooltip} cursor={{ fill: GRID_STROKE, fillOpacity: 0.3 }} />
            <Bar dataKey="netLocal" stackId="gross" fill={accent} radius={[4, 0, 0, 4]} />
            <Bar dataKey="taxAmount" stackId="gross" fill={COLOR_MUTED} radius={[0, 4, 4, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

// ── Block B: take-home, PPP-adjusted (the ONE cross-country-comparable figure) ─
function NetComparison({ model }: { model: ChartModel }) {
  const data = model.netComparison.map((d, i) => ({
    country: d.country,
    value: d.netTakehomePpp,
    fill: i === 0 ? COLOR_A : COLOR_B,
  }))

  const tooltip = ({ active, payload }: TooltipContentProps) => {
    if (!active || !payload?.length) return null
    const datum = payload[0].payload as { country: string }
    const v = payload[0].value
    return (
      <div style={TOOLTIP_STYLE}>
        {datum.country}: {v == null ? 'n/a' : formatCurrency(Number(v), 'USD')}
      </div>
    )
  }

  return (
    <div className="h-56 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 16, right: 8, bottom: 4, left: 8 }}>
          <XAxis dataKey="country" tick={{ fill: AXIS_TICK, fontSize: 12 }} axisLine={{ stroke: GRID_STROKE }} tickLine={false} />
          <YAxis hide />
          <Tooltip content={tooltip} cursor={{ fill: GRID_STROKE, fillOpacity: 0.3 }} />
          <Bar dataKey="value" radius={[4, 4, 0, 0]}>
            <LabelList
              dataKey="value"
              position="top"
              formatter={(v) => (v == null ? 'n/a' : formatCurrency(Number(v), 'USD'))}
              style={{ fill: AXIS_TICK, fontSize: 12 }}
            />
            {data.map((d) => (
              <Cell key={d.country} fill={d.fill} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

export default function WagePanel({ model }: WagePanelProps) {
  return (
    <section aria-label="Income comparison" className="rounded-xl border border-line bg-surface p-5">
      <h2 className="font-display text-lg font-semibold text-ink">What you actually keep</h2>

      {/* Gross — local currency, explicitly NOT cross-country comparable */}
      <p className="mt-3 font-mono text-[11px] uppercase tracking-[0.14em] text-ink-muted">
        Gross pay split — local currency, not comparable across countries
      </p>
      <div className="mt-3 space-y-3">
        <GrossBar income={model.incomeBreakdown.a} accent={COLOR_A} />
        <GrossBar income={model.incomeBreakdown.b} accent={COLOR_B} />
      </div>

      {/* Net take-home, PPP-adjusted — the one figure safe to compare directly */}
      <p className="mt-6 font-mono text-[11px] uppercase tracking-[0.14em] text-ink-muted">
        Take-home, cost-of-living adjusted (PPP) — comparable, NYC = 100 baseline
      </p>
      <NetComparison model={model} />
    </section>
  )
}
