import type { FinalStatus, MaintenanceStatus, MaintenanceType } from '@/types/api'

export const MAINTENANCE_TYPES = ['preventivo', 'correctivo', 'reemplazo', 'calibracion', 'limpieza', 'inspeccion'] as const
export const FINAL_STATUSES = ['operativo', 'operativo_con_observaciones', 'fuera_de_servicio', 'reemplazado'] as const

export const TYPE_LABELS: Record<MaintenanceType, string> = {
  preventivo: 'Preventivo',
  correctivo: 'Correctivo',
  reemplazo: 'Reemplazo',
  calibracion: 'Calibración',
  limpieza: 'Limpieza',
  inspeccion: 'Inspección',
}

export const FINAL_LABELS: Record<FinalStatus, string> = {
  operativo: 'Operativo',
  operativo_con_observaciones: 'Operativo con observaciones',
  fuera_de_servicio: 'Fuera de servicio',
  reemplazado: 'Reemplazado',
}

export const MAINTENANCE_STATUS_LABELS: Record<MaintenanceStatus, string> = {
  aceptado: 'Aceptado',
  en_progreso: 'En progreso',
  finalizado: 'Finalizado',
}
