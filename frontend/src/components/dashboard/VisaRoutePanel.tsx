import type { CountryBundle } from '../../types'
import { ConfidenceBadge } from './Badges'

// Full static class strings (Tailwind can't see dynamically-built names), keyed
// by which path this column represents.
export interface VisaAccent {
  text: string
  border: string
  hover: string
}

export const VISA_ACCENT_A: VisaAccent = {
  text: 'text-path-a',
  border: 'border-path-a/40',
  hover: 'hover:text-path-a',
}

export const VISA_ACCENT_B: VisaAccent = {
  text: 'text-path-b',
  border: 'border-path-b/40',
  hover: 'hover:text-path-b',
}

interface VisaRoutePanelProps {
  bundle: CountryBundle
  accent: VisaAccent
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-3 border-t border-line/60 py-2 first:border-t-0">
      <span className="shrink-0 text-[12px] text-ink-muted">{label}</span>
      <span className="text-right text-[12px] font-medium text-ink">{children}</span>
    </div>
  )
}

function yesNo(value: boolean | null, yes = 'Yes', no = 'No') {
  if (value === null) return '—'
  return value ? yes : no
}

export default function VisaRoutePanel({ bundle, accent }: VisaRoutePanelProps) {
  const { visa_route: route, visa_enrichment: enr } = bundle

  return (
    <div className={`rounded-xl border bg-surface-raised/40 p-4 ${accent.border}`}>
      <div className="flex items-center justify-between gap-2">
        <div>
          <span className={`font-mono text-[10px] uppercase tracking-[0.14em] ${accent.text}`}>
            {bundle.country}
          </span>
          <h3 className="font-display text-base font-semibold text-ink">{route.visa_name}</h3>
        </div>
        <ConfidenceBadge level={route.routing_confidence} />
      </div>

      <p className="mt-2 text-[13px] leading-snug text-ink-muted">{route.eligibility_summary}</p>

      <div className="mt-3 rounded-lg bg-signal/10 px-3 py-2">
        <p className="text-[12px] leading-snug text-ink">
          <span className="font-medium text-signal">Key constraint · </span>
          {route.key_constraint}
        </p>
      </div>

      <div className="mt-3">
        <Row label="Employer sponsorship">
          {yesNo(route.employer_sponsorship_required, 'Required', 'Not required')}
        </Row>
        <Row label="Path to residency">
          {route.path_to_residency_years != null ? `${route.path_to_residency_years} yrs` : '—'}
        </Row>
        {enr && (
          <>
            {enr.lottery_required != null && (
              <Row label="Lottery">
                {enr.lottery_required
                  ? enr.lottery_annual_rate != null
                    ? `Yes · ~${Math.round(enr.lottery_annual_rate * 100)}% selected/yr`
                    : 'Yes'
                  : 'None'}
              </Row>
            )}
            {enr.partner_work_rights && (
              <Row label="Partner work rights">
                <span className="capitalize">{enr.partner_work_rights}</span>
              </Row>
            )}
            {enr.can_switch_employer != null && (
              <Row label="Switch employer">{yesNo(enr.can_switch_employer)}</Row>
            )}
            {enr.min_salary != null && (
              <Row label="Salary floor">
                {enr.min_salary.toLocaleString('en-US')} {enr.currency ?? ''}
              </Row>
            )}
          </>
        )}
      </div>

      {enr?.switch_conditions && (
        <p className="mt-2 text-[11px] leading-snug text-ink-muted">{enr.switch_conditions}</p>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-ink-muted">
        <a
          href={route.source_url}
          target="_blank"
          rel="noreferrer noopener"
          className={`underline decoration-dotted underline-offset-2 ${accent.hover}`}
        >
          Official source
        </a>
        {enr?.last_verified && <span>· verified {enr.last_verified}</span>}
      </div>
    </div>
  )
}
