import { render, screen, within } from '@testing-library/react'

import { IncidentStatusBadge, IncidentTimeline } from '@/features/incidents/IncidentBits'
import type { Incident } from '@/types/api'

const incident: Incident = {
  id: 7,
  title: 'Malla rota',
  description: 'La malla tiene un desgarro.',
  priority: 'alta',
  location_reference: null,
  status: 'aceptado',
  device_id: 1,
  device_code: 'esp32-01',
  device_name: 'Estación norte',
  sensor_id: null,
  sensor_code: null,
  source: 'usuario',
  auto_cause: null,
  reporter: { id: 3, username: 'lticona', full_name: 'Lucía Ticona' },
  assignee: { id: 5, username: 'mhuanca', full_name: 'Marco Huanca' },
  created_at: '2026-10-15T14:00:00Z',
  maintenance: {
    id: 9,
    status: 'aceptado',
    incident_report_id: 7,
    device_id: 1,
    device_code: 'esp32-01',
    sensor_id: null,
    sensor_code: null,
    performed_at: null,
    user_id: 5,
    username: 'mhuanca',
    user_full_name: 'Marco Huanca',
    maintenance_type: null,
    description: null,
    final_status: null,
    accepted_at: '2026-10-15T14:30:00Z',
    started_at: null,
    finished_at: null,
    created_at: '2026-10-15T14:30:00Z',
    items: [],
  },
}

test('el seguimiento muestra quién atiende el reporte y las etapas pendientes', () => {
  render(<IncidentTimeline incident={incident} />)
  const steps = within(screen.getByRole('list', { name: 'Seguimiento del reporte' })).getAllByRole('listitem')
  expect(steps).toHaveLength(4)
  expect(steps[0]).toHaveTextContent('Lucía Ticona')
  expect(steps[1]).toHaveTextContent('(completado)')
  expect(steps[1]).toHaveTextContent('Marco Huanca')
  expect(steps[2]).toHaveTextContent('(pendiente)')
  expect(steps[3]).toHaveTextContent('Pendiente')
})

test('el estado se muestra con texto, no solo con color', () => {
  render(<IncidentStatusBadge status="en_progreso" />)
  expect(screen.getByText('En progreso')).toBeInTheDocument()
})

test('un reporte abierto por el sistema se identifica sin autor', () => {
  render(<IncidentTimeline incident={{ ...incident, source: 'sistema', auto_cause: 'sin_comunicacion', reporter: null }} />)
  const first = within(screen.getByRole('list', { name: 'Seguimiento del reporte' })).getAllByRole('listitem')[0]
  expect(first).toHaveTextContent('Detección automática')
  expect(first).toHaveTextContent('Sistema')
})
