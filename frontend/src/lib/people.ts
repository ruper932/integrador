// Mismas reglas que el backend (app/business/rules/people.py); el backend tiene la última palabra.
export const MIN_AGE = 18
export const MAX_AGE = 100

function parts(iso: string): [number, number, number] {
  const [y, m, d] = iso.split('-').map(Number)
  return [y ?? 0, m ?? 0, d ?? 0]
}

/** Fecha de hoy en Bolivia, en formato AAAA-MM-DD. */
export function todayIso(): string {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'America/La_Paz' }).format(new Date())
}

/** Años cumplidos a la fecha indicada (ambas en formato AAAA-MM-DD). */
export function ageOn(birthIso: string, todayIsoValue = todayIso()): number {
  const [by, bm, bd] = parts(birthIso)
  const [ty, tm, td] = parts(todayIsoValue)
  return ty - by - (tm < bm || (tm === bm && td < bd) ? 1 : 0)
}

/** Fecha de nacimiento más reciente permitida (cumple 18 años hoy). */
export function latestAdultBirthDate(todayIsoValue = todayIso()): string {
  const [y, m, d] = parts(todayIsoValue)
  return `${y - MIN_AGE}-${String(m).padStart(2, '0')}-${String(d).padStart(2, '0')}`
}

export function birthDateError(birthIso: string, todayIsoValue = todayIso()): string | null {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(birthIso)) return 'Indique la fecha de nacimiento'
  if (birthIso > todayIsoValue) return 'La fecha no puede ser futura'
  const age = ageOn(birthIso, todayIsoValue)
  if (age < MIN_AGE) return `Debe ser mayor de edad (según la fecha tiene ${age} años)`
  if (age > MAX_AGE) return `La fecha indica ${age} años; revise el dato`
  return null
}

/** Primer año en que es posible egresar con un nivel, según el año de nacimiento. */
export function earliestGraduationYear(birthIso: string, minGraduationAge: number): number {
  return parts(birthIso)[0] + minGraduationAge
}
