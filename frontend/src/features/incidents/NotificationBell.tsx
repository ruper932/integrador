import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Bell, CheckCheck } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { api } from '@/lib/api'
import { formatDateTime } from '@/lib/format'
import { cn } from '@/lib/utils'
import type { AppNotification } from '@/types/api'

const KEY = ['notifications']

/** Avisos internos (sin servicios externos). Se consultan periódicamente al servidor local. */
export function NotificationBell({
  onOpenIncident,
  onOpenRelocation,
  side = 'bottom',
}: {
  onOpenIncident: (id: number) => void
  onOpenRelocation: (id: number) => void
  side?: 'bottom' | 'right'
}) {
  const qc = useQueryClient()
  const notifications = useQuery({
    queryKey: KEY,
    queryFn: async () => (await api.get<{ items: AppNotification[]; unread: number }>('/notifications')).data,
    refetchInterval: 30_000,
  })
  const markRead = useMutation({
    mutationFn: (id: number) => api.post(`/notifications/${id}/read`),
    onSettled: () => qc.invalidateQueries({ queryKey: KEY }),
  })
  const markAll = useMutation({
    mutationFn: () => api.post('/notifications/read-all'),
    onSettled: () => qc.invalidateQueries({ queryKey: KEY }),
  })

  const unread = notifications.data?.unread ?? 0
  const items = notifications.data?.items ?? []

  // Anuncia a los lectores de pantalla cuando llega un aviso nuevo; los reportes se actualizan.
  const previous = useRef<number | null>(null)
  const [announcement, setAnnouncement] = useState('')
  useEffect(() => {
    if (!notifications.data) return
    if (previous.current !== null && unread > previous.current) {
      setAnnouncement(`Tiene ${unread} ${unread === 1 ? 'aviso nuevo' : 'avisos nuevos'}`)
      qc.invalidateQueries({ queryKey: ['incidents'] })
    }
    previous.current = unread
  }, [notifications.data, unread, qc])

  return (
    <>
      <span className="sr-only" aria-live="polite">
        {announcement}
      </span>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="ghost"
            size="icon"
            className="relative hover:bg-transparent hover:shadow-[var(--hover-shadow)]"
            aria-label={unread ? `Avisos: ${unread} sin leer` : 'Avisos'}
            title="Avisos"
          >
            <Bell className="size-5" />
            {unread > 0 && (
              <span className="bg-attention text-attention-foreground absolute -top-2 -right-2 grid h-5.5 min-w-5.5 place-items-center rounded-full px-1.5 text-xs leading-none font-bold ring-2 ring-[var(--card)]">
                {unread > 9 ? '9+' : unread}
              </span>
            )}
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent side={side} align="start" className="w-[min(22rem,calc(100vw-2rem))]">
          <DropdownMenuLabel className="flex items-center justify-between gap-2">
            <span>Avisos</span>
            {unread > 0 && (
              <Button
                variant="ghost"
                size="sm"
                className="h-7 text-xs"
                onClick={(e) => {
                  e.preventDefault()
                  markAll.mutate()
                }}
              >
                <CheckCheck /> Marcar todo como leído
              </Button>
            )}
          </DropdownMenuLabel>
          <DropdownMenuSeparator />
          {items.length === 0 ? (
            <div className="text-muted-foreground px-2 py-6 text-center text-sm">No tiene avisos.</div>
          ) : (
            <div className="max-h-96 overflow-y-auto">
              {items.map((n) => (
                <DropdownMenuItem
                  key={n.id}
                  className="items-start gap-2.5 py-2"
                  onSelect={() => {
                    if (!n.read_at) markRead.mutate(n.id)
                    if (n.incident_report_id) onOpenIncident(n.incident_report_id)
                    else if (n.relocation_id) onOpenRelocation(n.relocation_id)
                  }}
                >
                  <span
                    aria-hidden
                    className={cn('mt-1.5 size-2 shrink-0 rounded-full', n.read_at ? 'bg-transparent' : 'bg-attention')}
                  />
                  <span className="min-w-0">
                    <span className={cn('block text-sm', !n.read_at && 'font-semibold')}>
                      {n.title}
                      {!n.read_at && <span className="sr-only"> (sin leer)</span>}
                    </span>
                    <span className="text-muted-foreground block text-xs whitespace-normal">{n.message}</span>
                    <span className="text-muted-foreground block text-xs">{formatDateTime(n.created_at)}</span>
                  </span>
                </DropdownMenuItem>
              ))}
            </div>
          )}
        </DropdownMenuContent>
      </DropdownMenu>
    </>
  )
}
