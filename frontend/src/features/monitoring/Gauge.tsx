import { formatNumber } from '@/lib/format'

import { gaugeFraction } from './rules'

const CX = 100
const CY = 100
const R = 78

function point(fraction: number, radius = R): [number, number] {
  const angle = Math.PI * (1 - fraction)
  return [CX + radius * Math.cos(angle), CY - radius * Math.sin(angle)]
}

function arc(from: number, to: number, radius = R): string {
  const [x1, y1] = point(from, radius)
  const [x2, y2] = point(to, radius)
  return `M ${x1.toFixed(2)} ${y1.toFixed(2)} A ${radius} ${radius} 0 0 1 ${x2.toFixed(2)} ${y2.toFixed(2)}`
}

function Tick({ fraction, label }: { fraction: number; label: string }) {
  const [x1, y1] = point(fraction, R - 12)
  const [x2, y2] = point(fraction, R + 12)
  return (
    <line x1={x1} y1={y1} x2={x2} y2={y2} stroke="var(--foreground)" strokeWidth={2} strokeLinecap="round">
      <title>{label}</title>
    </line>
  )
}

/**
 * Medidor semicircular al estilo de los paneles de centros de datos: arco con el valor actual,
 * marcas del mínimo y el máximo de la ventana y, opcionalmente, una banda resaltada (p. ej. niebla).
 */
export function Gauge({
  value,
  unit,
  label,
  color,
  range,
  windowMin,
  windowMax,
  band,
  dimmed,
}: {
  value: number | null
  unit: string
  label: string
  color: string
  range: { min: number; max: number }
  windowMin?: number | null
  windowMax?: number | null
  band?: { from: number; label: string }
  dimmed?: boolean
}) {
  const f = value === null ? 0 : gaugeFraction(value, range)
  const digits = Math.abs(range.max - range.min) >= 200 ? 0 : 1
  return (
    <div
      role="meter"
      aria-label={label}
      aria-valuemin={range.min}
      aria-valuemax={range.max}
      aria-valuenow={value ?? undefined}
      aria-valuetext={value === null ? 'sin lectura' : `${formatNumber(value, digits)} ${unit}`}
      className={dimmed ? 'opacity-55' : undefined}
    >
      <svg viewBox="0 0 200 118" className="w-full max-w-60">
        <path d={arc(0, 1)} fill="none" stroke="var(--muted)" strokeWidth={14} strokeLinecap="round" />
        {band && (
          <path
            d={arc(gaugeFraction(band.from, range), 1, R + 13)}
            fill="none"
            stroke="var(--chart-1)"
            strokeWidth={4}
            strokeLinecap="round"
          >
            <title>{band.label}</title>
          </path>
        )}
        {value !== null && f > 0.005 && (
          <path d={arc(0, f)} fill="none" stroke={color} strokeWidth={14} strokeLinecap="round" />
        )}
        {windowMin != null && <Tick fraction={gaugeFraction(windowMin, range)} label="Mínimo de la ventana" />}
        {windowMax != null && <Tick fraction={gaugeFraction(windowMax, range)} label="Máximo de la ventana" />}
        <text x={CX} y={CY - 14} textAnchor="middle" className="fill-foreground" fontSize={28} fontWeight={600}>
          {value === null ? '—' : formatNumber(value, digits)}
        </text>
        <text x={CX} y={CY + 4} textAnchor="middle" className="fill-muted-foreground" fontSize={12}>
          {unit}
        </text>
        <text x={CX - R} y={CY + 16} textAnchor="middle" className="fill-muted-foreground" fontSize={10}>
          {formatNumber(range.min, 0)}
        </text>
        <text x={CX + R} y={CY + 16} textAnchor="middle" className="fill-muted-foreground" fontSize={10}>
          {formatNumber(range.max, 0)}
        </text>
      </svg>
    </div>
  )
}
