import { useEffect, useMemo } from 'react'
import { Navigate, useLocation } from 'react-router-dom'

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
import type { DashboardPayload } from '../types'

// Where a freshly-computed comparison is stashed so a refresh / back-forward on
// /dashboard keeps showing THIS run instead of dropping the user. Scoped to the
// tab (sessionStorage) and cleared when the tab closes — it is never a substitute
// for a live result, only a short-lived cache of the one the user just generated.
const PAYLOAD_STORAGE_KEY = 'tradeoff:dashboardPayload'

function SectionEyebrow({ children }: { children: React.ReactNode }) {
  return (
    <p className="mb-3 font-mono text-[11px] font-medium uppercase tracking-[0.18em] text-ink-muted">
      {children}
    </p>
  )
}

export default function DashboardPage() {
  // IntakePage navigates here with the live payload in router state. The dashboard
  // NEVER renders canned data: if there is no live result (direct visit, shared
  // link, or router state lost on refresh) we rehydrate the one saved this session,
  // and if that is also absent we send the user back to run a real comparison.
  const location = useLocation()
  const statePayload = (location.state as { payload?: DashboardPayload } | null)?.payload ?? null

  const payload = useMemo<DashboardPayload | null>(() => {
    if (statePayload) return statePayload
    try {
      const stored = sessionStorage.getItem(PAYLOAD_STORAGE_KEY)
      return stored ? (JSON.parse(stored) as DashboardPayload) : null
    } catch {
      return null
    }
  }, [statePayload])

  // Persist a freshly-navigated payload so a later refresh keeps it. A side
  // effect, so it runs in useEffect rather than during render.
  useEffect(() => {
    if (!statePayload) return
    try {
      sessionStorage.setItem(PAYLOAD_STORAGE_KEY, JSON.stringify(statePayload))
    } catch {
      // sessionStorage unavailable (private mode / quota) — non-fatal; the live
      // result still renders this visit, only the refresh-survival is lost.
    }
  }, [statePayload])

  // No live result and nothing cached → return to intake instead of showing data.
  if (!payload) {
    return <Navigate to="/" replace />
  }

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
            <InsightsPanel insights={payload.insights} countryA={countryA} countryB={countryB} />
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
