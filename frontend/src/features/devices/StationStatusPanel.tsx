import { Cpu, Radio } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'

import { EmptyState, ErrorAlert, Loading } from '@/components/common'
import { Badge } from '@/components/ui/badge'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { BADGE, connection, useStationSummary } from '@/features/devices/api'
import { relativeTime } from '@/lib/format'
import { cn } from '@/lib/utils'

/**
 * Indicador del menú lateral con las estaciones en línea / sin conexión y un panel con el detalle.
 * Comparte la consulta del resumen general (misma clave), así no se pide dos veces.
 */
export function StationStatusPanel({ collapsed, canManage }: { collapsed: boolean; canManage: boolean }) {
  const [open, setOpen] = useState(false)
  const summary = useStationSummary()
  const devices = summary.data?.devices ?? []
  const online = devices.filter((d) => connection(d) === 'en_linea').length
  const offline = devices.filter((d) => connection(d) === 'sin_conexion').length
  const label = summary.data
    ? `Estaciones: ${online} en línea, ${offline} sin conexión`
    : 'Estado de las estaciones'

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        title={collapsed ? label : undefined}
        aria-label={collapsed ? label : undefined}
        className={cn(
          'hover:shadow-[var(--hover-shadow)] mt-2 flex w-full items-center rounded-xl text-left text-xs',
          collapsed ? 'relative justify-center py-2' : 'gap-2 border p-3',
        )}
      >
        <Radio className="size-4 shrink-0" aria-hidden />
        {collapsed ? (
          offline > 0 && <span className="bg-danger absolute top-1.5 right-6 size-2 rounded-full" aria-hidden />
        ) : (
          <span className="min-w-0">
            <span className="block font-medium">Estaciones</span>
            <span className="text-muted-foreground block">
              {summary.data ? (
                <>
                  <span className="text-success">{online} en línea</span> ·{' '}
                  <span className={cn(offline > 0 && 'text-danger')}>{offline} sin conexión</span>
                </>
              ) : (
                'Consultando…'
              )}
            </span>
          </span>
        )}
      </button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-h-[92dvh] overflow-y-auto sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Estado de las estaciones</DialogTitle>
            <DialogDescription>
              {summary.data
                ? `${online} en línea · ${offline} sin conexión. Una estación pasa a «sin conexión» si no envía datos en ${summary.data.stale_threshold_minutes} min. Se actualiza cada 30 s.`
                : 'Comunicación de las estaciones ESP32 con el servidor local.'}
            </DialogDescription>
          </DialogHeader>
          <ErrorAlert error={summary.error} />
          {summary.isLoading && <Loading />}
          {summary.data &&
            (devices.length === 0 ? (
              <EmptyState icon={Radio} title="Sin estaciones registradas" />
            ) : (
              <ul className="divide-y">
                {devices.map((d) => {
                  const state = BADGE[connection(d)]
                  return (
                    <li key={d.id} className="flex items-center gap-3 py-3">
                      <Cpu className="text-muted-foreground size-4 shrink-0" aria-hidden />
                      <div className="min-w-0 flex-1">
                        <div className="truncate text-sm font-medium">{d.name}</div>
                        <div className="text-muted-foreground truncate text-xs">
                          {d.code} ·{' '}
                          {d.last_seen_at ? `último envío ${relativeTime(d.last_seen_at)}` : 'nunca se comunicó'}
                        </div>
                      </div>
                      <Badge variant={state.variant}>{state.label}</Badge>
                    </li>
                  )
                })}
              </ul>
            ))}
          {canManage && (
            <Link to="/dispositivos" onClick={() => setOpen(false)} className="text-sm underline underline-offset-2">
              Ver dispositivos y sensores
            </Link>
          )}
        </DialogContent>
      </Dialog>
    </>
  )
}
