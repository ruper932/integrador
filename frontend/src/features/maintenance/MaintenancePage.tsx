import { useQuery } from '@tanstack/react-query'
import { Plus } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'

import { ErrorAlert, Field, Loading, NativeSelect, PageHeader, Pagination, StatusBadge } from '@/components/common'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { useHasPermission } from '@/features/auth/useAuth'
import { IncidentStatusBadge } from '@/features/incidents/IncidentBits'
import { FINAL_LABELS, MAINTENANCE_STATUS_LABELS, TYPE_LABELS } from '@/features/maintenance/labels'
import { MaintenanceForm } from '@/features/maintenance/MaintenanceForm'
import { api } from '@/lib/api'
import { FilterToolbar } from '@/features/reports/FilterToolbar'
import { listParams } from '@/features/reports/params'
import type { FilterValues } from '@/features/reports/ReportFilterField'
import { formatDateTime, formatNumber } from '@/lib/format'
import type { MaintenanceRecord, MaintenanceStatus, Page } from '@/types/api'

const LIMIT = 25
const LIST_FILTERS = ['date_range', 'device_id', 'maintenance_type', 'final_status', 'responsible_id', 'origin']

export function MaintenancePage() {
  const can = useHasPermission()
  const [showForm, setShowForm] = useState(false)
  const [offset, setOffset] = useState(0)
  const [status, setStatus] = useState<MaintenanceStatus | ''>('')
  const [filters, setFilters] = useState<FilterValues>({})
  const records = useQuery({
    queryKey: ['maintenance', offset, status, filters],
    queryFn: async () => {
      const params = { ...listParams(LIST_FILTERS, filters), offset, limit: LIMIT, status: status || undefined }
      return (await api.get<Page<MaintenanceRecord>>('/maintenance', { params })).data
    },
  })

  return (
    <>
      <PageHeader
        eyebrow="Operaciones"
        title="Mantenimiento"
        description="Mantenimientos y reemplazos de componentes, incluidos los que atienden reportes de incidencia."
        actions={
          <>
            {can('mantenimiento.registrar') && (
              <Button onClick={() => setShowForm(!showForm)}>
                <Plus /> Registrar
              </Button>
            )}
          </>
        }
      />
      {showForm && (
        <Card className="mb-4">
          <CardContent>
            <MaintenanceForm onDone={() => setShowForm(false)} />
          </CardContent>
        </Card>
      )}
      <FilterToolbar
        kinds={['mantenimientos', 'inventario_consumo']}
        keys={LIST_FILTERS}
        values={filters}
        onChange={(v) => {
          setOffset(0)
          setFilters(v)
        }}
      >
        <Field label="Estado del mantenimiento" htmlFor="m-status">
          <NativeSelect
            id="m-status"
            value={status}
            onChange={(e) => {
              setStatus(e.target.value as MaintenanceStatus | '')
              setOffset(0)
            }}
          >
            <option value="">Todos</option>
            {(Object.keys(MAINTENANCE_STATUS_LABELS) as MaintenanceStatus[]).map((s) => (
              <option key={s} value={s}>
                {MAINTENANCE_STATUS_LABELS[s]}
              </option>
            ))}
          </NativeSelect>
        </Field>
      </FilterToolbar>
      <ErrorAlert error={records.error} />
      {records.isLoading ? (
        <Loading />
      ) : (
        <Card>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Fecha</TableHead>
                  <TableHead>Estado</TableHead>
                  <TableHead>Componente</TableHead>
                  <TableHead>Tipo</TableHead>
                  <TableHead>Descripción</TableHead>
                  <TableHead>Repuestos</TableHead>
                  <TableHead>Responsable</TableHead>
                  <TableHead>Estado final</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {records.data?.items.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={8} className="text-muted-foreground text-center">
                      Sin mantenimientos registrados.
                    </TableCell>
                  </TableRow>
                )}
                {records.data?.items.map((r) => (
                  <TableRow key={r.id}>
                    <TableCell>{formatDateTime(r.performed_at ?? r.started_at ?? r.accepted_at)}</TableCell>
                    <TableCell className="min-w-32">
                      <div className="grid justify-items-start gap-1">
                        <IncidentStatusBadge status={r.status} />
                        {r.incident_report_id && (
                          <Link
                            to={`/incidencias?reporte=${r.incident_report_id}`}
                            className="text-foreground text-xs underline decoration-primary decoration-2 underline-offset-2"
                          >
                            Reporte #{r.incident_report_id}
                          </Link>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      {r.device_code ?? '—'}
                      {r.sensor_code && ` / ${r.sensor_code}`}
                    </TableCell>
                    <TableCell>{r.maintenance_type ? TYPE_LABELS[r.maintenance_type] : '—'}</TableCell>
                    <TableCell className="max-w-xs whitespace-normal">
                      {r.description ?? <span className="text-muted-foreground">Pendiente de finalizar</span>}
                    </TableCell>
                    <TableCell className="whitespace-normal">
                      {r.items.length === 0
                        ? '—'
                        : r.items.map((i) => `${i.item_code} × ${formatNumber(i.quantity, 3)}`).join(', ')}
                    </TableCell>
                    <TableCell>{r.user_full_name}</TableCell>
                    <TableCell>
                      {r.final_status ? <StatusBadge value={r.final_status} label={FINAL_LABELS[r.final_status]} /> : '—'}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            {records.data && <Pagination offset={offset} limit={LIMIT} total={records.data.total} onChange={setOffset} />}
          </CardContent>
        </Card>
      )}
    </>
  )
}
