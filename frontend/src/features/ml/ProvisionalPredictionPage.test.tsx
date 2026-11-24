import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'

import { ProvisionalPredictionPage } from '@/features/ml/ProvisionalPredictionPage'
import { api } from '@/lib/api'
import type { ProvisionalPrediction, ProvisionalStation } from '@/types/api'

const base: ProvisionalPrediction = {
  provisional: true,
  modelo_disponible: true,
  motivo: null,
  version_modelo: 'sim-0.1.0',
  horizonte: null,
  metricas_simulacion: null,
  generado_en: '2026-11-12T15:00:00Z',
  dia_base: '2026-11-11',
  fecha_predicha: '2026-11-12',
  estaciones: [],
}

function renderWith(data: ProvisionalPrediction) {
  vi.spyOn(api, 'get').mockResolvedValue({ data })
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <ProvisionalPredictionPage />
    </QueryClientProvider>,
  )
}

test('sin estaciones conectadas muestra «Sin datos disponibles» y la marca de provisional', async () => {
  renderWith(base)
  expect(await screen.findByText('Sin datos disponibles')).toBeInTheDocument()
  expect(screen.getByText('Provisional')).toBeInTheDocument()
})

test('una estación sin datos suficientes no muestra un número inventado', async () => {
  const station: ProvisionalStation = {
    device_id: 1,
    device_code: 'esp32-01',
    device_name: 'Estación norte',
    fog_collector: 'Atrapanieblas norte',
    mesh_area_m2: 40,
    last_seen_at: '2026-11-12T14:55:00Z',
    estado: 'datos_insuficientes',
    resultado_litros: null,
    referencia_media_7d_litros: null,
    captado_hoy_litros: 3,
    variables: { volumen_dia: null },
    faltantes: ['volumen_dia'],
  }
  renderWith({ ...base, estaciones: [station] })
  expect(await screen.findByText('Datos insuficientes')).toBeInTheDocument()
  expect(screen.getByText(/Faltan datos de: Volumen del día base/)).toBeInTheDocument()
})
