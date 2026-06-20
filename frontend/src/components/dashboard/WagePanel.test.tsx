import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'

import WagePanel from './WagePanel'
import { toChartModel } from '../../lib/chartModel'
import { sampleDashboard } from '../../lib/sampleDashboard'

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

describe('WagePanel', () => {
  it('distinguishes the non-comparable gross from the comparable PPP take-home', () => {
    render(<WagePanel model={model} countryA="US" countryB="Germany" />)
    expect(screen.getByText(/not comparable across countries/i)).toBeInTheDocument()
    expect(screen.getByText(/comparable, NYC = 100 baseline/i)).toBeInTheDocument()
  })

  it('labels each country gross bar with its currency and effective tax rate', () => {
    render(<WagePanel model={model} countryA="US" countryB="Germany" />)
    expect(screen.getByText('US')).toBeInTheDocument()
    expect(screen.getByText('Germany')).toBeInTheDocument()
    expect(screen.getByText(/26\.4% effective tax · USD/)).toBeInTheDocument()
    expect(screen.getByText(/31\.7% effective tax · EUR/)).toBeInTheDocument()
  })
})
