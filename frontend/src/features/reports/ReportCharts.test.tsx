import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { ReportCharts } from '@/features/reports/ReportCharts'
import { api } from '@/lib/api'
import type { ReportCharts as ChartsData, ReportDefinition } from '@/types/api'

const volumen: ReportDefinition = {
  kind: 'volumen',
  module: 'Monitoreo IoT y volumen',
  label: 'Volumen de agua captada',
  description: '',
  filters: [{ key: 'date_range', label: 'Periodo', required: false }],
}

const data: ChartsData = {
  title: 'Volumen de agua captada',
  rows: 2,
  criteria: ['Periodo: 2026-11-01 00:00 a 2026-11-03 00:00 (hora de Bolivia)'],
  summary: [{ label: 'Total captado', value: '4 L' }],
  charts: [
    {
      title: 'Volumen de agua captada por día',
      kind: 'bar',
      unit: 'L',
      horizontal: false,
      categories: ['01/11/2026', '02/11/2026'],
      series: [{ name: 'Total (L)', values: [1.5, null] }],
    },
  ],
}

function renderWith(report: ReportDefinition, values: Record<string, string> = {}) {
  const get = vi.spyOn(api, 'get').mockResolvedValue({ data })
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <ReportCharts report={report} values={values} />
    </QueryClientProvider>,
  )
  return get
}

test('muestra el resumen y los gráficos del backend, con su tabla de datos', async () => {
  const get = renderWith(volumen, { date_from: '2026-11-01T00:00' })
  expect(await screen.findByText('4 L')).toBeInTheDocument()
  expect(screen.getByText('Volumen de agua captada por día')).toBeInTheDocument()
  expect(get).toHaveBeenCalledWith('/reports/charts', {
    params: expect.objectContaining({ report: 'volumen', date_from: expect.any(String) }),
  })
  expect(get.mock.calls[0]![1]!.params).not.toHaveProperty('format')

  await userEvent.click(screen.getByRole('button', { name: /Ver tabla/ }))
  expect(screen.getByText('1,5')).toBeInTheDocument()
  expect(screen.getByText('—')).toBeInTheDocument() // sin dato, no 0
})

test('si falta un filtro obligatorio lo pide en vez de consultar', () => {
  const get = renderWith({ ...volumen, kind: 'variable', filters: [{ key: 'sensor_type', label: 'Variable', required: true }] })
  expect(screen.getByText(/indique: variable/)).toBeInTheDocument()
  expect(get).not.toHaveBeenCalled()
})
