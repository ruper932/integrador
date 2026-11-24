import { useQuery } from '@tanstack/react-query'

import { api } from '@/lib/api'
import type { IncidentAlerts, IncidentSummary } from '@/types/api'

export function useIncidentSummary(enabled = true) {
  return useQuery({
    queryKey: ['incidents', 'summary'],
    queryFn: async () => (await api.get<IncidentSummary>('/incidents/summary')).data,
    enabled,
    refetchInterval: 60_000,
  })
}

export const ALERTS_KEY = ['incidents', 'alerts']

export function useIncidentAlerts(enabled = true) {
  return useQuery({
    queryKey: ALERTS_KEY,
    queryFn: async () => (await api.get<IncidentAlerts>('/incidents/alerts')).data,
    enabled,
    refetchInterval: 30_000,
  })
}
