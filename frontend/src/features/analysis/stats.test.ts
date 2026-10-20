import { histogram, linearFit, movingAverage } from '@/features/analysis/stats'

test('media móvil: vacía hasta completar la ventana', () => {
  expect(movingAverage([1, 2, 3, 4], 3)).toEqual([null, null, 2, 3])
})

test('histograma: todos los valores caen en algún rango', () => {
  const bins = histogram([0, 1, 2, 3, 4, 5, 6, 7, 10])
  expect(bins.reduce((s, b) => s + b.count, 0)).toBe(9)
  expect(bins[0]!.from).toBe(0)
  expect(bins.at(-1)!.to).toBe(10)
  expect(histogram([5, 5, 5])).toEqual([{ from: 5, to: 6, count: 3 }, { from: 6, to: 7, count: 0 }, { from: 7, to: 8, count: 0 }])
  expect(histogram([])).toEqual([])
})

test('recta de mínimos cuadrados', () => {
  expect(linearFit([{ x: 0, y: 1 }, { x: 1, y: 3 }, { x: 2, y: 5 }])).toEqual({ a: 1, b: 2 })
  expect(linearFit([{ x: 1, y: 1 }, { x: 1, y: 2 }])).toBeNull()
})
