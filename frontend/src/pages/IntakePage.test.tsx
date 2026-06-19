import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

import IntakePage from './IntakePage'
import { postCompare } from '../lib/api'
import type { DashboardPayload } from '../types'

vi.mock('../lib/api', () => ({ postCompare: vi.fn() }))

const navigateMock = vi.fn()
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>()
  return { ...actual, useNavigate: () => navigateMock }
})

const postCompareMock = vi.mocked(postCompare)

function renderPage() {
  return render(
    <MemoryRouter>
      <IntakePage />
    </MemoryRouter>,
  )
}

async function fillValidForm() {
  renderPage()
  const user = userEvent.setup()
  await user.type(screen.getByLabelText('Citizenship'), 'India')
  await user.type(screen.getByLabelText('Degree field'), 'Computer Science')
  await user.selectOptions(screen.getByLabelText('Career stage'), 'new_grad')
  await user.type(screen.getByLabelText('What matters most to you?'), 'stability')
  return user
}

const EXPECTED_PAYLOAD = {
  citizenship: 'India',
  degree_field: 'Computer Science',
  career_stage: 'new_grad',
  country_a: 'US',
  country_b: 'UK',
  user_context: 'stability',
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('IntakePage', () => {
  it('renders all form fields and the submit button', () => {
    renderPage()
    expect(screen.getByLabelText('Citizenship')).toBeInTheDocument()
    expect(screen.getByLabelText('Degree field')).toBeInTheDocument()
    expect(screen.getByLabelText('Career stage')).toBeInTheDocument()
    expect(screen.getByLabelText('Country A')).toBeInTheDocument()
    expect(screen.getByLabelText('Country B')).toBeInTheDocument()
    expect(screen.getByLabelText('What matters most to you?')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Compare' })).toBeInTheDocument()
  })

  it('blocks submit and shows errors when required fields are empty', async () => {
    const user = userEvent.setup()
    renderPage()

    await user.click(screen.getByRole('button', { name: 'Compare' }))

    expect(postCompareMock).not.toHaveBeenCalled()
    expect(screen.getByText('Citizenship is required.')).toBeInTheDocument()
    expect(screen.getByText('Degree field is required.')).toBeInTheDocument()
    expect(screen.getByText('Select a career stage.')).toBeInTheDocument()
    expect(screen.getByText('Tell us what matters most to you.')).toBeInTheDocument()
  })

  it('rejects two identical countries', async () => {
    const user = await fillValidForm()
    await user.selectOptions(screen.getByLabelText('Country B'), 'US') // same as Country A

    await user.click(screen.getByRole('button', { name: 'Compare' }))

    expect(screen.getByText('Pick two different countries.')).toBeInTheDocument()
    expect(postCompareMock).not.toHaveBeenCalled()
  })

  it('submits the request and navigates to /dashboard with the payload', async () => {
    const payload = { bundle_a: {} }
    postCompareMock.mockResolvedValue(payload)

    const user = await fillValidForm()
    await user.click(screen.getByRole('button', { name: 'Compare' }))

    await waitFor(() => expect(postCompareMock).toHaveBeenCalledTimes(1))
    expect(postCompareMock).toHaveBeenCalledWith(EXPECTED_PAYLOAD)
    await waitFor(() =>
      expect(navigateMock).toHaveBeenCalledWith('/dashboard', { state: { payload } }),
    )
  })

  it('surfaces an API error and does not navigate', async () => {
    postCompareMock.mockRejectedValue(new Error('Server boom'))

    const user = await fillValidForm()
    await user.click(screen.getByRole('button', { name: 'Compare' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Server boom')
    expect(navigateMock).not.toHaveBeenCalled()
  })

  it('disables the button and shows a loading label while pending', async () => {
    let resolve!: (value: DashboardPayload) => void
    postCompareMock.mockReturnValue(
      new Promise<DashboardPayload>((r) => {
        resolve = r
      }),
    )

    const user = await fillValidForm()
    await user.click(screen.getByRole('button', { name: 'Compare' }))

    const button = await screen.findByRole('button', { name: 'Comparing…' })
    expect(button).toBeDisabled()

    resolve({}) // let the pending request settle
  })
})
