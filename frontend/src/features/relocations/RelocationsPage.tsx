import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowRight, Ban, CheckCircle2, CircleDot, ClipboardCheck, Inbox, MapPin, Play, Plus, Truck, UserCheck, type LucideIcon } from 'lucide-react'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { useSearchParams } from 'react-router'
import { z } from 'zod'

import { EmptyState, ErrorAlert, Field, Loading, NativeSelect, NextStepCard, Notice, PageHeader, Pagination, StatCard, YourTurnBadge, type ToneColor } from '@/components/common'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { useHasPermission, useMe } from '@/features/auth/useAuth'
import { useLocations } from '@/features/devices/api'
import { ORIENTATIONS, REASON_LABELS, REASONS, RELOCATION_STATUS_LABELS, RELOCATION_STATUS_ORDER } from '@/features/relocations/labels'
import { api } from '@/lib/api'
import { ACTION_LABELS, relocationNextStep, type Viewer } from '@/lib/flow'
import { formatDateTime } from '@/lib/format'
import { cn } from '@/lib/utils'
import type { Location, Page, Relocation, RelocationStatus, RelocationSummary } from '@/types/api'

type Scope = 'mine' | 'open' | 'assigned' | 'all'
const LIMIT = 20
const OTHER_PLACE = 'otro'

const TABS: { scope: Scope; label: string; permission: string }[] = [
  { scope: 'open', label: 'Por atender', permission: 'reubicaciones.atender' },
  { scope: 'assigned', label: 'Asignadas a mí', permission: 'reubicaciones.atender' },
  { scope: 'all', label: 'Todas las solicitudes', permission: 'reubicaciones.supervisar' },
  { scope: 'mine', label: 'Mis solicitudes', permission: 'reubicaciones.solicitar' },
]
const STATUS_STYLE: Record<RelocationStatus, { tone: 'info' | 'secondary' | 'warning' | 'success' | 'danger'; icon: LucideIcon; color: ToneColor }> = {
  pendiente: { tone: 'info', icon: CircleDot, color: 'rose' },
  aceptado: { tone: 'secondary', icon: UserCheck, color: 'lavender' },
  en_progreso: { tone: 'warning', icon: Truck, color: 'peach' },
  finalizado: { tone: 'success', icon: CheckCircle2, color: 'mint' },
  rechazado: { tone: 'danger', icon: Ban, color: 'blue' },
}

/** Datos del resumen de atrapanieblas que necesita el formulario (ubicación actual y solicitud en curso). */
interface CollectorOption {
  id: number
  code: string
  name: string
  is_active: boolean
  orientation: string | null
  location: { id: number; name: string } | null
  active_relocation: { id: number; status: RelocationStatus } | null
}

function useCollectorOptions() {
  return useQuery({
    queryKey: ['fog-collectors', 'overview'],
    queryFn: async () => (await api.get<CollectorOption[]>('/fog-collectors/overview')).data,
  })
}

function StatusBadge({ status }: { status: RelocationStatus }) {
  const { tone, icon: Icon } = STATUS_STYLE[status]
  return (
    <Badge variant={tone}>
      <Icon aria-hidden />
      {RELOCATION_STATUS_LABELS[status]}
    </Badge>
  )
}

const destinationText = (r: Relocation) => {
  if (r.destination_location) return r.destination_location.name
  const proposal = r.proposed_location?.name ?? r.proposed_place
  return proposal ? `${proposal} (sugerido)` : 'Destino por definir'
}

// --- Nueva solicitud -------------------------------------------------------------

const requestSchema = z
  .object({
    fog_collector_id: z.string().min(1, 'Seleccione el atrapanieblas'),
    reason: z.enum(REASONS),
    description: z
      .string()
      .trim()
      .min(10, 'Explique el problema de espacio con al menos 10 caracteres')
      .max(2000, 'Máximo 2000 caracteres'),
    proposed: z.string(),
    proposed_place: z.string().trim().max(200, 'Máximo 200 caracteres'),
  })
  .refine((v) => v.proposed !== OTHER_PLACE || v.proposed_place.length >= 3, {
    message: 'Describa el lugar sugerido (al menos 3 caracteres)',
    path: ['proposed_place'],
  })
