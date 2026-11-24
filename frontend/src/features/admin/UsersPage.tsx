import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, KeyRound, Plus, UserX } from 'lucide-react'
import { useState } from 'react'

import { ConfirmDialog } from '@/components/ConfirmDialog'
import { ErrorAlert, Field, Loading, PageHeader, SecretNotice, StatusBadge } from '@/components/common'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { UserForm } from '@/features/admin/UserForm'
import { useMe } from '@/features/auth/useAuth'
import { api } from '@/lib/api'
import { FilterToolbar } from '@/features/reports/FilterToolbar'
import { listParams } from '@/features/reports/params'
import type { FilterValues } from '@/features/reports/ReportFilterField'
import { formatDateTime } from '@/lib/format'
import type { Page, User, UserWithTemporaryPassword } from '@/types/api'

const LIST_FILTERS = ['role_id', 'position_id', 'is_active']

function ciText(user: User): string {
  const p = user.profile
  if (!p?.ci_number) return '—'
  return [p.ci_number + (p.ci_complement ? `-${p.ci_complement}` : ''), p.ci_issued_in].filter(Boolean).join(' ')
}

/** Restablecer la contraseña: confirma las consecuencias y muestra la temporal en el mismo modal. */
function ResetPasswordDialog({ user, onClose }: { user: User; onClose: () => void }) {
  const qc = useQueryClient()
  const reset = useMutation({
    mutationFn: async () => (await api.post<UserWithTemporaryPassword>(`/users/${user.id}/reset-password`, {})).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['users'] }),
  })
  const temporary = reset.data?.temporary_password
  return (
    <ConfirmDialog
      title={`Restablecer la contraseña de ${user.full_name}`}
      description={reset.isSuccess ? undefined : `Usuario ${user.username}.`}
      confirmLabel={
        <>
          <KeyRound /> Generar contraseña temporal
        </>
      }
      pendingLabel="Generando…"
      pending={reset.isPending}
      error={reset.error}
      onConfirm={() => reset.mutate()}
      onClose={onClose}
      done={
        temporary && (
          <SecretNotice title="Contraseña temporal" secret={temporary}>
            Entréguela personalmente; deberá cambiarla al iniciar sesión.
          </SecretNotice>
        )
      }
    >
      <ul className="text-muted-foreground grid list-disc gap-1 pl-5 text-sm">
        <li>Se cerrarán todas sus sesiones abiertas.</li>
        <li>Recibirá una contraseña temporal que deberá cambiar al ingresar.</li>
        <li>La operación queda registrada en la auditoría.</li>
      </ul>
    </ConfirmDialog>
  )
}

/** Desactivar una cuenta: no se elimina, pero deja de poder ingresar. */
function DeactivateUserDialog({ user, onClose }: { user: User; onClose: () => void }) {
  const qc = useQueryClient()
  const deactivate = useMutation({
    mutationFn: () => api.put(`/users/${user.id}`, { is_active: false }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['users'] })
      onClose()
    },
  })
  return (
    <ConfirmDialog
      title={`Desactivar a ${user.full_name}`}
      description="La cuenta no se elimina: se conserva su historial y puede reactivarse más adelante."
      confirmLabel={
        <>
          <UserX /> Desactivar cuenta
        </>
      }
      pendingLabel="Desactivando…"
      destructive
      pending={deactivate.isPending}
      error={deactivate.error}
      onConfirm={() => deactivate.mutate()}
      onClose={onClose}
    >
      <p className="text-sm">No podrá iniciar sesión y se cerrarán sus sesiones abiertas.</p>
    </ConfirmDialog>
  )
}

export function UsersPage() {
  const qc = useQueryClient()
  const me = useMe()
  const [q, setQ] = useState('')
  const [filters, setFilters] = useState<FilterValues>({})
  const [mode, setMode] = useState<{ kind: 'create' } | { kind: 'edit'; user: User } | null>(null)
  const [secret, setSecret] = useState<UserWithTemporaryPassword | null>(null)
  const [action, setAction] = useState<{ kind: 'reset' | 'deactivate'; user: User } | null>(null)
  const users = useQuery({
    queryKey: ['users', q, filters],
    queryFn: async () => {
      const params = { ...listParams(LIST_FILTERS, filters), limit: 200, q: q || undefined }
      return (await api.get<Page<User>>('/users', { params })).data
    },
  })
  // Reactivar no tiene consecuencias que confirmar; desactivar sí (ver DeactivateUserDialog).
  const reactivate = useMutation({
    mutationFn: (id: number) => api.put(`/users/${id}`, { is_active: true }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['users'] }),
  })

  return (
    <>
      <PageHeader
        eyebrow="Administración"
        title="Usuarios y permisos"
        description="Las cuentas no se eliminan: se desactivan para conservar la trazabilidad."
        actions={
          <>
            <Button onClick={() => setMode({ kind: 'create' })}>
              <Plus /> Usuario
            </Button>
          </>
        }
      />
      {secret?.temporary_password && (
        <ConfirmDialog
          title={`Cuenta creada para ${secret.user.full_name}`}
          confirmLabel="Listo"
          onConfirm={() => setSecret(null)}
          onClose={() => setSecret(null)}
          done={
            <SecretNotice title="Contraseña temporal" secret={secret.temporary_password}>
              Entréguela personalmente; deberá cambiarla al iniciar sesión.
            </SecretNotice>
          }
        />
      )}
      {action?.kind === 'reset' && <ResetPasswordDialog user={action.user} onClose={() => setAction(null)} />}
      {action?.kind === 'deactivate' && <DeactivateUserDialog user={action.user} onClose={() => setAction(null)} />}
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
      <FilterToolbar kinds={['usuarios']} keys={LIST_FILTERS} values={filters} onChange={setFilters}>
        <Field label="Buscar" htmlFor="u-q">
          <Input id="u-q" placeholder="Nombre, apellido, CI o usuario" value={q} onChange={(e) => setQ(e.target.value)} />
        </Field>
      </FilterToolbar>
      <ErrorAlert error={users.error ?? reactivate.error} />
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
                      <Button size="sm" variant="ghost" onClick={() => setAction({ kind: 'reset', user: u })}>
                        <KeyRound /> Restablecer clave
                      </Button>
                      {u.id !== me.data?.id &&
                        (u.is_active ? (
                          <Button size="sm" variant="ghost" onClick={() => setAction({ kind: 'deactivate', user: u })}>
                            <UserX /> Desactivar
                          </Button>
                        ) : (
                          <Button size="sm" variant="ghost" onClick={() => reactivate.mutate(u.id)} disabled={reactivate.isPending}>
                            Reactivar
                          </Button>
                        ))}
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
