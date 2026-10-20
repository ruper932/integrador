import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ClipboardCheck, Inbox, MapPin, Play, Plus, UserCheck, Wrench } from 'lucide-react'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { useSearchParams } from 'react-router'
import { z } from 'zod'

import { EmptyState, ErrorAlert, Field, Loading, NativeSelect, Notice, PageHeader, Pagination, StatCard } from '@/components/common'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { useHasPermission, useMe } from '@/features/auth/useAuth'
import { useDevices, useSensors } from '@/features/devices/api'
import { useIncidentSummary } from '@/features/incidents/api'
import { AutoBadge, IncidentStatusBadge, IncidentTimeline, PriorityBadge, reporterName } from '@/features/incidents/IncidentBits'
import { PRIORITY_LABELS, STATUS_LABELS, STATUS_ORDER } from '@/features/incidents/labels'
import { FINAL_LABELS, TYPE_LABELS } from '@/features/maintenance/labels'
import { MaintenanceForm } from '@/features/maintenance/MaintenanceForm'
import { api } from '@/lib/api'
import { ExportReportButton } from '@/features/reports/ExportReportButton'
import { formatDateTime, formatNumber } from '@/lib/format'
import { cn } from '@/lib/utils'
import type { Incident, IncidentScope, IncidentStatus, IncidentSummary, Page } from '@/types/api'

const LIMIT = 20
const PRIORITIES = ['alta', 'media', 'baja'] as const

// Pestañas en orden de preferencia; cada una exige un permiso (el backend también lo valida).
const TABS: { scope: IncidentScope; label: string; permission: string }[] = [
  { scope: 'open', label: 'Por atender', permission: 'incidencias.atender' },
  { scope: 'assigned', label: 'Asignados a mí', permission: 'incidencias.atender' },
  { scope: 'all', label: 'Todos los reportes', permission: 'incidencias.supervisar' },
  { scope: 'mine', label: 'Mis reportes', permission: 'incidencias.reportar' },
]

// --- Nuevo reporte ------------------------------------------------------------

const reportSchema = z
  .object({
    title: z.string().trim().min(5, 'Escriba un título de al menos 5 caracteres').max(120, 'Máximo 120 caracteres'),
    description: z
      .string()
      .trim()
      .min(10, 'Describa la situación con al menos 10 caracteres')
      .max(2000, 'Máximo 2000 caracteres'),
    priority: z.enum(PRIORITIES),
    location_reference: z.string().trim().max(200, 'Máximo 200 caracteres'),
    device_id: z.string(),
    sensor_id: z.string(),
  })
  .refine((v) => !v.sensor_id || v.device_id, { message: 'Seleccione primero el dispositivo', path: ['sensor_id'] })
type ReportValues = z.infer<typeof reportSchema>

function ReportForm({ onDone }: { onDone: (incident: Incident) => void }) {
  const qc = useQueryClient()
  const devices = useDevices()
  const sensors = useSensors()
  const form = useForm<ReportValues>({
    resolver: zodResolver(reportSchema),
    defaultValues: { title: '', description: '', priority: 'media', location_reference: '', device_id: '', sensor_id: '' },
  })
  const deviceId = form.watch('device_id')
  const create = useMutation({
    mutationFn: async (v: ReportValues) =>
      (
        await api.post<Incident>('/incidents', {
          title: v.title,
          description: v.description,
          priority: v.priority,
          location_reference: v.location_reference || null,
          device_id: v.device_id ? Number(v.device_id) : null,
          sensor_id: v.sensor_id ? Number(v.sensor_id) : null,
        })
      ).data,
    onSuccess: (incident) => {
      qc.invalidateQueries({ queryKey: ['incidents'] })
      onDone(incident)
    },
  })
  const { errors } = form.formState

  return (
    <form onSubmit={form.handleSubmit((v) => create.mutate(v))} className="grid gap-3" noValidate>
      <div className="grid gap-3 sm:grid-cols-[1fr_12rem]">
        <Field label="¿Qué sucede?" htmlFor="inc-title" error={errors.title?.message}>
          <Input id="inc-title" placeholder="Ej.: Malla rota en el atrapanieblas sur" {...form.register('title')} />
        </Field>
        <Field label="Prioridad" htmlFor="inc-priority">
          <NativeSelect id="inc-priority" {...form.register('priority')}>
            {PRIORITIES.map((p) => (
              <option key={p} value={p}>
                {PRIORITY_LABELS[p]}
              </option>
            ))}
          </NativeSelect>
        </Field>
      </div>
      <Field label="Descripción" htmlFor="inc-desc" error={errors.description?.message}>
        <Textarea
          id="inc-desc"
          rows={3}
          placeholder="Qué observó, desde cuándo y cualquier detalle útil para el personal de mantenimiento."
          {...form.register('description')}
        />
      </Field>
      <div className="grid gap-3 sm:grid-cols-3">
        <Field label="Dispositivo (opcional)" htmlFor="inc-device">
          <NativeSelect id="inc-device" {...form.register('device_id', { onChange: () => form.setValue('sensor_id', '') })}>
            <option value="">No lo sé / no aplica</option>
            {devices.data?.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name} ({d.code})
              </option>
            ))}
          </NativeSelect>
        </Field>
        <Field label="Sensor (opcional)" htmlFor="inc-sensor" error={errors.sensor_id?.message}>
          <NativeSelect id="inc-sensor" {...form.register('sensor_id')} disabled={!deviceId}>
            <option value="">Todo el dispositivo</option>
            {sensors.data
              ?.filter((s) => String(s.device_id) === deviceId)
              .map((s) => (
                <option key={s.id} value={s.id}>
                  {s.sensor_type.name} ({s.code})
                </option>
              ))}
          </NativeSelect>
        </Field>
        <Field label="Lugar (opcional)" htmlFor="inc-place" error={errors.location_reference?.message}>
          <Input id="inc-place" placeholder="Ej.: junto al tanque principal" {...form.register('location_reference')} />
        </Field>
      </div>
      <ErrorAlert error={create.error} />
      <div>
        <Button type="submit" disabled={create.isPending}>
          Enviar reporte
        </Button>
      </div>
    </form>
  )
}