type RequestValues = z.infer<typeof requestSchema>

export function RequestForm({ initialCollector, onDone }: { initialCollector: string; onDone: (r: Relocation) => void }) {
  const collectors = useCollectorOptions()
  const locations = useLocations()
  // Los catálogos se cargan antes de montar el formulario: sus reglas dependen de ellos.
  if (!collectors.data || !locations.data) {
    const error = collectors.error ?? locations.error
    return error ? <ErrorAlert error={error} /> : <Loading />
  }
  return (
    <RequestFields
      initialCollector={initialCollector}
      available={collectors.data.filter((c) => c.is_active)}
      locations={locations.data}
      onDone={onDone}
    />
  )
}

function RequestFields({
  initialCollector,
  available,
  locations,
  onDone,
}: {
  initialCollector: string
  available: CollectorOption[]
  locations: Location[]
  onDone: (r: Relocation) => void
}) {
  const qc = useQueryClient()
  const form = useForm<RequestValues>({
    resolver: zodResolver(
      // La propuesta depende del atrapanieblas elegido: no puede ser su ubicación actual ni uno con solicitud en curso.
      requestSchema.superRefine((v, ctx) => {
        const c = available.find((x) => String(x.id) === v.fog_collector_id)
        if (c?.active_relocation) {
          ctx.addIssue({ code: 'custom', path: ['fog_collector_id'], message: `Ya tiene la solicitud #${c.active_relocation.id} en curso` })
        }
        if (c?.location && v.proposed === String(c.location.id)) {
          ctx.addIssue({ code: 'custom', path: ['proposed'], message: 'Es la ubicación actual del atrapanieblas' })
        }
      }),
    ),
    defaultValues: { fog_collector_id: initialCollector, reason: 'espacio_insuficiente', description: '', proposed: '', proposed_place: '' },
  })
  const collectorId = form.watch('fog_collector_id')
  const proposed = form.watch('proposed')
  const collector = available.find((c) => String(c.id) === collectorId)
  const destinations = locations.filter((l) => l.id !== collector?.location?.id)
  const create = useMutation({
    mutationFn: async (v: RequestValues) =>
      (
        await api.post<Relocation>('/relocations', {
          fog_collector_id: Number(v.fog_collector_id),
          reason: v.reason,
          description: v.description,
          proposed_location_id: v.proposed && v.proposed !== OTHER_PLACE ? Number(v.proposed) : null,
          proposed_place: v.proposed === OTHER_PLACE ? v.proposed_place : null,
        })
      ).data,
    onSuccess: (r) => {
      qc.invalidateQueries({ queryKey: ['relocations'] })
      qc.invalidateQueries({ queryKey: ['fog-collectors'] })
      onDone(r)
    },
  })
  const { errors } = form.formState

  return (
    <form onSubmit={form.handleSubmit((v) => create.mutate(v))} className="grid gap-3" noValidate>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field
          label="Atrapanieblas"
          htmlFor="rl-fc"
          error={errors.fog_collector_id?.message}
          hint={collector ? `Ubicación actual: ${collector.location?.name ?? 'sin registrar'}` : undefined}
        >
          <NativeSelect
            id="rl-fc"
            {...form.register('fog_collector_id', {
              // Al cambiar de atrapanieblas, la propuesta anterior puede dejar de ser válida.
              onChange: () => form.setValue('proposed', ''),
            })}
          >
            <option value="">Seleccione…</option>
            {available.map((c) => (
              <option key={c.id} value={c.id} disabled={Boolean(c.active_relocation)}>
                {c.code} — {c.name}
                {c.active_relocation ? ' (solicitud en curso)' : ''}
              </option>
            ))}
          </NativeSelect>
        </Field>
        <Field label="Motivo" htmlFor="rl-reason">
          <NativeSelect id="rl-reason" {...form.register('reason')}>
            {REASONS.map((r) => (
              <option key={r} value={r}>
                {REASON_LABELS[r]}
              </option>
            ))}
          </NativeSelect>
        </Field>
      </div>
      <Field label="Descripción del problema" htmlFor="rl-desc" error={errors.description?.message}>
        <Textarea
          id="rl-desc"
          rows={3}
          placeholder="Qué ocurre con el espacio actual y desde cuándo (p. ej. se construirá un aula, el área se usará para cultivos)."
          {...form.register('description')}
        />
      </Field>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field
          label="Lugar sugerido (opcional)"
          htmlFor="rl-proposed"
          error={errors.proposed?.message}
          hint={collector ? undefined : 'Primero seleccione el atrapanieblas'}
        >
          <NativeSelect id="rl-proposed" disabled={!collector} {...form.register('proposed')}>
            <option value="">Sin propuesta: que lo decida mantenimiento</option>
            {destinations.map((l) => (
              <option key={l.id} value={l.id}>
                {l.name}
              </option>
            ))}
            <option value={OTHER_PLACE}>Otro lugar (aún no registrado)…</option>
          </NativeSelect>
        </Field>
        {proposed === OTHER_PLACE && (
          <Field label="Describa el lugar" htmlFor="rl-place" error={errors.proposed_place?.message}>
            <Input id="rl-place" placeholder="Ej.: detrás del invernadero 2" {...form.register('proposed_place')} />
          </Field>
        )}
      </div>
      <ErrorAlert error={create.error} />
      <div>
        <Button type="submit" disabled={create.isPending}>
          Enviar solicitud
        </Button>
      </div>
    </form>
  )
}

