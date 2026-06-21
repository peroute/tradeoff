import type { CompareRequest, DashboardPayload } from '../types'

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'
const TIMEOUT_MS = 90_000

export async function postCompare(body: CompareRequest): Promise<DashboardPayload> {
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), TIMEOUT_MS)
  try {
    const res = await fetch(`${BASE_URL}/api/compare`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: controller.signal,
    })
    if (!res.ok) {
      throw new Error(`Compare request failed (${res.status})`)
    }
    return res.json()
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new Error('Analysis is taking longer than expected — please try again.')
    }
    throw err
  } finally {
    clearTimeout(timeoutId)
  }
}