// --- Detalle y acciones ---------------------------------------------------------

function IncidentDetail({ id, onClose }: { id: number; onClose: () => void }) {
  const qc = useQueryClient()
  const me = useMe()
  const can = useHasPermission()
  const [finishing, setFinishing] = useState(false)
  const incident = useQuery({
    queryKey: ['incidents', 'detail', id],
    queryFn: async () => (await api.get<Incident>(`/incidents/${id}`)).data,
  })
  const action = useMutation({
    mutationFn: async (step: 'accept' | 'start') => (await api.post<Incident>(`/incidents/${id}/${step}`)).data,
    onSuccess: (updated) => {
      qc.setQueryData(['incidents', 'detail', id], updated)
      qc.invalidateQueries({ queryKey: ['incidents'] })
      qc.invalidateQueries({ queryKey: ['maintenance'] })
    },
  })

  const data = incident.data
  const m = data?.maintenance
  const isAssignee = Boolean(data?.assignee && data.assignee.id === me.data?.id)
  const attend = can('incidencias.atender')

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[92dvh] overflow-y-auto sm:max-w-2xl">
        {!data ? (
          <>
            <DialogTitle className="sr-only">Reporte #{id}</DialogTitle>
            {incident.error ? <ErrorAlert error={incident.error} /> : <Loading />}
          </>
        ) : (
          <>
            <DialogHeader>
              <div className="flex flex-wrap items-center gap-2 pr-8">
                <IncidentStatusBadge status={data.status} />
                <PriorityBadge priority={data.priority} />
                <span className="text-muted-foreground text-xs">Reporte #{data.id}</span>
              </div>
              <DialogTitle className="text-lg">{data.title}</DialogTitle>
              <DialogDescription>
                {data.source === 'sistema' ? 'Detectado por el sistema' : `Reportado por ${reporterName(data)}`} el {formatDateTime(data.created_at)}
              </DialogDescription>
            </DialogHeader>

            <p className="text-sm whitespace-pre-line">{data.description}</p>
            <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
              <div>
                <dt className="text-muted-foreground text-xs">Componente</dt>
                <dd>
                  {data.device_name ? `${data.device_name} (${data.device_code})` : 'Sin indicar'}
                  {data.sensor_code && ` · sensor ${data.sensor_code}`}
                </dd>
              </div>
              <div>
                <dt className="text-muted-foreground text-xs">Lugar</dt>
                <dd className="flex items-center gap-1">
                  {data.location_reference ? (
                    <>
                      <MapPin className="size-3.5 shrink-0" aria-hidden /> {data.location_reference}
                    </>
                  ) : (
                    'Sin indicar'
                  )}
                </dd>
              </div>
              <div>
                <dt className="text-muted-foreground text-xs">Personal asignado</dt>
                <dd className="font-medium">{data.assignee?.full_name ?? 'Aún sin asignar'}</dd>
              </div>
            </dl>

            <div className="bg-muted/50 rounded-xl border p-4">
              <IncidentTimeline incident={data} />
            </div>

            {m?.status === 'finalizado' && (
              <div className="grid gap-2 rounded-xl border p-4 text-sm">
                <div className="font-medium">Trabajo realizado</div>
                <div className="text-muted-foreground text-xs">
                  {m.maintenance_type && TYPE_LABELS[m.maintenance_type]} · {m.device_code}
                  {m.sensor_code && ` / ${m.sensor_code}`} · estado final:{' '}
                  {m.final_status ? FINAL_LABELS[m.final_status].toLowerCase() : '—'}
                </div>
                <p className="whitespace-pre-line">{m.description}</p>
                {m.items.length > 0 && (
                  <div className="text-muted-foreground text-xs">
                    Repuestos: {m.items.map((i) => `${i.item_name} × ${formatNumber(i.quantity, 3)}`).join(', ')}
                  </div>
                )}
              </div>
            )}

            <ErrorAlert error={action.error} />
            {attend && data.status === 'abierto' && (
              <div className="flex flex-wrap items-center gap-3">
                <Button onClick={() => action.mutate('accept')} disabled={action.isPending}>
                  <UserCheck /> Aceptar reporte
                </Button>
                <span className="text-muted-foreground text-xs">
                  {data.source === 'sistema'
                    ? 'Quedará asignado a usted.'
                    : 'Quedará asignado a usted y se avisará a quien lo reportó.'}
                </span>
              </div>
            )}
            {isAssignee && data.status === 'aceptado' && (
              <div>
                <Button onClick={() => action.mutate('start')} disabled={action.isPending}>
                  <Play /> Iniciar mantenimiento
                </Button>
              </div>
            )}
            {isAssignee && data.status === 'en_progreso' &&
              (finishing ? (
                <div className="rounded-xl border p-4">
                  <div className="mb-3 font-medium">Finalizar mantenimiento</div>
                  <MaintenanceForm incident={data} onDone={() => setFinishing(false)} />
                </div>
              ) : (
                <div>
                  <Button onClick={() => setFinishing(true)}>
                    <ClipboardCheck /> Registrar trabajo y finalizar
                  </Button>
                </div>
              ))}
            {!isAssignee && data.assignee && data.status !== 'finalizado' && attend && (
              <Notice tone="info">Este reporte está asignado a {data.assignee.full_name}.</Notice>
            )}
          </>
        )}
      </DialogContent>
    </Dialog>
  )
}