// --- Atención ------------------------------------------------------------------------

const finishSchema = z.object({
  destination_location_id: z.string().min(1, 'Seleccione la nueva ubicación'),
  new_orientation: z.union([z.literal(''), z.enum(ORIENTATIONS)]),
  work_notes: z.string().trim().min(5, 'Describa el trabajo realizado').max(4000, 'Máximo 4000 caracteres'),
})
type FinishValues = z.infer<typeof finishSchema>

function FinishForm({ relocation, onDone }: { relocation: Relocation; onDone: (r: Relocation) => void }) {
  const locations = useLocations()
  if (!locations.data) return locations.error ? <ErrorAlert error={locations.error} /> : <Loading />
  return <FinishFields relocation={relocation} locations={locations.data} onDone={onDone} />
}

function FinishFields({ relocation, locations, onDone }: { relocation: Relocation; locations: Location[]; onDone: (r: Relocation) => void }) {
  const qc = useQueryClient()
  // El destino no puede ser la ubicación actual (la de origen: no cambia mientras la solicitud está en curso).
  const destinations = locations.filter((l) => l.id !== relocation.origin_location?.id)
  const suggested = destinations.find((l) => l.id === relocation.proposed_location?.id)
  const form = useForm<FinishValues>({
    resolver: zodResolver(finishSchema),
    defaultValues: { destination_location_id: suggested ? String(suggested.id) : '', new_orientation: '', work_notes: '' },
  })
  const finish = useMutation({
    mutationFn: async (v: FinishValues) =>
      (
        await api.post<Relocation>(`/relocations/${relocation.id}/finish`, {
          destination_location_id: Number(v.destination_location_id),
          new_orientation: v.new_orientation || null,
          work_notes: v.work_notes,
        })
      ).data,
    onSuccess: (r) => {
      qc.invalidateQueries({ queryKey: ['fog-collectors'] })
      qc.invalidateQueries({ queryKey: ['devices'] })
      onDone(r)
    },
  })
  const { errors } = form.formState
  return (
    <form onSubmit={form.handleSubmit((v) => finish.mutate(v))} className="grid gap-3" noValidate>
      {relocation.proposed_place && (
        <Notice tone="info">
          Lugar sugerido sin registrar: «{relocation.proposed_place}». Si corresponde, regístrelo primero como ubicación.
        </Notice>
      )}
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Nueva ubicación" htmlFor="rl-dest" error={errors.destination_location_id?.message}>
          <NativeSelect id="rl-dest" {...form.register('destination_location_id')}>
            <option value="">Seleccione…</option>
            {destinations.map((l) => (
              <option key={l.id} value={l.id}>
                {l.name}
                {l.id === relocation.proposed_location?.id ? ' (sugerida)' : ''}
              </option>
            ))}
          </NativeSelect>
        </Field>
        <Field label="Orientación de la malla" htmlFor="rl-orient" hint="Hacia dónde mira la malla en el nuevo lugar">
          <NativeSelect id="rl-orient" {...form.register('new_orientation')}>
            <option value="">Conservar la actual</option>
            {ORIENTATIONS.map((o) => (
              <option key={o} value={o}>
                {o}
              </option>
            ))}
          </NativeSelect>
        </Field>
      </div>
      <Field label="Trabajo realizado" htmlFor="rl-notes" error={errors.work_notes?.message}>
        <Textarea id="rl-notes" rows={3} placeholder="Desmontaje, traslado, anclaje de postes, tensado de la malla y prueba de la estación." {...form.register('work_notes')} />
      </Field>
      <p className="text-muted-foreground text-xs">
        Al finalizar, el atrapanieblas y sus estaciones IoT pasan a la nueva ubicación (se conserva el historial).
      </p>
      <ErrorAlert error={finish.error} />
      <div>
        <Button type="submit" disabled={finish.isPending}>
          <ClipboardCheck /> Finalizar reubicación
        </Button>
      </div>
    </form>
  )
}

