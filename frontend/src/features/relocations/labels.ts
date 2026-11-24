import type { RelocationReason, RelocationStatus } from '@/types/api'

export const RELOCATION_STATUS_ORDER: RelocationStatus[] = ['pendiente', 'aceptado', 'en_progreso', 'finalizado', 'rechazado']

export const RELOCATION_STATUS_LABELS: Record<RelocationStatus, string> = {
  pendiente: 'Pendiente',
  aceptado: 'Aceptada',
  en_progreso: 'Traslado en curso',
  finalizado: 'Reubicado',
  rechazado: 'Rechazada',
}

export const REASONS = ['espacio_insuficiente', 'interferencia_con_actividades', 'obstruccion_de_la_niebla', 'otro'] as const

export const REASON_LABELS: Record<RelocationReason, string> = {
  espacio_insuficiente: 'Espacio insuficiente',
  interferencia_con_actividades: 'Interfiere con otras actividades (cultivos, construcción, tránsito)',
  obstruccion_de_la_niebla: 'Algo obstruye la niebla o el viento',
  otro: 'Otro motivo',
}

/** Orientación de la malla: la misma lista que acepta el backend. */
export const ORIENTATIONS = ['N', 'NE', 'E', 'SE', 'S', 'SO', 'O', 'NO'] as const
