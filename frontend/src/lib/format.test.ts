import { formatNumber, localInputToIso } from '@/lib/format'

describe('format', () => {
  it('muestra guion para valores no medidos (null), no cero', () => {
    expect(formatNumber(null)).toBe('—')
    expect(formatNumber(0)).toBe('0')
  })

  it('convierte fechas locales a ISO 8601 con zona horaria', () => {
    expect(localInputToIso('2025-05-01T08:30')).toMatch(/Z$/)
  })
})
