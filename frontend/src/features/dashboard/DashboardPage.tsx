import { useQuery } from '@tanstack/react-query'
import {
  Activity,
  ArrowRight,
  Cpu,
  Droplets,
  Gauge,
  Radio,
  Search,
  Thermometer,
  WifiOff,
} from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link } from 'react-router'

import { CardHead, EmptyState, ErrorAlert, Loading, NativeSelect, Notice, PageHeader, StatCard, type ToneColor } from '@/components/common'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { useHasPermission } from '@/features/auth/useAuth'
import { SeriesChart, seriesSummary } from '@/features/dashboard/SeriesChart'
import { api } from '@/lib/api'
import { ExportReportButton } from '@/features/reports/ExportReportButton'
import { formatDateTime, formatNumber, relativeTime } from '@/lib/format'
import type { Bucket, DashboardSummary, InventoryItem, LatestValue, Series } from '@/types/api'

const VARIABLES = [
  { code: 'volumen_captado', label: 'Volumen captado' },
  { code: 'nivel_almacenamiento', label: 'Nivel de almacenamiento' },
  { code: 'temperatura', label: 'Temperatura' },
  { code: 'humedad_relativa', label: 'Humedad relativa' },
  { code: 'presion_atmosferica', label: 'Presión atmosférica' },
  { code: 'velocidad_viento', label: 'Velocidad del viento' },
  { code: 'direccion_viento', label: 'Dirección del viento' },
  { code: 'niebla', label: 'Intensidad de niebla' },
]

const RANGES: { days: number; label: string; bucket: Bucket }[] = [
  { days: 1, label: 'Últimas 24 horas', bucket: 'hour' },
  { days: 7, label: 'Últimos 7 días', bucket: 'day' },
  { days: 30, label: 'Últimos 30 días', bucket: 'day' },
  { days: 180, label: 'Últimos 6 meses', bucket: 'week' },
]

const UNIT_LABEL: Record<string, string> = { C: '°C', deg: '°' }

function unitText(unit: string): string {
  return UNIT_LABEL[unit] ?? unit
}

function latestOf(latest: LatestValue[], code: string): LatestValue | undefined {
  return latest
    .filter((v) => v.sensor_type_code === code)
    .sort((a, b) => b.measured_at.localeCompare(a.measured_at))[0]
}

function LatestStat({
  value,
  label,
  icon,
  color,
}: {
  value?: LatestValue
  label: string
  icon: typeof Activity
  color: ToneColor
}) {
  if (!value) return <StatCard color={color} label={label} value="—" icon={icon} foot="Sin lecturas válidas aún" />
  return (
    <StatCard
      color={color}
      label={label}
      value={formatNumber(value.value, 1)}
      unit={unitText(value.unit)}
      icon={icon}
      tone={value.is_stale ? 'warning' : undefined}
      foot={
        <>
          {value.is_stale && <WifiOff className="size-3" aria-hidden />}
          <span title={formatDateTime(value.measured_at)}>
            {value.is_stale ? 'Desactualizada' : 'Última lectura'} · {relativeTime(value.measured_at)}
          </span>
        </>
      }
    />
  )
}

