// Cálculos para los gráficos del análisis (sin dependencias).

export function movingAverage(values: number[], window: number): (number | null)[] {
  return values.map((_, i) => (i + 1 < window ? null : values.slice(i + 1 - window, i + 1).reduce((a, b) => a + b, 0) / window))
}

export function histogram(values: number[]): { from: number; to: number; count: number }[] {
  if (values.length === 0) return []
  const min = Math.min(...values)
  const max = Math.max(...values)
  const bins = Math.max(1, Math.ceil(Math.log2(values.length) + 1)) // regla de Sturges
  const width = (max - min) / bins || 1
  const out = Array.from({ length: bins }, (_, i) => ({ from: min + i * width, to: min + (i + 1) * width, count: 0 }))
  for (const v of values) out[Math.min(bins - 1, Math.floor((v - min) / width))]!.count += 1
  return out
}

/** Recta de mínimos cuadrados (y = a + b·x); null si x no varía. */
export function linearFit(points: { x: number; y: number }[]): { a: number; b: number } | null {
  const n = points.length
  if (n < 2) return null
  const mx = points.reduce((s, p) => s + p.x, 0) / n
  const my = points.reduce((s, p) => s + p.y, 0) / n
  const sxx = points.reduce((s, p) => s + (p.x - mx) ** 2, 0)
  if (sxx === 0) return null
  const b = points.reduce((s, p) => s + (p.x - mx) * (p.y - my), 0) / sxx
  return { a: my - b * mx, b }
}
