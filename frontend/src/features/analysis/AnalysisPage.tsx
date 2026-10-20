import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { CalendarCheck, Droplets, Gauge, ShieldCheck } from 'lucide-react'
import type { ReactNode } from 'react'
import { useState } from 'react'

import { CardHead, ErrorAlert, Loading, NativeSelect, Notice, PageHeader, StatCard } from '@/components/common'
import { Card, CardContent } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import {
  CategoryBars,
  CategoryTable,
  ChartOrTable,
  CorrelationBars,
  DailyCaptureChart,
  type DailyMode,
  Histogram,
  ScatterPlot,
  Segmented,
} from '@/features/analysis/charts'
import { PRIORITY_LABELS, STATUS_LABELS } from '@/features/incidents/labels'
import { FINAL_LABELS, TYPE_LABELS } from '@/features/maintenance/labels'
import { ReportFilterField, type FilterValues } from '@/features/reports/ReportFilterField'
import { api } from '@/lib/api'
import { formatNumber } from '@/lib/format'

interface Summary {
  n: number
  mean: number | null
  median: number | null
  std: number | null
  min: number | null
  max: number | null
}

interface Analysis {
  date_from: string
  date_to: string
  capture?: {
    total: number
    days_with_data: number
    days_with_capture: number
    daily: Summary
    best_day: string | null
    series: { date: string; value: number }[]
    by_fog_collector: { name: string; total: number; share: number | null }[]
  }
  variables?: ({ code: string; name: string; unit: string } & Summary)[]
  correlations?: {
    code: string
    name: string
    unit: string
    r: number | null
    n: number
    strength: string
    points: { date: string; x: number; y: number }[]
  }[]
  quality?: {
    total: number
    by_quality: Record<string, number>
    valid_share: number | null
    by_device: { device: string; total: number; valid_share: number }[]
  }
  maintenance?: {
    total: number
    by_type: Record<string, number>
    by_final_status: Record<string, number>
    from_incidents: number
    with_parts: number
  }
  incidents?: {
    total: number
    by_status: Record<string, number>
    by_priority: Record<string, number>
    hours_to_accept: Summary
    hours_to_finish: Summary
  }
  inventory?: { low_stock: number; top_consumed: { code: string; name: string; unit: string; quantity: string }[] }
}

const QUALITY_LABELS: Record<string, string> = {
  valida: 'Válida',
  sin_dato: 'Sin dato',
  fuera_de_rango: 'Fuera de rango',
  unidad_invalida: 'Unidad inválida',
  invalida: 'Inválida',
}

const FILTERS = [
  { key: 'date_range', label: 'Periodo', required: false },
  { key: 'fog_collector_id', label: 'Atrapanieblas', required: false },
  { key: 'device_id', label: 'Dispositivo', required: false },
]

const toRows = (data: Record<string, number>, labels?: Record<string, string>) =>
  Object.entries(data).map(([key, value]) => ({ label: labels?.[key] ?? key.replaceAll('_', ' '), value }))

const pct = (v: number | null | undefined) => (v === null || v === undefined ? '—' : `${formatNumber(v * 100, 1)} %`)
const num = (v: number | null | undefined, digits = 1) => formatNumber(v ?? null, digits)

function params(values: FilterValues): Record<string, string> {
  const p: Record<string, string> = {}
  if (values.date_from) p.date_from = new Date(values.date_from).toISOString()
  if (values.date_to) p.date_to = new Date(values.date_to).toISOString()
  if (values.device_id) p.device_id = values.device_id
  if (values.fog_collector_id) p.fog_collector_id = values.fog_collector_id
  return p
}

/** Tabla de conteos (clave → cantidad) con etiquetas legibles y porcentaje del total. */
function Counts({ data, labels, empty = 'Sin registros en el periodo.' }: { data: Record<string, number>; labels?: Record<string, string>; empty?: string }) {
  const total = Object.values(data).reduce((a, b) => a + b, 0)
  if (total === 0) return <p className="text-muted-foreground text-sm">{empty}</p>
  return (
    <Table>
      <TableBody>
        {Object.entries(data)
          .sort((a, b) => b[1] - a[1])
          .map(([key, count]) => (
            <TableRow key={key}>
              <TableCell>{labels?.[key] ?? key.replaceAll('_', ' ')}</TableCell>
              <TableCell className="text-right tabular-nums">{count}</TableCell>
              <TableCell className="text-muted-foreground w-24 text-right tabular-nums">{pct(count / total)}</TableCell>
            </TableRow>
          ))}
      </TableBody>
    </Table>
  )
}

