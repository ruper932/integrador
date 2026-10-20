import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, Download, Lock, Plus } from 'lucide-react'
import { useEffect, useState } from 'react'

import { ErrorAlert, Field, Loading, StatusBadge } from '@/components/common'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { useHasPermission } from '@/features/auth/useAuth'
import { api, downloadFile } from '@/lib/api'
import { formatDate, formatNumber } from '@/lib/format'
import type { InventoryPeriod, PeriodSummary } from '@/types/api'

const QTY = /^\d+(\.\d{1,3})?$/

function money(value: string | null): string {
  return value === null ? 'sin costo' : `Bs ${formatNumber(value, 2)}`
}

function PeriodForm({ onDone }: { onDone: () => void }) {
  const qc = useQueryClient()
  const [name, setName] = useState('')
  const [start, setStart] = useState('')
  const [end, setEnd] = useState('')
  const create = useMutation({
    mutationFn: () => api.post('/inventory/periods', { name, start_date: start, end_date: end }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['inventory', 'periods'] })
      onDone()
    },
  })
  return (
    <div className="grid gap-3 sm:grid-cols-[1fr_11rem_11rem_auto] sm:items-end">
      <Field label="Nombre del periodo" htmlFor="p-name">
        <Input id="p-name" placeholder="Octubre 2026 / Gestión 2026" value={name} onChange={(e) => setName(e.target.value)} />
      </Field>
      <Field label="Desde" htmlFor="p-start">
        <Input id="p-start" type="date" value={start} onChange={(e) => setStart(e.target.value)} />
      </Field>
      <Field label="Hasta" htmlFor="p-end">
        <Input id="p-end" type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
      </Field>
      <Button disabled={name.trim().length < 3 || !start || !end || create.isPending} onClick={() => create.mutate()}>
        Abrir periodo
      </Button>
      <div className="sm:col-span-4">
        <ErrorAlert error={create.error} />
      </div>
    </div>
  )
}

