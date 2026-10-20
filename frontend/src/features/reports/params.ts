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

export function countApplied(report: ReportDefinition, values: FilterValues): number {
  return report.filters.filter((f) => (f.key === 'date_range' ? values.date_from || values.date_to : values[f.key])).length
}
