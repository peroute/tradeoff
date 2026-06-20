import { useLocation } from 'react-router-dom'

import AmbientBackground from '../components/shared/AmbientBackground'
import HumanBoundaryBanner from '../components/dashboard/HumanBoundaryBanner'
import InsightsPanel from '../components/dashboard/InsightsPanel'
import OutlookPanel from '../components/dashboard/OutlookPanel'
import PrecisionCaveats from '../components/dashboard/PrecisionCaveats'
import SacrificeMap from '../components/dashboard/SacrificeMap'
import VisaRoutePanel, {
  VISA_ACCENT_A,
  VISA_ACCENT_B,
} from '../components/dashboard/VisaRoutePanel'
import WagePanel from '../components/dashboard/WagePanel'
import { toChartModel } from '../lib/chartModel'
import { sampleDashboard } from '../lib/sampleDashboard'
import type { DashboardPayload } from '../types'

function SectionEyebrow({ children }: { children: React.ReactNode }) {
  return (
    <p className="mb-3 font-mono text-[11px] font-medium uppercase tracking-[0.18em] text-ink-muted">
      {children}
    </p>
  )
}

export default function DashboardPage() {
  // IntakePage navigates here with the live payload in router state. Falling back
  // to the sample fixture lets the dashboard render standalone (direct visit / dev).
  const location = useLocation()
  const payload = (location.state as { payload?: DashboardPayload } | null)?.payload ?? sampleDashboard

  const model = toChartModel(payload)
  const countryA = payload.bundle_a.country
  const countryB = payload.bundle_b.country

  return (
    <main className="relative min-h-dvh">
      <AmbientBackground />
      <HumanBoundaryBanner />

      <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6">
        <header className="mb-8">
          <h1 className="font-display text-2xl font-semibold text-ink sm:text-3xl">
            <span className="text-path-a">{countryA}</span>{' '}
            <span className="text-ink-muted">vs</span>{' '}
            <span className="text-path-b">{countryB}</span>
          </h1>
          <p className="mt-1 text-sm text-ink-muted">
            The trade-offs laid out — we never pick for you.
          </p>
        </header>

        <div className="space-y-10">
          {/* The AI reasoning leads — it's the reason the rest of the page matters. */}
          <section>
            <SectionEyebrow>What-if reasoning</SectionEyebrow>
            <InsightsPanel insights={payload.insights} />
          </section>

          <section>
            <SectionEyebrow>Visa routes for your citizenship</SectionEyebrow>
            <div className="grid gap-4 lg:grid-cols-2">
              <VisaRoutePanel bundle={payload.bundle_a} accent={VISA_ACCENT_A} />
              <VisaRoutePanel bundle={payload.bundle_b} accent={VISA_ACCENT_B} />
            </div>
          </section>

          <section>
            <SectionEyebrow>Immigration outlook</SectionEyebrow>
            <div className="grid gap-4 lg:grid-cols-2">
              <OutlookPanel country={countryA} outlook={payload.outlook_a} />
              <OutlookPanel country={countryB} outlook={payload.outlook_b} />
            </div>
          </section>

          <section>
            <SectionEyebrow>The numbers</SectionEyebrow>
            <div className="grid gap-6 lg:grid-cols-2">
              <SacrificeMap model={model} countryA={countryA} countryB={countryB} />
              <WagePanel model={model} countryA={countryA} countryB={countryB} />
            </div>
          </section>

          <PrecisionCaveats payload={payload} />
        </div>
      </div>
    </main>
  )
}