export function DashboardPage() {
  const can = useHasPermission()
  const [variable, setVariable] = useState('volumen_captado')
  const [rangeIndex, setRangeIndex] = useState(1)
  const [filter, setFilter] = useState('')
  const range = RANGES[rangeIndex] ?? RANGES[1]!

  const summary = useQuery({
    queryKey: ['dashboard', 'summary'],
    queryFn: async () => (await api.get<DashboardSummary>('/dashboard/summary')).data,
    refetchInterval: 60_000,
  })
  const series = useQuery({
    queryKey: ['dashboard', 'series', variable, range.days],
    queryFn: async () => {
      const dateTo = new Date()
      const dateFrom = new Date(dateTo.getTime() - range.days * 86_400_000)
      const params = { sensor_type: variable, bucket: range.bucket, date_from: dateFrom.toISOString(), date_to: dateTo.toISOString() }
      return (await api.get<Series>('/dashboard/series', { params })).data
    },
  })
  const lowStock = useQuery({
    queryKey: ['inventory', 'alerts'],
    queryFn: async () => (await api.get<InventoryItem[]>('/inventory/alerts/low-stock')).data,
    enabled: can('inventario.consultar'),
  })

  const rows = useMemo(() => {
    const q = filter.trim().toLocaleLowerCase('es')
    const all = summary.data?.latest ?? []
    return q ? all.filter((v) => `${v.sensor_type_name} ${v.sensor_code}`.toLocaleLowerCase('es').includes(q)) : all
  }, [summary.data, filter])

  if (summary.isLoading) return <Loading />
  if (summary.error) return <ErrorAlert error={summary.error} />
  const data = summary.data!
  const variableLabel = VARIABLES.find((v) => v.code === variable)?.label ?? variable
  const total = series.data ? seriesSummary(series.data) : null
  const deviceCodes = new Map(data.devices.map((d) => [d.id, d.code]))
  const tank = latestOf(data.latest, 'nivel_almacenamiento')

  return (
    <>
      <PageHeader
        eyebrow="Monitoreo de atrapanieblas"
        title="El agua, en perspectiva."
        description={
          <>
            Estado de captación de las estaciones IoT · última comunicación{' '}
            <strong className="text-foreground font-medium">{relativeTime(data.last_communication_at)}</strong>
          </>
        }
        actions={<ExportReportButton kinds={['volumen']} />}
      />

      {data.has_stale_data && (
        <Notice tone="warning" title="Hay datos desactualizados" className="mb-5">
          Algunas estaciones o sensores no envían datos desde hace más de {data.stale_threshold_minutes} minutos. Revise la
          conexión o la alimentación de la estación.
        </Notice>
      )}

      <section aria-label="Indicadores principales" className="mb-5 grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-4">
        <StatCard
          color="blue"
          label="Agua captada hoy"
          value={formatNumber(data.volume.today_liters, 1)}
          unit="litros"
          icon={Droplets}
          foot={`Últimos 7 días: ${formatNumber(data.volume.last_7_days_liters, 1)} L · mes: ${formatNumber(data.volume.month_liters, 1)} L`}
        />
        <LatestStat color="mint" label="Humedad relativa" value={latestOf(data.latest, 'humedad_relativa')} icon={Activity} />
        <LatestStat color="peach" label="Temperatura ambiente" value={latestOf(data.latest, 'temperatura')} icon={Thermometer} />
        {tank ? (
          <LatestStat color="lavender" label="Nivel del tanque" value={tank} icon={Gauge} />
        ) : (
          <StatCard
            color="lavender"
            label="Agua captada en el mes"
            value={formatNumber(data.volume.month_liters, 1)}
            unit="litros"
            icon={Gauge}
            foot="Suma de lecturas válidas"
          />
        )}
      </section>

      <section className="mb-5 grid gap-5 lg:grid-cols-[minmax(0,1.9fr)_minmax(280px,1fr)]">
        <Card>
          <CardHead
            title={variableLabel}
            subtitle={`${series.data?.aggregation === 'incremental' ? 'Total' : 'Promedio'} por intervalo · solo lecturas válidas`}
            actions={
              <>
                <label className="sr-only" htmlFor="variable">
                  Variable
                </label>
                <NativeSelect id="variable" className="w-auto" value={variable} onChange={(e) => setVariable(e.target.value)}>
                  {VARIABLES.map((v) => (
                    <option key={v.code} value={v.code}>
                      {v.label}
                    </option>
                  ))}
                </NativeSelect>
                <label className="sr-only" htmlFor="range">
                  Periodo
                </label>
                <NativeSelect id="range" className="w-auto" value={rangeIndex} onChange={(e) => setRangeIndex(Number(e.target.value))}>
                  {RANGES.map((r, i) => (
                    <option key={r.days} value={i}>
                      {r.label}
                    </option>
                  ))}
                </NativeSelect>
              </>
            }
          />
          <div className="px-5">
            {total && total.value !== null && series.data && (
              <div className="mb-2 text-2xl font-semibold tracking-tight tabular-nums">
                {formatNumber(total.value, 1)}{' '}
                <small className="text-muted-foreground text-xs font-normal">
                  {unitText(series.data.sensor_type.unit)} {total.suffix}
                </small>
              </div>
            )}
            {series.isLoading && <Loading />}
            <ErrorAlert error={series.error} />
            {series.data && <SeriesChart series={series.data} />}
          </div>
        </Card>

        <Card>
          <CardHead title="Estado de las estaciones" subtitle="Comunicación de los dispositivos ESP32" actions={<Cpu className="text-muted-foreground size-4" />} />
          <div className="px-5">
            {data.devices.length === 0 ? (
              <EmptyState
                icon={Radio}
                title="Sin estaciones registradas"
                description="Registre un dispositivo y sus sensores para empezar a recibir mediciones."
                action={
                  can('infraestructura.gestionar') && (
                    <Button asChild size="sm" variant="outline">
                      <Link to="/dispositivos">Registrar dispositivo</Link>
                    </Button>
                  )
                }
              />
            ) : (
              <ul className="divide-y">
                {data.devices.map((d) => (
                  <li key={d.id} className="flex items-center gap-3 py-3.5">
                    <span className="bg-muted text-muted-foreground grid size-9 shrink-0 place-items-center rounded-lg border">
                      <Cpu className="size-4" aria-hidden />
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm font-medium">{d.name}</div>
                      <div className="text-muted-foreground truncate text-xs">
                        {d.code} · último envío {relativeTime(d.last_seen_at)}
                      </div>
                    </div>
                    {d.is_stale ? <Badge variant="warning">Sin datos recientes</Badge> : <Badge variant="success">En línea</Badge>}
                  </li>
                ))}
              </ul>
            )}
            {lowStock.data && lowStock.data.length > 0 && (
              <Notice
                tone="warning"
                className="my-3"
                title={`${lowStock.data.length} ${lowStock.data.length === 1 ? 'repuesto con stock bajo' : 'repuestos con stock bajo'}`}
              >
                <Link to="/inventario" className="inline-flex items-center gap-1 text-xs underline underline-offset-2">
                  Consultar inventario <ArrowRight className="size-3" aria-hidden />
                </Link>
              </Notice>
            )}
          </div>
        </Card>
      </section>

      <Card>
        <CardHead
          title="Últimas mediciones"
          subtitle="Valor válido más reciente de cada sensor"
          actions={
            <label className="relative">
              <Search className="text-muted-foreground absolute top-2.5 left-2.5 size-4" aria-hidden />
              <span className="sr-only">Buscar variable o sensor</span>
              <Input
                type="search"
                className="w-full pl-8 sm:w-60"
                placeholder="Buscar variable o sensor…"
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
              />
            </label>
          }
        />
        <div className="px-5">
          {data.latest.length === 0 ? (
            <EmptyState icon={Activity} title="Aún no se recibieron mediciones" />
          ) : (
            <>
              <Table>
                <TableHeader>
                  <TableRow className="hover:bg-transparent">
                    <TableHead>Fecha / hora</TableHead>
                    <TableHead>Dispositivo</TableHead>
                    <TableHead>Variable</TableHead>
                    <TableHead className="text-right">Valor</TableHead>
                    <TableHead>Estado</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {rows.map((v) => (
                    <TableRow key={v.sensor_id}>
                      <TableCell>{formatDateTime(v.measured_at)}</TableCell>
                      <TableCell>{deviceCodes.get(v.device_id) ?? v.device_id}</TableCell>
                      <TableCell>
                        {v.sensor_type_name} <span className="text-muted-foreground text-xs">· {v.sensor_code}</span>
                      </TableCell>
                      <TableCell className="text-right font-medium tabular-nums">
                        {formatNumber(v.value)} {unitText(v.unit)}
                      </TableCell>
                      <TableCell>
                        {v.is_stale ? <Badge variant="warning">Desactualizada</Badge> : <Badge variant="success">Reciente</Badge>}
                      </TableCell>
                    </TableRow>
                  ))}
                  {rows.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={5} className="text-muted-foreground py-6 text-center">
                        No se encontraron mediciones.
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
              <div className="text-muted-foreground border-t py-3 text-xs">
                {rows.length} de {data.latest.length} sensores · actualizado {formatDateTime(data.generated_at)}
              </div>
            </>
          )}
        </div>
      </Card>
    </>
  )
}
