import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { RequestForm } from '@/features/relocations/RelocationsPage'
import { api } from '@/lib/api'

const data: Record<string, unknown> = {
  '/fog-collectors/overview': [
    { id: 1, code: 'AN-01', name: 'Norte', is_active: true, orientation: 'NE', location: { id: 10, name: 'Ladera norte' }, active_relocation: null },
    { id: 2, code: 'AN-02', name: 'Sur', is_active: true, orientation: null, location: null, active_relocation: { id: 7, status: 'pendiente' } },
  ],
  '/locations': [
    { id: 10, name: 'Ladera norte', is_active: true },
    { id: 11, name: 'Patio trasero', is_active: true },
  ],
}

function renderForm(initialCollector = '') {
  vi.spyOn(api, 'get').mockImplementation(async (url: string) => ({ data: data[url] }))
  const post = vi.spyOn(api, 'post').mockResolvedValue({ data: { id: 1 } })
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <RequestForm initialCollector={initialCollector} onDone={() => {}} />
    </QueryClientProvider>,
  )
  return post
}

describe('RequestForm', () => {
  beforeEach(() => vi.restoreAllMocks())

  it('respeta los datos del atrapanieblas elegido', async () => {
    renderForm()
    const collector = await screen.findByLabelText('Atrapanieblas')
    // Un atrapanieblas con una solicitud en curso no se puede elegir.
    expect(within(collector).getByRole('option', { name: /AN-02/ })).toBeDisabled()
    const proposal = screen.getByLabelText('Lugar sugerido (opcional)')
    expect(proposal).toBeDisabled()

    await userEvent.selectOptions(collector, '1')
    expect(screen.getByText('Ubicación actual: Ladera norte')).toBeInTheDocument()
    // Su ubicación actual no aparece como destino posible.
    expect(within(proposal).queryByRole('option', { name: 'Ladera norte' })).toBeNull()
    expect(within(proposal).getByRole('option', { name: 'Patio trasero' })).toBeInTheDocument()
  })

  it('valida la descripción y el lugar no registrado antes de enviar', async () => {
    const post = renderForm('1')
    await userEvent.selectOptions(await screen.findByLabelText('Lugar sugerido (opcional)'), 'otro')
    await userEvent.click(screen.getByRole('button', { name: 'Enviar solicitud' }))
    expect(await screen.findByText('Explique el problema de espacio con al menos 10 caracteres')).toBeInTheDocument()
    expect(screen.getByText('Describa el lugar sugerido (al menos 3 caracteres)')).toBeInTheDocument()
    expect(post).not.toHaveBeenCalled()

    await userEvent.type(screen.getByLabelText('Descripción del problema'), 'Se construirá un aula en ese terreno.')
    await userEvent.type(screen.getByLabelText('Describa el lugar'), 'Detrás del invernadero 2')
    await userEvent.click(screen.getByRole('button', { name: 'Enviar solicitud' }))
    await vi.waitFor(() => expect(post).toHaveBeenCalled())
    expect(post.mock.calls[0]).toEqual([
      '/relocations',
      {
        fog_collector_id: 1,
        reason: 'espacio_insuficiente',
        description: 'Se construirá un aula en ese terreno.',
        proposed_location_id: null,
        proposed_place: 'Detrás del invernadero 2',
      },
    ])
  })
})