// --- Lista -------------------------------------------------------------------

function IncidentRow({ incident, onOpen }: { incident: Incident; onOpen: () => void }) {
  return (
    <li>
      <button
        type="button"
        onClick={onOpen}
        className="hover:bg-muted/60 focus-visible:bg-muted/60 grid w-full gap-1.5 rounded-lg px-3 py-3 text-left sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center sm:gap-4"
      >
        <span className="min-w-0">
          <span className="flex flex-wrap items-center gap-2">
            <span className="truncate font-medium">{incident.title}</span>
            {incident.priority === 'alta' && <PriorityBadge priority="alta" />}
            {incident.source === 'sistema' && <AutoBadge />}
          </span>
          <span className="text-muted-foreground block truncate text-xs">
            #{incident.id} · {reporterName(incident)} · {formatDateTime(incident.created_at)}
            {incident.device_name && ` · ${incident.device_name}`}
          </span>
        </span>
        <span className="flex flex-wrap items-center gap-2 sm:justify-end">
          <span className="text-muted-foreground text-xs">
            {incident.assignee ? `Asignado a ${incident.assignee.full_name}` : 'Sin asignar'}
          </span>
          <IncidentStatusBadge status={incident.status} />
        </span>
      </button>
    </li>
  )
}

function SummaryCards({ summary, scopes }: { summary: IncidentSummary; scopes: IncidentScope[] }) {
  const counts = summary.all ?? summary.mine
  if (scopes.includes('open')) {
    return (
      <div className="mb-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Reportes por atender"
          value={summary.open ?? 0}
          icon={Inbox}
          tone={summary.open ? 'warning' : undefined}
          foot={summary.open ? 'Esperan que alguien los acepte' : 'No hay reportes pendientes'}
        />
        <StatCard label="Asignados a mí en curso" value={summary.assigned_active ?? 0} icon={Wrench} />
      </div>
    )
  }
  if (!counts) return null
  return (
    <div className="mb-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
      {STATUS_ORDER.map((s) => (
        <StatCard key={s} label={STATUS_LABELS[s]} value={counts[s] ?? 0} />
      ))}
    </div>
  )
}

