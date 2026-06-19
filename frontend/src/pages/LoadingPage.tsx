import { useEffect, useState } from 'react'

import type { SupportedCountry } from '../types'
import { COUNTRY_META } from '../types'

interface GeneratingScreenProps {
  countryA?: SupportedCountry
  countryB?: SupportedCountry
}

// Honest descriptions of what the pipeline actually does — not live per-stage telemetry.
const REASSURANCES = [
  'Weighing wages, cost of living, and taxes…',
  'Mapping visa routes for your citizenship…',
  'Reasoning through the trade-offs…',
  'Cross-checking every figure against its source…',
]

// Two diagonal strokes drawing in and converging on a single point.
const PATH_A = 'M 20 24 L 100 100'
const PATH_B = 'M 180 24 L 100 100'

export default function GeneratingScreen({ countryA, countryB }: GeneratingScreenProps) {
  const [line, setLine] = useState(0)

  useEffect(() => {
    const id = setInterval(() => setLine((i) => (i + 1) % REASSURANCES.length), 2600)
    return () => clearInterval(id)
  }, [])

  const heading =
    countryA && countryB
      ? `Comparing ${COUNTRY_META[countryA].name} and ${COUNTRY_META[countryB].name}`
      : 'Comparing your two options'

  return (
    <div
      role="status"
      aria-live="polite"
      className="flex min-h-screen flex-col items-center justify-center bg-paper px-6 text-center"
    >
      <svg
        width="200"
        height="120"
        viewBox="0 0 200 120"
        fill="none"
        aria-hidden="true"
        className="overflow-visible"
      >
        {countryA && (
          <text x="20" y="14" textAnchor="middle" className="fill-path-a font-mono text-[11px] font-semibold">
            {COUNTRY_META[countryA].code}
          </text>
        )}
        {countryB && (
          <text x="180" y="14" textAnchor="middle" className="fill-path-b font-mono text-[11px] font-semibold">
            {COUNTRY_META[countryB].code}
          </text>
        )}
        <path
          d={PATH_A}
          className="path-draw stroke-path-a"
          style={{ ['--path-length' as string]: 110 }}
          strokeWidth="2.5"
          strokeLinecap="round"
        />
        <path
          d={PATH_B}
          className="path-draw stroke-path-b"
          style={{ ['--path-length' as string]: 110 }}
          strokeWidth="2.5"
          strokeLinecap="round"
        />
        <circle cx="100" cy="100" r="6" className="meet-point fill-ink" />
      </svg>

      <h1 className="mt-8 font-display text-xl font-semibold text-ink sm:text-2xl">{heading}</h1>
      <p className="mt-3 h-6 text-sm text-ink-muted transition-opacity">{REASSURANCES[line]}</p>

      <p className="mt-10 max-w-sm font-mono text-xs uppercase tracking-[0.16em] text-ink-muted/80">
        We never pick for you — we lay out the trade-offs.
      </p>
    </div>
  )
}
