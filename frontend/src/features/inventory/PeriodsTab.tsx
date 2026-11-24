import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, Download, Lock, Plus } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'

import { ConfirmDialog } from '@/components/ConfirmDialog'
import { ErrorAlert, Field, Loading, StatusBadge } from '@/components/common'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { useHasPermission } from '@/features/auth/useAuth'
import { api, downloadFile } from '@/lib/api'
import { formatDate, formatNumber } from '@/lib/format'
import { todayIso } from '@/lib/people'
import type { InventoryPeriod, PeriodSummary } from '@/types/api'

const QTY = /^\d+(\.\d{1,3})?$/

function money(value: string | null): string {
  return value === null ? 'sin costo' : `Bs ${formatNumber(value, 2)}`
}

const periodSchema = z
  .object({
    name: z.string().trim().min(3, 'Mínimo 3 caracteres').max(80, 'Máximo 80 caracteres'),
    start_date: z.string().min(1, 'Indique la fecha inicial'),
    end_date: z.string().min(1, 'Indique la fecha final'),
  })
  .refine((v) => !v.start_date || !v.end_date || v.start_date <= v.end_date, {
    message: 'Debe ser igual o posterior a la fecha inicial',
    path: ['end_date'],
  })
type PeriodValues = z.infer<typeof periodSchema>

function PeriodForm({ onDone }: { onDone: () => void }) {
  const qc = useQueryClient()
  const form = useForm<PeriodValues>({
    resolver: zodResolver(periodSchema),
    defaultValues: { name: '', start_date: '', end_date: '' },
  })
  const start = form.watch('start_date')
  const create = useMutation({
    mutationFn: (v: PeriodValues) => api.post('/inventory/periods', v),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['inventory', 'periods'] })
      onDone()
    },
  })
  const { errors } = form.formState
  return (
    <form
      onSubmit={form.handleSubmit((v) => create.mutate(v))}
      className="grid gap-3 sm:grid-cols-[1fr_11rem_11rem_auto] sm:items-start"
      noValidate
    >
      <Field label="Nombre del periodo" htmlFor="p-name" error={errors.name?.message}>
        <Input id="p-name" placeholder="Octubre 2026 / Gestión 2026" {...form.register('name')} />
      </Field>
      <Field label="Desde" htmlFor="p-start" error={errors.start_date?.message}>
        <Input id="p-start" type="date" {...form.register('start_date')} />
      </Field>
      <Field label="Hasta" htmlFor="p-end" error={errors.end_date?.message}>
        {/* La fecha final depende de la inicial. */}
        <Input id="p-end" type="date" min={start || undefined} {...form.register('end_date')} />
      </Field>
      <div className="sm:pt-6">
        <Button type="submit" disabled={create.isPending}>
          Abrir periodo
        </Button>
      </div>
      <div className="sm:col-span-4">
        <ErrorAlert error={create.error} />
      </div>
    </form>
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
  const [confirmClose, setConfirmClose] = useState(false)
  const close = useMutation({
    mutationFn: () => api.post(`/inventory/periods/${periodId}/close`),
    onSuccess: () => {
      refresh()
      setConfirmClose(false)
    },
  })

  if (summary.isLoading) return <Loading />
  if (summary.error) return <ErrorAlert error={summary.error} />
  const data = summary.data!
  const { period } = data
  const open = period.status === 'abierto'
  const invalid = Object.values(draft).some((v) => v !== '' && !QTY.test(v))
  const notEnded = period.end_date >= todayIso()
  // Conteos escritos pero no guardados: el cierre usa solo los guardados.
  const unsaved = data.balances.some(
    (b) => (draft[b.item.id] ?? '') !== (b.counted_quantity === null ? '' : String(Number(b.counted_quantity))),
  )
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
            <Button disabled={close.isPending} onClick={() => setConfirmClose(true)}>
              <Lock /> Cerrar periodo
            </Button>
          </div>
        )}
        {confirmClose && (
          <ConfirmDialog
            title={`Cerrar el periodo «${period.name}»`}
            description="El cierre es definitivo: el periodo ya no admitirá movimientos ni cambios en el conteo."
            confirmLabel={
              <>
                <Lock /> Cerrar periodo
              </>
            }
            pendingLabel="Cerrando…"
            destructive
            disabled={unsaved || data.pending_count_items > 0 || notEnded}
            pending={close.isPending}
            error={close.error}
            onConfirm={() => close.mutate()}
            onClose={() => {
              setConfirmClose(false)
              close.reset()
            }}
          >
            <p className="text-sm">Se generarán los ajustes por sobrante o faltante según el conteo físico.</p>
            {/* Mismas condiciones que exige el backend: se avisan antes de intentar el cierre. */}
            {(notEnded || data.pending_count_items > 0 || unsaved) && (
              <ul className="text-danger grid list-disc gap-1 pl-5 text-sm font-medium">
                {notEnded && <li>El periodo termina el {formatDate(period.end_date + 'T12:00:00')}: podrá cerrarse después de esa fecha.</li>}
                {data.pending_count_items > 0 && <li>Faltan {data.pending_count_items} repuesto(s) por contar.</li>}
                {unsaved && <li>Hay conteos sin guardar: use «Guardar conteo» primero.</li>}
              </ul>
            )}
          </ConfirmDialog>
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
