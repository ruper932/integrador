import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { UsersPage } from '@/features/admin/UsersPage'
import { api } from '@/lib/api'
import type { User } from '@/types/api'

const juana: User = {
  id: 5,
  username: 'jmamani',
  full_name: 'Juana Mamani',
  is_active: true,
  must_change_password: false,
  last_login_at: null,
  created_at: '2026-11-01T12:00:00Z',
  roles: [{ id: 2, name: 'docente' }],
  profile_complete: true,
  profile: null,
  degrees: [],
}

function renderPage() {
  vi.spyOn(api, 'get').mockImplementation(async (url: string) => {
    if (url === '/auth/me') return { data: { ...juana, id: 1, username: 'admin', permissions: ['usuarios.gestionar'] } }
    if (url === '/users') return { data: { items: [juana], total: 1, offset: 0, limit: 200 } }
    return { data: [] }
  })
  const post = vi.spyOn(api, 'post').mockResolvedValue({ data: { user: juana, temporary_password: 'Temporal-2026x' } })
  const put = vi.spyOn(api, 'put').mockResolvedValue({ data: {} })
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <UsersPage />
    </QueryClientProvider>,
  )
  return { post, put }
}

afterEach(() => vi.restoreAllMocks())

test('restablecer clave pide confirmación en un modal y muestra ahí la contraseña temporal', async () => {
  const { post } = renderPage()
  await userEvent.click(await screen.findByRole('button', { name: /Restablecer clave/ }))
  const dialog = screen.getByRole('dialog', { name: 'Restablecer la contraseña de Juana Mamani' })
  expect(within(dialog).getByText('Se cerrarán todas sus sesiones abiertas.')).toBeInTheDocument()
  expect(post).not.toHaveBeenCalled()

  await userEvent.click(within(dialog).getByRole('button', { name: /Generar contraseña temporal/ }))
  expect(post).toHaveBeenCalledWith('/users/5/reset-password', {})
  expect(await within(dialog).findByText('Temporal-2026x')).toBeInTheDocument()
  await userEvent.click(within(dialog).getByRole('button', { name: 'Listo' }))
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
})

test('cancelar la desactivación no cambia nada', async () => {
  const { put } = renderPage()
  await userEvent.click(await screen.findByRole('button', { name: /Desactivar/ }))
  const dialog = screen.getByRole('dialog', { name: 'Desactivar a Juana Mamani' })
  await userEvent.click(within(dialog).getByRole('button', { name: 'Cancelar' }))
  expect(put).not.toHaveBeenCalled()
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
})
