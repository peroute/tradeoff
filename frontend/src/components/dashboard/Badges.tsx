// Shared status pills used across the dashboard panels. Kept in one place so the
// confidence + trend vocabulary reads identically everywhere it appears.

import type { ConfidenceLevel, TrendDirection } from '../../types'

const PILL_BASE =
  'inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 font-mono text-[10px] font-medium uppercase tracking-[0.12em]'

const CONFIDENCE_STYLE: Record<ConfidenceLevel, string> = {
  high: 'bg-path-a/15 text-path-a',
  medium: 'bg-path-b/15 text-path-b',
  low: 'bg-signal/15 text-signal',
}

export function ConfidenceBadge({ level }: { level: ConfidenceLevel }) {
  return (
    <span className={`${PILL_BASE} ${CONFIDENCE_STYLE[level]}`}>
      <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-current" />
      {level} confidence
    </span>
  )
}

const TREND_STYLE: Record<TrendDirection, { cls: string; label: string; glyph: string }> = {
  improving: { cls: 'bg-path-a/15 text-path-a', label: 'Improving', glyph: '↗' },
  stable: { cls: 'bg-ink-muted/15 text-ink-muted', label: 'Stable', glyph: '→' },
  restrictive: { cls: 'bg-signal/15 text-signal', label: 'Restrictive', glyph: '↘' },
}

export function TrendBadge({ direction }: { direction: TrendDirection }) {
  const t = TREND_STYLE[direction]
  return (
    <span className={`${PILL_BASE} ${t.cls}`}>
      <span aria-hidden>{t.glyph}</span>
      {t.label}
    </span>
  )
}
