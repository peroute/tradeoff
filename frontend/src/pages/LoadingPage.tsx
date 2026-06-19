import { useEffect, useState } from 'react'

import AmbientBackground from '../components/shared/AmbientBackground'
import type { SupportedCountry } from '../types'
import { COUNTRY_META } from '../types'

interface GeneratingScreenProps {
  countryA?: SupportedCountry
  countryB?: SupportedCountry
}

// Honest descriptions of what the pipeline actually does — not live per-stage telemetry.
const REASSURANCES = [
  'Weighing wages, cost of living, and taxes',
  'Mapping visa routes for your citizenship',
  'Reasoning through the trade-offs',
  'Cross-checking every figure against its source',
]

// Two diagonal strokes drawing in and converging on a single decision node.
const PATH_A = 'M 28 26 L 130 150'
const PATH_B = 'M 232 26 L 130 150'

export default function GeneratingScreen({ countryA, countryB }: GeneratingScreenProps) {
  const [step, setStep] = useState(0)

  useEffect(() => {
    const id = setInterval(() => setStep((i) => (i + 1) % REASSURANCES.length), 2600)
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
      className="relative flex min-h-dvh flex-col items-center justify-center px-6 text-center"
    >
      <AmbientBackground />

      <svg
        width="260"
        height="180"
        viewBox="0 0 260 180"
        fill="none"
        aria-hidden="true"
        className="overflow-visible"
      >
        {/* Origin glyphs — the two countries at the top of each path */}
        {countryA && (
          <g className="glyph-float">
            <text
              x="28"
              y="16"
              textAnchor="middle"
              className="fill-path-a font-mono text-[12px] font-semibold"
            >
              {COUNTRY_META[countryA].code}
            </text>
            <circle cx="28" cy="26" r="4" className="fill-path-a" />
          </g>
        )}
        {countryB && (
          <g className="glyph-float" style={{ animationDelay: '2s' }}>
            <text
              x="232"
              y="16"
              textAnchor="middle"
              className="fill-path-b font-mono text-[12px] font-semibold"
            >
              {COUNTRY_META[countryB].code}
            </text>
            <circle cx="232" cy="26" r="4" className="fill-path-b" />
          </g>
        )}

        {/* Faint full paths underneath, then the animated draw on top */}
        <path d={PATH_A} className="stroke-line" strokeWidth="1.5" opacity="0.5" />
        <path d={PATH_B} className="stroke-line" strokeWidth="1.5" opacity="0.5" />
        <path
          d={PATH_A}
          className="path-draw stroke-path-a"
          style={{ ['--path-length' as string]: 162 }}
          strokeWidth="2.5"
          strokeLinecap="round"
        />
        <path
          d={PATH_B}
          className="path-draw stroke-path-b"
          style={{ ['--path-length' as string]: 162 }}
          strokeWidth="2.5"
          strokeLinecap="round"
        />

        {/* Data packets travelling toward the convergence node */}
        <circle
          r="3.5"
          className="packet fill-path-a"
          style={{ offsetPath: `path('${PATH_A}')` }}
        />
        <circle
          r="3.5"
          className="packet fill-path-b"
          style={{ offsetPath: `path('${PATH_B}')`, animationDelay: '0.4s' }}
        />

        {/* Convergence node with emitted rings */}
        <circle cx="130" cy="150" r="9" className="meet-ring stroke-path-a" strokeWidth="1.5" />
        <circle
          cx="130"
          cy="150"
          r="9"
          className="meet-ring stroke-path-b"
          strokeWidth="1.5"
          style={{ animationDelay: '1.2s' }}
        />
        <circle cx="130" cy="150" r="7" className="meet-point fill-ink" />
      </svg>

      <h1 className="mt-10 font-display text-xl font-semibold text-ink sm:text-2xl">{heading}</h1>

      {/* Reassurance stepper — describes the pipeline stage by stage */}
      <div className="mt-4 flex h-6 items-center justify-center gap-2 text-sm text-ink-muted">
        <span aria-hidden className="h-1.5 w-1.5 animate-pulse rounded-full bg-path-a" />
        <span key={step} className="transition-opacity">
          {REASSURANCES[step]}…
        </span>
      </div>

      <div aria-hidden className="mt-5 flex items-center gap-1.5">
        {REASSURANCES.map((_, i) => (
          <span
            key={i}
            className={`h-1 rounded-full transition-all duration-500 ${
              i === step ? 'w-6 bg-ink/80' : 'w-1.5 bg-line'
            }`}
          />
        ))}
      </div>

      <p className="mt-12 max-w-sm font-mono text-[11px] uppercase tracking-[0.18em] text-ink-muted/70">
        We never pick for you — we lay out the trade-offs
      </p>
    </div>
  )
}
