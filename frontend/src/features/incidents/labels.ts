import type { IncidentPriority, IncidentStatus } from '@/types/api'

export const STATUS_ORDER: IncidentStatus[] = ['abierto', 'aceptado', 'en_progreso', 'finalizado']

export const STATUS_LABELS: Record<IncidentStatus, string> = {
  abierto: 'Abierto',
  aceptado: 'Aceptado',
  en_progreso: 'En progreso',
  finalizado: 'Finalizado',
}

export const PRIORITY_LABELS: Record<IncidentPriority, string> = { alta: 'Alta', media: 'Media', baja: 'Baja' }
