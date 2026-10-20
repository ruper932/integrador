import { CheckCircle2, CircleDot, Flag, UserCheck, Wrench, type LucideIcon } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { PRIORITY_LABELS, STATUS_LABELS } from '@/features/incidents/labels'
import { formatDateTime } from '@/lib/format'
import { cn } from '@/lib/utils'
import type { Incident, IncidentPriority, IncidentStatus } from '@/types/api'

const STATUS_STYLE: Record<IncidentStatus, { tone: 'info' | 'secondary' | 'warning' | 'success'; icon: LucideIcon }> = {
  abierto: { tone: 'info', icon: CircleDot },
  aceptado: { tone: 'secondary', icon: UserCheck },
  en_progreso: { tone: 'warning', icon: Wrench },
  finalizado: { tone: 'success', icon: CheckCircle2 },
}

export function IncidentStatusBadge({ status }: { status: IncidentStatus }) {
  const { tone, icon: Icon } = STATUS_STYLE[status]
  return (
    <Badge variant={tone}>
      <Icon aria-hidden />
      {STATUS_LABELS[status]}
    </Badge>
  )
}

export function PriorityBadge({ priority }: { priority: IncidentPriority }) {
  return (
    <Badge variant={priority === 'alta' ? 'danger' : 'outline'}>
      <Flag aria-hidden />
      Prioridad {PRIORITY_LABELS[priority].toLowerCase()}
    </Badge>
  )
}

/** Etapas del reporte con su fecha y responsable; las etapas pendientes se muestran atenuadas. */
export function IncidentTimeline({ incident }: { incident: Incident }) {
  const m = incident.maintenance
  const assignee = incident.assignee?.full_name
  const steps: { status: IncidentStatus; at: string | null | undefined; who?: string; text: string }[] = [
    { status: 'abierto', at: incident.created_at, who: incident.reporter.full_name, text: 'Reporte enviado' },
    { status: 'aceptado', at: m?.accepted_at, who: assignee, text: 'Aceptado por el personal de mantenimiento' },
    { status: 'en_progreso', at: m?.started_at, who: assignee, text: 'Mantenimiento en progreso' },
    { status: 'finalizado', at: m?.finished_at, who: assignee, text: 'Mantenimiento finalizado' },
  ]
  return (
    <ol className="grid gap-0" aria-label="Seguimiento del reporte">
      {steps.map((step, index) => {
        const done = Boolean(step.at)
        const { icon: Icon } = STATUS_STYLE[step.status]
        return (
          <li key={step.status} className="relative flex gap-3 pb-4 last:pb-0">
            {index < steps.length - 1 && (
              <span
                aria-hidden
                className={cn('absolute top-8 bottom-0 left-[15px] w-0.5', done && steps[index + 1]?.at ? 'bg-primary' : 'bg-border')}
              />
            )}
            <span
              className={cn(
                'relative grid size-8 shrink-0 place-items-center rounded-full border',
                done ? 'bg-primary text-primary-foreground border-primary' : 'bg-muted text-muted-foreground',
              )}
            >
              <Icon className="size-4" aria-hidden />
            </span>
            <div className={cn('min-w-0 pt-1 text-sm', !done && 'text-muted-foreground')}>
              <div className="font-medium">
                {STATUS_LABELS[step.status]}
                <span className="sr-only">{done ? ' (completado)' : ' (pendiente)'}</span>
              </div>
              <div className="text-muted-foreground text-xs">
                {done ? (
                  <>
                    {step.text}
                    {step.who && ` · ${step.who}`} · {formatDateTime(step.at)}
                  </>
                ) : (
                  'Pendiente'
                )}
              </div>
            </div>
          </li>
        )
      })}
    </ol>
  )
}