const rejectSchema = z.object({
  reason: z.string().trim().min(10, 'Explique el motivo con al menos 10 caracteres').max(1000, 'Máximo 1000 caracteres'),
})

function RejectForm({ relocation, onDone }: { relocation: Relocation; onDone: (r: Relocation) => void }) {
  const form = useForm<z.infer<typeof rejectSchema>>({ resolver: zodResolver(rejectSchema), defaultValues: { reason: '' } })
  const reject = useMutation({
    mutationFn: async (v: z.infer<typeof rejectSchema>) => (await api.post<Relocation>(`/relocations/${relocation.id}/reject`, v)).data,
    onSuccess: onDone,
  })
  return (
    <form onSubmit={form.handleSubmit((v) => reject.mutate(v))} className="grid gap-3" noValidate>
      <Field label="Motivo del rechazo" htmlFor="rl-reject" error={form.formState.errors.reason?.message}>
        <Textarea id="rl-reject" rows={2} placeholder="Ej.: no hay otro lugar con suficiente niebla dentro del predio." {...form.register('reason')} />
      </Field>
      <ErrorAlert error={reject.error} />
      <div>
        <Button type="submit" variant="destructive" disabled={reject.isPending}>
          <Ban /> Rechazar solicitud
        </Button>
      </div>
    </form>
  )
}

function Timeline({ r }: { r: Relocation }) {
  const who = r.assignee?.full_name
  const steps: { status: RelocationStatus; at: string | null; text: string }[] = [
    { status: 'pendiente', at: r.created_at, text: `Solicitud de ${r.requester.full_name}` },
    ...(r.status === 'rechazado'
      ? [{ status: 'rechazado' as const, at: r.finished_at, text: `Rechazada por ${who}` }]
      : [
          { status: 'aceptado' as const, at: r.accepted_at, text: `Aceptada por ${who}` },
          { status: 'en_progreso' as const, at: r.started_at, text: 'Traslado iniciado' },
          { status: 'finalizado' as const, at: r.finished_at, text: 'Atrapanieblas reubicado' },
        ]),
  ]
  return (
    <ol className="grid gap-3" aria-label="Seguimiento de la solicitud">
      {steps.map((s) => {
        const { icon: Icon } = STATUS_STYLE[s.status]
        return (
          <li key={s.status} className={cn('flex items-start gap-3 text-sm', !s.at && 'text-muted-foreground')}>
            <span className={cn('grid size-7 shrink-0 place-items-center rounded-full border', s.at ? 'bg-emphasis text-emphasis-foreground border-emphasis' : 'bg-muted')}>
              <Icon className="size-3.5" aria-hidden />
            </span>
            <span className="pt-0.5">
              <span className="font-medium">{RELOCATION_STATUS_LABELS[s.status]}</span>
              <span className="text-muted-foreground block text-xs">{s.at ? `${s.text} · ${formatDateTime(s.at)}` : 'Pendiente'}</span>
            </span>
          </li>
        )
      })}
    </ol>
  )
}

