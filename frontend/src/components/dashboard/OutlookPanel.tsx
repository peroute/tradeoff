import type { ImmigrationOutlook } from '../../types'
import { ConfidenceBadge, TrendBadge } from './Badges'

interface OutlookPanelProps {
  country: string
  outlook: ImmigrationOutlook
}

export default function OutlookPanel({ country, outlook }: OutlookPanelProps) {
  return (
    <div className="rounded-xl border border-line bg-surface-raised/40 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="font-display text-base font-semibold text-ink">{country}</h3>
        <div className="flex items-center gap-2">
          <TrendBadge direction={outlook.trend_direction} />
          <ConfidenceBadge level={outlook.confidence} />
        </div>
      </div>

      <p className="mt-2 text-[13px] leading-relaxed text-ink">{outlook.trend_summary}</p>

      <dl className="mt-3 space-y-2">
        <div>
          <dt className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink-muted">
            Recent change
          </dt>
          <dd className="mt-0.5 text-[12px] leading-snug text-ink">{outlook.key_recent_change}</dd>
        </div>
        <div>
          <dt className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink-muted">
            Career context
          </dt>
          <dd className="mt-0.5 text-[12px] leading-snug text-ink">{outlook.career_context}</dd>
        </div>
      </dl>

      <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-ink-muted">
        <a
          href={outlook.source_url}
          target="_blank"
          rel="noreferrer noopener"
          className="underline decoration-dotted underline-offset-2 hover:text-ink"
        >
          Source
        </a>
        {outlook.source_publish_date && <span>· published {outlook.source_publish_date}</span>}
      </div>
    </div>
  )
}
