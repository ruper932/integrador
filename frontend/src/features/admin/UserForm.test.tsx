import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { UserForm } from '@/features/admin/UserForm'
import { api } from '@/lib/api'

const catalogs: Record<string, unknown> = {
  '/roles': [{ id: 1, name: 'docente', description: '', is_system: true, permissions: [] }],
  '/catalogs/academic-levels': [{ id: 1, code: 'licenciatura', name: 'Licenciatura', min_graduation_age: 21 }],
  '/catalogs/institutions': [{ id: 1, name: 'Universidad Mayor de San Andrés', acronym: 'UMSA', institution_type: 'universidad_publica', city: 'La Paz', is_active: true }],
  '/catalogs/positions': [{ id: 1, code: 'docente', name: 'Docente / facilitador/a' }],
}

function renderForm() {
  vi.spyOn(api, 'get').mockImplementation(async (url: string) => ({ data: catalogs[url] }))
  const post = vi.spyOn(api, 'post').mockResolvedValue({ data: { user: {}, temporary_password: 'x' } })
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <UserForm onDone={() => {}} />
    </QueryClientProvider>,
  )
  return post
}

describe('UserForm', () => {
  beforeEach(() => vi.restoreAllMocks())

  it('valida CI, celular de Bolivia y apellido antes de enviar', async () => {
    const post = renderForm()
    await userEvent.type(await screen.findByLabelText('Usuario'), 'juana')
    await userEvent.type(screen.getByLabelText('Nombres'), 'Juana')
    await userEvent.type(screen.getByLabelText('Cédula de identidad (CI)'), '12AB')
    await userEvent.type(screen.getByLabelText('Número de celular'), '22445566')
    await userEvent.click(screen.getByRole('button', { name: 'Crear usuario' }))
    expect(await screen.findByText('Solo números (4 a 10 dígitos)')).toBeInTheDocument()
    expect(screen.getByText('8 dígitos, inicia en 6 o 7')).toBeInTheDocument()
    expect(screen.getByText('Indique al menos un apellido')).toBeInTheDocument()
    expect(post).not.toHaveBeenCalled()
  })

  it('envía el perfil normalizado con sus títulos', async () => {
    const post = renderForm()
    await userEvent.type(await screen.findByLabelText('Usuario'), 'juana')
    await userEvent.click(screen.getByRole('checkbox'))
    await userEvent.type(screen.getByLabelText('Nombres'), 'Juana')
    await userEvent.type(screen.getByLabelText('Apellido materno'), 'Quispe')
    await userEvent.type(screen.getByLabelText('Cédula de identidad (CI)'), '4567890')
    await userEvent.type(screen.getByLabelText('Número de celular'), '71234567')
    await userEvent.type(screen.getByLabelText('Fecha de nacimiento'), '1990-04-12')
    await userEvent.click(screen.getByRole('button', { name: 'Título' }))
    await userEvent.selectOptions(screen.getByLabelText('Nivel'), '1')
    await userEvent.type(screen.getByLabelText('Título obtenido'), 'Licenciatura en Agronomía')
    await userEvent.selectOptions(screen.getByLabelText('Institución de egreso'), '1')
    await userEvent.click(screen.getByRole('button', { name: 'Crear usuario' }))
    await vi.waitFor(() => expect(post).toHaveBeenCalled())
    const [url, body] = post.mock.calls[0]!
    expect(url).toBe('/users')
    expect(body).toMatchObject({
      username: 'juana',
      role_ids: [1],
      profile: {
        first_names: 'Juana',
        paternal_surname: null,
        maternal_surname: 'Quispe',
        ci_number: '4567890',
        mobile_phone: '71234567',
        birth_date: '1990-04-12',
      },
      degrees: [{ academic_level_id: 1, title: 'Licenciatura en Agronomía', institution_id: 1, graduation_year: null }],
    })
  })

  async function fillRequired(birthDate: string) {
    await userEvent.type(await screen.findByLabelText('Usuario'), 'pedro')
    await userEvent.click(screen.getByRole('checkbox'))
    await userEvent.type(screen.getByLabelText('Nombres'), 'Pedro')
    await userEvent.type(screen.getByLabelText('Apellido paterno'), 'Mamani')
    await userEvent.type(screen.getByLabelText('Cédula de identidad (CI)'), '4567891')
    await userEvent.type(screen.getByLabelText('Número de celular'), '71234568')
    await userEvent.type(screen.getByLabelText('Fecha de nacimiento'), birthDate)
  }

  it('rechaza a una persona menor de 18 años', async () => {
    const post = renderForm()
    const today = new Date()
    const minor = `${today.getFullYear() - 17}-01-01`
    await fillRequired(minor)
    await userEvent.click(screen.getByRole('button', { name: 'Crear usuario' }))
    expect(await screen.findByText(/Debe ser mayor de edad/)).toBeInTheDocument()
    expect(post).not.toHaveBeenCalled()
  })

  it('rechaza un año de egreso imposible para la edad y el nivel', async () => {
    const post = renderForm()
    const birthYear = new Date().getFullYear() - 30
    await fillRequired(`${birthYear}-06-15`)
    await userEvent.click(screen.getByRole('button', { name: 'Título' }))
    await userEvent.selectOptions(screen.getByLabelText('Nivel'), '1')
    expect(screen.getByText(`Desde ${birthYear + 21}`)).toBeInTheDocument()
    await userEvent.type(screen.getByLabelText('Título obtenido'), 'Licenciatura en Agronomía')
    await userEvent.selectOptions(screen.getByLabelText('Institución de egreso'), '1')
    await userEvent.type(screen.getByLabelText('Año de egreso'), String(birthYear + 18))
    await userEvent.click(screen.getByRole('button', { name: 'Crear usuario' }))
    expect(await screen.findByText(new RegExp(`el egreso debe ser desde ${birthYear + 21}`))).toBeInTheDocument()
    expect(post).not.toHaveBeenCalled()
  })
})