function PeriodDetail({ periodId, canManage }: { periodId: number; canManage: boolean }) {
  const qc = useQueryClient()
  const summary = useQuery({
    queryKey: ['inventory', 'periods', periodId],
    queryFn: async () => (await api.get<PeriodSummary>(`/inventory/periods/${periodId}`)).data,
  })
  const [draft, setDraft] = useState<Record<number, string>>({})
  useEffect(() => {
    if (summary.data) {
      setDraft(
        Object.fromEntries(
          summary.data.balances.map((b) => [b.item.id, b.counted_quantity === null ? '' : String(Number(b.counted_quantity))]),
        ),
      )
    }
  }, [summary.data])

  const refresh = () => qc.invalidateQueries({ queryKey: ['inventory'] })
  const saveCounts = useMutation({
    mutationFn: () => {
      const counts = Object.entries(draft)
        .filter(([, v]) => v !== '')
        .map(([itemId, v]) => ({ item_id: Number(itemId), counted_quantity: v }))
      return api.put(`/inventory/periods/${periodId}/counts`, { counts })
    },
    onSuccess: refresh,
  })
  const close = useMutation({ mutationFn: () => api.post(`/inventory/periods/${periodId}/close`), onSuccess: refresh })

  if (summary.isLoading) return <Loading />
  if (summary.error) return <ErrorAlert error={summary.error} />
  const data = summary.data!
  const { period } = data
  const open = period.status === 'abierto'
  const invalid = Object.values(draft).some((v) => v !== '' && !QTY.test(v))
  const report = (kind: string, format: string) =>
    downloadFile('/reports/export', { report: kind, format, period_id: period.id }, `${kind}_${period.start_date}.${format}`)

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <CardTitle className="flex items-center gap-2">
              {period.name} <StatusBadge value={open ? 'pendiente' : 'activo'} label={period.status} />
            </CardTitle>
            <CardDescription>
              {formatDate(period.start_date + 'T12:00:00')} al {formatDate(period.end_date + 'T12:00:00')} · Valor del
              inventario: <strong>{money(data.total_value)}</strong>
              {data.provisional && ' (provisional)'}
            </CardDescription>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button size="sm" variant="outline" onClick={() => report('inventario_conteo', 'pdf')}>
              <Download /> {open ? 'Planilla de conteo' : 'Acta de conteo'} (PDF)
            </Button>
            <Button size="sm" variant="outline" onClick={() => report('inventario_periodo', 'xlsx')}>
              <Download /> Resumen (Excel)
            </Button>
            <Button size="sm" variant="outline" onClick={() => report('inventario_periodo', 'pdf')}>
              <Download /> Resumen (PDF)
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="grid gap-4">
        {open && (
          <Alert>
            <CheckCircle2 />
            <AlertTitle>
              Conteo físico: {data.counted_items} registrados, {data.pending_count_items} pendientes
            </AlertTitle>
            <AlertDescription>
              Registre la cantidad contada de cada repuesto. Al cerrar, las diferencias generan ajustes (sobrantes o
              faltantes) y los saldos quedan congelados. El periodo solo puede cerrarse después de su fecha final.
            </AlertDescription>
          </Alert>
        )}
        <ErrorAlert error={saveCounts.error ?? close.error} />
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Repuesto</TableHead>
              <TableHead className="text-right">Saldo inicial</TableHead>
              <TableHead className="text-right">Entradas</TableHead>
              <TableHead className="text-right">Salidas</TableHead>
              <TableHead className="text-right">Según registros</TableHead>
              <TableHead className="text-right">Contado</TableHead>
              <TableHead className="text-right">Diferencia</TableHead>
              <TableHead className="text-right">Costo prom.</TableHead>
              <TableHead className="text-right">Valor final</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.balances.length === 0 && (
              <TableRow>
                <TableCell colSpan={9} className="text-muted-foreground text-center">
                  No hay repuestos con movimientos en este periodo.
                </TableCell>
              </TableRow>
            )}
            {data.balances.map((b) => {
              const value = draft[b.item.id] ?? ''
              const diff = open && value !== '' && QTY.test(value) ? Number(value) - Number(b.theoretical_quantity) : b.difference
              const diffNumber = diff === null ? null : Number(diff)
              return (
                <TableRow key={b.item.id}>
                  <TableCell>
                    <div className="font-mono text-xs">{b.item.code}</div>
                    <div>
                      {b.item.name} <span className="text-muted-foreground text-xs">({b.item.unit})</span>
                    </div>
                  </TableCell>
                  <TableCell className="text-right tabular-nums">{formatNumber(b.opening_quantity, 3)}</TableCell>
                  <TableCell className="text-right tabular-nums">{formatNumber(b.entries_quantity, 3)}</TableCell>
                  <TableCell className="text-right tabular-nums">
                    {formatNumber(Number(b.exits_quantity) + Number(b.maintenance_exits_quantity), 3)}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">{formatNumber(b.theoretical_quantity, 3)}</TableCell>
                  <TableCell className="text-right">
                    {open && canManage ? (
                      <Input
                        aria-label={`Cantidad contada de ${b.item.code}`}
                        className="ml-auto w-24 text-right"
                        inputMode="decimal"
                        value={value}
                        aria-invalid={value !== '' && !QTY.test(value)}
                        onChange={(e) => setDraft((d) => ({ ...d, [b.item.id]: e.target.value }))}
                      />
                    ) : (
                      <span className="tabular-nums">{b.counted_quantity === null ? '—' : formatNumber(b.counted_quantity, 3)}</span>
                    )}
                  </TableCell>
                  <TableCell
                    className={`text-right tabular-nums ${diffNumber && diffNumber < 0 ? 'text-danger' : diffNumber && diffNumber > 0 ? 'text-success' : ''}`}
                  >
                    {diffNumber === null ? '—' : `${diffNumber > 0 ? '+' : ''}${formatNumber(diffNumber, 3)}`}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {b.average_unit_cost === null ? '—' : formatNumber(b.average_unit_cost, 4)}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">{money(b.closing_value)}</TableCell>
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
        {open && canManage && data.balances.length > 0 && (
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" disabled={invalid || saveCounts.isPending} onClick={() => saveCounts.mutate()}>
              Guardar conteo
            </Button>
            <Button
              disabled={close.isPending}
              onClick={() => {
                if (confirm(`¿Cerrar "${period.name}"? Se generarán los ajustes y no podrá modificarse.`)) close.mutate()
              }}
            >
              <Lock /> Cerrar periodo
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

export function PeriodsTab() {
  const can = useHasPermission()
  const canManage = can('inventario.gestionar')
  const [showForm, setShowForm] = useState(false)
  const [selected, setSelected] = useState<number | null>(null)
  const periods = useQuery({
    queryKey: ['inventory', 'periods'],
    queryFn: async () => (await api.get<InventoryPeriod[]>('/inventory/periods')).data,
  })
  const current = selected ?? periods.data?.[0]?.id ?? null

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-muted-foreground max-w-2xl text-sm">
          Sistema de inventario periódico: al final de cada periodo se realiza el conteo físico, se registran los ajustes y
          se congelan los saldos valorizados (costo promedio ponderado).
        </p>
        {canManage && (
          <Button onClick={() => setShowForm(!showForm)}>
            <Plus /> Periodo
          </Button>
        )}
      </div>
      {showForm && (
        <Card>
          <CardContent>
            <PeriodForm onDone={() => setShowForm(false)} />
          </CardContent>
        </Card>
      )}
      <ErrorAlert error={periods.error} />
      {periods.isLoading && <Loading />}
      {periods.data?.length === 0 && <p className="text-muted-foreground text-sm">Aún no hay periodos de inventario.</p>}
      {periods.data && periods.data.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {periods.data.map((p) => (
            <Button key={p.id} size="sm" variant={p.id === current ? 'default' : 'outline'} onClick={() => setSelected(p.id)}>
              {p.status === 'cerrado' && <Lock />} {p.name}
            </Button>
          ))}
        </div>
      )}
      {current !== null && <PeriodDetail key={current} periodId={current} canManage={canManage} />}
    </div>
  )
}
