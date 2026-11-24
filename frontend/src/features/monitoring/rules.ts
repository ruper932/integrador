import type { LivePoint } from '@/types/api'

/** Intervalos de muestreo que acepta la estación (el backend valida los mismos valores). */
export const SAMPLE_OPTIONS = [
  { seconds: 5, label: 'Tiempo real', hint: 'cada 5 s' },
  { seconds: 30, label: 'Cada 30 s', hint: 'cada 30 s' },
  { seconds: 60, label: 'Cada minuto', hint: 'cada 60 s' },
] as const

export const WINDOW_OPTIONS = [
  { minutes: 15, label: '15 min' },
  { minutes: 60, label: '1 h' },
  { minutes: 360, label: '6 h' },
] as const

/**
 * Escala de los medidores. Es solo de presentación: un rango razonable para la zona (Titicachi, ~3100 m),
 * no un umbral de alarma. Los valores fuera de la escala se dibujan en el extremo.
 */
export const GAUGE_RANGE: Record<string, { min: number; max: number }> = {
  temperatura: { min: -10, max: 40 },
  humedad_relativa: { min: 0, max: 100 },
  presion_atmosferica: { min: 600, max: 1100 },
  velocidad_viento: { min: 0, max: 20 },
  niebla: { min: 0, max: 100 },
  nivel_almacenamiento: { min: 0, max: 200 },
}

/** Humedad a partir de la cual el aire está prácticamente saturado: condición de niebla. */
export const FOG_HUMIDITY = 95

export function gaugeFraction(value: number, range: { min: number; max: number }): number {
  return Math.min(1, Math.max(0, (value - range.min) / (range.max - range.min)))
}

export type Freshness = 'en_vivo' | 'retrasada' | 'sin_conexion'

/**
 * Estado de la comunicación según el intervalo configurado: en vivo si la última lectura llegó dentro de
 * tres intervalos (más un margen de 10 s por el envío), retrasada si no, y sin conexión si el servidor ya
 * la marca como desactualizada.
 */
export function freshness(lastSeen: string | null, intervalS: number, isStale: boolean, now: number): Freshness {
  if (!lastSeen || isStale) return 'sin_conexion'
  const ageS = (now - new Date(lastSeen).getTime()) / 1000
  return ageS <= intervalS * 3 + 10 ? 'en_vivo' : 'retrasada'
}

export function ageText(iso: string | null, now: number): string {
  if (!iso) return 'nunca'
  const s = Math.max(0, Math.round((now - new Date(iso).getTime()) / 1000))
  if (s < 60) return `hace ${s} s`
  const m = Math.floor(s / 60)
  if (m < 60) return `hace ${m} min ${s % 60} s`
  return `hace ${Math.floor(m / 60)} h ${m % 60} min`
}

/** Diferencia entre la última lectura y la anterior (null si hay menos de dos). */
export function trend(points: LivePoint[]): number | null {
  if (points.length < 2) return null
  return points[points.length - 1]!.v - points[points.length - 2]!.v
}

export interface ChartPoint {
  t: number
  v: number | null
}

/** Puntos para el gráfico, cortando la línea donde faltan más de tres lecturas seguidas (sin inventar datos). */
export function withGaps(points: LivePoint[], intervalS: number): ChartPoint[] {
  const out: ChartPoint[] = []
  let prev: number | null = null
  for (const p of points) {
    const t = new Date(p.t).getTime()
    if (prev !== null && t - prev > intervalS * 3 * 1000 + 10_000) out.push({ t: prev + 1, v: null })
    out.push({ t, v: p.v })
    prev = t
  }
  return out
}
