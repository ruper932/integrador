import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { ErrorAlert, Field, Loading, NativeSelect, PageHeader, SecretNotice, StatusBadge } from '@/components/common'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { api } from '@/lib/api'
import { formatDateTime } from '@/lib/format'
import type { Page, RecoveryRequest, RecoveryStatus } from '@/types/api'

function ResolvePanel({ request, onDone }: { request: RecoveryRequest; onDone: (temporary: string | null) => void }) {
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
    onSuccess: (r) => {
      refresh()
      onDone(r.temporary_password)
    },
  })
  const reject = useMutation({
    mutationFn: () => api.post(`/admin/recovery-requests/${request.id}/reject`, { reason: note }),
    onSuccess: () => {
      refresh()
      onDone(null)
    },
  })

  return (
    <div className="grid gap-3 border-t pt-3">
      <label className="flex items-center gap-2 text-sm">
        <Checkbox checked={verified} onCheckedChange={(v) => setVerified(v === true)} />
        Verifiqué presencialmente la identidad del solicitante
      </label>
      <Field label="Cómo se verificó / motivo del rechazo" htmlFor={`note-${request.id}`}>
        <Input id={`note-${request.id}`} value={note} onChange={(e) => setNote(e.target.value)} placeholder="Ej.: presentó carnet de identidad" />
      </Field>
      <ErrorAlert error={approve.error ?? reject.error} />
      <div className="flex gap-2">
        <Button disabled={!verified || note.trim().length < 3 || approve.isPending || !request.user_id} onClick={() => approve.mutate()}>
          Aprobar y generar contraseña temporal
        </Button>
        <Button variant="outline" disabled={note.trim().length < 3 || reject.isPending} onClick={() => reject.mutate()}>
          Rechazar
        </Button>
      </div>
    </div>
  )
}

export function RecoveryRequestsPage() {
  const [status, setStatus] = useState<RecoveryStatus | ''>('pendiente')
  const [openId, setOpenId] = useState<number | null>(null)
  const [secret, setSecret] = useState<{ username: string; password: string } | null>(null)
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
      {secret && (
        <div className="mb-4">
          <SecretNotice title={`Contraseña temporal de ${secret.username}`} secret={secret.password}>
            Entréguela personalmente; deberá cambiarla al iniciar sesión.
          </SecretNotice>
        </div>
      )}
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
              {r.status === 'pendiente' &&
                (openId === r.id ? (
                  <ResolvePanel
                    request={r}
                    onDone={(temporary) => {
                      setOpenId(null)
                      if (temporary) setSecret({ username: r.username_requested, password: temporary })
                    }}
                  />
                ) : (
                  <div>
                    <Button size="sm" variant="outline" onClick={() => setOpenId(r.id)}>
                      Resolver
                    </Button>
                  </div>
                ))}
            </CardContent>
          </Card>
        ))}
      </div>
    </>
  )
}
