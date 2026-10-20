import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { Link } from 'react-router'
import { z } from 'zod'

import { ErrorAlert, Field } from '@/components/common'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { AuthShell } from '@/features/auth/LoginPage'
import { api } from '@/lib/api'

const schema = z.object({
  username: z.string().trim().min(1, 'Ingrese su usuario').max(64),
  message: z.string().max(500).optional(),
})
type FormValues = z.infer<typeof schema>

export function RecoveryRequestPage() {
  const form = useForm<FormValues>({ resolver: zodResolver(schema), defaultValues: { username: '', message: '' } })
  const submit = useMutation({
    mutationFn: async (values: FormValues) =>
      (await api.post<{ message: string }>('/auth/recovery-requests', values)).data,
  })

  return (
    <AuthShell
      title="Recuperar cuenta"
      description="La solicitud se revisa de forma presencial con el administrador del sistema."
    >
      {submit.data ? (
        <div className="grid gap-4">
          <Alert>
            <AlertDescription>{submit.data.message}</AlertDescription>
          </Alert>
          <Button asChild variant="outline">
            <Link to="/login">Volver al inicio de sesión</Link>
          </Button>
        </div>
      ) : (
        <form onSubmit={form.handleSubmit((v) => submit.mutate(v))} className="grid gap-4" noValidate>
          <ErrorAlert error={submit.error} />
          <Field label="Usuario" htmlFor="username" error={form.formState.errors.username?.message}>
            <Input id="username" autoComplete="username" {...form.register('username')} />
          </Field>
          <Field label="Mensaje para el administrador (opcional)" htmlFor="message">
            <Textarea id="message" rows={3} {...form.register('message')} />
          </Field>
          <Button type="submit" disabled={submit.isPending}>
            Enviar solicitud
          </Button>
          <Link to="/login" className="text-muted-foreground text-center text-sm underline decoration-primary decoration-2 underline-offset-4">
            Volver
          </Link>
        </form>
      )}
    </AuthShell>
  )
}
