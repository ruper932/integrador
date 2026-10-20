import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import { ErrorAlert, Loading, PageHeader, Pagination } from '@/components/common'
import { Card, CardContent } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { api } from '@/lib/api'
import { FilterToolbar } from '@/features/reports/FilterToolbar'
import { listParams } from '@/features/reports/params'
import type { FilterValues } from '@/features/reports/ReportFilterField'
import { formatDateTime } from '@/lib/format'
import type { AuditLog, Page } from '@/types/api'

const LIMIT = 50
const LIST_FILTERS = ['date_range', 'action', 'actor_id']

export function AuditPage() {
  const [filters, setFilters] = useState<FilterValues>({})
  const [offset, setOffset] = useState(0)
  const logs = useQuery({
    queryKey: ['audit', filters, offset],
    queryFn: async () => {
      const params = { ...listParams(LIST_FILTERS, filters, { actor_id: 'user_id' }), offset, limit: LIMIT }
      return (await api.get<Page<AuditLog>>('/admin/audit-logs', { params })).data
    },
  })

  return (
    <>
      <PageHeader
        eyebrow="Administración"
        title="Auditoría"
        description="Registro de operaciones relevantes y administrativas."
      />
      <FilterToolbar
        kinds={['auditoria']}
        keys={LIST_FILTERS}
        values={filters}
        onChange={(v) => {
          setOffset(0)
          setFilters(v)
        }}
      />
      <ErrorAlert error={logs.error} />
      {logs.isLoading ? (
        <Loading />
      ) : (
        <Card>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Fecha</TableHead>
                  <TableHead>Usuario</TableHead>
                  <TableHead>Acción</TableHead>
                  <TableHead>Entidad</TableHead>
                  <TableHead>Detalle</TableHead>
                  <TableHead>IP</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {logs.data?.items.map((log) => (
                  <TableRow key={log.id}>
                    <TableCell>{formatDateTime(log.created_at)}</TableCell>
                    <TableCell>{log.username ?? '—'}</TableCell>
                    <TableCell className="font-mono text-xs">{log.action}</TableCell>
                    <TableCell>{log.entity_type ? `${log.entity_type} #${log.entity_id ?? ''}` : '—'}</TableCell>
                    <TableCell className="max-w-sm truncate font-mono text-xs" title={JSON.stringify(log.details)}>
                      {log.details ? JSON.stringify(log.details) : '—'}
                    </TableCell>
                    <TableCell>{log.ip_address ?? '—'}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            {logs.data && <Pagination offset={offset} limit={LIMIT} total={logs.data.total} onChange={setOffset} />}
          </CardContent>
        </Card>
      )}
    </>
  )
}
