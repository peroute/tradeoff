// useCompare: POST /api/compare, manages loading + result state.
import { useState } from 'react'

import { postCompare } from '../lib/api'
import type { CompareRequest, DashboardPayload } from '../types'

interface UseCompare {
  submit: (request: CompareRequest) => Promise<DashboardPayload>
  loading: boolean
  error: string | null
  data: DashboardPayload | null
}

export function useCompare(): UseCompare {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [data, setData] = useState<DashboardPayload | null>(null)

  async function submit(request: CompareRequest): Promise<DashboardPayload> {
    setLoading(true)
    setError(null)
    try {
      const payload = await postCompare(request)
      setData(payload)
      return payload
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Something went wrong'
      setError(message)
      throw err
    } finally {
      setLoading(false)
    }
  }

  return { submit, loading, error, data }
}
