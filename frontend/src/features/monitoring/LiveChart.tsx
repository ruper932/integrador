import { Area, AreaChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

import { formatNumber } from '@/lib/format'

import type { ChartPoint } from './rules'

const TZ = 'America/La_Paz'
const hhmm = new Intl.DateTimeFormat('es-BO', { hour: '2-digit', minute: '2-digit', timeZone: TZ })
const hhmmss = new Intl.DateTimeFormat('es-BO', { hour: '2-digit', minute: '2-digit', second: '2-digit', timeZone: TZ })

/** Serie en vivo: una variable, un eje, sin animación (se redibuja en cada muestreo). */
export function LiveChart({
  data,
  color,
  unit,
  name,
  from,
  to,
  average,
}: {
  data: ChartPoint[]
  color: string
  unit: string
  name: string
  from: number
  to: number
  average: number | null
}) {
  return (
    <div className="h-52 w-full" role="img" aria-label={`Gráfico en vivo de ${name}`}>
      <ResponsiveContainer>
        <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -8 }}>
          <CartesianGrid vertical={false} stroke="var(--grid)" strokeDasharray="3 5" />
          <XAxis
            dataKey="t"
            type="number"
            scale="time"
            domain={[from, to]}
            tickFormatter={(t: number) => hhmm.format(t)}
            tick={{ fill: 'var(--muted-foreground)', fontSize: 12 }}
            tickLine={false}
            axisLine={false}
            minTickGap={28}
          />
          <YAxis
            domain={[(min: number) => Math.floor(min - 1), (max: number) => Math.ceil(max + 1)]}
            tick={{ fill: 'var(--muted-foreground)', fontSize: 12 }}
            tickLine={false}
            axisLine={false}
            width={48}
            tickFormatter={(v: number) => formatNumber(v, 0)}
          />
          {average !== null && (
            <ReferenceLine
              y={average}
              stroke="var(--muted-foreground)"
              strokeDasharray="4 4"
              label={{ value: 'promedio', position: 'insideTopRight', fill: 'var(--muted-foreground)', fontSize: 11 }}
            />
          )}
          <Tooltip
            labelFormatter={(t) => hhmmss.format(Number(t))}
            formatter={(value) => [`${formatNumber(Number(value), 2)} ${unit}`, name]}
            cursor={{ stroke: 'var(--border)' }}
            labelStyle={{ color: 'var(--foreground)', fontWeight: 600 }}
            itemStyle={{ color: 'var(--foreground)' }}
            contentStyle={{
              background: 'var(--popover)',
              border: '1px solid var(--border)',
              borderRadius: 10,
              fontSize: 12,
              boxShadow: 'var(--shadow)',
            }}
          />
          <Area
            dataKey="v"
            stroke={color}
            strokeWidth={2}
            fill={color}
            fillOpacity={0.1}
            dot={false}
            activeDot={{ r: 4, stroke: 'var(--card)', strokeWidth: 2, fill: color }}
            connectNulls={false}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}
