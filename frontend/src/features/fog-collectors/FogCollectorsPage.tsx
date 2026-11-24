import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CloudFog, Compass, Cpu, Droplets, Gauge, MapPin, Pencil, Truck, TriangleAlert, Wrench } from 'lucide-react'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link } from 'react-router'
import { z } from 'zod'

import { ErrorAlert, Field, Loading, NativeSelect, PageHeader, StatCard, StatusBadge } from '@/components/common'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { useHasPermission } from '@/features/auth/useAuth'
import { ORIENTATIONS, RELOCATION_STATUS_LABELS } from '@/features/relocations/labels'
import { FilterToolbar } from '@/features/reports/FilterToolbar'
import type { FilterValues } from '@/features/reports/ReportFilterField'
import { api } from '@/lib/api'
import { formatCalendarDate, formatDate, formatNumber, relativeTime } from '@/lib/format'
import { cn } from '@/lib/utils'
import { todayIso } from '@/lib/people'
import { name, numberOrNull, optionalNumber, pastOrToday } from '@/lib/validation'
import type { RelocationStatus } from '@/types/api'

interface Overview {
  id: number
  code: string
  name: string
  is_active: boolean
  mesh_area_m2: string | null
  mesh_type: string | null
  orientation: string | null
  installed_on: string | null
  location: { id: number; name: string; latitude: string | null; longitude: string | null; altitude_m: string | null } | null
  status: 'operativo' | 'sin_datos_recientes' | 'mantenimiento' | 'sin_estacion' | 'inactivo'
  stations: { id: number; code: string; name: string; status: string; last_seen_at: string | null; is_stale: boolean }[]
  tanks: { code: string; name: string; capacity_liters: string | null; level_cm: number | null; level_at: string | null; fill_share: number | null }[]
  volume_last_7_days: number
  liters_per_m2_day: number | null
  daily: { date: string; value: number }[]
  open_incidents: { id: number; title: string; status: string }[]
  last_maintenance_at: string | null
  active_relocation: { id: number; status: RelocationStatus } | null
}

const STATUS_LABELS: Record<Overview['status'], string> = {
  operativo: 'Operativo',
  sin_datos_recientes: 'Sin datos recientes',
  mantenimiento: 'En mantenimiento',
  sin_estacion: 'Sin estación IoT',
  inactivo: 'Inactivo',
}

const hasCoords = (f: Overview) => f.location?.latitude != null && f.location?.longitude != null

/**
 * Plano esquemático de ubicación (sin mapa base, funciona sin Internet): posiciones relativas a
 * partir de latitud y longitud, con escala aproximada y el norte hacia arriba.
 */
