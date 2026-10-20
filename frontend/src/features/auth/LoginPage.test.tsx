import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AxiosError, AxiosHeaders } from 'axios'
import { MemoryRouter } from 'react-router'

import { LoginPage } from '@/features/auth/LoginPage'
import { api } from '@/lib/api'

function renderLogin() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

function unauthorized(message: string) {
  const config = { headers: new AxiosHeaders() }
  return new AxiosError('401', 'ERR_BAD_REQUEST', config, null, {
    status: 401,
    statusText: 'Unauthorized',
    headers: {},
    config,
    data: { error: { code: 'credenciales_invalidas', message, details: null } },
  })
}

describe('LoginPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    vi.spyOn(api, 'get').mockRejectedValue(unauthorized('Debe iniciar sesión.'))
  })

  it('valida los campos obligatorios sin llamar a la API', async () => {
    const post = vi.spyOn(api, 'post')
    renderLogin()
    await userEvent.click(await screen.findByRole('button', { name: 'Ingresar' }))
    expect(await screen.findByText('Ingrese su usuario')).toBeInTheDocument()
    expect(screen.getByText('Ingrese su contraseña')).toBeInTheDocument()
    expect(post).not.toHaveBeenCalled()
  })

  it('muestra el mensaje de error del backend', async () => {
    vi.spyOn(api, 'post').mockRejectedValue(unauthorized('Usuario o contraseña incorrectos.'))
    renderLogin()
    await userEvent.type(await screen.findByLabelText('Usuario'), 'ana')
    await userEvent.type(screen.getByLabelText('Contraseña'), 'mala')
    await userEvent.click(screen.getByRole('button', { name: 'Ingresar' }))
    await waitFor(() => expect(screen.getByText('Usuario o contraseña incorrectos.')).toBeInTheDocument())
  })

  it('ofrece la recuperación de cuenta mediante el administrador', async () => {
    renderLogin()
    expect(await screen.findByRole('link', { name: '¿Olvidó su contraseña?' })).toHaveAttribute('href', '/recuperar-cuenta')
  })
})
