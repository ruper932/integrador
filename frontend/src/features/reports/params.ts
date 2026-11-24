import type { FilterValues } from '@/features/reports/ReportFilterField'
import type { ReportDefinition } from '@/types/api'

export const FORMATS = { xlsx: 'Excel (.xlsx)', pdf: 'PDF', csv: 'CSV' } as const
export type Format = keyof typeof FORMATS

/** Parámetros de la exportación: solo los filtros del reporte elegido que tienen valor. */
export function buildParams(report: ReportDefinition, values: FilterValues, format: Format): Record<string, string> {
  const params: Record<string, string> = { report: report.kind, format }
  for (const { key } of report.filters) {
    if (key === 'date_range') {
      if (values.date_from) params.date_from = new Date(values.date_from).toISOString()
      if (values.date_to) params.date_to = new Date(values.date_to).toISOString()
    } else if (values[key]) {
      params[key] = values[key]
    }
  }
  return params
}

export function isApplied(key: string, values: FilterValues): boolean {
  return Boolean(key === 'date_range' ? values.date_from || values.date_to : values[key])
}

/** Etiquetas de los filtros (las mismas que `FILTER_LABELS` del catálogo de reportes del backend). */
export const FILTER_LABELS: Record<string, string> = {
  date_range: 'Periodo',
  bucket: 'Agrupación',
  device_id: 'Dispositivo',
  sensor_type: 'Variable',
  fog_collector_id: 'Atrapanieblas',
  quality: 'Calidad de la lectura',
  device_status: 'Estado del dispositivo',
  connection: 'Comunicación',
  category_id: 'Categoría',
  item_id: 'Repuesto',
  condition: 'Estado del repuesto',
  low_stock_only: 'Solo stock bajo',
  include_inactive: 'Incluir desactivados',
  movement_type: 'Tipo de movimiento',
  period_id: 'Periodo de inventario',
  maintenance_type: 'Tipo de mantenimiento',
  final_status: 'Estado final del componente',
  responsible_id: 'Responsable',
  origin: 'Origen',
  incident_status: 'Estado del reporte',
  priority: 'Prioridad',
  reporter_id: 'Reportado por',
  role_id: 'Rol',
  position_id: 'Cargo',
  is_active: 'Estado de la cuenta',
  action: 'Acción',
  actor_id: 'Usuario',
}

/**
 * Parámetros del listado a partir de los filtros con valor. `rename` adapta los nombres del
 * catálogo de reportes a los del endpoint del listado (p. ej. `actor_id` → `user_id`).
 */
export function listParams(
  keys: string[],
  values: FilterValues,
  rename: Record<string, string> = {},
): Record<string, string> {
  const params: Record<string, string> = {}
  for (const key of keys) {
    if (key === 'date_range') {
      if (values.date_from) params.date_from = new Date(values.date_from).toISOString()
      if (values.date_to) params.date_to = new Date(values.date_to).toISOString()
    } else if (values[key]) {
      params[rename[key] ?? key] = values[key]
    }
  }
  return params
}
