import { useQuery } from '@tanstack/react-query'
import { BrainCircuit, CloudOff, Cpu } from 'lucide-react'

import { EmptyState, ErrorAlert, Loading, Notice, PageHeader } from '@/components/common'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableRow } from '@/components/ui/table'
import { api } from '@/lib/api'
import { formatCalendarDate, formatNumber, relativeTime } from '@/lib/format'
import type { ProvisionalPrediction, ProvisionalStation } from '@/types/api'

// Nombres legibles de las variables del modelo (backend/app/business/ml/features.py).
const VARIABLE_LABELS: Record<string, string> = {
  volumen_dia: 'Volumen del día base (L)',
  volumen_dia_anterior: 'Volumen del día anterior (L)',
  volumen_media_7d: 'Volumen medio de 7 días (L)',
  humedad_media: 'Humedad media (%)',
  humedad_max: 'Humedad máxima (%)',
  horas_humedad_95: 'Horas con humedad ≥ 95 %',
  temperatura_media: 'Temperatura media (°C)',
  temperatura_rango: 'Rango de temperatura (°C)',
  viento_medio: 'Viento medio (m/s)',
  presion_media: 'Presión media (hPa)',
  presion_cambio: 'Cambio de presión (hPa)',
  niebla_media: 'Niebla media (%)',
  horas_niebla_40: 'Horas con niebla ≥ 40 %',
  niebla_ultimas_6h: 'Niebla, últimas 6 h (%)',
  dia_anio_sen: 'Época del año (seno)',
  dia_anio_cos: 'Época del año (coseno)',
}

const litres = (value: number | null) => (value === null ? '—' : `${formatNumber(value, 1)} L`)

function StationCard({ station }: { station: ProvisionalStation }) {
  const generated = station.estado === 'generada'
  return (
    <Card>
      <CardContent className="grid gap-4">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <div className="text-muted-foreground text-xs">{station.device_code}</div>
            <h2 className="text-lg font-semibold">{station.device_name}</h2>
            <div className="text-muted-foreground text-sm">
              {station.fog_collector ?? 'Sin atrapanieblas'}
              {station.mesh_area_m2 !== null && ` · malla de ${formatNumber(station.mesh_area_m2, 0)} m²`}
            </div>
          </div>
          <Badge variant="success">
            <Cpu aria-hidden /> Conectada · {relativeTime(station.last_seen_at)}
          </Badge>
        </div>

        <div className="grid gap-3 sm:grid-cols-3">
          <div className="bg-muted/60 rounded-lg border p-3">
            <div className="text-muted-foreground text-xs">Estimado para hoy</div>
            {generated ? (
              <div className="text-2xl font-semibold tabular-nums">{litres(station.resultado_litros)}</div>
            ) : (
              <div className="text-warning font-medium">Datos insuficientes</div>
            )}
          </div>
          <div className="rounded-lg border p-3">
            <div className="text-muted-foreground text-xs">Referencia: media de 7 días</div>
            <div className="text-xl font-semibold tabular-nums">{litres(station.referencia_media_7d_litros)}</div>
          </div>
          <div className="rounded-lg border p-3">
            <div className="text-muted-foreground text-xs">Captado hoy hasta ahora</div>
            <div className="text-xl font-semibold tabular-nums">{litres(station.captado_hoy_litros)}</div>
          </div>
        </div>

        {station.faltantes.length > 0 && (
          <p className="text-muted-foreground text-sm">
            {generated ? 'Estimado sin: ' : 'Faltan datos de: '}
            {station.faltantes.map((f) => VARIABLE_LABELS[f] ?? f).join(', ')}.
          </p>
        )}

        <details>
          <summary className="cursor-pointer text-sm font-medium">Variables usadas por el modelo</summary>
          <Table className="mt-2">
            <TableBody>
              {Object.entries(station.variables).map(([key, value]) => (
                <TableRow key={key}>
                  <TableCell>{VARIABLE_LABELS[key] ?? key}</TableCell>
                  <TableCell className="text-right tabular-nums">{value === null ? 'sin dato' : formatNumber(value, 2)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </details>
      </CardContent>
    </Card>
  )
}

export function ProvisionalPredictionPage() {
  const query = useQuery({
    queryKey: ['ml', 'provisional'],
    queryFn: async () => (await api.get<ProvisionalPrediction>('/ml/provisional')).data,
    refetchInterval: 5 * 60_000, // «en vivo»: se recalcula con las lecturas que van llegando
  })
  const data = query.data
  const model = data?.metricas_simulacion?.modelo
  const reference = data?.metricas_simulacion?.referencia_media_7d

  return (
    <>
      <PageHeader
        eyebrow="Principal"
        title="Estimación de volumen"
        description={
          data
            ? `Volumen estimado para hoy (${formatCalendarDate(data.fecha_predicha)}) con los datos de las estaciones conectadas hasta el cierre de ayer.`
            : 'Volumen estimado para hoy con los datos de las estaciones conectadas.'
        }
        actions={
          <Badge variant="warning">
            <BrainCircuit aria-hidden /> Provisional
          </Badge>
        }
      />
      <ErrorAlert error={query.error} />
      {query.isLoading && <Loading />}
      {data && (
        <div className="grid gap-5">
          <Notice tone="warning" title="Módulo provisional">
            El modelo {data.version_modelo ?? ''} se entrenó con datos simulados: muestra el flujo funcionando con
            lecturas reales, pero sus cifras no están validadas. No lo use para planificar el riego hasta contar con el
            modelo entrenado con datos del C.E.A.
          </Notice>
          {!data.modelo_disponible && <Notice tone="danger" title="Modelo no disponible">{data.motivo}</Notice>}

          {data.modelo_disponible &&
            (data.estaciones.length === 0 ? (
              <Card>
                <CardContent>
                  <EmptyState
                    icon={CloudOff}
                    title="Sin datos disponibles"
                    description="No hay estaciones meteorológicas conectadas en este momento. La estimación aparece cuando alguna envía datos."
                  />
                </CardContent>
              </Card>
            ) : (
              <div className="grid gap-5 xl:grid-cols-2">
                {data.estaciones.map((s) => (
                  <StationCard key={s.device_id} station={s} />
                ))}
              </div>
            ))}

          {model && reference && (
            <p className="text-muted-foreground text-xs">
              En la simulación el modelo se equivocó en promedio {formatNumber(model.mae_litros, 1)} L/día; la
              referencia simple (media de 7 días), {formatNumber(reference.mae_litros, 1)} L/día. Por eso se muestran
              juntas.
            </p>
          )}
        </div>
      )}
    </>
  )
}
