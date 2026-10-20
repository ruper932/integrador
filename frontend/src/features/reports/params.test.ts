import { buildParams, isApplied, listParams } from '@/features/reports/params'
import type { ReportDefinition } from '@/types/api'

const stock: ReportDefinition = {
  kind: 'inventario_stock',
  module: 'Inventario',
  label: 'Stock actual',
  description: '',
  filters: [
    { key: 'category_id', label: 'Categoría', required: false },
    { key: 'low_stock_only', label: 'Solo stock bajo', required: false },
  ],
}

test('solo se envían los filtros del reporte elegido que tienen valor', () => {
  // `device_id` quedó de otro reporte: no corresponde al de stock y no se envía.
  const values = { category_id: '3', low_stock_only: 'true', device_id: '9', date_from: '2026-10-01T00:00' }
  expect(buildParams(stock, values, 'pdf')).toEqual({
    report: 'inventario_stock',
    format: 'pdf',
    category_id: '3',
    low_stock_only: 'true',
  })
  expect(isApplied('date_range', values)).toBe(true)
  expect(isApplied('category_id', {})).toBe(false)
})

test('el rango de fechas se envía en ISO', () => {
  const movements: ReportDefinition = { ...stock, filters: [{ key: 'date_range', label: 'Periodo', required: false }] }
  const params = buildParams(movements, { date_from: '2026-10-01T08:00' }, 'csv')
  expect(params.date_from).toBe(new Date('2026-10-01T08:00').toISOString())
  expect(params.date_to).toBeUndefined()
})

test('el listado recibe solo sus filtros con valor, con el nombre de su endpoint', () => {
  const values = { actor_id: '4', action: '', date_to: '2026-10-02T00:00', bucket: 'week' }
  expect(listParams(['date_range', 'action', 'actor_id'], values, { actor_id: 'user_id' })).toEqual({
    user_id: '4',
    date_to: new Date('2026-10-02T00:00').toISOString(),
  })
})
