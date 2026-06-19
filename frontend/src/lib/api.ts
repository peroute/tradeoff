import type { CompareRequest, DashboardPayload } from '../types'

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

export async function postCompare(body: CompareRequest): Promise<DashboardPayload> {
  const res = await fetch(`${BASE_URL}/api/compare`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    throw new Error(`Compare request failed (${res.status})`)
  }
  return res.json()
}
