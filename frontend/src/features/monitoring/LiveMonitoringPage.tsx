import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowDownRight, ArrowRight, ArrowUpRight, Cpu, Radio, WifiOff } from 'lucide-react'
import { useEffect, useState } from 'react'

import { CardHead, EmptyState, ErrorAlert, Loading, NativeSelect, Notice, PageHeader } from '@/components/common'
import { Card, CardContent } from '@/components/ui/card'
import { useHasPermission } from '@/features/auth/useAuth'
import { SERIES_COLOR } from '@/features/dashboard/SeriesChart'
import { refreshStations } from '@/features/devices/api'
import { api } from '@/lib/api'
import { formatDateTime, formatNumber } from '@/lib/format'
import { cn } from '@/lib/utils'
import type { DashboardSummary, LiveData, LiveVariable } from '@/types/api'

import { Gauge } from './Gauge'
import { LiveChart } from './LiveChart'
import {
  ageText,
  FOG_HUMIDITY,
  freshness,
  type Freshness,
  GAUGE_RANGE,
  SAMPLE_OPTIONS,
  trend,
  WINDOW_OPTIONS,
  withGaps,
} from './rules'

const UNIT: Record<string, string> = { C: '°C', deg: '°' }
const unitOf = (v: LiveVariable) => UNIT[v.sensor_type.unit] ?? v.sensor_type.unit
const colorOf = (v: LiveVariable) => SERIES_COLOR[v.sensor_type.code] ?? 'var(--chart-1)'
// Orden del panel: primero las variables meteorológicas principales; el resto, después.
const ORDER = ['temperatura', 'humedad_relativa', 'presion_atmosferica', 'velocidad_viento', 'niebla']
const rank = (v: LiveVariable) => {
  const i = ORDER.indexOf(v.sensor_type.code)
  return i < 0 ? ORDER.length : i
}

const STATE: Record<Freshness, { label: string; dot: string; text: string }> = {
  en_vivo: { label: 'En vivo', dot: 'bg-success animate-pulse', text: 'text-success' },
  retrasada: { label: 'Lecturas retrasadas', dot: 'bg-warning', text: 'text-warning' },
  sin_conexion: { label: 'Sin conexión', dot: 'bg-danger', text: 'text-danger' },
}

function useNow(): number {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(id)
  }, [])
  return now
}

