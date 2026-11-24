import { z } from 'zod'

import { todayIso } from '@/lib/people'

/** Mismas reglas que el backend (CODE_PATTERN). */
export const code = z
  .string()
  .trim()
  .regex(/^[A-Za-z0-9_.-]{2,40}$/, 'Solo letras, números, guion, guion bajo y punto (2 a 40)')

export const name = (max = 120) =>
  z.string().trim().min(2, 'Mínimo 2 caracteres').max(max, `Máximo ${max} caracteres`)

/** Número opcional escrito en un campo de texto: vacío equivale a «sin dato». */
export function optionalNumber(min: number, max: number, { exclusiveMin = false } = {}) {
  return z
    .string()
    .trim()
    .refine((v) => v === '' || Number.isFinite(Number(v.replace(',', '.'))), 'Ingrese un número')
    .refine((v) => {
      if (v === '') return true
      const n = Number(v.replace(',', '.'))
      return (exclusiveMin ? n > min : n >= min) && n <= max
    }, `Debe estar entre ${min} y ${max}${exclusiveMin ? ' (mayor que ' + min + ')' : ''}`)
}

/** Fecha de calendario (AAAA-MM-DD) opcional que no puede estar en el futuro. */
export const pastOrToday = z.string().refine((v) => v === '' || v <= todayIso(), 'No puede ser una fecha futura')

/** Convierte un número opcional del formulario al valor que espera la API. */
export const numberOrNull = (v: string) => (v.trim() === '' ? null : v.trim().replace(',', '.'))
