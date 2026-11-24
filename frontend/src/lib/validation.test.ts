import { numberOrNull, optionalNumber, pastOrToday } from '@/lib/validation'

describe('validation', () => {
  it('acepta un número opcional dentro del rango', () => {
    const lat = optionalNumber(-90, 90)
    expect(lat.safeParse('').success).toBe(true)
    expect(lat.safeParse('-15,40').success).toBe(true)
    expect(lat.safeParse('91').success).toBe(false)
    expect(lat.safeParse('abc').success).toBe(false)
    expect(optionalNumber(0, 10, { exclusiveMin: true }).safeParse('0').success).toBe(false)
  })

  it('rechaza fechas futuras', () => {
    expect(pastOrToday.safeParse('2000-01-01').success).toBe(true)
    expect(pastOrToday.safeParse('2999-01-01').success).toBe(false)
  })

  it('convierte comas decimales para la API', () => {
    expect(numberOrNull(' 12,5 ')).toBe('12.5')
    expect(numberOrNull('')).toBeNull()
  })
})
