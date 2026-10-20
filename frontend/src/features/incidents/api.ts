import { useQuery } from '@tanstack/react-query'

import { api } from '@/lib/api'
import type { IncidentSummary } from '@/types/api'

export function useIncidentSummary(enabled = true) {
  return useQuery({
    queryKey: ['incidents', 'summary'],
    queryFn: async () => (await api.get<IncidentSummary>('/incidents/summary')).data,
    enabled,
    refetchInterval: 60_000,
  })
}
