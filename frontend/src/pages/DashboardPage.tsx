import { useLocation } from 'react-router-dom'

import AmbientBackground from '../components/shared/AmbientBackground'
import SacrificeMap from '../components/dashboard/SacrificeMap'
import WagePanel from '../components/dashboard/WagePanel'
import { toChartModel } from '../lib/chartModel'
import { sampleDashboard } from '../lib/sampleDashboard'
import type { DashboardPayload } from '../types'

export default function DashboardPage() {
  // IntakePage navigates here with the live payload in router state. Falling back
  // to the sample fixture lets the dashboard render standalone (direct visit / dev).
  const location = useLocation()
  const payload = (location.state as { payload?: DashboardPayload } | null)?.payload ?? sampleDashboard

  const model = toChartModel(payload)
  const countryA = payload.bundle_a.country
  const countryB = payload.bundle_b.country

  return (
    <main className="relative min-h-dvh px-4 py-10 sm:px-6">
      <AmbientBackground />

      <div className="mx-auto max-w-5xl">
        <header className="mb-8">
          <h1 className="font-display text-2xl font-semibold text-ink sm:text-3xl">
            {countryA} <span className="text-ink-muted">vs</span> {countryB}
          </h1>
          <p className="mt-1 text-sm text-ink-muted">
            The trade-offs laid out — we never pick for you.
          </p>
        </header>

        <div className="grid gap-6 lg:grid-cols-2">
          <SacrificeMap model={model} countryA={countryA} countryB={countryB} />
          <WagePanel model={model} countryA={countryA} countryB={countryB} />
        </div>
      </div>
    </main>
  )
}
