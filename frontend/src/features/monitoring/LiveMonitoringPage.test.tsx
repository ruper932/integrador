import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'

import { LiveMonitoringPage } from '@/features/monitoring/LiveMonitoringPage'
import { api } from '@/lib/api'
import type { LiveData, SensorType } from '@/types/api'

const now = new Date()
const iso = (secondsAgo: number) => new Date(now.getTime() - secondsAgo * 1000).toISOString()

const temperatura: SensorType = {
  id: 1,
  code: 'temperatura',
  name: 'Temperatura del aire',
  unit: 'C',
  min_value: -40,
  max_value: 85,
  aggregation: 'instantaneo',
  description: null,
}

const live: LiveData = {
  generated_at: iso(0),
  window_minutes: 15,
  device: { id: 4, code: 'esp32-04', name: 'Estación norte', status: 'activo', last_seen_at: iso(3), sample_interval_s: 30, is_stale: false },
  variables: [
    {
      sensor_type: temperatura,
      aggregation: 'instantaneo',
      latest_value: 12.4,
      latest_at: iso(3),
      minimum: 11.8,
      maximum: 12.4,
      average: 12.1,
      points: [
        { t: iso(33), v: 11.8 },
        { t: iso(3), v: 12.4 },
      ],
    },
  ],
}

function renderWith(permissions: string[]) {
  vi.spyOn(api, 'get').mockImplementation(async (url: string) => {
    if (url === '/auth/me') return { data: { permissions } }
    if (url === '/dashboard/summary') return { data: { devices: [{ ...live.device, minutes_since_last_seen: 0 }] } }
    return { data: live }
  })
  const put = vi.spyOn(api, 'put').mockResolvedValue({ data: {} })
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <LiveMonitoringPage />
    </QueryClientProvider>,
  )
  return put
}

afterEach(() => vi.restoreAllMocks())

test('muestra el medidor con el último valor y la estación en vivo', async () => {
  renderWith(['dashboard.consultar'])
  const meter = await screen.findByRole('meter', { name: 'Temperatura del aire' })
  expect(meter).toHaveAttribute('aria-valuetext', '12,4 °C')
  expect(screen.getByText('En vivo')).toBeInTheDocument()
  expect(screen.getByRole('radio', { name: 'Cada 30 s' })).toHaveAttribute('aria-checked', 'true')
})

test('sin permiso de gestión el intervalo de muestreo no se puede cambiar', async () => {
  renderWith(['dashboard.consultar'])
  expect(await screen.findByRole('radio', { name: 'Tiempo real' })).toBeDisabled()
})

test('el administrador cambia la estación a tiempo real', async () => {
  const put = renderWith(['dashboard.consultar', 'infraestructura.gestionar'])
  const realtime = await screen.findByRole('radio', { name: 'Tiempo real' })
  await vi.waitFor(() => expect(realtime).toBeEnabled())
  fireEvent.click(realtime)
  await vi.waitFor(() => expect(put).toHaveBeenCalledWith('/devices/4', { sample_interval_s: 5 }))
  expect(await screen.findByText('Intervalo guardado')).toBeInTheDocument()
})
