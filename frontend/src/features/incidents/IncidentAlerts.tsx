import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Eye, TriangleAlert } from 'lucide-react'
import { useEffect, useState } from 'react'

import { ErrorAlert, Notice } from '@/components/common'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { ALERTS_KEY, useIncidentAlerts } from '@/features/incidents/api'
import { AutoBadge, PriorityBadge, reporterName } from '@/features/incidents/IncidentBits'
import { api } from '@/lib/api'
import { formatDateTime } from '@/lib/format'
import type { IncidentAlerts } from '@/types/api'

/** Una alerta de prioridad alta sin revisar bloquea toda la interfaz hasta que el usuario la revisa. */
export function HighAlertGate({ enabled, onReviewed }: { enabled: boolean; onReviewed: (id: number) => void }) {
  const qc = useQueryClient()
  const alerts = useIncidentAlerts(enabled)
  const review = useMutation({
    mutationFn: (id: number) => api.post(`/incidents/${id}/review`),
    onSuccess: (_, id) => {
      // Se quita de inmediato para no tapar el reporte que se abre a continuación.
      qc.setQueryData<IncidentAlerts>(ALERTS_KEY, (d) => d && { ...d, blocking: d.blocking.filter((a) => a.id !== id) })
      qc.invalidateQueries({ queryKey: ['incidents'] })
      qc.invalidateQueries({ queryKey: ['notifications'] })
      onReviewed(id)
    },
  })

  const pending = (enabled && alerts.data?.blocking) || []
  const alert = pending[0]
  if (!alert) return null
  return (
    <Dialog open>
      <DialogContent
        role="alertdialog"
        showCloseButton={false}
        onEscapeKeyDown={(e) => e.preventDefault()}
        onInteractOutside={(e) => e.preventDefault()}
        className="border-danger border-2 sm:max-w-lg"
      >
        <DialogHeader>
          <div className="flex flex-wrap items-center gap-2">
            <PriorityBadge priority="alta" />
            {alert.source === 'sistema' && <AutoBadge />}
            {pending.length > 1 && <span className="text-muted-foreground text-xs">1 de {pending.length} alertas</span>}
          </div>
          <DialogTitle className="flex items-center gap-2 text-lg">
            <TriangleAlert className="text-danger size-5 shrink-0" aria-hidden />
            Alerta de prioridad alta
          </DialogTitle>
          <DialogDescription>Debe revisar esta alerta para continuar usando el sistema.</DialogDescription>
        </DialogHeader>
        <div className="grid gap-1.5 rounded-xl border p-4">
          <div className="font-medium">{alert.title}</div>
          <p className="text-sm whitespace-pre-line">{alert.description}</p>
          <div className="text-muted-foreground text-xs">
            #{alert.id} · {reporterName(alert)} · {formatDateTime(alert.created_at)}
            {alert.device_name && ` · ${alert.device_name}`}
            {alert.location_reference && ` · ${alert.location_reference}`}
          </div>
        </div>
        <ErrorAlert error={review.error} />
        <DialogFooter>
          <Button onClick={() => review.mutate(alert.id)} disabled={review.isPending} autoFocus>
            <Eye /> Revisar alerta
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

const SNOOZE_MINUTES = 15

/** Recordatorio de las alertas de prioridad media sin atender; al posponerlo vuelve a aparecer. */
export function MediumAlertReminders({ onOpen }: { onOpen: (id: number) => void }) {
  const alerts = useIncidentAlerts()
  const [snoozed, setSnoozed] = useState(false)
  useEffect(() => {
    if (!snoozed) return
    const timer = setTimeout(() => setSnoozed(false), SNOOZE_MINUTES * 60_000)
    return () => clearTimeout(timer)
  }, [snoozed])

  const reminders = alerts.data?.reminders ?? []
  if (snoozed || reminders.length === 0) return null
  return (
    <Notice
      tone="warning"
      className="mb-4"
      title={`Recordatorio: ${reminders.length === 1 ? 'una alerta' : `${reminders.length} alertas`} de prioridad media sin atender`}
      action={
        <Button variant="outline" size="sm" onClick={() => setSnoozed(true)}>
          Recordar en {SNOOZE_MINUTES} min
        </Button>
      }
    >
      <ul className="mt-1 grid gap-0.5">
        {reminders.map((r) => (
          <li key={r.id}>
            <button type="button" className="text-left font-medium underline-offset-2 hover:underline" onClick={() => onOpen(r.id)}>
              #{r.id} {r.title}
            </button>{' '}
            · desde {formatDateTime(r.created_at)}
          </li>
        ))}
      </ul>
    </Notice>
  )
}
