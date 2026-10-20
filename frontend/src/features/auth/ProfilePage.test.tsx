import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'

import { ProfilePage } from '@/features/auth/ProfilePage'
import { api } from '@/lib/api'
import type { Me } from '@/types/api'

const me: Me = {
  id: 7,
  username: 'rquispe',
  full_name: 'Rosa Quispe',
  is_active: true,
  must_change_password: false,
  last_login_at: null,
  created_at: '2026-10-01T12:00:00Z',
  roles: [{ id: 3, name: 'docente' }],
  permissions: ['dashboard.consultar'],
  profile_complete: true,
  profile: {
    first_names: 'Rosa',
    paternal_surname: 'Quispe',
    maternal_surname: null,
    ci_number: '4455667',
    ci_complement: null,
    ci_issued_in: 'LP',
    institutional_email: null,
    personal_email: 'rosa@example.com',
    mobile_phone: '76543210',
    birth_date: '1990-04-12',
    address: 'Titicachi',
    position: { id: 2, code: 'docente', name: 'Docente / facilitador/a' },
  },
  degrees: [],
}

const responses: Record<string, unknown> = {
  '/auth/me': me,
  '/catalogs/academic-levels': [{ id: 1, code: 'licenciatura', name: 'Licenciatura', min_graduation_age: 21 }],
  '/catalogs/institutions': [],
  '/catalogs/positions': [{ id: 2, code: 'docente', name: 'Docente / facilitador/a' }],
}

function renderPage() {
  const get = vi.spyOn(api, 'get').mockImplementation(async (url: string) => {
    if (url === '/roles') throw new Error('un docente no puede consultar roles')
    return { data: responses[url] }
  })
  const put = vi.spyOn(api, 'put').mockResolvedValue({ data: me })
  const post = vi.spyOn(api, 'post').mockResolvedValue({ data: { message: 'ok' } })
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <ProfilePage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
  return { get, put, post }
}

describe('ProfilePage', () => {
  beforeEach(() => vi.restoreAllMocks())

  it('muestra los datos del usuario y su cuenta', async () => {
    renderPage()
    expect(await screen.findByText('4455667 (La Paz)')).toBeInTheDocument()
    expect(screen.getByText('76543210')).toBeInTheDocument()
    expect(screen.getByText('rquispe')).toBeInTheDocument()
    expect(screen.getAllByText('Docente / facilitador/a').length).toBeGreaterThan(0)
  })

  it('edita sus datos sin cambiar usuario, roles ni cargo', async () => {
    const { get, put } = renderPage()
    await userEvent.click(await screen.findByRole('button', { name: 'Editar datos' }))
    const phone = await screen.findByLabelText('Número de celular')
    expect(screen.queryByLabelText('Usuario')).not.toBeInTheDocument()
    expect(screen.getByLabelText('Cargo en el CEA')).toBeDisabled()
    await userEvent.clear(phone)
    await userEvent.type(phone, '69998877')
    await userEvent.click(screen.getByRole('button', { name: 'Guardar cambios' }))
    await vi.waitFor(() => expect(put).toHaveBeenCalled())
    const [url, body] = put.mock.calls[0]!
    expect(url).toBe('/auth/me/profile')
    expect((body as { profile: Record<string, unknown> }).profile).toMatchObject({ mobile_phone: '69998877' })
    expect((body as { profile: Record<string, unknown> }).profile).not.toHaveProperty('position_id')
    expect(get).not.toHaveBeenCalledWith('/roles')
  })

  it('valida la nueva contraseña antes de enviarla', async () => {
    const { post } = renderPage()
    await userEvent.type(await screen.findByLabelText('Contraseña actual'), 'Actual-2026x')
    await userEvent.type(screen.getByLabelText('Nueva contraseña'), 'rquispe2026x')
    await userEvent.type(screen.getByLabelText('Repita la nueva contraseña'), 'otra')
    await userEvent.click(screen.getByRole('button', { name: 'Cambiar contraseña' }))
    expect(await screen.findByText('No debe contener su usuario')).toBeInTheDocument()
    expect(screen.getByText('Las contraseñas no coinciden')).toBeInTheDocument()
    expect(post).not.toHaveBeenCalled()
  })
})
