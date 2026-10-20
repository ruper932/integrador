import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { z } from 'zod'

import { ErrorAlert, Field, Notice } from '@/components/common'
import { Button } from '@/components/ui/button'
import { PasswordInput } from '@/components/PasswordInput'
import { ME_KEY } from '@/features/auth/useAuth'
import { api } from '@/lib/api'

// La política definitiva se valida en el backend; aquí se orienta al usuario.
export function changePasswordSchema(username: string) {
  return z
    .object({
      current_password: z.string().min(1, 'Ingrese su contraseña actual'),
      new_password: z
        .string()
        .min(10, 'Mínimo 10 caracteres')
        .max(128, 'Máximo 128 caracteres')
        .regex(/[A-Za-z]/, 'Incluya al menos una letra')
        .regex(/\d/, 'Incluya al menos un número')
        .refine((v) => !username || !v.toLowerCase().includes(username.toLowerCase()), 'No debe contener su usuario'),
      confirm: z.string(),
    })
    .refine((v) => v.new_password === v.confirm, { message: 'Las contraseñas no coinciden', path: ['confirm'] })
    .refine((v) => v.new_password !== v.current_password, {
      message: 'Debe ser distinta de la actual',
      path: ['new_password'],
    })
}

type FormValues = z.infer<ReturnType<typeof changePasswordSchema>>

export function ChangePasswordForm({ username, onSuccess }: { username: string; onSuccess?: () => void }) {
  const queryClient = useQueryClient()
  const form = useForm<FormValues>({
    resolver: zodResolver(changePasswordSchema(username)),
    defaultValues: { current_password: '', new_password: '', confirm: '' },
  })
  const change = useMutation({
    mutationFn: (v: FormValues) =>
      api.post('/auth/change-password', { current_password: v.current_password, new_password: v.new_password }),
    onSuccess: async () => {
      form.reset()
      await queryClient.invalidateQueries({ queryKey: ME_KEY })
      onSuccess?.()
    },
  })
  const { errors } = form.formState

  return (
    <form onSubmit={form.handleSubmit((v) => change.mutate(v))} className="grid gap-4" noValidate>
      <ErrorAlert error={change.error} />
      {change.isSuccess && (
        <Notice tone="success">Contraseña actualizada. Se cerraron sus sesiones en otros equipos.</Notice>
      )}
      <Field label="Contraseña actual" htmlFor="current_password" error={errors.current_password?.message}>
        <PasswordInput id="current_password"
          autoComplete="current-password"
          {...form.register('current_password')}
        />
      </Field>
      <Field
        label="Nueva contraseña"
        htmlFor="new_password"
        error={errors.new_password?.message}
        hint="Mínimo 10 caracteres, con letras y números, sin incluir su usuario."
      >
        <PasswordInput id="new_password" autoComplete="new-password" {...form.register('new_password')} />
      </Field>
      <Field label="Repita la nueva contraseña" htmlFor="confirm" error={errors.confirm?.message}>
        <PasswordInput id="confirm" autoComplete="new-password" {...form.register('confirm')} />
      </Field>
      <div>
        <Button type="submit" disabled={change.isPending}>
          Cambiar contraseña
        </Button>
      </div>
    </form>
  )
}