function Segmented<T extends number>({
  label,
  value,
  options,
  onChange,
  disabled,
}: {
  label: string
  value: T
  options: readonly { value: T; label: string; title?: string }[]
  onChange: (value: T) => void
  disabled?: boolean
}) {
  return (
    <div role="radiogroup" aria-label={label} className="bg-muted inline-flex flex-wrap rounded-lg p-0.5">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          role="radio"
          aria-checked={o.value === value}
          title={o.title}
          disabled={disabled}
          onClick={() => onChange(o.value)}
          className={cn(
            'rounded-md px-3 py-1.5 text-sm font-medium whitespace-nowrap transition-colors disabled:cursor-not-allowed',
            o.value === value
              ? 'bg-card text-foreground shadow-card'
              : 'text-muted-foreground hover:text-foreground disabled:hover:text-muted-foreground',
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

function Trend({ delta, unit }: { delta: number | null; unit: string }) {
  if (delta === null) return null
  const Icon = delta > 0.05 ? ArrowUpRight : delta < -0.05 ? ArrowDownRight : ArrowRight
  const text = delta > 0.05 ? 'sube' : delta < -0.05 ? 'baja' : 'estable'
  return (
    <span className="text-muted-foreground inline-flex items-center gap-1 text-xs">
      <Icon className="size-3.5" aria-hidden />
      {text} {delta !== 0 && `${delta > 0 ? '+' : ''}${formatNumber(delta, 2)} ${unit}`}
    </span>
  )
}

function GaugeTile({ variable, now, intervalS }: { variable: LiveVariable; now: number; intervalS: number }) {
  const range = GAUGE_RANGE[variable.sensor_type.code]
  const unit = unitOf(variable)
  const fresh = freshness(variable.latest_at, intervalS, false, now) === 'en_vivo'
  const incremental = variable.aggregation === 'incremental'
  const total = variable.points.reduce((sum, p) => sum + p.v, 0)
  return (
    <Card>
      <CardContent className="grid justify-items-center gap-1 text-center">
        <div className="text-sm font-medium">{variable.sensor_type.name}</div>
        {incremental || !range ? (
          <div className="py-6">
            <div className="text-3xl font-semibold tabular-nums">
              {incremental ? formatNumber(total, 2) : formatNumber(variable.latest_value, 1)}
              <span className="text-muted-foreground ml-1 text-sm font-normal">{unit}</span>
            </div>
            <div className="text-muted-foreground text-xs">{incremental ? 'captado en la ventana' : 'último valor'}</div>
          </div>
        ) : (
          <Gauge
            value={variable.latest_value}
            unit={unit}
            label={variable.sensor_type.name}
            color={colorOf(variable)}
            range={range}
            windowMin={variable.minimum}
            windowMax={variable.maximum}
            band={
              variable.sensor_type.code === 'humedad_relativa'
                ? { from: FOG_HUMIDITY, label: `Condición de niebla: humedad ≥ ${FOG_HUMIDITY} %` }
                : undefined
            }
            dimmed={!fresh}
          />
        )}
        <div className="flex flex-wrap items-center justify-center gap-x-3 gap-y-1">
          <Trend delta={trend(variable.points)} unit={unit} />
          <span
            className={cn('text-xs', fresh ? 'text-muted-foreground' : 'text-warning')}
            title={variable.latest_at ? formatDateTime(variable.latest_at) : undefined}
          >
            {!fresh && <WifiOff className="mr-1 inline size-3" aria-hidden />}
            {variable.latest_at ? ageText(variable.latest_at, now) : 'sin lecturas válidas'}
          </span>
        </div>
      </CardContent>
    </Card>
  )
}

function ChartCard({ variable, data, intervalS }: { variable: LiveVariable; data: LiveData; intervalS: number }) {
  const unit = unitOf(variable)
  const to = new Date(data.generated_at).getTime()
  const from = to - data.window_minutes * 60_000
  const stat = (v: number | null) => (v === null ? '—' : `${formatNumber(v, 1)} ${unit}`)
  return (
    <Card>
      <CardHead
        title={variable.sensor_type.name}
        subtitle={`Mín. ${stat(variable.minimum)} · Prom. ${stat(variable.average)} · Máx. ${stat(variable.maximum)} · ${variable.points.length} lecturas`}
      />
      <CardContent>
        {variable.points.length === 0 ? (
          <EmptyState
            icon={WifiOff}
            title="Sin lecturas válidas en la ventana"
            description="Cuando la estación envíe esta variable, aparecerá aquí."
          />
        ) : (
          <LiveChart
            data={withGaps(variable.points, intervalS)}
            color={colorOf(variable)}
            unit={unit}
            name={variable.sensor_type.name}
            from={from}
            to={to}
            average={variable.aggregation === 'instantaneo' ? variable.average : null}
          />
        )}
      </CardContent>
    </Card>
  )
}

export function LiveMonitoringPage() {
  const can = useHasPermission()
  const qc = useQueryClient()
  const now = useNow()
  const [deviceId, setDeviceId] = useState<number | null>(null)
  const [minutes, setMinutes] = useState<number>(15)

  const summary = useQuery({
    queryKey: ['dashboard', 'summary'],
    queryFn: async () => (await api.get<DashboardSummary>('/dashboard/summary')).data,
    refetchInterval: 30_000,
  })
  const stations = summary.data?.devices.filter((d) => d.status !== 'inactivo') ?? []
  const selected = deviceId ?? stations.find((d) => !d.is_stale)?.id ?? stations[0]?.id ?? null

  const live = useQuery({
    queryKey: ['monitoring', 'live', selected, minutes],
    queryFn: async () => (await api.get<LiveData>('/dashboard/live', { params: { device_id: selected, minutes } })).data,
    enabled: selected !== null,
    // Se actualiza al mismo ritmo con que la estación toma lecturas.
    refetchInterval: (query) => Math.max(5, query.state.data?.device.sample_interval_s ?? 30) * 1000,
  })
  const setInterval_ = useMutation({
    mutationFn: async (seconds: number) => api.put(`/devices/${selected}`, { sample_interval_s: seconds }),
    // El intervalo define cuándo se considera perdida la conexión: lo ven todos los módulos.
    onSuccess: () => refreshStations(qc),
  })

  if (summary.isLoading) return <Loading />
  if (summary.error) return <ErrorAlert error={summary.error} />

  const data = live.data
  const intervalS = data?.device.sample_interval_s ?? 60
  const state = data ? freshness(data.device.last_seen_at, intervalS, data.device.is_stale, now) : null
  const canConfigure = can('infraestructura.gestionar')
  const instant = (data?.variables.filter((v) => v.points.length > 0 || v.latest_value !== null) ?? []).sort(
    (a, b) => rank(a) - rank(b),
  )

  return (
    <>
      <PageHeader
        eyebrow="Principal"
        title="Monitoreo en vivo"
        description="Variables meteorológicas de la estación, actualizadas al ritmo del muestreo."
        actions={
          stations.length > 0 && (
            <NativeSelect
              aria-label="Estación"
              className="h-9 w-56"
              value={selected ?? ''}
              onChange={(e) => {
                setDeviceId(Number(e.target.value))
                setInterval_.reset()
              }}
            >
              {stations.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name} ({d.code})
                </option>
              ))}
            </NativeSelect>
          )
        }
      />
      {stations.length === 0 ? (
        <Card>
          <CardContent>
            <EmptyState icon={Cpu} title="Sin estaciones registradas" />
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-5">
          <Card>
            <CardContent className="flex flex-wrap items-center justify-between gap-x-6 gap-y-4">
              <div className="flex items-center gap-3" aria-live="polite">
                <Radio className="text-muted-foreground size-5" aria-hidden />
                {state ? (
                  <div>
                    <div className={cn('flex items-center gap-2 font-semibold', STATE[state].text)}>
                      <span className={cn('size-2.5 rounded-full', STATE[state].dot)} aria-hidden />
                      {STATE[state].label}
                    </div>
                    <div className="text-muted-foreground text-xs">
                      Último envío {ageText(data!.device.last_seen_at, now)} · se actualiza cada {intervalS} s
                    </div>
                  </div>
                ) : (
                  <span className="text-muted-foreground text-sm">Consultando la estación…</span>
                )}
              </div>
              <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
                <div className="grid gap-1">
                  <span className="text-muted-foreground text-xs">Muestreo de la estación</span>
                  <Segmented
                    label="Intervalo de muestreo de la estación"
                    value={intervalS}
                    options={SAMPLE_OPTIONS.map((o) => ({ value: o.seconds, label: o.label, title: o.hint }))}
                    onChange={(seconds) => seconds !== intervalS && setInterval_.mutate(seconds)}
                    disabled={!canConfigure || !data || setInterval_.isPending}
                  />
                </div>
                <div className="grid gap-1">
                  <span className="text-muted-foreground text-xs">Ventana</span>
                  <Segmented
                    label="Ventana de tiempo"
                    value={minutes}
                    options={WINDOW_OPTIONS.map((o) => ({ value: o.minutes, label: o.label }))}
                    onChange={setMinutes}
                  />
                </div>
              </div>
            </CardContent>
          </Card>

          <ErrorAlert error={live.error ?? setInterval_.error} />
          {setInterval_.isSuccess && (
            <Notice tone="success" title="Intervalo guardado">
              La estación lo aplica al confirmar su próximo envío (en hasta {setInterval_.variables} s más el ciclo
              actual). Con «Tiempo real» se guardan 12 lecturas por minuto de cada variable.
            </Notice>
          )}
          {!canConfigure && (
            <p className="text-muted-foreground -mt-2 text-xs">
              Solo el personal que administra los dispositivos puede cambiar el intervalo de muestreo.
            </p>
          )}

          {live.isLoading && <Loading />}
          {data &&
            (instant.length === 0 ? (
              <Card>
                <CardContent>
                  <EmptyState
                    icon={WifiOff}
                    title="Sin lecturas válidas"
                    description="La estación no tiene sensores activos o todavía no envió lecturas válidas."
                  />
                </CardContent>
              </Card>
            ) : (
              <>
                <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
                  {instant.map((v) => (
                    <GaugeTile key={v.sensor_type.code} variable={v} now={now} intervalS={intervalS} />
                  ))}
                </div>
                <div className="grid gap-5">
                  {instant.map((v) => (
                    <ChartCard key={v.sensor_type.code} variable={v} data={data} intervalS={intervalS} />
                  ))}
                </div>
              </>
            ))}
        </div>
      )}
    </>
  )
}
