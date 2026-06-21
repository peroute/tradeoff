import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'

import VisaRoutePanel, { VISA_ACCENT_A } from './VisaRoutePanel'
import { dashboardFixture } from '../../test/fixtures/dashboardFixture'

const enrichedBundle = dashboardFixture.bundle_a

describe('VisaRoutePanel', () => {
  it('renders curated enrichment rows when visa_enrichment is present', () => {
    render(<VisaRoutePanel bundle={enrichedBundle} accent={VISA_ACCENT_A} />)
    expect(screen.getByText('Salary floor')).toBeInTheDocument()
    expect(screen.getByText('Lottery')).toBeInTheDocument()
    expect(screen.getByText('Switch employer')).toBeInTheDocument()
    expect(screen.getByText(/verified/i)).toBeInTheDocument()
    // The honest "not modeled" note must NOT appear when data exists.
    expect(screen.queryByText(/not in curated dataset/i)).not.toBeInTheDocument()
  })

  it('shows an honest note instead of collapsing when enrichment is null', () => {
    const bundle = { ...enrichedBundle, visa_enrichment: null }
    render(<VisaRoutePanel bundle={bundle} accent={VISA_ACCENT_A} />)
    expect(screen.getByText(/not in curated dataset/i)).toBeInTheDocument()
    // Enrichment-only rows and the verified date are absent.
    expect(screen.queryByText('Salary floor')).not.toBeInTheDocument()
    expect(screen.queryByText('Lottery')).not.toBeInTheDocument()
    expect(screen.queryByText(/verified/i)).not.toBeInTheDocument()
    // But the AI-route rows still render.
    expect(screen.getByText('Employer sponsorship')).toBeInTheDocument()
  })
})