export function IncidentsPage() {
  const can = useHasPermission()
  const [params, setParams] = useSearchParams()
  const tabs = TABS.filter((t) => can(t.permission))
  const [scope, setScope] = useState<IncidentScope>(tabs[0]?.scope ?? 'mine')
  const [status, setStatus] = useState<IncidentStatus | ''>('')
  const [offset, setOffset] = useState(0)
  const [showForm, setShowForm] = useState(false)
  const [sent, setSent] = useState<Incident | null>(null)
  const summary = useIncidentSummary()
  const list = useQuery({
    queryKey: ['incidents', 'list', scope, status, offset],
    queryFn: async () =>
      (
        await api.get<Page<Incident>>('/incidents', {
          params: { scope, status: scope === 'open' ? undefined : status || undefined, offset, limit: LIMIT },
        })
      ).data,
    refetchInterval: 60_000,
  })
  const selected = Number(params.get('reporte')) || null
  const open = (id: number) => setParams({ reporte: String(id) })
  const close = () => setParams({})

  return (
    <>
      <PageHeader
        eyebrow="Operaciones"
        title="Reportes de incidencia"
        description={
          can('incidencias.atender')
            ? 'Acepte los reportes, inicie el mantenimiento y finalícelo registrando el trabajo y los repuestos.'
            : 'Informe al personal de mantenimiento sobre fallas en las estaciones o los atrapanieblas y siga su atención.'
        }
        actions={
          <>
          <ExportReportButton kinds={['incidencias']} />
          {can('incidencias.reportar') && (
            <Button
              onClick={() => {
                setShowForm(!showForm)
                setSent(null)
              }}
            >
              <Plus /> Nuevo reporte
            </Button>
          )}
          </>
        }
      />

      {sent && (
        <Notice tone="success" title="Reporte enviado" className="mb-4">
          El personal de mantenimiento recibió un aviso. Puede seguir su estado en «Mis reportes».
        </Notice>
      )}
      {showForm && (
        <Card className="mb-5">
          <CardContent>
            <ReportForm
              onDone={(incident) => {
                setShowForm(false)
                setSent(incident)
                setScope('mine')
                setOffset(0)
              }}
            />
          </CardContent>
        </Card>
      )}

      {summary.data && <SummaryCards summary={summary.data} scopes={tabs.map((t) => t.scope)} />}

      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="bg-muted inline-flex flex-wrap rounded-xl border p-1" role="tablist" aria-label="Vistas de reportes">
          {tabs.map((t) => (
            <button
              key={t.scope}
              type="button"
              role="tab"
              aria-selected={scope === t.scope}
              onClick={() => {
                setScope(t.scope)
                setOffset(0)
              }}
              className={cn(
                'rounded-lg px-3.5 py-1.5 text-sm',
                scope === t.scope ? 'bg-card text-foreground shadow-card font-medium' : 'text-muted-foreground hover:text-foreground',
              )}
            >
              {t.label}
              {t.scope === 'open' && Boolean(summary.data?.open) && (
                <span className="bg-warning-soft text-warning ml-1.5 rounded-md px-1.5 text-[11px] font-medium">
                  {summary.data?.open}
                </span>
              )}
            </button>
          ))}
        </div>
        {scope !== 'open' && (
          <label className="flex items-center gap-2 text-sm">
            <span className="text-muted-foreground">Estado</span>
            <NativeSelect
              value={status}
              onChange={(e) => {
                setStatus(e.target.value as IncidentStatus | '')
                setOffset(0)
              }}
              className="w-40"
            >
              <option value="">Todos</option>
              {STATUS_ORDER.map((s) => (
                <option key={s} value={s}>
                  {STATUS_LABELS[s]}
                </option>
              ))}
            </NativeSelect>
          </label>
        )}
      </div>

      <ErrorAlert error={list.error} />
      {list.isLoading ? (
        <Loading />
      ) : (
        <Card>
          <CardContent>
            {list.data?.items.length === 0 ? (
              <EmptyState
                icon={Inbox}
                title={scope === 'open' ? 'No hay reportes por atender' : 'No hay reportes'}
                description={
                  scope === 'mine' ? 'Cuando reporte una situación, aquí verá su estado y quién la atiende.' : undefined
                }
              />
            ) : (
              <ul className="divide-y">
                {list.data?.items.map((incident) => (
                  <IncidentRow key={incident.id} incident={incident} onOpen={() => open(incident.id)} />
                ))}
              </ul>
            )}
            {list.data && <Pagination offset={offset} limit={LIMIT} total={list.data.total} onChange={setOffset} />}
          </CardContent>
        </Card>
      )}

      {selected && <IncidentDetail key={selected} id={selected} onClose={close} />}
    </>
  )
}