function LocationPlan({ items, selected, onSelect }: { items: Overview[]; selected: number | null; onSelect: (id: number) => void }) {
  const located = items.filter(hasCoords)
  if (located.length === 0) {
    return <p className="text-muted-foreground text-sm">Ningún atrapanieblas tiene coordenadas registradas.</p>
  }
  const lat = located.map((f) => Number(f.location!.latitude))
  const lon = located.map((f) => Number(f.location!.longitude))
  const midLat = (Math.min(...lat) + Math.max(...lat)) / 2
  const kx = Math.cos((midLat * Math.PI) / 180) // un grado de longitud mide menos que uno de latitud
  const xs = lon.map((v) => v * kx)
  const span = Math.max(Math.max(...xs) - Math.min(...xs), Math.max(...lat) - Math.min(...lat), 0.0005)
  const [W, H, pad] = [640, 300, 56]
  const scale = Math.min((W - 2 * pad) / span, (H - 2 * pad) / span)
  const cx = (Math.min(...xs) + Math.max(...xs)) / 2
  const cy = (Math.min(...lat) + Math.max(...lat)) / 2
  const point = (i: number) => ({ x: W / 2 + (xs[i]! - cx) * scale, y: H / 2 - (lat[i]! - cy) * scale })
  // Barra de escala de ~1/4 del ancho útil, redondeada a 50 m.
  const metersPerUnit = 111_320 / scale
  const barMeters = Math.max(50, Math.round(((W - 2 * pad) / 4) * metersPerUnit / 50) * 50)
  const barPx = barMeters / metersPerUnit

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="h-64 w-full sm:h-72" role="group" aria-label="Plano de ubicación de los atrapanieblas">
      <rect x={0} y={0} width={W} height={H} rx={8} fill="var(--muted)" />
      {[1, 2, 3].map((i) => (
        <g key={i} stroke="var(--grid)" strokeDasharray="3 6">
          <line x1={(W / 4) * i} y1={0} x2={(W / 4) * i} y2={H} />
          {i < 3 && <line x1={0} y1={(H / 3) * i} x2={W} y2={(H / 3) * i} />}
        </g>
      ))}
      <g transform={`translate(${W - 34}, 34)`} aria-hidden>
        <path d="M0 -16 L6 4 L0 0 L-6 4 Z" fill="var(--foreground)" />
        <text y={18} textAnchor="middle" fontSize={12} fill="var(--foreground)" fontWeight={584}>
          N
        </text>
      </g>
      <g transform={`translate(20, ${H - 22})`} aria-hidden>
        <line x1={0} y1={0} x2={barPx} y2={0} stroke="var(--foreground)" strokeWidth={2} />
        <line x1={0} y1={-4} x2={0} y2={4} stroke="var(--foreground)" strokeWidth={2} />
        <line x1={barPx} y1={-4} x2={barPx} y2={4} stroke="var(--foreground)" strokeWidth={2} />
        <text x={barPx / 2} y={-8} textAnchor="middle" fontSize={12} fill="var(--muted-foreground)">
          ≈ {barMeters} m
        </text>
      </g>
      {located.map((f, i) => {
        const { x, y } = point(i)
        const active = selected === f.id
        return (
          <g
            key={f.id}
            transform={`translate(${x}, ${y})`}
            role="button"
            tabIndex={0}
            aria-pressed={active}
            aria-label={`${f.name}: ${STATUS_LABELS[f.status]}, altitud ${f.location!.altitude_m ?? 'sin dato'} m`}
            onClick={() => onSelect(f.id)}
            onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), onSelect(f.id))}
            className="cursor-pointer outline-none"
          >
            <title>{`${f.name} · ${STATUS_LABELS[f.status]} · ${formatNumber(Number(f.location!.altitude_m ?? 0), 0)} m s. n. m.`}</title>
            {/* Zona de clic amplia: el punto y sus rótulos. */}
            <rect x={-64} y={-18} width={128} height={66} fill="transparent" />
            {active && <circle r={19} fill="none" stroke="var(--foreground)" strokeWidth={1.5} />}
            <circle r={active ? 13 : 10} fill={active ? 'var(--primary)' : 'var(--chart-1)'} stroke="var(--card)" strokeWidth={3} />
            {f.status !== 'operativo' && <circle r={4} cx={9} cy={-9} fill="var(--warning)" stroke="var(--card)" strokeWidth={2} />}
            <text y={28} textAnchor="middle" fontSize={12} fill="var(--foreground)" fontWeight={active ? 584 : 492}>
              {f.name}
            </text>
            <text y={42} textAnchor="middle" fontSize={12} fill="var(--muted-foreground)">
              {f.code} · {formatNumber(Number(f.location!.altitude_m ?? 0), 0)} m
            </text>
          </g>
        )
      })}
    </svg>
  )
}

/** Mini barras de los últimos 7 días (solo días con datos). */
function Spark({ daily }: { daily: Overview['daily'] }) {
  if (daily.length === 0) return <span className="text-muted-foreground text-xs">Sin lecturas de volumen</span>
  const max = Math.max(...daily.map((d) => d.value), 1)
  return (
    <svg viewBox={`0 0 ${daily.length * 10} 28`} className="h-7 w-28" role="img" aria-label="Captación de los últimos días">
      {daily.map((d, i) => {
        const h = Math.max(2, (d.value / max) * 26)
        return (
          <rect key={d.date} x={i * 10 + 1} y={28 - h} width={8} height={h} rx={2} fill="var(--chart-1)">
            <title>{`${formatDate(d.date)}: ${formatNumber(d.value, 1)} L`}</title>
          </rect>
        )
      })}
    </svg>
  )
}

function Detail({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-muted-foreground text-xs">{label}</dt>
      <dd className="text-sm">{children}</dd>
    </div>
  )
}