function Section({
  title,
  subtitle,
  actions,
  children,
}: {
  title: string
  subtitle?: string
  actions?: ReactNode
  children: ReactNode
}) {
  return (
    <Card>
      <CardHead title={title} subtitle={subtitle} actions={actions} />
      <CardContent>{children}</CardContent>
    </Card>
  )
}

export function AnalysisPage() {
  const [values, setValues] = useState<FilterValues>({})
  const set = (key: string, value: string) => setValues((v) => ({ ...v, [key]: value }))
  const query = params(values)
  const analysis = useQuery({
    queryKey: ['analysis', query],
    queryFn: async () => (await api.get<Analysis>('/analysis', { params: query })).data,
    placeholderData: keepPreviousData,
  })
  const a = analysis.data
  const [dailyMode, setDailyMode] = useState<DailyMode>('bars')
  const [showAverage, setShowAverage] = useState(true)
  const [picked, setPicked] = useState<string | null>(null)
  // Por defecto, la variable con la relación más fuerte (en valor absoluto).
  const strongest = [...(a?.correlations ?? [])].filter((c) => c.r !== null).sort((x, y) => Math.abs(y.r!) - Math.abs(x.r!))[0]
  const selected = a?.correlations?.find((c) => c.code === picked) ?? strongest

  return (
    <>
      <PageHeader
        eyebrow="Principal"
        title="Análisis estadístico"
        description="Indicadores del periodo elegido: captación, variables ambientales, calidad de los datos y operación. Si no indica fechas, se usan los últimos 30 días."
      />
      <Card className="mb-5">
        <CardContent className="grid gap-3 sm:grid-cols-2">
          {FILTERS.map((def) => (
            <ReportFilterField key={def.key} def={def} values={values} set={set} />
          ))}
        </CardContent>
      </Card>

      <ErrorAlert error={analysis.error} />
      {analysis.isLoading && <Loading />}
      {a && (
        <div className="grid gap-5">
          {a.capture && (
            <>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <StatCard color="blue" label="Agua captada en el periodo" value={num(a.capture.total)} unit="L" icon={Droplets} />
                <StatCard
                  color="lavender"
                  label="Promedio diario"
                  value={num(a.capture.daily.mean)}
                  unit="L/día"
                  icon={Gauge}
                  foot={`Mediana ${num(a.capture.daily.median)} L · desviación ${num(a.capture.daily.std)} L`}
                />
                <StatCard
                  color="peach"
                  label="Días con captación"
                  value={a.capture.days_with_capture}
                  icon={CalendarCheck}
                  foot={`de ${a.capture.days_with_data} días con datos${a.capture.best_day ? ` · máximo el ${a.capture.best_day}` : ''}`}
                />
                <StatCard
                  color="mint"
                  label="Lecturas válidas"
                  value={pct(a.quality?.valid_share)}
                  icon={ShieldCheck}
                  tone={a.quality?.valid_share !== null && (a.quality?.valid_share ?? 1) < 0.9 ? 'warning' : undefined}
                  foot={`${a.quality?.total ?? 0} lecturas recibidas`}
                />
              </div>

              <Section
                title="Captación diaria"
                subtitle="Litros por día (solo lecturas válidas); los días sin datos no se cuentan como cero"
                actions={
                  <div className="flex flex-wrap items-center gap-3">
                    <Segmented
                      label="Tipo de gráfico"
                      value={dailyMode}
                      onChange={setDailyMode}
                      options={[
                        ['bars', 'Barras'],
                        ['line', 'Línea'],
                        ['cumulative', 'Acumulado'],
                      ]}
                    />
                    {dailyMode !== 'cumulative' && (
                      <label className="flex items-center gap-2 text-xs">
                        <Checkbox checked={showAverage} onCheckedChange={(c) => setShowAverage(c === true)} />
                        Media móvil 7 días
                      </label>
                    )}
                  </div>
                }
              >
                <ChartOrTable
                  title="captación diaria"
                  chart={
                    <DailyCaptureChart
                      points={a.capture.series}
                      mode={dailyMode}
                      showAverage={showAverage}
                      mean={a.capture.daily.mean}
                    />
                  }
                  table={
                    <CategoryTable unit=" L" rows={a.capture.series.map((p) => ({ label: p.date, value: p.value }))} />
                  }
                />
              </Section>

              <div className="grid gap-5 lg:grid-cols-2">
                <Section title="Distribución de la captación diaria" subtitle="Cuántos días cayeron en cada rango de litros">
                  <Histogram values={a.capture.series.map((p) => p.value)} />
                </Section>
                <Section title="Captación por atrapanieblas">
                  {a.capture.by_fog_collector.length === 0 ? (
                    <p className="text-muted-foreground text-sm">Filtrado por un atrapanieblas.</p>
                  ) : (
                    <ChartOrTable
                      title="captación por atrapanieblas"
                      chart={<CategoryBars color="var(--chart-2)" unit=" L" rows={a.capture.by_fog_collector.map((f) => ({ label: f.name, value: f.total }))} />}
                      table={<CategoryTable unit=" L" rows={a.capture.by_fog_collector.map((f) => ({ label: f.name, value: f.total }))} />}
                    />
                  )}
                </Section>
              </div>

              <div className="grid gap-5 lg:grid-cols-2">
                <Section
                  title="Relación con la captación"
                  subtitle="Correlación de Pearson entre el volumen diario y el promedio diario de cada variable. Haga clic en una barra para ver su dispersión."
                >
                  <ChartOrTable
                    title="correlaciones"
                    chart={
                      <CorrelationBars rows={a.correlations ?? []} selected={selected?.code ?? null} onSelect={setPicked} />
                    }
                    table={
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead>Variable</TableHead>
                            <TableHead className="text-right">r</TableHead>
                            <TableHead>Interpretación</TableHead>
                            <TableHead className="text-right">Días</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {a.correlations?.map((c) => (
                            <TableRow key={c.code}>
                              <TableCell>{c.name}</TableCell>
                              <TableCell className="text-right tabular-nums">{c.r === null ? '—' : formatNumber(c.r, 2)}</TableCell>
                              <TableCell>{c.strength}</TableCell>
                              <TableCell className="text-right tabular-nums">{c.n}</TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    }
                  />
                  <p className="text-muted-foreground mt-3 text-xs">
                    Azul: relación positiva · naranja: negativa. Una correlación indica asociación, no causa; con pocos
                    días los valores son poco confiables.
                  </p>
                </Section>

                <Section
                  title="Dispersión"
                  subtitle={selected ? `Captación diaria frente a ${selected.name.toLowerCase()} · línea: tendencia lineal` : undefined}
                  actions={
                    a.correlations && a.correlations.length > 0 ? (
                      <NativeSelect
                        aria-label="Variable de la dispersión"
                        value={selected?.code ?? ''}
                        onChange={(e) => setPicked(e.target.value)}
                        className="h-8 w-48 text-xs"
                      >
                        {a.correlations.map((c) => (
                          <option key={c.code} value={c.code}>
                            {c.name}
                          </option>
                        ))}
                      </NativeSelect>
                    ) : undefined
                  }
                >
                  {selected && selected.points.length > 0 ? (
                    <>
                      <ScatterPlot points={selected.points} xName={selected.name} xUnit={selected.unit} />
                      <p className="text-muted-foreground mt-2 text-xs">
                        r = {selected.r === null ? '—' : formatNumber(selected.r, 2)} ({selected.strength}) · {selected.n} días
                      </p>
                    </>
                  ) : (
                    <p className="text-muted-foreground text-sm">Sin días con datos de ambas variables.</p>
                  )}
                </Section>
              </div>

              <Section title="Variables ambientales" subtitle="Estadística de los promedios diarios">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Variable</TableHead>
                      <TableHead className="text-right">Promedio</TableHead>
                      <TableHead className="text-right">Mediana</TableHead>
                      <TableHead className="text-right">Desv. estándar</TableHead>
                      <TableHead className="text-right">Mínimo</TableHead>
                      <TableHead className="text-right">Máximo</TableHead>
                      <TableHead className="text-right">Días</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {a.variables?.map((v) => (
                      <TableRow key={v.code}>
                        <TableCell>
                          {v.name} <span className="text-muted-foreground">({v.unit})</span>
                        </TableCell>
                        {[v.mean, v.median, v.std, v.min, v.max].map((x, i) => (
                          <TableCell key={i} className="text-right tabular-nums">
                            {num(x)}
                          </TableCell>
                        ))}
                        <TableCell className="text-right tabular-nums">{v.n}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </Section>

              <div className="grid gap-5 lg:grid-cols-2">
                <Section title="Calidad de las lecturas">
                  <ChartOrTable title="calidad de las lecturas" chart={<CategoryBars color="var(--chart-2)" rows={toRows(a.quality?.by_quality ?? {}, QUALITY_LABELS)} />} table={<Counts data={a.quality?.by_quality ?? {}} labels={QUALITY_LABELS} />} />
                </Section>
                <Section title="Lecturas válidas por estación">
                  <Table>
                    <TableBody>
                      {a.quality?.by_device.map((d) => (
                        <TableRow key={d.device}>
                          <TableCell>{d.device}</TableCell>
                          <TableCell className="text-right tabular-nums">{d.total}</TableCell>
                          <TableCell className="w-24 text-right tabular-nums">{pct(d.valid_share)}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </Section>
              </div>
            </>
          )}

          <div className="grid gap-5 lg:grid-cols-2">
            {a.incidents && (
              <Section title="Reportes de incidencia" subtitle={`${a.incidents.total} reportes en el periodo`}>
                <div className="mb-4 grid grid-cols-2 gap-3 text-sm">
                  <div>
                    <div className="text-muted-foreground text-xs">Horas hasta aceptar (promedio)</div>
                    <div className="text-xl font-semibold tabular-nums">{num(a.incidents.hours_to_accept.mean)}</div>
                  </div>
                  <div>
                    <div className="text-muted-foreground text-xs">Horas hasta finalizar (promedio)</div>
                    <div className="text-xl font-semibold tabular-nums">{num(a.incidents.hours_to_finish.mean)}</div>
                  </div>
                </div>
                <ChartOrTable title="reportes por estado" chart={<CategoryBars color="var(--chart-3)" rows={toRows(a.incidents.by_status, STATUS_LABELS)} />} table={<Counts data={a.incidents.by_status} labels={STATUS_LABELS} />} />
                <div className="mt-3">
                  <ChartOrTable title="reportes por prioridad" chart={<CategoryBars color="var(--chart-5)" rows={toRows(a.incidents.by_priority, PRIORITY_LABELS)} />} table={<Counts data={a.incidents.by_priority} labels={PRIORITY_LABELS} />} />
                </div>
              </Section>
            )}
            {a.maintenance && (
              <Section
                title="Mantenimientos finalizados"
                subtitle={`${a.maintenance.total} en el periodo · ${a.maintenance.from_incidents} por reportes de incidencia · ${a.maintenance.with_parts} con repuestos`}
              >
                <ChartOrTable title="mantenimientos por tipo" chart={<CategoryBars color="var(--chart-4)" rows={toRows(a.maintenance.by_type, TYPE_LABELS)} />} table={<Counts data={a.maintenance.by_type} labels={TYPE_LABELS} />} />
                <div className="mt-3">
                  <ChartOrTable title="estado final de los componentes" chart={<CategoryBars color="var(--chart-2)" rows={toRows(a.maintenance.by_final_status, FINAL_LABELS)} />} table={<Counts data={a.maintenance.by_final_status} labels={FINAL_LABELS} />} />
                </div>
              </Section>
            )}
            {a.inventory && (
              <Section title="Repuestos más utilizados" subtitle={`${a.inventory.low_stock} repuestos con stock bajo actualmente`}>
                {a.inventory.top_consumed.length === 0 ? (
                  <p className="text-muted-foreground text-sm">No se usaron repuestos en el periodo.</p>
                ) : (
                  <Table>
                    <TableBody>
                      {a.inventory.top_consumed.map((i) => (
                        <TableRow key={i.code}>
                          <TableCell>
                            {i.name} <span className="text-muted-foreground">({i.code})</span>
                          </TableCell>
                          <TableCell className="text-right tabular-nums">
                            {formatNumber(i.quantity, 3)} {i.unit}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </Section>
            )}
          </div>
          {!a.capture && !a.maintenance && !a.incidents && !a.inventory && (
            <Notice tone="info">Su rol no tiene acceso a los datos de ningún módulo para el análisis.</Notice>
          )}
        </div>
      )}
    </>
  )
}
