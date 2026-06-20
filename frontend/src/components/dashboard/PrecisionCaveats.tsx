import type { DashboardPayload } from '../../types'

interface PrecisionCaveatsProps {
  payload: DashboardPayload
}

// Honest disclosure of where the numbers are precise vs. approximated. Wage and
// cost-of-living resolution differ by country (US metro/national BLS vs. OECD
// national average; city Numbeo vs. national PPP), so we surface every gap rather
// than let the side-by-side imply equal precision.
export default function PrecisionCaveats({ payload }: PrecisionCaveatsProps) {
  const { bundle_a, bundle_b, pipeline_meta: meta } = payload

  const caveats: string[] = []

  for (const bundle of [bundle_a, bundle_b]) {
    if (bundle.wage.precision_note) {
      caveats.push(`${bundle.country} wage: ${bundle.wage.precision_note}`)
    }
    if (bundle.col.col_source === 'national_ppp') {
      caveats.push(
        `${bundle.country} cost of living: national PPP fallback — no city-level index for the city provided.`,
      )
    }
    if (bundle.col.precision_note) {
      caveats.push(`${bundle.country} cost of living: ${bundle.col.precision_note}`)
    }
    if (bundle.tax.notes) {
      caveats.push(`${bundle.country} tax: ${bundle.tax.notes}`)
    }
  }

  if (meta.insights_withheld > 0) {
    caveats.push(
      `${meta.insights_withheld} generated insight${meta.insights_withheld > 1 ? 's were' : ' was'} withheld for failing fact-validation.`,
    )
  }

  return (
    <section
      aria-label="Data precision and sources"
      className="rounded-xl border border-line bg-surface/60 p-5"
    >
      <h2 className="font-display text-base font-semibold text-ink">How precise is this?</h2>
      <p className="mt-1 text-sm text-ink-muted">
        Resolution differs by country — here's exactly where, so you can weight each figure
        accordingly.
      </p>

      <ul className="mt-3 space-y-1.5">
        {caveats.map((c) => (
          <li key={c} className="flex gap-2 text-[12px] leading-snug text-ink-muted">
            <span aria-hidden className="text-ink-muted/60">
              ·
            </span>
            {c}
          </li>
        ))}
      </ul>

      <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-1.5 border-t border-line/60 pt-3 font-mono text-[11px] text-ink-muted">
        <span>{meta.ai_calls_made} AI calls</span>
        <span>·</span>
        <span>{meta.insights_passed} insights validated</span>
        {Object.entries(meta.fact_sources).map(([k, v]) => (
          <span key={k}>
            · {k}: {v}
          </span>
        ))}
      </div>
    </section>
  )
}
