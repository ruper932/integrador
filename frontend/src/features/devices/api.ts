import { type QueryClient, useQuery } from '@tanstack/react-query'

import { api } from '@/lib/api'
import type { DashboardSummary, Device, DeviceStatusItem, FogCollector, Location, Sensor, SensorType, Tank } from '@/types/api'

// La última comunicación se refresca con la misma frecuencia que el resumen de estaciones.
const CONNECTION_REFRESH_MS = 30_000

export function useDevices() {
  return useQuery({
    queryKey: ['devices'],
    queryFn: async () => (await api.get<Device[]>('/devices')).data,
    refetchInterval: CONNECTION_REFRESH_MS,
  })
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

/** Ubicaciones activas (destinos posibles de un atrapanieblas o una estación). */
export function useLocations() {
  return useQuery({ queryKey: ['locations'], queryFn: async () => (await api.get<Location[]>('/locations')).data })
}

export type Connection = 'en_linea' | 'sin_conexion' | 'mantenimiento'

export function connection(device: DeviceStatusItem): Connection {
  if (device.status === 'mantenimiento') return 'mantenimiento'
  return device.is_stale ? 'sin_conexion' : 'en_linea'
}

export const BADGE: Record<Connection, { label: string; variant: 'success' | 'danger' | 'secondary' }> = {
  en_linea: { label: 'En línea', variant: 'success' },
  sin_conexion: { label: 'Sin conexión', variant: 'danger' },
  mantenimiento: { label: 'En mantenimiento', variant: 'secondary' },
}

/** Resumen general con la conexión de cada estación; misma clave que el dashboard, así no se pide dos veces. */
export function useStationSummary() {
  return useQuery({
    queryKey: ['dashboard', 'summary'],
    queryFn: async () => (await api.get<DashboardSummary>('/dashboard/summary')).data,
    refetchInterval: CONNECTION_REFRESH_MS,
  })
}

/**
 * Avisa a todos los módulos que muestran estaciones (dispositivos, sensores, resumen y menú lateral,
 * monitoreo y atrapanieblas) que cambió el estado de una estación o sensor: activar/desactivar, el estado
 * final de un mantenimiento o incidencia, el intervalo de envío o la versión de firmware asignada.
 */
export function refreshStations(qc: QueryClient) {
  for (const queryKey of [['devices'], ['sensors'], ['dashboard'], ['monitoring'], ['fog-collectors']]) {
    void qc.invalidateQueries({ queryKey })
  }
}
