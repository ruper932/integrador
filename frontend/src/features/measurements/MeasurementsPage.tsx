import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import { ErrorAlert, Field, Loading, NativeSelect, PageHeader, Pagination, StatusBadge } from '@/components/common'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { useDevices, useSensorTypes, useSensors } from '@/features/devices/api'
import { api } from '@/lib/api'
import { ExportReportButton } from '@/features/reports/ExportReportButton'
import { QUALITY_LABELS, formatDateTime, formatNumber } from '@/lib/format'
import type { Page, Reading } from '@/types/api'

const LIMIT = 50

export function MeasurementsPage() {
  const [filters, setFilters] = useState({ device_id: '', sensor_type: '', quality: '', date_from: '', date_to: '' })
  const [offset, setOffset] = useState(0)
  const devices = useDevices()
  const sensorTypes = useSensorTypes()
  const sensors = useSensors()

  const readings = useQuery({
    queryKey: ['measurements', filters, offset],
    queryFn: async () => {
      const params: Record<string, string | number> = { offset, limit: LIMIT }
      if (filters.device_id) params.device_id = filters.device_id
      if (filters.sensor_type) params.sensor_type = filters.sensor_type
      if (filters.quality) params.quality = filters.quality
      if (filters.date_from) params.date_from = new Date(filters.date_from).toISOString()
      if (filters.date_to) params.date_to = new Date(filters.date_to).toISOString()
      return (await api.get<Page<Reading>>('/measurements', { params })).data
    },
  })

  const update = (key: keyof typeof filters) => (e: { target: { value: string } }) => {
    setOffset(0)
    setFilters((f) => ({ ...f, [key]: e.target.value }))
  }
  const sensorById = new Map((sensors.data ?? []).map((s) => [s.id, s]))
  const deviceById = new Map((devices.data ?? []).map((d) => [d.id, d]))

  return (
    <>
      <PageHeader
        eyebrow="Principal"
        title="Histórico de lecturas"
        description="Lecturas recibidas desde las estaciones, con su estado de calidad."
        actions={<ExportReportButton kinds={['mediciones', 'volumen', 'variable']} />}
      />
      <Card className="mb-4">
        <CardContent className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <Field label="Dispositivo" htmlFor="f-device">
            <NativeSelect id="f-device" value={filters.device_id} onChange={update('device_id')}>
              <option value="">Todos</option>
              {devices.data?.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                </option>
              ))}
            </NativeSelect>
          </Field>
          <Field label="Variable" htmlFor="f-type">
            <NativeSelect id="f-type" value={filters.sensor_type} onChange={update('sensor_type')}>
              <option value="">Todas</option>
              {sensorTypes.data?.map((t) => (
                <option key={t.code} value={t.code}>
                  {t.name}
                </option>
              ))}
            </NativeSelect>
          </Field>
          <Field label="Calidad" htmlFor="f-quality">
            <NativeSelect id="f-quality" value={filters.quality} onChange={update('quality')}>
              <option value="">Todas</option>
              {Object.entries(QUALITY_LABELS).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </NativeSelect>
          </Field>
          <Field label="Desde" htmlFor="f-from">
            <Input id="f-from" type="datetime-local" value={filters.date_from} onChange={update('date_from')} />
          </Field>
          <Field label="Hasta" htmlFor="f-to">
            <Input id="f-to" type="datetime-local" value={filters.date_to} onChange={update('date_to')} />
          </Field>
        </CardContent>
      </Card>

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