function FogCollectorCard({
  f,
  selected,
  onEdit,
  canRequestRelocation,
}: {
  f: Overview
  selected: boolean
  onEdit?: () => void
  canRequestRelocation: boolean
}) {
  const loc = f.location
  return (
    <Card id={`atrapanieblas-${f.id}`} className={cn('scroll-mt-24 transition-shadow', selected && 'ring-primary ring-2')}>
      <CardContent className="grid gap-4">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <div className="text-muted-foreground text-xs">{f.code}</div>
            <h2 className="text-lg font-semibold">{f.name}</h2>
          </div>
          <div className="flex items-center gap-2">
            <StatusBadge value={f.status} label={STATUS_LABELS[f.status]} />
            {onEdit && (
              <Button size="icon-sm" variant="ghost" onClick={onEdit} aria-label={`Editar ${f.name}`}>
                <Pencil />
              </Button>
            )}
          </div>
        </div>

        <dl className="grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-3">
          <Detail label="Ubicación">
            <span className="flex items-start gap-1">
              <MapPin className="mt-0.5 size-3.5 shrink-0" aria-hidden /> {loc?.name ?? 'Sin ubicación'}
            </span>
          </Detail>
          <Detail label="Coordenadas">
            {loc?.latitude != null && loc.longitude != null
              ? `${Number(loc.latitude).toFixed(5)}, ${Number(loc.longitude).toFixed(5)}`
              : '—'}
          </Detail>
          <Detail label="Altitud">{loc?.altitude_m != null ? `${formatNumber(Number(loc.altitude_m), 0)} m s. n. m.` : '—'}</Detail>
          <Detail label="Malla">
            {f.mesh_area_m2 ? `${formatNumber(Number(f.mesh_area_m2), 1)} m²` : '—'}
            {f.mesh_type && <span className="text-muted-foreground"> · {f.mesh_type}</span>}
          </Detail>
          <Detail label="Orientación">
            <span className="flex items-center gap-1">
              <Compass className="size-3.5" aria-hidden /> {f.orientation ?? '—'}
            </span>
          </Detail>
          <Detail label="Instalado">{f.installed_on ? formatCalendarDate(f.installed_on) : '—'}</Detail>
        </dl>

        <div className="bg-muted/60 grid gap-3 rounded-lg border p-3 sm:grid-cols-3">
          <div>
            <div className="text-muted-foreground text-xs">Captación, últimos 7 días</div>
            <div className="text-lg font-semibold tabular-nums">{formatNumber(f.volume_last_7_days, 1)} L</div>
            <Spark daily={f.daily} />
          </div>
          <div>
            <div className="text-muted-foreground text-xs">Rendimiento de la malla</div>
            <div className="text-lg font-semibold tabular-nums">
              {f.liters_per_m2_day === null ? '—' : `${formatNumber(f.liters_per_m2_day, 2)}`}
              <span className="text-muted-foreground text-xs font-normal"> L/m²·día</span>
            </div>
          </div>
          <div>
            <div className="text-muted-foreground text-xs">Tanque</div>
            {f.tanks.length === 0 ? (
              <div className="text-sm">Sin tanque asociado</div>
            ) : (
              f.tanks.map((t) => (
                <div key={t.code} className="grid gap-1">
                  <div className="text-sm">
                    {t.name}: {t.level_cm === null ? 'sin lectura' : `${formatNumber(t.level_cm, 0)} cm`}
                  </div>
                  {t.fill_share !== null && (
                    <div
                      className="bg-card h-2 overflow-hidden rounded-full border"
                      role="meter"
                      aria-valuenow={Math.round(t.fill_share * 100)}
                      aria-valuemin={0}
                      aria-valuemax={100}
                      aria-label={`Nivel de ${t.name}`}
                    >
                      <div className="bg-chart-1 h-full" style={{ width: `${t.fill_share * 100}%` }} />
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <h3 className="mb-1.5 flex items-center gap-1.5 text-sm font-medium">
              <Cpu className="size-4" aria-hidden /> Estaciones IoT
            </h3>
            {f.stations.length === 0 ? (
              <p className="text-muted-foreground text-sm">Sin estación asociada.</p>
            ) : (
              <ul className="grid gap-1.5">
                {f.stations.map((s) => (
                  <li key={s.id} className="flex flex-wrap items-center justify-between gap-2 text-sm">
                    <span>
                      {s.name} <span className="text-muted-foreground">({s.code})</span>
                    </span>
                    <span className={cn('text-xs', s.is_stale ? 'text-warning' : 'text-muted-foreground')}>
                      {s.status !== 'activo' ? s.status : relativeTime(s.last_seen_at)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div>
            <h3 className="mb-1.5 flex items-center gap-1.5 text-sm font-medium">
              <Wrench className="size-4" aria-hidden /> Mantenimiento
            </h3>
            <p className="text-sm">
              Último: {f.last_maintenance_at ? formatDate(f.last_maintenance_at) : 'sin registros'}
            </p>
            {f.active_relocation ? (
              <Link
                to={`/reubicaciones?solicitud=${f.active_relocation.id}`}
                className="mt-1 flex items-center gap-1.5 text-sm underline decoration-primary decoration-2 underline-offset-2"
              >
                <Truck className="size-3.5 shrink-0" aria-hidden /> Reubicación #{f.active_relocation.id}:{' '}
                {RELOCATION_STATUS_LABELS[f.active_relocation.status].toLowerCase()}
              </Link>
            ) : (
              canRequestRelocation &&
              f.is_active && (
                <Link
                  to={`/reubicaciones?nuevo=${f.id}`}
                  className="mt-1 flex items-center gap-1.5 text-sm underline decoration-primary decoration-2 underline-offset-2"
                >
                  <Truck className="size-3.5 shrink-0" aria-hidden /> Solicitar reubicación
                </Link>
              )
            )}
            {f.open_incidents.map((i) => (
              <Link
                key={i.id}
                to={`/incidencias?reporte=${i.id}`}
                className="mt-1 flex items-center gap-1.5 text-sm underline decoration-primary decoration-2 underline-offset-2"
              >
                <TriangleAlert className="text-warning size-3.5 shrink-0" aria-hidden /> #{i.id} {i.title}
              </Link>
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

const editSchema = z
  .object({
    name: name(),
    mesh_area_m2: optionalNumber(0, 10000, { exclusiveMin: true }),
    mesh_type: z.string().trim().max(80, 'Máximo 80 caracteres'),
    orientation: z.string(),
    installed_on: pastOrToday,
    latitude: optionalNumber(-90, 90),
    longitude: optionalNumber(-180, 180),
    altitude_m: optionalNumber(-500, 9000),
  })
  // Las coordenadas solo sirven juntas (el plano de ubicación usa ambas).
  .refine((v) => (v.latitude === '') === (v.longitude === ''), {
    message: 'Indique la latitud y la longitud juntas, o ninguna',
    path: ['longitude'],
  })
type EditValues = z.infer<typeof editSchema>

function EditDialog({ f, onClose }: { f: Overview; onClose: () => void }) {
  const qc = useQueryClient()
  const form = useForm<EditValues>({
    resolver: zodResolver(editSchema),
    defaultValues: {
      name: f.name,
      mesh_area_m2: f.mesh_area_m2 ?? '',
      mesh_type: f.mesh_type ?? '',
      orientation: f.orientation ?? '',
      installed_on: f.installed_on ?? '',
      latitude: f.location?.latitude ?? '',
      longitude: f.location?.longitude ?? '',
      altitude_m: f.location?.altitude_m ?? '',
    },
  })
  const save = useMutation({
    mutationFn: async (v: EditValues) => {
      await api.put(`/fog-collectors/${f.id}`, {
        name: v.name,
        mesh_area_m2: numberOrNull(v.mesh_area_m2),
        mesh_type: v.mesh_type || null,
        orientation: v.orientation || null,
        installed_on: v.installed_on || null,
      })
      if (f.location) {
        await api.put(`/locations/${f.location.id}`, {
          latitude: numberOrNull(v.latitude),
          longitude: numberOrNull(v.longitude),
          altitude_m: numberOrNull(v.altitude_m),
        })
      }
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['fog-collectors'] })
      onClose()
    },
  })
  const { errors } = form.formState
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-h-[92dvh] overflow-y-auto sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>Editar {f.code}</DialogTitle>
          <DialogDescription>
            Datos técnicos del atrapanieblas{f.location ? ` y coordenadas de «${f.location.name}»` : ''}. Para cambiarlo de
            lugar, use una solicitud de reubicación.
          </DialogDescription>
        </DialogHeader>
        <form className="grid gap-3" onSubmit={form.handleSubmit((v) => save.mutate(v))} noValidate>
          <Field label="Nombre" htmlFor="fc-name" error={errors.name?.message}>
            <Input id="fc-name" {...form.register('name')} />
          </Field>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Área de malla (m²)" htmlFor="fc-area" error={errors.mesh_area_m2?.message}>
              <Input id="fc-area" inputMode="decimal" {...form.register('mesh_area_m2')} />
            </Field>
            <Field label="Tipo de malla" htmlFor="fc-type" error={errors.mesh_type?.message}>
              <Input id="fc-type" placeholder="Raschel 35 %" {...form.register('mesh_type')} />
            </Field>
            <Field label="Orientación" htmlFor="fc-orient">
              <NativeSelect id="fc-orient" {...form.register('orientation')}>
                <option value="">—</option>
                {/* Una orientación antigua escrita a mano se conserva como opción. */}
                {f.orientation && !(ORIENTATIONS as readonly string[]).includes(f.orientation) && (
                  <option value={f.orientation}>{f.orientation}</option>
                )}
                {ORIENTATIONS.map((o) => (
                  <option key={o} value={o}>
                    {o}
                  </option>
                ))}
              </NativeSelect>
            </Field>
            <Field label="Fecha de instalación" htmlFor="fc-date" error={errors.installed_on?.message}>
              <Input id="fc-date" type="date" max={todayIso()} {...form.register('installed_on')} />
            </Field>
          </div>
          {f.location && (
            <div className="grid gap-3 sm:grid-cols-3">
              <Field label="Latitud" htmlFor="fc-lat" hint="Ej.: -15.4021" error={errors.latitude?.message}>
                <Input id="fc-lat" inputMode="decimal" {...form.register('latitude')} />
              </Field>
              <Field label="Longitud" htmlFor="fc-lon" hint="Ej.: -68.9384" error={errors.longitude?.message}>
                <Input id="fc-lon" inputMode="decimal" {...form.register('longitude')} />
              </Field>
              <Field label="Altitud (m)" htmlFor="fc-alt" error={errors.altitude_m?.message}>
                <Input id="fc-alt" inputMode="decimal" {...form.register('altitude_m')} />
              </Field>
            </div>
          )}
          <ErrorAlert error={save.error} />
          <div>
            <Button type="submit" disabled={save.isPending}>
              Guardar cambios
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}

export function FogCollectorsPage() {
  const can = useHasPermission()
  const [selected, setSelected] = useState<number | null>(null)
  const [editing, setEditing] = useState<Overview | null>(null)
  const overview = useQuery({
    queryKey: ['fog-collectors', 'overview'],
    queryFn: async () => (await api.get<Overview[]>('/fog-collectors/overview')).data,
    refetchInterval: 60_000,
  })
  const [filters, setFilters] = useState<FilterValues>({})
  // shortcut: el resumen trae todos los atrapanieblas (pocos); se filtra aquí en vez de en la API.
  const items = (overview.data ?? []).filter((f) => !filters.fog_collector_id || String(f.id) === filters.fog_collector_id)
  const active = items.filter((f) => f.is_active)
  const select = (id: number) => {
    setSelected(id)
    document.getElementById(`atrapanieblas-${id}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  return (
    <>
      <PageHeader
        eyebrow="Operaciones"
        title="Atrapanieblas"
        description="Ubicación, estado según sus estaciones IoT, captación, tanque y mantenimiento de cada atrapanieblas."
      />
      <FilterToolbar kinds={['dispositivos', 'volumen']} keys={['fog_collector_id']} values={filters} onChange={setFilters} />
      <ErrorAlert error={overview.error} />
      {overview.isLoading ? (
        <Loading />
      ) : (
        <div className="grid gap-5">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard color="lavender" label="Atrapanieblas activos" value={active.length} icon={CloudFog} foot={`${items.length} registrados`} />
            <StatCard
              color="mint"
              label="Operativos"
              value={active.filter((f) => f.status === 'operativo').length}
              icon={Gauge}
              tone={active.some((f) => f.status !== 'operativo') ? 'warning' : undefined}
              foot={`${active.filter((f) => f.status !== 'operativo').length} requieren atención`}
            />
            <StatCard
              color="peach"
              label="Área de malla"
              value={formatNumber(
                active.reduce((s, f) => s + Number(f.mesh_area_m2 ?? 0), 0),
                1,
              )}
              unit="m²"
              icon={Compass}
            />
            <StatCard
              color="blue"
              label="Captación, últimos 7 días"
              value={formatNumber(
                active.reduce((s, f) => s + f.volume_last_7_days, 0),
                1,
              )}
              unit="L"
              icon={Droplets}
            />
          </div>

          <Card>
            <CardContent className="grid gap-2">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <h2 className="font-medium">Ubicación</h2>
                <span className="text-muted-foreground text-xs">
                  Plano esquemático según latitud y longitud (sin mapa base: funciona sin Internet). Seleccione un punto.
                </span>
              </div>
              <LocationPlan items={items} selected={selected} onSelect={select} />
            </CardContent>
          </Card>

          <div className="grid gap-5 xl:grid-cols-2">
            {items.map((f) => (
              <FogCollectorCard
                key={f.id}
                f={f}
                selected={selected === f.id}
                onEdit={can('infraestructura.gestionar') ? () => setEditing(f) : undefined}
                canRequestRelocation={can('reubicaciones.solicitar')}
              />
            ))}
          </div>
        </div>
      )}
      {editing && <EditDialog f={editing} onClose={() => setEditing(null)} />}
    </>
  )
}
