import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'

import SacrificeMap from './SacrificeMap'
import { toChartModel } from '../../lib/chartModel'
import { sampleDashboard } from '../../lib/sampleDashboard'

// Recharts' ResponsiveContainer measures its parent, which is 0×0 in jsdom and
// suppresses rendering. Give it fixed dimensions so the chart mounts.
vi.mock('recharts', async (importOriginal) => {
  const actual = await importOriginal<typeof import('recharts')>()
  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
      <div style={{ width: 800, height: 400 }}>{children}</div>
    ),
  }
})

const model = toChartModel(sampleDashboard)

describe('SacrificeMap', () => {
  it('renders the comparison heading and the normalization caveat', () => {
    render(<SacrificeMap model={model} countryA="US" countryB="Germany" />)
    expect(screen.getByRole('heading', { name: 'Where each path wins' })).toBeInTheDocument()
    expect(screen.getByText(/normalized 0–1/i)).toBeInTheDocument()
  })

  it('is labeled as the trade-off comparison region', () => {
    render(<SacrificeMap model={model} countryA="US" countryB="Germany" />)
    expect(screen.getByRole('region', { name: 'Trade-off comparison' })).toBeInTheDocument()
  })
})
