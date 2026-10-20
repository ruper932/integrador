import { useQuery } from '@tanstack/react-query'

import { api } from '@/lib/api'
import type { Device, FogCollector, Sensor, SensorType, Tank } from '@/types/api'

export function useDevices() {
  return useQuery({ queryKey: ['devices'], queryFn: async () => (await api.get<Device[]>('/devices')).data })
}

export function useSensors() {
  return useQuery({ queryKey: ['sensors'], queryFn: async () => (await api.get<Sensor[]>('/sensors')).data })
}

export function useSensorTypes() {
  return useQuery({
    queryKey: ['sensor-types'],
    queryFn: async () => (await api.get<SensorType[]>('/sensor-types')).data,
    staleTime: Infinity,
  })
}

export function useFogCollectors() {
  return useQuery({
    queryKey: ['fog-collectors'],
    queryFn: async () => (await api.get<FogCollector[]>('/fog-collectors')).data,
  })
}

export function useTanks() {
  return useQuery({ queryKey: ['tanks'], queryFn: async () => (await api.get<Tank[]>('/tanks')).data })
}
