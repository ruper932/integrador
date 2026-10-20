import { Navigate, useNavigate } from 'react-router'

import { Loading } from '@/components/common'
import { Button } from '@/components/ui/button'
import { ChangePasswordForm } from '@/features/auth/ChangePasswordForm'
import { AuthShell } from '@/features/auth/LoginPage'
import { useLogout, useMe } from '@/features/auth/useAuth'

/** Pantalla obligatoria para quien ingresa con una contraseña temporal. */
export function ChangePasswordPage() {
  const me = useMe()
  const logout = useLogout()
  const navigate = useNavigate()

  if (me.isLoading) return <Loading />
  if (!me.data) return <Navigate to="/login" replace />
  if (!me.data.must_change_password) return <Navigate to="/perfil" replace />

  return (
    <AuthShell title="Cambiar contraseña" description="Debe definir una contraseña propia antes de continuar.">
      <div className="grid gap-2">
        <ChangePasswordForm username={me.data.username} onSuccess={() => navigate('/', { replace: true })} />
        <Button type="button" variant="ghost" onClick={() => logout.mutate(undefined, { onSettled: () => navigate('/login') })}>
          Cerrar sesión
        </Button>
      </div>
    </AuthShell>
  )
}
