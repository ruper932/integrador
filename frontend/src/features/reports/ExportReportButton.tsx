import { useMutation, useQuery } from '@tanstack/react-query'
import { Download, Eraser } from 'lucide-react'
import { useState } from 'react'

import { ErrorAlert, Field, NativeSelect, Notice } from '@/components/common'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { useHasPermission } from '@/features/auth/useAuth'
import { ReportFilterField, type FilterValues } from '@/features/reports/ReportFilterField'
import { buildParams, countApplied, FORMATS, type Format } from '@/features/reports/params'
import { api, downloadFile } from '@/lib/api'
import type { ReportDefinition, ReportFilterOptions } from '@/types/api'

const PEOPLE_FILTERS = ['responsible_id', 'reporter_id', 'actor_id', 'action']

/**
 * Exportación de los reportes de un módulo, con sus filtros, desde la propia pantalla del módulo.
 * No se muestra si el rol no puede generar ninguno de los reportes indicados (el backend también lo valida).
 */
export function ExportReportButton({ kinds }: { kinds: string[] }) {
  const can = useHasPermission()
  const catalog = useQuery({
    queryKey: ['reports', 'catalog'],
    queryFn: async () => (await api.get<ReportDefinition[]>('/reports/catalog')).data,
    staleTime: Infinity,
    enabled: can('reportes.generar'),
  })
  const [open, setOpen] = useState(false)
  const reports = (catalog.data ?? []).filter((r) => kinds.includes(r.kind))
  if (reports.length === 0) return null
  return (
    <>
      <Button variant="outline" onClick={() => setOpen(true)}>
        <Download /> Exportar reporte
      </Button>
      {open && <ExportDialog reports={reports} onClose={() => setOpen(false)} />}
    </>
  )
}

function ExportDialog({ reports, onClose }: { reports: ReportDefinition[]; onClose: () => void }) {
  const [kind, setKind] = useState(reports[0]!.kind)
  const [format, setFormat] = useState<Format>('xlsx')
  // Los valores se conservan al cambiar de reporte (p. ej. el periodo); solo se envían los del reporte elegido.
  const [values, setValues] = useState<FilterValues>({})
  const report = reports.find((r) => r.kind === kind) ?? reports[0]!
  const options = useQuery({
    queryKey: ['reports', 'filter-options'],
    queryFn: async () => (await api.get<ReportFilterOptions>('/reports/filter-options')).data,
    enabled: report.filters.some((f) => PEOPLE_FILTERS.includes(f.key)),
  })
  const download = useMutation({
    mutationFn: () => downloadFile('/reports/export', buildParams(report, values, format), `${report.kind}.${format}`),
  })

  const missing = report.filters.filter((f) => f.required && !values[f.key])
  const badRange = Boolean(values.date_from && values.date_to && values.date_from >= values.date_to)
  const applied = countApplied(report, values)
  const set = (key: string, value: string) => setValues((v) => ({ ...v, [key]: value }))

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-h-[92dvh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <div className="text-[11px] font-semibold tracking-[0.12em] uppercase">{report.module}</div>
          <DialogTitle className="text-lg">Exportar reporte</DialogTitle>
          <DialogDescription>Se genera en el servidor local con los filtros indicados.</DialogDescription>
        </DialogHeader>
        {reports.length > 1 && (
          <Field label="Reporte" htmlFor="x-kind">
            <NativeSelect
              id="x-kind"
              value={kind}
              onChange={(e) => {
                setKind(e.target.value)
                download.reset()
              }}
            >
              {reports.map((r) => (
                <option key={r.kind} value={r.kind}>
                  {r.label}
                </option>
              ))}
            </NativeSelect>
          </Field>
        )}
        <p className="text-muted-foreground text-sm">{report.description}</p>

        <section aria-labelledby="x-filtros" className="grid gap-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 id="x-filtros" className="font-medium">
              Filtros{' '}
              <span className="text-muted-foreground text-sm font-normal">
                {applied ? `· ${applied} aplicado${applied > 1 ? 's' : ''}` : '· ninguno (incluye todo)'}
              </span>
            </h3>
            {applied > 0 && (
              <Button type="button" size="sm" variant="ghost" onClick={() => setValues({})}>
                <Eraser /> Limpiar filtros
              </Button>
            )}
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            {report.filters.map((def) => (
              <ReportFilterField key={def.key} def={def} values={values} set={set} options={options.data} />
            ))}
          </div>
          {report.filters.some((f) => f.required) && (
            <p className="text-muted-foreground text-xs">* Filtro obligatorio para este reporte.</p>
          )}
        </section>

        <div className="flex flex-wrap items-end gap-3 border-t pt-4">
          <Field label="Formato" htmlFor="x-format">
            <NativeSelect id="x-format" value={format} onChange={(e) => setFormat(e.target.value as Format)} className="w-44">
              {Object.entries(FORMATS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </NativeSelect>
          </Field>
          <Button onClick={() => download.mutate()} disabled={download.isPending || missing.length > 0 || badRange}>
            <Download /> {download.isPending ? 'Generando…' : 'Descargar'}
          </Button>
        </div>
        {missing.length > 0 && <Notice tone="info">Indique: {missing.map((f) => f.label.toLowerCase()).join(', ')}.</Notice>}
        {download.isSuccess && <Notice tone="success">Reporte generado; su encabezado indica los filtros aplicados.</Notice>}
        <ErrorAlert error={download.error} />
      </DialogContent>
    </Dialog>
  )
}
