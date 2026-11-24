import { Area, AreaChart, Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

import { EmptyState } from '@/components/common'
import { formatNumber } from '@/lib/format'
import type { Bucket, Series } from '@/types/api'
import { BarChart3 } from 'lucide-react'

// Colores tomados del tema (claro/oscuro) mediante variables CSS.
// Una sola serie por gráfico (el título la nombra) y un único eje Y. Sin animaciones:
// los equipos de la institución pueden ser modestos. Cada variable tiene su color para
// reconocerla de un vistazo; las no listadas usan el azul del agua.
export const SERIES_COLOR: Record<string, string> = {
  temperatura: 'var(--chart-3)',
  humedad_relativa: 'var(--chart-2)',
  presion_atmosferica: 'var(--chart-4)',
  velocidad_viento: 'var(--chart-5)',
  direccion_viento: 'var(--chart-5)',
  niebla: 'var(--chart-4)',
}
const GRID = 'var(--grid)'
const AXIS = 'var(--muted-foreground)'

const bucketFormat: Record<Bucket, Intl.DateTimeFormatOptions> = {
  hour: { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' },
  day: { day: '2-digit', month: 'short' },
  week: { day: '2-digit', month: 'short' },
  month: { month: 'short', year: 'numeric' },
}

function label(bucket: string, kind: Bucket): string {
  return new Intl.DateTimeFormat('es-BO', { ...bucketFormat[kind], timeZone: 'America/La_Paz' }).format(new Date(bucket))
}

/** Total del periodo (variables incrementales) o promedio (instantáneas). */
export function seriesSummary(series: Series): { value: number | null; suffix: string } {
  const values = series.points.map((p) => p.value).filter((v): v is number => v !== null)
  const incremental = series.aggregation === 'incremental'
  const suffix = incremental ? 'en el periodo' : 'de promedio'
  if (values.length === 0) return { value: null, suffix }
  const sum = values.reduce((a, b) => a + b, 0)
  return { value: incremental ? sum : sum / values.length, suffix }
}

export function SeriesChart({ series }: { series: Series }) {
  const unit = series.sensor_type.unit
  const SERIES = SERIES_COLOR[series.sensor_type.code] ?? 'var(--chart-1)'
  const incremental = series.aggregation === 'incremental'
  const data = series.points.map((p) => ({ x: label(p.bucket, series.bucket), value: p.value, count: p.count }))

  if (data.length === 0) {
    return (
      <EmptyState
        icon={BarChart3}
        title="Sin lecturas válidas en el periodo"
        description="Cuando la estación envíe mediciones, se mostrarán aquí."
      />
    )
  }

  const common = (
    <>
      <CartesianGrid vertical={false} stroke={GRID} strokeDasharray="3 5" />
      <XAxis dataKey="x" tick={{ fill: AXIS, fontSize: 12 }} tickLine={false} axisLine={false} minTickGap={16} />
      <YAxis
        tick={{ fill: AXIS, fontSize: 12 }}
        tickLine={false}
        axisLine={false}
        width={52}
        tickFormatter={(v: number) => formatNumber(v, 1)}
      />
      <Tooltip
        cursor={incremental ? { fill: 'var(--muted)' } : { stroke: 'var(--border)' }}
        formatter={(value) => [`${formatNumber(Number(value))} ${unit}`, incremental ? 'Total' : 'Promedio']}
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
    </>
  )

  return (
    <div className="h-72 w-full" role="img" aria-label={`Gráfico de ${series.sensor_type.name} por intervalo`}>
      <ResponsiveContainer>
        {incremental ? (
          <BarChart data={data} margin={{ top: 8, right: 4, bottom: 0, left: -8 }} barCategoryGap="22%">
            {common}
            <Bar dataKey="value" fill={SERIES} radius={[4, 4, 0, 0]} maxBarSize={34} isAnimationActive={false} />
          </BarChart>
        ) : (
          <AreaChart data={data} margin={{ top: 8, right: 4, bottom: 0, left: -8 }}>
            {common}
            <Area
              dataKey="value"
              stroke={SERIES}
              strokeWidth={2.5}
              fill={SERIES}
              fillOpacity={0.08}
              dot={false}
              activeDot={{ r: 5, stroke: 'var(--card)', strokeWidth: 2, fill: SERIES }}
              connectNulls={false}
              isAnimationActive={false}
            />
          </AreaChart>
        )}
      </ResponsiveContainer>
    </div>
  )
}
