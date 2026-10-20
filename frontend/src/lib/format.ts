const TIME_ZONE = 'America/La_Paz'

const dateTime = new Intl.DateTimeFormat('es-BO', {
  dateStyle: 'short',
  timeStyle: 'short',
  timeZone: TIME_ZONE,
})

const dateOnly = new Intl.DateTimeFormat('es-BO', { dateStyle: 'medium', timeZone: TIME_ZONE })

export function formatDateTime(value: string | null | undefined): string {
  return value ? dateTime.format(new Date(value)) : '—'
}

export function formatDate(value: string | null | undefined): string {
  return value ? dateOnly.format(new Date(value)) : '—'
}

export function formatNumber(value: number | string | null | undefined, digits = 2): string {
  if (value === null || value === undefined || value === '') return '—'
  const n = typeof value === 'string' ? Number(value) : value
  return n.toLocaleString('es-BO', { maximumFractionDigits: digits })
}

/** Convierte el valor de un <input type="datetime-local"> a ISO 8601 con zona horaria. */
export function localInputToIso(value: string): string {
  return new Date(value).toISOString()
}

export function nowForInput(): string {
  const d = new Date()
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset())
  return d.toISOString().slice(0, 16)
}

export const QUALITY_LABELS: Record<string, string> = {
  valida: 'Válida',
  sin_dato: 'Sin dato',
  fuera_de_rango: 'Fuera de rango',
  unidad_invalida: 'Unidad inválida',
  invalida: 'Inválida',
}

/** Fecha de calendario sin hora (AAAA-MM-DD), p. ej. una fecha de nacimiento: no se convierte de zona horaria. */
export function formatCalendarDate(value: string | null | undefined): string {
  const match = value?.match(/^(\d{4})-(\d{2})-(\d{2})$/)
  return match ? `${match[3]}/${match[2]}/${match[1]}` : '—'
}

/** Tiempo transcurrido legible (p. ej. «hace 5 min»). */
export function relativeTime(iso: string | null): string {
  if (!iso) return 'sin comunicación'
  const minutes = Math.round((Date.now() - new Date(iso).getTime()) / 60_000)
  if (minutes < 1) return 'hace instantes'
  if (minutes < 60) return `hace ${minutes} min`
  const hours = Math.round(minutes / 60)
  if (hours < 48) return `hace ${hours} h`
  return `hace ${Math.round(hours / 24)} días`
}
