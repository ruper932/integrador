import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, Plus } from 'lucide-react'
import { useState } from 'react'

import { ErrorAlert, Field, Loading, PageHeader, SecretNotice, StatusBadge } from '@/components/common'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { UserForm } from '@/features/admin/UserForm'
import { useMe } from '@/features/auth/useAuth'
import { api } from '@/lib/api'
import { ExportReportButton } from '@/features/reports/ExportReportButton'
import { formatDateTime } from '@/lib/format'
import type { Page, User, UserWithTemporaryPassword } from '@/types/api'

function ciText(user: User): string {
  const p = user.profile
  if (!p?.ci_number) return '—'
  return [p.ci_number + (p.ci_complement ? `-${p.ci_complement}` : ''), p.ci_issued_in].filter(Boolean).join(' ')
}

export function UsersPage() {
  const qc = useQueryClient()
  const me = useMe()
  const [q, setQ] = useState('')
  const [mode, setMode] = useState<{ kind: 'create' } | { kind: 'edit'; user: User } | null>(null)
  const [secret, setSecret] = useState<UserWithTemporaryPassword | null>(null)
  const users = useQuery({
    queryKey: ['users', q],
    queryFn: async () => (await api.get<Page<User>>('/users', { params: { limit: 200, q: q || undefined } })).data,
  })
  const toggle = useMutation({
    mutationFn: ({ id, is_active }: { id: number; is_active: boolean }) => api.put(`/users/${id}`, { is_active }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['users'] }),
  })
  const reset = useMutation({
    mutationFn: async (id: number) => (await api.post<UserWithTemporaryPassword>(`/users/${id}/reset-password`, {})).data,
    onSuccess: setSecret,
  })

  return (
    <>
      <PageHeader
        eyebrow="Administración"
        title="Usuarios y permisos"
        description="Las cuentas no se eliminan: se desactivan para conservar la trazabilidad."
        actions={
          <>
            <ExportReportButton kinds={['usuarios']} />
            <Button onClick={() => setMode({ kind: 'create' })}>
              <Plus /> Usuario
            </Button>
          </>
        }
      />
      {secret?.temporary_password && (
        <div className="mb-4">
          <SecretNotice title={`Contraseña temporal de ${secret.user.username}`} secret={secret.temporary_password}>
            Entréguela personalmente al usuario.
          </SecretNotice>
        </div>
      )}
      {mode && (
        <Card className="mb-4">
          <CardHeader>
            <CardTitle>{mode.kind === 'create' ? 'Nuevo usuario' : `Editar ${mode.user.full_name}`}</CardTitle>
          </CardHeader>
          <CardContent>
            <UserForm
              key={mode.kind === 'edit' ? mode.user.id : 'new'}
              user={mode.kind === 'edit' ? mode.user : undefined}
              onDone={(result) => {
                if (result) setSecret(result)
                setMode(null)
              }}
            />
          </CardContent>
        </Card>
      )}
      <div className="mb-4 w-full max-w-sm">
        <Field label="Buscar" htmlFor="u-q">
          <Input id="u-q" placeholder="Nombre, apellido, CI o usuario" value={q} onChange={(e) => setQ(e.target.value)} />
        </Field>
      </div>
      <ErrorAlert error={users.error ?? toggle.error ?? reset.error} />
      {users.isLoading ? (
        <Loading />
      ) : (
        <Card>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Nombre</TableHead>
                  <TableHead>CI</TableHead>
                  <TableHead>Celular</TableHead>
                  <TableHead>Cargo / formación</TableHead>
                  <TableHead>Roles</TableHead>
                  <TableHead>Estado</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {users.data?.items.map((u) => (
                  <TableRow key={u.id}>
                    <TableCell>
                      <div className="font-medium">{u.full_name}</div>
                      <div className="text-muted-foreground text-xs">{u.username}</div>
                      {!u.profile_complete && (
                        <Badge variant="warning" className="mt-1">
                          <AlertTriangle /> Perfil incompleto
                        </Badge>
                      )}
                    </TableCell>
                    <TableCell className="tabular-nums">{ciText(u)}</TableCell>
                    <TableCell className="tabular-nums">{u.profile?.mobile_phone ?? '—'}</TableCell>
                    <TableCell
                      className="max-w-52 whitespace-normal"
                      title={u.degrees.map((d) => `${d.title} — ${d.institution.name}`).join('\n')}
                    >
                      <div>{u.profile?.position?.name ?? '—'}</div>
                      {u.degrees[0] && (
                        <div className="text-muted-foreground line-clamp-2 text-xs">
                          {u.degrees[0].academic_level.name} — {u.degrees[0].institution.acronym ?? u.degrees[0].institution.name}
                          {u.degrees.length > 1 && ` (+${u.degrees.length - 1})`}
                        </div>
                      )}
                    </TableCell>
                    <TableCell className="whitespace-normal">{u.roles.map((r) => r.name.replaceAll('_', ' ')).join(', ')}</TableCell>
                    <TableCell>
                      <StatusBadge value={u.is_active ? 'activo' : 'inactivo'} />
                      {u.must_change_password && <div className="text-muted-foreground text-xs">clave temporal</div>}
                      <div className="text-muted-foreground text-xs">Último acceso: {formatDateTime(u.last_login_at)}</div>
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-col items-end gap-1">
                      <Button size="sm" variant="outline" onClick={() => setMode({ kind: 'edit', user: u })}>
                        Editar
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => {
                          if (confirm(`¿Restablecer la contraseña de ${u.username}? Se cerrarán sus sesiones.`)) reset.mutate(u.id)
                        }}
                      >
                        Restablecer clave
                      </Button>
                      {u.id !== me.data?.id && (
                        <Button size="sm" variant="ghost" onClick={() => toggle.mutate({ id: u.id, is_active: !u.is_active })}>
                          {u.is_active ? 'Desactivar' : 'Reactivar'}
                        </Button>
                      )}
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </>
  )
}
