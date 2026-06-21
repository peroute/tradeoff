import {
  Legend,
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
  type TooltipContentProps,
} from 'recharts'

import type { ChartModel, ComparisonPoint } from '../../lib/chartModel'
import { AXIS_TICK, COLOR_A, COLOR_B, GRID_STROKE, TOOLTIP_STYLE } from '../../lib/chartTheme'

interface SacrificeMapProps {
  model: ChartModel
  countryA: string
  countryB: string
}

// Recharts hands the tooltip the full datum on `payload[0].payload`, so we read
// the *raw* values off it — the radar axes are normalized 0–1 shares, which are
// only meaningful as a shape comparison, not as numbers to report.
function renderRawValue(v: ComparisonPoint['aRaw']): string {
  if (v === null) return 'n/a'
  if (typeof v === 'number') return Number.isInteger(v) ? String(v) : v.toLocaleString('en-US', { maximumFractionDigits: 2 })
  return v
}

function ComparisonTooltip(
  { active, payload, countryA, countryB }: TooltipContentProps & {
    countryA: string
    countryB: string
  },
) {
  if (!active || !payload?.length) return null
  const point = payload[0].payload as ComparisonPoint
  const winnerLabel =
    point.winner === 'a' ? countryA : point.winner === 'b' ? countryB : point.winner === 'tie' ? 'Tie' : '—'
  return (
    <div style={TOOLTIP_STYLE}>
      <div style={{ fontWeight: 600, marginBottom: 4 }}>{point.label}</div>
      <div style={{ color: COLOR_A }}>
        {countryA}: {renderRawValue(point.aRaw)}
      </div>
      <div style={{ color: COLOR_B }}>
        {countryB}: {renderRawValue(point.bRaw)}
      </div>
      <div style={{ color: AXIS_TICK, marginTop: 4 }}>Edge: {winnerLabel}</div>
    </div>
  )
}

export default function SacrificeMap({ model, countryA, countryB }: SacrificeMapProps) {
  // Recharts overlays both series off one row per spoke; null shares collapse to 0
  // so the polygon still closes (the tooltip shows the honest "n/a").
  const data = model.comparison
    // Drop an axis only when BOTH countries are n/a (e.g. PR speed, Lottery often
    // empty); an axis with one real value is kept so the present side still shows.
    .filter((c) => c.a !== null || c.b !== null)
    .map((c) => ({
      ...c,
      a: c.a ?? 0,
      b: c.b ?? 0,
    }))

  return (
    <section
      aria-label="Trade-off comparison"
      className="rounded-xl border border-line bg-surface p-5"
    >
      <h2 className="font-display text-lg font-semibold text-ink">Where each path wins</h2>
      <p className="mt-1 text-sm text-ink-muted">
        Each axis is normalized 0–1 — further out is better. Hover a point for the real figure.
      </p>

      <div className="mt-4 h-80 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <RadarChart data={data} outerRadius="72%">
            <PolarGrid stroke={GRID_STROKE} />
            <PolarAngleAxis dataKey="label" tick={{ fill: AXIS_TICK, fontSize: 12 }} />
            <PolarRadiusAxis domain={[0, 1]} tick={false} axisLine={false} />
            <Radar
              name={countryA}
              dataKey="a"
              stroke={COLOR_A}
              fill={COLOR_A}
              fillOpacity={0.25}
            />
            <Radar
              name={countryB}
              dataKey="b"
              stroke={COLOR_B}
              fill={COLOR_B}
              fillOpacity={0.25}
            />
            <Legend wrapperStyle={{ fontSize: 13, color: AXIS_TICK }} />
            <Tooltip
              content={(props) => (
                <ComparisonTooltip {...props} countryA={countryA} countryB={countryB} />
              )}
            />
          </RadarChart>
        </ResponsiveContainer>
      </div>
    </section>
  )
}
