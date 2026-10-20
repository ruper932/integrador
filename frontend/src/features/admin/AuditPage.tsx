import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import { ErrorAlert, Field, Loading, PageHeader, Pagination } from '@/components/common'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { api } from '@/lib/api'
import { ExportReportButton } from '@/features/reports/ExportReportButton'
import { formatDateTime } from '@/lib/format'
import type { AuditLog, Page } from '@/types/api'

const LIMIT = 50

export function AuditPage() {
  const [action, setAction] = useState('')
  const [offset, setOffset] = useState(0)
  const logs = useQuery({
    queryKey: ['audit', action, offset],
    queryFn: async () =>
      (await api.get<Page<AuditLog>>('/admin/audit-logs', { params: { action: action || undefined, offset, limit: LIMIT } }))
        .data,
  })

  return (
    <>
      <PageHeader
        eyebrow="Administración"
        title="Auditoría"
        description="Registro de operaciones relevantes y administrativas."
        actions={<ExportReportButton kinds={['auditoria']} />}
      />
      <div className="mb-4 w-72">
        <Field label="Acción exacta" htmlFor="a-action" hint="Ej.: auth.login_fallido, usuario.crear">
          <Input
            id="a-action"
            value={action}
            onChange={(e) => {
              setOffset(0)
              setAction(e.target.value.trim())
            }}
          />
        </Field>
      </div>
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
