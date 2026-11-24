import { describe, expect, it } from 'vitest'

import { ageText, freshness, gaugeFraction, trend, withGaps } from './rules'

const NOW = Date.parse('2026-11-17T12:00:00Z')
const ago = (s: number) => new Date(NOW - s * 1000).toISOString()

describe('freshness', () => {
  it('está en vivo si la última lectura llegó dentro de tres intervalos', () => {
    expect(freshness(ago(20), 5, false, NOW)).toBe('en_vivo')
    expect(freshness(ago(26), 5, false, NOW)).toBe('retrasada')
    expect(freshness(ago(150), 60, false, NOW)).toBe('en_vivo')
  })

  it('sin conexión si nunca envió o el servidor la marca desactualizada', () => {
    expect(freshness(null, 5, false, NOW)).toBe('sin_conexion')
    expect(freshness(ago(5), 5, true, NOW)).toBe('sin_conexion')
  })
})

describe('gaugeFraction', () => {
  it('ubica el valor en la escala y lo acota a los extremos', () => {
    expect(gaugeFraction(15, { min: -10, max: 40 })).toBe(0.5)
    expect(gaugeFraction(60, { min: -10, max: 40 })).toBe(1)
    expect(gaugeFraction(-30, { min: -10, max: 40 })).toBe(0)
  })
})

describe('trend y ageText', () => {
  it('compara la última lectura con la anterior', () => {
    expect(trend([{ t: ago(10), v: 10 }])).toBeNull()
    expect(trend([{ t: ago(10), v: 10 }, { t: ago(5), v: 10.5 }])).toBe(0.5)
  })

  it('expresa la antigüedad en segundos o minutos', () => {
    expect(ageText(ago(7), NOW)).toBe('hace 7 s')
    expect(ageText(ago(125), NOW)).toBe('hace 2 min 5 s')
    expect(ageText(null, NOW)).toBe('nunca')
  })
})

describe('withGaps', () => {
  it('corta la línea cuando faltan lecturas, sin inventar valores', () => {
    const points = [
      { t: ago(60), v: 1 },
      { t: ago(55), v: 2 },
      { t: ago(5), v: 3 }, // 50 s sin lecturas con muestreo de 5 s
    ]
    const out = withGaps(points, 5)
    expect(out.map((p) => p.v)).toEqual([1, 2, null, 3])
    expect(withGaps(points.slice(0, 2), 5).every((p) => p.v !== null)).toBe(true)
  })
})
