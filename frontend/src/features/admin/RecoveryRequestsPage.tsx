import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Ban, KeyRound } from 'lucide-react'
import { useState } from 'react'

import { ErrorAlert, Field, Loading, NativeSelect, PageHeader, SecretNotice, StatusBadge } from '@/components/common'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { api } from '@/lib/api'
import { formatDateTime } from '@/lib/format'
import type { Page, RecoveryRequest, RecoveryStatus } from '@/types/api'

/** Resolver una solicitud en un modal: verificar identidad, aprobar (contraseña temporal) o rechazar. */
function ResolveDialog({ request, onClose }: { request: RecoveryRequest; onClose: () => void }) {
  const qc = useQueryClient()
  const [verified, setVerified] = useState(false)
  const [note, setNote] = useState('')
  const refresh = () => qc.invalidateQueries({ queryKey: ['recovery-requests'] })
  const approve = useMutation({
    mutationFn: async () =>
      (
        await api.post<{ temporary_password: string | null }>(`/admin/recovery-requests/${request.id}/approve`, {
          identity_verified: verified,
          verification_note: note,
        })
      ).data,
    onSuccess: refresh,
  })
  const reject = useMutation({
    mutationFn: () => api.post(`/admin/recovery-requests/${request.id}/reject`, { reason: note }),
    onSuccess: () => {
      refresh()
      onClose()
    },
  })
  const pending = approve.isPending || reject.isPending
  const noteOk = note.trim().length >= 3
  const temporary = approve.data?.temporary_password

  return (
    <Dialog open onOpenChange={(open) => !open && !pending && onClose()}>
      <DialogContent className="sm:max-w-md" showCloseButton={!pending}>
        <DialogHeader>
          <DialogTitle>Solicitud de {request.username_requested}</DialogTitle>
          <DialogDescription>
            {request.user_id ? request.user_full_name : 'No corresponde a un usuario registrado: solo puede rechazarse.'} ·{' '}
            {formatDateTime(request.created_at)}
          </DialogDescription>
        </DialogHeader>
        {temporary ? (
          <SecretNotice title="Contraseña temporal" secret={temporary}>
            Entréguela personalmente; deberá cambiarla al iniciar sesión.
          </SecretNotice>
        ) : (
          <div className="grid gap-3">
            {request.message && <p className="text-sm">“{request.message}”</p>}
            <label className="flex items-start gap-2 text-sm">
              <Checkbox className="mt-0.5" checked={verified} onCheckedChange={(v) => setVerified(v === true)} />
              Verifiqué presencialmente la identidad del solicitante
            </label>
            <Field
              label="Cómo se verificó o motivo del rechazo"
              htmlFor={`note-${request.id}`}
              hint="Obligatorio para aprobar o rechazar (mínimo 3 caracteres)."
            >
              <Input
                id={`note-${request.id}`}
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="Ej.: presentó su carnet de identidad"
              />
            </Field>
            <ErrorAlert error={approve.error ?? reject.error} />
          </div>
        )}
        <DialogFooter>
          {temporary ? (
            <Button onClick={onClose}>Listo</Button>
          ) : (
            <>
              <Button variant="outline" onClick={onClose} disabled={pending}>
                Cancelar
              </Button>
              <Button variant="destructive" disabled={!noteOk || pending} onClick={() => reject.mutate()}>
                <Ban /> {reject.isPending ? 'Rechazando…' : 'Rechazar'}
              </Button>
              <Button disabled={!verified || !noteOk || pending || !request.user_id} onClick={() => approve.mutate()}>
                <KeyRound /> {approve.isPending ? 'Generando…' : 'Aprobar y generar contraseña'}
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export function RecoveryRequestsPage() {
  const [status, setStatus] = useState<RecoveryStatus | ''>('pendiente')
  // Se guarda la solicitud (no solo su id): al aprobarla sale de «Pendientes» y el modal debe seguir abierto.
  const [resolving, setResolving] = useState<RecoveryRequest | null>(null)
  const requests = useQuery({
    queryKey: ['recovery-requests', status],
    queryFn: async () =>
      (await api.get<Page<RecoveryRequest>>('/admin/recovery-requests', { params: { status: status || undefined } })).data,
  })

  return (
    <>
      <PageHeader
        eyebrow="Administración"
        title="Recuperación de cuentas"
        description="Apruebe una solicitud solo después de verificar en persona la identidad del solicitante."
      />
      <div className="mb-4 w-48">
        <Field label="Estado" htmlFor="rr-status">
          <NativeSelect id="rr-status" value={status} onChange={(e) => setStatus(e.target.value as RecoveryStatus | '')}>
            <option value="pendiente">Pendientes</option>
            <option value="aprobada">Aprobadas</option>
            <option value="rechazada">Rechazadas</option>
            <option value="">Todas</option>
          </NativeSelect>
        </Field>
      </div>
      <ErrorAlert error={requests.error} />
      {requests.isLoading && <Loading />}
      <div className="grid gap-3">
        {requests.data?.items.length === 0 && <p className="text-muted-foreground text-sm">No hay solicitudes.</p>}
        {requests.data?.items.map((r) => (
          <Card key={r.id}>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                {r.username_requested} <StatusBadge value={r.status} />
              </CardTitle>
              <CardDescription>
                {r.user_id ? r.user_full_name : 'No corresponde a un usuario registrado'} · {formatDateTime(r.created_at)} · IP{' '}
                {r.requester_ip ?? '—'}
              </CardDescription>
            </CardHeader>
            <CardContent className="grid gap-2 text-sm">
              {r.message && <p>“{r.message}”</p>}
              {r.resolution_note && <p className="text-muted-foreground">Resolución: {r.resolution_note}</p>}
              {r.status === 'pendiente' && (
                <div>
                  <Button size="sm" variant="outline" onClick={() => setResolving(r)}>
                    Resolver
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
      {resolving && <ResolveDialog request={resolving} onClose={() => setResolving(null)} />}
    </>
  )
}
