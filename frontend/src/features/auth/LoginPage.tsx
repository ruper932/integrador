import { zodResolver } from '@hookform/resolvers/zod'
import { LogIn } from 'lucide-react'
import { useForm } from 'react-hook-form'
import { Link, Navigate, useLocation, useNavigate } from 'react-router'
import { z } from 'zod'

import { ErrorAlert, Field } from '@/components/common'
import { PasswordInput } from '@/components/PasswordInput'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { AuthShell } from '@/features/auth/AuthShell'
import { useLogin, useMe } from '@/features/auth/useAuth'

export { AuthShell } from '@/features/auth/AuthShell'

const schema = z.object({
  // Mismos límites que el backend (LoginRequest); la contraseña no se recorta: los espacios cuentan.
  username: z.string().trim().min(1, 'Ingrese su usuario').max(64, 'Máximo 64 caracteres'),
  password: z.string().min(1, 'Ingrese su contraseña').max(128, 'Máximo 128 caracteres'),
})
type FormValues = z.infer<typeof schema>

export function LoginPage() {
  const me = useMe()
  const login = useLogin()
  const navigate = useNavigate()
  const location = useLocation()
  const form = useForm<FormValues>({ resolver: zodResolver(schema), defaultValues: { username: '', password: '' } })
  // Tras iniciar sesión se vuelve a la página que se intentaba abrir.
  const from = (location.state as { from?: string } | null)?.from ?? '/'

  if (me.data) return <Navigate to={me.data.must_change_password ? '/cambiar-contrasena' : from} replace />

  const onSubmit = form.handleSubmit((values) =>
    login.mutate(values, {
      onSuccess: (user) => navigate(user.must_change_password ? '/cambiar-contrasena' : from, { replace: true }),
      onError: () => form.setValue('password', ''),
    }),
  )

  return (
    <AuthShell title="Iniciar sesión" description="Ingrese con el usuario asignado por el administrador del sistema.">
      <form onSubmit={onSubmit} className="grid gap-4" noValidate>
        <ErrorAlert error={login.error} title="No se pudo iniciar sesión" />
        <Field label="Usuario" htmlFor="username" error={form.formState.errors.username?.message}>
          <Input id="username" autoComplete="username" autoCapitalize="none" spellCheck={false} autoFocus {...form.register('username')} />
        </Field>
        <Field label="Contraseña" htmlFor="password" error={form.formState.errors.password?.message}>
          <PasswordInput id="password" autoComplete="current-password" {...form.register('password')} />
        </Field>
        <Button type="submit" size="lg" disabled={login.isPending}>
          <LogIn /> {login.isPending ? 'Ingresando…' : 'Ingresar'}
        </Button>
        <Link
          to="/recuperar-cuenta"
          className="text-muted-foreground hover:text-foreground text-center text-sm underline decoration-primary decoration-2 underline-offset-4"
        >
          ¿Olvidó su contraseña?
        </Link>
      </form>
    </AuthShell>
  )
}