function RelocationDetail({ id, onClose }: { id: number; onClose: () => void }) {
  const qc = useQueryClient()
  const me = useMe()
  const can = useHasPermission()
  const [panel, setPanel] = useState<'finish' | 'reject' | null>(null)
  const detail = useQuery({
    queryKey: ['relocations', 'detail', id],
    queryFn: async () => (await api.get<Relocation>(`/relocations/${id}`)).data,
  })
  const updated = (r: Relocation) => {
    qc.setQueryData(['relocations', 'detail', id], r)
    qc.invalidateQueries({ queryKey: ['relocations'] })
    qc.invalidateQueries({ queryKey: ['fog-collectors'] })
    setPanel(null)
  }
  const action = useMutation({
    mutationFn: async (step: 'accept' | 'start') => (await api.post<Relocation>(`/relocations/${id}/${step}`)).data,
    onSuccess: updated,
  })
  const r = detail.data
  const step = r && relocationNextStep(r, { id: me.data?.id, canAttend: can('reubicaciones.atender') })
  // Se rechaza antes de iniciar el traslado: al revisarla (pendiente) o el asignado, ya aceptada.
  const canReject = Boolean(step?.yourTurn && (step.action === 'aceptar' || step.action === 'iniciar'))

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[92dvh] overflow-y-auto sm:max-w-2xl">
        {!r ? (
          <>
            <DialogTitle className="sr-only">Solicitud #{id}</DialogTitle>
            {detail.error ? <ErrorAlert error={detail.error} /> : <Loading />}
          </>
        ) : (
          <>
            <DialogHeader>
              <div className="flex flex-wrap items-center gap-2 pr-8">
                <StatusBadge status={r.status} />
                <span className="text-muted-foreground text-xs">Solicitud #{r.id}</span>
              </div>
              <DialogTitle className="text-lg">
                Reubicar {r.fog_collector.name} ({r.fog_collector.code})
              </DialogTitle>
              <DialogDescription>
                {REASON_LABELS[r.reason]} · solicitada por {r.requester.full_name} el {formatDateTime(r.created_at)}
              </DialogDescription>
            </DialogHeader>
            {step && (
              <NextStepCard
                yourTurn={step.yourTurn}
                title={step.title}
                actions={
                  step.yourTurn &&
                  panel === null && (
                    <>
                      {step.action === 'aceptar' && (
                        <Button onClick={() => action.mutate('accept')} disabled={action.isPending}>
                          <UserCheck /> Aceptar solicitud
                        </Button>
                      )}
                      {step.action === 'iniciar' && (
                        <Button onClick={() => action.mutate('start')} disabled={action.isPending}>
                          <Play /> Iniciar traslado
                        </Button>
                      )}
                      {step.action === 'finalizar' && (
                        <Button onClick={() => setPanel('finish')}>
                          <ClipboardCheck /> Registrar nueva ubicación y finalizar
                        </Button>
                      )}
                      {canReject && (
                        <Button variant="outline" onClick={() => setPanel('reject')}>
                          <Ban /> Rechazar
                        </Button>
                      )}
                    </>
                  )
                }
              >
                {step.text}
                <ErrorAlert error={action.error} />
              </NextStepCard>
            )}
            {panel && step?.yourTurn && (
              <div className="rounded-xl border p-4">
                <div className="mb-3 flex items-center justify-between gap-2">
                  <span className="font-medium">{panel === 'finish' ? 'Finalizar reubicación' : 'Rechazar solicitud'}</span>
                  <Button variant="ghost" size="sm" onClick={() => setPanel(null)}>
                    Cancelar
                  </Button>
                </div>
                {panel === 'finish' ? <FinishForm relocation={r} onDone={updated} /> : <RejectForm relocation={r} onDone={updated} />}
              </div>
            )}
            <p className="text-sm whitespace-pre-line">{r.description}</p>
            <div className="bg-muted/50 flex flex-wrap items-center gap-2 rounded-xl border p-3 text-sm">
              <MapPin className="size-4" aria-hidden />
              <span>{r.origin_location?.name ?? 'Sin ubicación registrada'}</span>
              <ArrowRight className="size-4" aria-label="hacia" />
              <span className="font-medium">{destinationText(r)}</span>
              {r.new_orientation && <span className="text-muted-foreground">· orientación {r.previous_orientation ?? '—'} → {r.new_orientation}</span>}
            </div>
            <div className="rounded-xl border p-4">
              <Timeline r={r} />
            </div>
            {r.work_notes && (
              <div className="grid gap-1 rounded-xl border p-4 text-sm">
                <div className="font-medium">Trabajo realizado</div>
                <p className="whitespace-pre-line">{r.work_notes}</p>
              </div>
            )}
            {r.rejection_reason && (
              <Notice tone="warning" title="Motivo del rechazo">
                {r.rejection_reason}
              </Notice>
            )}

          </>
        )}
      </DialogContent>
    </Dialog>
  )
}

