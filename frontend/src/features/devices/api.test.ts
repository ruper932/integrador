import { QueryClient } from '@tanstack/react-query'

import { refreshStations } from '@/features/devices/api'

test('un cambio de estado de una estación actualiza todos los módulos que la muestran', () => {
  const qc = new QueryClient()
  const invalidate = vi.spyOn(qc, 'invalidateQueries')
  refreshStations(qc)
  const keys = invalidate.mock.calls.map(([filters]) => filters?.queryKey)
  expect(keys).toEqual([['devices'], ['sensors'], ['dashboard'], ['monitoring'], ['fog-collectors']])
})
