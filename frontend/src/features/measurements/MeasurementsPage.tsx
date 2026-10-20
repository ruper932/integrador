import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import { ErrorAlert, Loading, PageHeader, Pagination, StatusBadge } from '@/components/common'
import { Card, CardContent } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { useDevices, useSensors } from '@/features/devices/api'
import { api } from '@/lib/api'
import { FilterToolbar } from '@/features/reports/FilterToolbar'
import { listParams } from '@/features/reports/params'
import type { FilterValues } from '@/features/reports/ReportFilterField'
import { QUALITY_LABELS, formatDateTime, formatNumber } from '@/lib/format'
import type { Page, Reading } from '@/types/api'

const LIMIT = 50
const LIST_FILTERS = ['date_range', 'device_id', 'fog_collector_id', 'sensor_type', 'quality']

export function MeasurementsPage() {
  const [filters, setFilters] = useState<FilterValues>({})
  const [offset, setOffset] = useState(0)
  const devices = useDevices()
  const sensors = useSensors()

  const readings = useQuery({
    queryKey: ['measurements', filters, offset],
    queryFn: async () => {
      const params = { ...listParams(LIST_FILTERS, filters), offset, limit: LIMIT }
      return (await api.get<Page<Reading>>('/measurements', { params })).data
    },
  })

  const sensorById = new Map((sensors.data ?? []).map((s) => [s.id, s]))
  const deviceById = new Map((devices.data ?? []).map((d) => [d.id, d]))

  return (
    <>
      <PageHeader
        eyebrow="Principal"
        title="Histórico de lecturas"
        description="Lecturas recibidas desde las estaciones, con su estado de calidad."
      />
      <FilterToolbar
        kinds={['mediciones', 'volumen', 'variable']}
        keys={LIST_FILTERS}
        values={filters}
        onChange={(v) => {
          setOffset(0)
          setFilters(v)
        }}
      />

      <ErrorAlert error={readings.error} />
      {readings.isLoading ? (
        <Loading />
      ) : (
        <Card>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Medido</TableHead>
                  <TableHead>Recibido</TableHead>
                  <TableHead>Dispositivo / sensor</TableHead>
                  <TableHead className="text-right">Valor</TableHead>
                  <TableHead>Calidad</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {readings.data?.items.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={5} className="text-muted-foreground text-center">
                      Sin lecturas para los filtros seleccionados.
                    </TableCell>
                  </TableRow>
                )}
                {readings.data?.items.map((r) => {
                  const sensor = sensorById.get(r.sensor_id)
                  return (
                    <TableRow key={r.id}>
                      <TableCell>{formatDateTime(r.measured_at)}</TableCell>
                      <TableCell className="text-muted-foreground">{formatDateTime(r.received_at)}</TableCell>
                      <TableCell>
                        {deviceById.get(r.device_id)?.code ?? r.device_id} / {sensor?.code ?? r.sensor_id}
                        <div className="text-muted-foreground text-xs">{sensor?.sensor_type.name}</div>
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {r.value === null ? '—' : `${formatNumber(r.value)} ${r.unit}`}
                      </TableCell>
                      <TableCell title={r.quality_detail ?? undefined}>
                        <StatusBadge value={r.quality} label={QUALITY_LABELS[r.quality]} />
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
            {readings.data && (
              <Pagination offset={offset} limit={LIMIT} total={readings.data.total} onChange={setOffset} />
            )}
          </CardContent>
        </Card>
      )}
    </>
  )
}
