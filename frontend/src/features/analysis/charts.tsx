import { useState, type ReactNode } from 'react'
import {
  Area,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import { Button } from '@/components/ui/button'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { histogram, linearFit, movingAverage } from '@/features/analysis/stats'
import { formatNumber } from '@/lib/format'
import { cn } from '@/lib/utils'

// Colores del tema (validados con el verificador de paletas en claro y oscuro). Una serie por
// gráfico y un único eje Y; sin animaciones (equipos modestos).
const SERIES = 'var(--chart-1)'
const POSITIVE = 'var(--chart-pos)'
const NEGATIVE = 'var(--chart-neg)'
const GRID = 'var(--grid)'
const AXIS = 'var(--muted-foreground)'
const tick = { fill: AXIS, fontSize: 11 }
const tooltipStyle = {
  labelStyle: { color: 'var(--foreground)', fontWeight: 584 },
  itemStyle: { color: 'var(--foreground)' },
  contentStyle: {
    background: 'var(--popover)',
    border: '1px solid var(--border)',
    borderRadius: 8,
    fontSize: 12,
    boxShadow: 'var(--shadow)',
  },
}

const dayLabel = (iso: string) =>
  new Intl.DateTimeFormat('es-BO', { day: '2-digit', month: 'short', timeZone: 'UTC' }).format(new Date(`${iso}T00:00:00Z`))

/** Botones segmentados para cambiar la vista de un gráfico. */
export function Segmented<T extends string>({
  value,
  options,
  onChange,
  label,
}: {
  value: T
  options: [T, string][]
  onChange: (v: T) => void
  label: string
}) {
  return (
    <div className="bg-muted inline-flex rounded-lg border p-0.5" role="group" aria-label={label}>
      {options.map(([key, text]) => (
        <button
          key={key}
          type="button"
          aria-pressed={value === key}
          onClick={() => onChange(key)}
          className={cn(
            'rounded-md px-2.5 py-1 text-xs',
            value === key ? 'bg-card text-foreground shadow-card font-medium' : 'text-muted-foreground hover:text-foreground',
          )}
        >
          {text}
        </button>
      ))}
    </div>
  )
}

/** Gráfico con alternativa en tabla (accesible y útil para copiar los datos). */
export function ChartOrTable({ chart, table, title }: { chart: ReactNode; table: ReactNode; title: string }) {
  const [asTable, setAsTable] = useState(false)
  return (
    <div className="grid gap-2">
      <div className="flex justify-end">
        <Button type="button" size="sm" variant="ghost" className="h-7 text-xs" onClick={() => setAsTable(!asTable)}>
          {asTable ? 'Ver gráfico' : 'Ver tabla'}
          <span className="sr-only"> de {title}</span>
        </Button>
      </div>
      {asTable ? table : chart}
    </div>
  )
}

// --- Captación diaria: barras, línea o acumulado, con media móvil opcional ------------------

export type DailyMode = 'bars' | 'line' | 'cumulative'


export function DailyCaptureChart({
  points,
  mode,
  showAverage,
  mean,
}: {
  points: { date: string; value: number }[]
  mode: DailyMode
  showAverage: boolean
  mean: number | null
}) {
  const cumulative = points.reduce<number[]>((acc, p) => [...acc, (acc.at(-1) ?? 0) + p.value], [])
  const avg = movingAverage(
    points.map((p) => p.value),
    7,
  )
  const data = points.map((p, i) => ({
    x: dayLabel(p.date),
    value: mode === 'cumulative' ? cumulative[i] : p.value,
    avg: avg[i],
  }))
  const unit = 'L'
  return (
    <div className="h-72 w-full" role="img" aria-label="Captación diaria en litros">
      <ResponsiveContainer>
        <ComposedChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -8 }} barCategoryGap="22%">
          <CartesianGrid vertical={false} stroke={GRID} strokeDasharray="3 5" />
          <XAxis dataKey="x" tick={tick} tickLine={false} axisLine={false} minTickGap={16} />
          <YAxis tick={tick} tickLine={false} axisLine={false} width={52} tickFormatter={(v: number) => formatNumber(v, 0)} />
          <Tooltip
            {...tooltipStyle}
            cursor={mode === 'bars' ? { fill: 'var(--muted)' } : { stroke: 'var(--border)' }}
            formatter={(value, name) => [
              `${formatNumber(Number(value))} ${unit}`,
              name === 'avg' ? 'Media móvil 7 días' : mode === 'cumulative' ? 'Acumulado' : 'Captado',
            ]}
          />
          {mode === 'bars' && <Bar dataKey="value" fill={SERIES} radius={[4, 4, 0, 0]} maxBarSize={28} isAnimationActive={false} />}
          {mode !== 'bars' && (
            <Area
              dataKey="value"
              stroke={SERIES}
              strokeWidth={2}
              fill={SERIES}
              fillOpacity={0.1}
              dot={false}
              activeDot={{ r: 5, stroke: 'var(--card)', strokeWidth: 2, fill: SERIES }}
              isAnimationActive={false}
            />
          )}
          {showAverage && mode !== 'cumulative' && (
            <Line dataKey="avg" stroke="var(--foreground)" strokeWidth={2} strokeDasharray="5 4" dot={false} isAnimationActive={false} />
          )}
          {mean !== null && mode !== 'cumulative' && (
            <ReferenceLine
              y={mean}
              stroke={AXIS}
              strokeDasharray="2 4"
              label={{ value: `media ${formatNumber(mean, 1)} L`, position: 'insideTopRight', fill: AXIS, fontSize: 11 }}
            />
          )}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}

