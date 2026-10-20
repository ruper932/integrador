import { KeyRound, Pencil, UserRound } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useLocation } from 'react-router'

import { Loading, Notice, PageHeader, StatusBadge } from '@/components/common'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { CI_DEPARTMENTS } from '@/features/admin/catalogs'
import { UserForm } from '@/features/admin/UserForm'
import { ChangePasswordForm } from '@/features/auth/ChangePasswordForm'
import { useMe } from '@/features/auth/useAuth'
import type { Me } from '@/types/api'
import { formatCalendarDate, formatDateTime } from '@/lib/format'
import { ageOn } from '@/lib/people'

function Item({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="grid gap-0.5">
      <dt className="text-muted-foreground text-xs">{label}</dt>
      <dd className="text-sm break-words">{value || '—'}</dd>
    </div>
  )
}

function ciText(me: Me): string {
  const p = me.profile
  if (!p?.ci_number) return ''
  const department = CI_DEPARTMENTS.find((d) => d.value === p.ci_issued_in)?.label
  return `${p.ci_number}${p.ci_complement ? `-${p.ci_complement}` : ''}${department ? ` (${department})` : ''}`
}

function ProfileSummary({ me }: { me: Me }) {
  const p = me.profile
  return (
    <div className="grid gap-6">
      <dl className="grid gap-4 sm:grid-cols-3">
        <Item label="Nombres" value={p?.first_names} />
        <Item label="Apellido paterno" value={p?.paternal_surname} />
        <Item label="Apellido materno" value={p?.maternal_surname} />
        <Item label="Cédula de identidad" value={ciText(me)} />
        <Item label="Número de celular" value={p?.mobile_phone} />
        <Item
          label="Fecha de nacimiento"
          value={p?.birth_date ? `${formatCalendarDate(p.birth_date)} (${ageOn(p.birth_date)} años)` : null}
        />
        <Item label="Cargo en el CEA" value={p?.position?.name} />
        <Item label="Correo institucional" value={p?.institutional_email} />
        <Item label="Correo personal" value={p?.personal_email} />
        <Item label="Dirección" value={p?.address} />
      </dl>
      <div className="grid gap-2">
        <h3 className="text-sm font-medium">Formación académica</h3>
        {me.degrees.length === 0 ? (
          <p className="text-muted-foreground text-sm">Sin títulos registrados.</p>
        ) : (
          <ul className="grid gap-2">
            {me.degrees.map((d) => (
              <li key={d.id} className="rounded-lg border p-3 text-sm">
                <div className="font-medium">{d.title}</div>
                <div className="text-muted-foreground">
                  {d.academic_level.name} · {d.institution.name}
                  {d.graduation_year ? ` · ${d.graduation_year}` : ''}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}

export function ProfilePage() {
  const me = useMe()
  const [editing, setEditing] = useState(false)
  const [saved, setSaved] = useState(false)
  const location = useLocation()

  // El menú de usuario enlaza a /perfil#contrasena.
  useEffect(() => {
    if (location.hash === '#contrasena' && me.data) {
      document.getElementById('contrasena')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      document.getElementById('current_password')?.focus({ preventScroll: true })
    }
  }, [location.hash, me.data])

  if (me.isLoading || !me.data) return <Loading />
  const user = me.data

  return (
    <>
      <PageHeader
        eyebrow="Cuenta"
        title="Mi perfil"
        description="Revise y actualice sus datos personales, su formación y su contraseña."
      />

      {!user.profile_complete && (
        <Notice tone="warning" title="Perfil incompleto" className="mb-5">
          Registre al menos un apellido, su CI y su número de celular.
        </Notice>
      )}

      <div className="grid gap-6 lg:grid-cols-[1fr_22rem]">
        <Card>
          <CardHeader>
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <UserRound className="size-5" /> {user.full_name}
                </CardTitle>
                <CardDescription>Datos personales e información laboral</CardDescription>
              </div>
              {!editing && (
                <Button
                  variant="outline"
                  onClick={() => {
                    setSaved(false)
                    setEditing(true)
                  }}
                >
                  <Pencil /> Editar datos
                </Button>
              )}
            </div>
          </CardHeader>
          <CardContent className="grid gap-4">
            {saved && !editing && (
              <Notice tone="success">Datos actualizados.</Notice>
            )}
            {editing ? (
              <UserForm
                mode="self"
                user={user}
                onDone={(result) => {
                  setEditing(false)
                  setSaved(result === null)
                }}
              />
            ) : (
              <ProfileSummary me={user} />
            )}
          </CardContent>
        </Card>

        <div className="grid content-start gap-6">
          <Card>
            <CardHeader>
              <CardTitle>Cuenta</CardTitle>
            </CardHeader>
            <CardContent>
              <dl className="grid gap-3">
                <Item label="Usuario" value={<span className="font-mono">{user.username}</span>} />
                <Item
                  label="Roles"
                  value={
                    <span className="flex flex-wrap gap-1">
                      {user.roles.map((r) => (
                        <Badge key={r.id} variant="secondary">
                          {r.name.replaceAll('_', ' ')}
                        </Badge>
                      ))}
                    </span>
                  }
                />
                <Item label="Estado" value={<StatusBadge value={user.is_active ? 'activo' : 'inactivo'} />} />
                <Item label="Último acceso" value={formatDateTime(user.last_login_at)} />
                <Item label="Cuenta creada" value={formatDateTime(user.created_at)} />
              </dl>
              <p className="text-muted-foreground mt-3 text-xs">
                El usuario, los roles y el cargo los administra el administrador del sistema.
              </p>
            </CardContent>
          </Card>

          <Card id="contrasena" className="scroll-mt-24">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <KeyRound className="size-5" /> Cambiar contraseña
              </CardTitle>
              <CardDescription>Al cambiarla se cierran sus sesiones en otros equipos.</CardDescription>
            </CardHeader>
            <CardContent>
              <ChangePasswordForm username={user.username} />
            </CardContent>
          </Card>
        </div>
      </div>
    </>
  )
}
