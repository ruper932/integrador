import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { HighAlertGate } from '@/features/incidents/IncidentAlerts'
import { api } from '@/lib/api'
import type { Incident } from '@/types/api'

const alert = {
  id: 4,
  title: 'Estación norte sin comunicación',
  description: 'No envía mediciones hace 6 h.',
  priority: 'alta',
  status: 'abierto',
  source: 'sistema',
  reporter: null,
  device_name: 'Estación norte',
  location_reference: null,
  created_at: '2026-11-05T10:00:00Z',
} as Incident

describe('HighAlertGate', () => {
  beforeEach(() => vi.restoreAllMocks())

  it('bloquea la interfaz hasta que se revisa la alerta', async () => {
    let reviewed = false
    vi.spyOn(api, 'get').mockImplementation(async () => ({ data: { blocking: reviewed ? [] : [alert], reminders: [] } }))
    const post = vi.spyOn(api, 'post').mockImplementation(async () => {
      reviewed = true
      return { data: {} }
    })
    const onReviewed = vi.fn()
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={client}>
        <HighAlertGate enabled onReviewed={onReviewed} />
      </QueryClientProvider>,
    )

    const dialog = await screen.findByRole('alertdialog', { name: 'Alerta de prioridad alta' })
    expect(dialog).toHaveTextContent('Estación norte sin comunicación')
    expect(screen.queryByRole('button', { name: 'Cerrar' })).toBeNull()
    await userEvent.keyboard('{Escape}')
    expect(dialog).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Revisar alerta' }))
    expect(post).toHaveBeenCalledWith('/incidents/4/review')
    expect(onReviewed).toHaveBeenCalledWith(4)
    await waitFor(() => expect(screen.queryByRole('alertdialog')).toBeNull())
  })
})