// --- Histograma: cuántos días cayeron en cada rango de captación ---------------------------


export function Histogram({ values, color = 'var(--chart-4)' }: { values: number[]; color?: string }) {
  const data = histogram(values).map((b) => ({ ...b, x: `${formatNumber(b.from, 0)}–${formatNumber(b.to, 0)}` }))
  return (
    <div className="h-64 w-full" role="img" aria-label="Distribución de la captación diaria">
      <ResponsiveContainer>
        <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -16 }} barCategoryGap={2}>
          <CartesianGrid vertical={false} stroke={GRID} strokeDasharray="3 5" />
          <XAxis dataKey="x" tick={tick} tickLine={false} axisLine={false} />
          <YAxis allowDecimals={false} tick={tick} tickLine={false} axisLine={false} width={40} />
          <Tooltip
            {...tooltipStyle}
            cursor={{ fill: 'var(--muted)' }}
            labelFormatter={(label) => `${label} L por día`}
            formatter={(value) => [`${value} días`, 'Frecuencia']}
          />
          <Bar dataKey="count" fill={color} radius={[4, 4, 0, 0]} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

// --- Correlaciones (barras divergentes, seleccionables) y dispersión ------------------------

export function CorrelationBars({
  rows,
  selected,
  onSelect,
}: {
  rows: { code: string; name: string; r: number | null; strength: string }[]
  selected: string | null
  onSelect: (code: string) => void
}) {
  const data = rows.filter((r) => r.r !== null)
  return (
    <div className="w-full" style={{ height: 32 * data.length + 40 }} role="img" aria-label="Correlación de cada variable con la captación">
      <ResponsiveContainer>
        <BarChart data={data} layout="vertical" margin={{ top: 4, right: 40, bottom: 0, left: 8 }} barCategoryGap={6}>
          <CartesianGrid horizontal={false} stroke={GRID} strokeDasharray="3 5" />
          <XAxis type="number" domain={[-1, 1]} ticks={[-1, -0.5, 0, 0.5, 1]} tick={tick} tickLine={false} axisLine={false} />
          <YAxis type="category" dataKey="name" width={150} tick={tick} tickLine={false} axisLine={false} />
          <ReferenceLine x={0} stroke={AXIS} />
          <Tooltip
            {...tooltipStyle}
            cursor={{ fill: 'var(--muted)' }}
            formatter={(value, _name, item) => [`${formatNumber(Number(value), 2)} · ${item.payload.strength}`, 'r de Pearson']}
          />
          <Bar
            dataKey="r"
            radius={4}
            isAnimationActive={false}
            label={{ position: 'right', fill: 'var(--foreground)', fontSize: 11, formatter: (v: unknown) => formatNumber(Number(v), 2) }}
          >
            {data.map((row) => (
              <Cell
                key={row.code}
                fill={(row.r ?? 0) >= 0 ? POSITIVE : NEGATIVE}
                fillOpacity={selected === null || selected === row.code ? 1 : 0.45}
                cursor="pointer"
                onClick={() => onSelect(row.code)}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}


export function ScatterPlot({
  points,
  xName,
  xUnit,
}: {
  points: { date: string; x: number; y: number }[]
  xName: string
  xUnit: string
}) {
  const fit = linearFit(points)
  const xs = points.map((p) => p.x)
  const [x0, x1] = [Math.min(...xs), Math.max(...xs)]
  return (
    <div className="h-72 w-full" role="img" aria-label={`Dispersión de captación diaria frente a ${xName}`}>
      <ResponsiveContainer>
        <ScatterChart margin={{ top: 8, right: 16, bottom: 16, left: -8 }}>
          <CartesianGrid stroke={GRID} strokeDasharray="3 5" />
          <XAxis
            type="number"
            dataKey="x"
            name={xName}
            domain={['auto', 'auto']}
            tick={tick}
            tickLine={false}
            axisLine={false}
            label={{ value: `${xName} (${xUnit})`, position: 'insideBottom', offset: -10, fill: AXIS, fontSize: 11 }}
          />
          <YAxis
            type="number"
            dataKey="y"
            name="Captación"
            domain={[0, 'auto']}
            tick={tick}
            tickLine={false}
            axisLine={false}
            width={52}
            tickFormatter={(v: number) => `${formatNumber(v, 0)} L`}
          />
          <Tooltip
            {...tooltipStyle}
            cursor={{ strokeDasharray: '3 3', stroke: 'var(--border)' }}
            labelFormatter={() => ''}
            formatter={(value, name) => [
              name === 'Captación' ? `${formatNumber(Number(value))} L` : `${formatNumber(Number(value))} ${xUnit}`,
              name,
            ]}
          />
          {fit && x0 !== x1 && (
            <ReferenceLine
              segment={[
                { x: x0, y: fit.a + fit.b * x0 },
                { x: x1, y: fit.a + fit.b * x1 },
              ]}
              stroke="var(--foreground)"
              strokeDasharray="5 4"
              ifOverflow="hidden"
            />
          )}
          <Scatter data={points} fill={SERIES} stroke="var(--card)" strokeWidth={2} isAnimationActive={false} />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  )
}

// --- Barras horizontales de categorías (estados, tipos, atrapanieblas, repuestos) -----------

export function CategoryBars({
  rows,
  unit = '',
  color = SERIES,
}: {
  rows: { label: string; value: number }[]
  unit?: string
  color?: string
}) {
  const total = rows.reduce((s, r) => s + r.value, 0)
  if (total === 0) return <p className="text-muted-foreground text-sm">Sin registros en el periodo.</p>
  const data = [...rows].sort((a, b) => b.value - a.value)
  return (
    <div className="w-full" style={{ height: 30 * data.length + 16 }} role="img" aria-label="Distribución por categoría">
      <ResponsiveContainer>
        <BarChart data={data} layout="vertical" margin={{ top: 0, right: 72, bottom: 0, left: 8 }} barCategoryGap={6}>
          <XAxis type="number" hide />
          <YAxis type="category" dataKey="label" width={170} tick={tick} tickLine={false} axisLine={false} />
          <Tooltip
            {...tooltipStyle}
            cursor={{ fill: 'var(--muted)' }}
            formatter={(value) => [`${formatNumber(Number(value), unit ? 1 : 0)}${unit} · ${formatNumber((Number(value) / total) * 100, 1)} %`, 'Total']}
          />
          <Bar
            dataKey="value"
            fill={color}
            radius={4}
            isAnimationActive={false}
            label={{
              position: 'right',
              fill: 'var(--foreground)',
              fontSize: 11,
              formatter: (v: unknown) => `${formatNumber(Number(v), unit ? 1 : 0)}${unit}`,
            }}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

/** Tabla simple de categorías (alternativa accesible a CategoryBars). */
export function CategoryTable({ rows, unit = '' }: { rows: { label: string; value: number }[]; unit?: string }) {
  const total = rows.reduce((s, r) => s + r.value, 0)
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Categoría</TableHead>
          <TableHead className="text-right">Total</TableHead>
          <TableHead className="text-right">%</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {[...rows]
          .sort((a, b) => b.value - a.value)
          .map((r) => (
            <TableRow key={r.label}>
              <TableCell>{r.label}</TableCell>
              <TableCell className="text-right tabular-nums">
                {formatNumber(r.value, unit ? 1 : 0)}
                {unit}
              </TableCell>
              <TableCell className="text-right tabular-nums">{total ? formatNumber((r.value / total) * 100, 1) : '—'}</TableCell>
            </TableRow>
          ))}
      </TableBody>
    </Table>
  )
}
