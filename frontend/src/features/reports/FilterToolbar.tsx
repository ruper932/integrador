import { useMutation, useQuery } from '@tanstack/react-query'
import { Download, Eraser, SlidersHorizontal } from 'lucide-react'
import { useState, type ReactNode } from 'react'

import { ErrorAlert, Field, NativeSelect, Notice } from '@/components/common'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { useHasPermission } from '@/features/auth/useAuth'
import { ReportFilterField, type FilterValues } from '@/features/reports/ReportFilterField'
import { buildParams, FILTER_LABELS, FORMATS, isApplied, type Format } from '@/features/reports/params'
import { api, downloadFile } from '@/lib/api'
import type { ReportDefinition, ReportFilterOptions } from '@/types/api'

// Filtros de personas: sus opciones solo las entrega el backend a quien puede generar reportes.
const PEOPLE_FILTERS = ['responsible_id', 'reporter_id', 'actor_id', 'action']

/** Reportes del módulo que el rol puede generar (vacío si no tiene `reportes.generar`). */
export function useModuleReports(kinds: string[]): ReportDefinition[] {
  const can = useHasPermission()
  const catalog = useQuery({
    queryKey: ['reports', 'catalog'],
    queryFn: async () => (await api.get<ReportDefinition[]>('/reports/catalog')).data,
    staleTime: Infinity,
    enabled: can('reportes.generar'),
  })
  return (catalog.data ?? []).filter((r) => kinds.includes(r.kind))
}

function useFilterOptions(enabled: boolean) {
  return useQuery({
    queryKey: ['reports', 'filter-options'],
    queryFn: async () => (await api.get<ReportFilterOptions>('/reports/filter-options')).data,
    enabled,
  })
}

/**
 * Filtros del módulo en la vista principal: el listado se actualiza con ellos y el botón «Exportar»
 * descarga el reporte elegido con esos mismos filtros, en el formato indicado (sin ventana intermedia).
 * `keys` son los filtros que el listado aplica; los propios de un reporte (p. ej. agrupación o periodo
 * de inventario) aparecen junto al botón al elegir ese reporte.
 */
export function FilterToolbar({
  kinds,
  keys,
  values,
  onChange,
  children,
}: {
  kinds: string[]
  keys: string[]
  values: FilterValues
  onChange: (values: FilterValues) => void
  children?: ReactNode
}) {
  const reports = useModuleReports(kinds)
  const options = useFilterOptions(reports.length > 0 && keys.some((k) => PEOPLE_FILTERS.includes(k)))
  const visible = keys.filter((k) => !PEOPLE_FILTERS.includes(k) || options.data)
  const set = (key: string, value: string) => onChange({ ...values, [key]: value })
  const applied = visible.filter((k) => isApplied(k, values)).length

  return (
    <Card className="mb-4" aria-labelledby="filtros-titulo">
      <CardContent className="grid gap-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 id="filtros-titulo" className="flex items-center gap-2 text-sm font-semibold">
            <SlidersHorizontal className="size-4" aria-hidden /> Filtros
            <span className="text-muted-foreground font-normal">
              {applied ? `· ${applied} aplicado${applied > 1 ? 's' : ''}` : '· ninguno'}
            </span>
          </h2>
          {applied > 0 && (
            <Button type="button" size="sm" variant="ghost" onClick={() => onChange({})}>
              <Eraser /> Limpiar filtros
            </Button>
          )}
        </div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {children}
          {visible.map((key) => (
            <ReportFilterField
              key={key}
              def={{ key, label: FILTER_LABELS[key] ?? key, required: false }}
              values={values}
              set={set}
              options={options.data}
            />
          ))}
        </div>
        {reports.length > 0 && <ExportRow reports={reports} listKeys={keys} values={values} set={set} options={options.data} />}
      </CardContent>
    </Card>
  )
}

function ExportRow({
  reports,
  listKeys,
  values,
  set,
  options,
}: {
  reports: ReportDefinition[]
  listKeys: string[]
  values: FilterValues
  set: (key: string, value: string) => void
  options?: ReportFilterOptions
}) {
  const [kind, setKind] = useState(reports[0]!.kind)
  const report = reports.find((r) => r.kind === kind) ?? reports[0]!
  const extras = report.filters.filter((f) => !listKeys.includes(f.key))
  return (
    <section aria-label="Exportar reporte" className="grid gap-3 border-t pt-4">
      <div className="grid items-end gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {reports.length > 1 && (
          <Field label="Reporte" htmlFor="x-kind">
            <NativeSelect id="x-kind" value={report.kind} onChange={(e) => setKind(e.target.value)}>
              {reports.map((r) => (
                <option key={r.kind} value={r.kind}>
                  {r.label}
                </option>
              ))}
            </NativeSelect>
          </Field>
        )}
        {extras.map((def) => (
          <ReportFilterField key={def.key} def={def} values={values} set={set} options={options} />
        ))}
        <ExportControls report={report} values={values} />
      </div>
      <p className="text-muted-foreground text-xs">
        {report.description} El reporte usa los filtros de arriba que le corresponden
        {report.filters.some((f) => f.key === 'date_range') && '; sin fechas, los últimos 30 días'}.
      </p>
    </section>
  )
}

/** Formato y botón de exportación de un reporte con los valores dados (también usado fuera de la barra). */
export function ExportControls({
  report,
  values,
  compact = false,
}: {
  report: ReportDefinition
  values: FilterValues
  /** Sin etiqueta visible, para cabeceras con otros selectores en línea. */
  compact?: boolean
}) {
  const [format, setFormat] = useState<Format>('xlsx')
  const download = useMutation({
    mutationFn: () => downloadFile('/reports/export', buildParams(report, values, format), `${report.kind}.${format}`),
  })
  const missing = report.filters.filter((f) => f.required && !values[f.key])
  const badRange = Boolean(values.date_from && values.date_to && values.date_from >= values.date_to)
  const id = `x-format-${report.kind}`
  const formatSelect = (
    <NativeSelect id={id} value={format} onChange={(e) => setFormat(e.target.value as Format)} className="w-36">
      {Object.entries(FORMATS).map(([value, label]) => (
        <option key={value} value={value}>
          {label}
        </option>
      ))}
    </NativeSelect>
  )
  return (
    <>
      <div className="flex items-end gap-2">
        {compact ? (
          <>
            <label className="sr-only" htmlFor={id}>
              Formato
            </label>
            {formatSelect}
          </>
        ) : (
          <Field label="Formato" htmlFor={id}>
            {formatSelect}
          </Field>
        )}
        <Button
          onClick={() => download.mutate()}
          disabled={download.isPending || missing.length > 0 || badRange}
          title={missing.length ? `Indique: ${missing.map((f) => f.label.toLowerCase()).join(', ')}` : undefined}
        >
          <Download /> {download.isPending ? 'Generando…' : 'Exportar'}
        </Button>
      </div>
      {(missing.length > 0 || download.isSuccess || download.error) && (
        <div className="basis-full sm:col-span-full">
          {missing.length > 0 && (
            <Notice tone="info">Para este reporte indique: {missing.map((f) => f.label.toLowerCase()).join(', ')}.</Notice>
          )}
          {download.isSuccess && <Notice tone="success">Reporte descargado; su encabezado indica los filtros aplicados.</Notice>}
          <ErrorAlert error={download.error} />
        </div>
      )}
    </>
  )
}