// --- Lista ---------------------------------------------------------------------------

function Summary({ summary, attend }: { summary: RelocationSummary; attend: boolean }) {
  if (attend) {
    return (
      <div className="mb-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard color="rose" label="Solicitudes por atender" value={summary.open ?? 0} icon={Inbox} tone={summary.open ? 'warning' : undefined} />
        <StatCard color="peach" label="Mis traslados en curso" value={summary.assigned_active ?? 0} icon={Truck} />
      </div>
    )
  }
  const counts = summary.all ?? summary.mine
  if (!counts) return null
  return (
    <div className="mb-5 grid grid-cols-2 gap-3 lg:grid-cols-5">
      {RELOCATION_STATUS_ORDER.map((s) => (
        <StatCard key={s} color={STATUS_STYLE[s].color} label={RELOCATION_STATUS_LABELS[s]} value={counts[s] ?? 0} />
      ))}
    </div>
  )
}

export function RelocationsPage() {
  const can = useHasPermission()
  const me = useMe()
  const viewer: Viewer = { id: me.data?.id, canAttend: can('reubicaciones.atender') }
  const [params, setParams] = useSearchParams()
  const tabs = TABS.filter((t) => can(t.permission))
  const preselected = params.get('nuevo') ?? ''
  const [scope, setScope] = useState<Scope>(preselected ? 'mine' : (tabs[0]?.scope ?? 'mine'))
  const [status, setStatus] = useState('')
  const [offset, setOffset] = useState(0)
  const [showForm, setShowForm] = useState(Boolean(preselected) && can('reubicaciones.solicitar'))
  const [sent, setSent] = useState(false)
  const summary = useQuery({
    queryKey: ['relocations', 'summary'],
    queryFn: async () => (await api.get<RelocationSummary>('/relocations/summary')).data,
  })
  // «Por atender» siempre muestra pendientes: el filtro de estado no aplica.
  const statusFilter = scope === 'open' ? '' : status
  const list = useQuery({
    queryKey: ['relocations', 'list', scope, statusFilter, offset],
    queryFn: async () =>
      (await api.get<Page<Relocation>>('/relocations', { params: { scope, status: statusFilter || undefined, offset, limit: LIMIT } })).data,
    refetchInterval: 60_000,
  })
  const selected = Number(params.get('solicitud')) || null

  return (
    <>
      <PageHeader
        eyebrow="Operaciones"
        title="Reubicación de atrapanieblas"
        description={
          can('reubicaciones.atender')
            ? 'Acepte las solicitudes, realice el traslado y registre la nueva ubicación del atrapanieblas.'
            : 'Solicite mover un atrapanieblas cuando el espacio donde está ya no es adecuado y siga su atención.'
        }
        actions={
          can('reubicaciones.solicitar') && (
            <Button
              onClick={() => {
                setShowForm(!showForm)
                setSent(false)
              }}
            >
              <Plus /> Nueva solicitud
            </Button>
          )
        }
      />
      {sent && (
        <Notice tone="success" title="Solicitud enviada" className="mb-4">
          El personal de mantenimiento recibió un aviso. Puede seguir su estado en «Mis solicitudes».
        </Notice>
      )}
      {showForm && (
        <Card className="mb-5">
          <CardContent>
            <RequestForm
              initialCollector={preselected}
              onDone={() => {
                setShowForm(false)
                setSent(true)
                setScope('mine')
                setOffset(0)
                setParams({})
              }}
            />
          </CardContent>
        </Card>
      )}

      {summary.data && <Summary summary={summary.data} attend={can('reubicaciones.atender')} />}

      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="bg-muted inline-flex flex-wrap rounded-xl border p-1" role="tablist" aria-label="Vistas de solicitudes">
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
            </button>
          ))}
        </div>
        {scope !== 'open' && (
          <NativeSelect
            aria-label="Filtrar por estado"
            className="w-48"
            value={status}
            onChange={(e) => {
              setStatus(e.target.value)
              setOffset(0)
            }}
          >
            <option value="">Todos los estados</option>
            {RELOCATION_STATUS_ORDER.map((s) => (
              <option key={s} value={s}>
                {RELOCATION_STATUS_LABELS[s]}
              </option>
            ))}
          </NativeSelect>
        )}
      </div>

      <ErrorAlert error={list.error} />
      {list.isLoading ? (
        <Loading />
      ) : (
        <Card>
          <CardContent>
            {list.data?.items.length === 0 ? (
              <EmptyState icon={Inbox} title={scope === 'open' ? 'No hay solicitudes por atender' : 'No hay solicitudes'} />
            ) : (
              <ul className="divide-y">
                {list.data?.items.map((r) => (
                  <li key={r.id}>
                    <button
                      type="button"
                      onClick={() => setParams({ solicitud: String(r.id) })}
                      className="hover:bg-muted/60 focus-visible:bg-muted/60 grid w-full gap-1.5 rounded-lg px-3 py-3 text-left sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center sm:gap-4"
                    >
                      <span className="min-w-0">
                        <span className="block truncate font-medium">
                          {r.fog_collector.name} · {r.origin_location?.name ?? 'sin ubicación'} → {destinationText(r)}
                        </span>
                        <span className="text-muted-foreground block truncate text-xs">
                          #{r.id} · {REASON_LABELS[r.reason]} · {r.requester.full_name} · {formatDateTime(r.created_at)}
                        </span>
                      </span>
                      <span className="flex flex-wrap items-center gap-2 sm:justify-end">
                        {(() => {
                          const next = relocationNextStep(r, viewer)
                          return next?.yourTurn ? (
                            <YourTurnBadge action={ACTION_LABELS[next.action]} />
                          ) : (
                            <span className="text-muted-foreground text-xs">{r.assignee ? r.assignee.full_name : 'Sin asignar'}</span>
                          )
                        })()}
                        <StatusBadge status={r.status} />
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
            {list.data && <Pagination offset={offset} limit={LIMIT} total={list.data.total} onChange={setOffset} />}
          </CardContent>
        </Card>
      )}
      {selected && <RelocationDetail key={selected} id={selected} onClose={() => setParams({})} />}
    </>
  )
}
