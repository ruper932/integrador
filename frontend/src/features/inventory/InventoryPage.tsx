import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, Plus } from 'lucide-react'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'

import { ConfirmDialog } from '@/components/ConfirmDialog'
import { ErrorAlert, Field, Loading, NativeSelect, Notice, PageHeader } from '@/components/common'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { useHasPermission } from '@/features/auth/useAuth'
import { PeriodsTab } from '@/features/inventory/PeriodsTab'
import { FilterToolbar } from '@/features/reports/FilterToolbar'
import { listParams } from '@/features/reports/params'
import type { FilterValues } from '@/features/reports/ReportFilterField'
import { api } from '@/lib/api'
import { formatDateTime, formatNumber } from '@/lib/format'
import { code, name } from '@/lib/validation'
import type { InventoryCategory, InventoryItem, InventoryMovement, Page } from '@/types/api'

const decimal = z.string().regex(/^\d+(\.\d{1,3})?$/, 'Número con hasta 3 decimales')

const itemSchema = z.object({
  code: code,
  name: name(150),
  category_id: z.string().min(1, 'Seleccione una categoría'),
  unit: z.string().trim().min(1, 'Indique la unidad').max(20, 'Máximo 20 caracteres'),
  min_stock: decimal,
  initial_stock: decimal,
  initial_unit_cost: z.string().regex(/^(\d+(\.\d{1,4})?)?$/, 'Monto en Bs, hasta 4 decimales'),
  storage_location: z.string().trim().max(120, 'Máximo 120 caracteres').optional(),
})
type ItemValues = z.infer<typeof itemSchema>

const movementSchema = z.object({
  movement_type: z.enum(['entrada', 'salida']),
  quantity: decimal.refine((v) => Number(v) > 0, 'Debe ser mayor que cero'),
  reason: z.string().trim().min(3, 'Indique el motivo').max(255, 'Máximo 255 caracteres'),
  unit_cost: z.string().regex(/^(\d+(\.\d{1,4})?)?$/, 'Monto en Bs, hasta 4 decimales'),
})
type MovementValues = z.infer<typeof movementSchema>

function useCategories() {
  return useQuery({
    queryKey: ['inventory', 'categories'],
    queryFn: async () => (await api.get<InventoryCategory[]>('/inventory/categories')).data,
  })
}

function ItemForm({ onDone }: { onDone: () => void }) {
  const qc = useQueryClient()
  const categories = useCategories()
  const form = useForm<ItemValues>({
    resolver: zodResolver(itemSchema),
    defaultValues: {
      code: '',
      name: '',
      category_id: '',
      unit: 'unidad',
      min_stock: '0',
      initial_stock: '0',
      initial_unit_cost: '',
    },
  })
  const create = useMutation({
    mutationFn: (v: ItemValues) =>
      api.post('/inventory/items', {
        ...v,
        category_id: Number(v.category_id),
        storage_location: v.storage_location || null,
        initial_unit_cost: v.initial_unit_cost || null,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['inventory'] })
      onDone()
    },
  })
  const { errors } = form.formState
  return (
    <form onSubmit={form.handleSubmit((v) => create.mutate(v))} className="grid gap-3 sm:grid-cols-4 sm:items-start" noValidate>
      <Field label="Código" htmlFor="i-code" error={errors.code?.message}>
        <Input id="i-code" {...form.register('code')} />
      </Field>
      <Field label="Nombre" htmlFor="i-name" error={errors.name?.message}>
        <Input id="i-name" {...form.register('name')} />
      </Field>
      <Field label="Categoría" htmlFor="i-cat" error={errors.category_id?.message}>
        <NativeSelect id="i-cat" {...form.register('category_id')}>
          <option value="">Seleccione…</option>
          {categories.data?.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </NativeSelect>
      </Field>
      <Field label="Unidad de medida" htmlFor="i-unit" error={errors.unit?.message}>
        <Input id="i-unit" {...form.register('unit')} />
      </Field>
      <Field label="Stock inicial" htmlFor="i-initial" error={errors.initial_stock?.message}>
        <Input id="i-initial" inputMode="decimal" {...form.register('initial_stock')} />
      </Field>
      <Field label="Stock mínimo" htmlFor="i-min" error={errors.min_stock?.message}>
        <Input id="i-min" inputMode="decimal" {...form.register('min_stock')} />
      </Field>
      <Field label="Costo unitario inicial (Bs)" htmlFor="i-cost" error={errors.initial_unit_cost?.message} hint="Para valorizar el inventario">
        <Input id="i-cost" inputMode="decimal" {...form.register('initial_unit_cost')} />
      </Field>
      <Field label="Ubicación en almacén" htmlFor="i-loc">
        <Input id="i-loc" {...form.register('storage_location')} />
      </Field>
      <div className="flex items-end sm:pt-6">
        <Button type="submit" disabled={create.isPending}>
          Guardar repuesto
        </Button>
      </div>
      <div className="sm:col-span-4">
        <ErrorAlert error={create.error} />
      </div>
    </form>
  )
}

function ItemDetail({ item, canManage }: { item: InventoryItem; canManage: boolean }) {
  const qc = useQueryClient()
  const movements = useQuery({
    queryKey: ['inventory', 'movements', item.id],
    queryFn: async () => (await api.get<Page<InventoryMovement>>(`/inventory/items/${item.id}/movements`)).data,
  })
  const form = useForm<MovementValues>({
    // Una salida depende del stock disponible del repuesto.
    resolver: zodResolver(
      movementSchema.refine((v) => v.movement_type !== 'salida' || Number(v.quantity) <= Number(item.current_stock), {
        message: `No puede superar el stock disponible (${formatNumber(item.current_stock, 3)} ${item.unit})`,
        path: ['quantity'],
      }),
    ),
    defaultValues: { movement_type: 'entrada', quantity: '', reason: '', unit_cost: '' },
  })
  const isEntry = form.watch('movement_type') === 'entrada'
  const register = useMutation({
    mutationFn: (v: MovementValues) =>
      api.post(`/inventory/items/${item.id}/movements`, {
        ...v,
        unit_cost: v.movement_type === 'entrada' && v.unit_cost ? v.unit_cost : null,
      }),
    onSuccess: () => {
      form.reset({ movement_type: 'entrada', quantity: '', reason: '', unit_cost: '' })
      qc.invalidateQueries({ queryKey: ['inventory'] })
    },
  })
  const { errors } = form.formState

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          {item.name} <span className="text-muted-foreground font-mono text-sm">{item.code}</span>
        </CardTitle>
        <CardDescription>
          Disponible: <strong className="tabular-nums">{formatNumber(item.current_stock, 3)}</strong> {item.unit} · Mínimo{' '}
          {formatNumber(item.min_stock, 3)} {item.unit}
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4">
        {canManage && item.is_active && (
          <form onSubmit={form.handleSubmit((v) => register.mutate(v))} className="grid gap-3 sm:grid-cols-5 sm:items-start" noValidate>
            <Field label="Movimiento" htmlFor="m-type">
              <NativeSelect id="m-type" {...form.register('movement_type')}>
                <option value="entrada">Entrada</option>
                <option value="salida">Salida</option>
              </NativeSelect>
            </Field>
            <Field label={`Cantidad (${item.unit})`} htmlFor="m-qty" error={errors.quantity?.message}>
              <Input id="m-qty" inputMode="decimal" {...form.register('quantity')} />
            </Field>
            <Field label="Motivo" htmlFor="m-reason" error={errors.reason?.message}>
              <Input id="m-reason" placeholder="Compra, donación, préstamo…" {...form.register('reason')} />
            </Field>
            {isEntry && (
              <Field label="Costo unitario (Bs)" htmlFor="m-cost" error={errors.unit_cost?.message} hint="Opcional; necesario para valorizar">
                <Input id="m-cost" inputMode="decimal" {...form.register('unit_cost')} />
              </Field>
            )}
            <div className="sm:pt-6">
              <Button type="submit" disabled={register.isPending}>
                Registrar
              </Button>
            </div>
            <div className="sm:col-span-5">
              <ErrorAlert error={register.error} />
            </div>
          </form>
        )}
        {movements.isLoading && <Loading />}
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Fecha</TableHead>
              <TableHead>Tipo</TableHead>
              <TableHead className="text-right">Cantidad</TableHead>
              <TableHead className="text-right">Stock</TableHead>
              <TableHead className="text-right">Costo unit. (Bs)</TableHead>
              <TableHead>Usuario</TableHead>
              <TableHead>Motivo</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {movements.data?.items.map((m) => (
              <TableRow key={m.id}>
                <TableCell>{formatDateTime(m.occurred_at)}</TableCell>
                <TableCell>{m.movement_type.name}</TableCell>
                <TableCell className="text-right tabular-nums">
                  {m.movement_type.direction > 0 ? '+' : '−'}
                  {formatNumber(m.quantity, 3)}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {formatNumber(m.stock_before, 3)} → {formatNumber(m.stock_after, 3)}
                </TableCell>
                <TableCell className="text-right tabular-nums">{m.unit_cost ? formatNumber(m.unit_cost, 4) : '—'}</TableCell>
                <TableCell>{m.username}</TableCell>
                <TableCell>{m.reason}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  )
}

const INVENTORY_REPORTS = [
  'inventario_stock',
  'inventario_movimientos',
  'inventario_periodo',
  'inventario_conteo',
  'inventario_kardex',
  'inventario_consumo',
]
const ITEM_FILTERS = ['category_id', 'condition', 'low_stock_only', 'include_inactive']

export function InventoryPage() {
  const [tab, setTab] = useState<'items' | 'periods'>('items')
  return (
    <>
      <PageHeader
        eyebrow="Operaciones"
        title="Inventario IoT"
        description="Componentes, consumibles y herramientas para el hardware IoT y los atrapanieblas."
      />
      <div className="bg-muted mb-5 inline-flex rounded-xl border p-1" role="tablist" aria-label="Secciones del inventario">
        {(
          [
            ['items', 'Repuestos y movimientos'],
            ['periods', 'Periodos y conteo físico'],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            type="button"
            role="tab"
            aria-selected={tab === key}
            onClick={() => setTab(key)}
            className={
              tab === key
                ? 'bg-card text-foreground shadow-card rounded-lg px-3.5 py-1.5 text-sm font-medium'
                : 'text-muted-foreground hover:text-foreground rounded-lg px-3.5 py-1.5 text-sm'
            }
          >
            {label}
          </button>
        ))}
      </div>
      {tab === 'items' ? <ItemsTab /> : <PeriodsTab />}
    </>
  )
}

function ItemsTab() {
  const can = useHasPermission()
  const canManage = can('inventario.gestionar')
  const qc = useQueryClient()
  const [q, setQ] = useState('')
  const [filters, setFilters] = useState<FilterValues>({})
  const [showForm, setShowForm] = useState(false)
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [toDeactivate, setToDeactivate] = useState<InventoryItem | null>(null)

  const items = useQuery({
    queryKey: ['inventory', 'items', q, filters],
    queryFn: async () => {
      const params = { ...listParams(ITEM_FILTERS, filters), q: q || undefined, limit: 500 }
      return (await api.get<Page<InventoryItem>>('/inventory/items', { params })).data
    },
  })
  const alerts = useQuery({
    queryKey: ['inventory', 'alerts'],
    queryFn: async () => (await api.get<InventoryItem[]>('/inventory/alerts/low-stock')).data,
  })
  const deactivate = useMutation({
    mutationFn: (id: number) => api.delete(`/inventory/items/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['inventory'] })
      setToDeactivate(null)
    },
  })
  const selected = items.data?.items.find((i) => i.id === selectedId)

  return (
    <>
      {canManage && (
        <div className="mb-4 flex flex-wrap justify-end gap-2">
          <Button onClick={() => setShowForm(!showForm)}>
            <Plus /> Repuesto
          </Button>
        </div>
      )}

      {alerts.data && alerts.data.length > 0 && (
        <Notice
          tone="warning"
          className="mb-4"
          title={`Reposición necesaria: ${alerts.data.length} ${alerts.data.length === 1 ? 'repuesto' : 'repuestos'} en o bajo el stock mínimo`}
        >
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {alerts.data.map((a) => (
              <Badge key={a.id} variant="outline" className="border-warning/40 bg-card text-foreground">
                {a.code}: {formatNumber(a.current_stock, 3)} / mín. {formatNumber(a.min_stock, 3)} {a.unit}
              </Badge>
            ))}
          </div>
        </Notice>
      )}

      {showForm && (
        <Card className="mb-4">
          <CardContent>
            <ItemForm onDone={() => setShowForm(false)} />
          </CardContent>
        </Card>
      )}

      <FilterToolbar kinds={INVENTORY_REPORTS} keys={ITEM_FILTERS} values={filters} onChange={setFilters}>
        <Field label="Buscar" htmlFor="inv-q">
          <Input id="inv-q" placeholder="Código o nombre" value={q} onChange={(e) => setQ(e.target.value)} />
        </Field>
      </FilterToolbar>

      <ErrorAlert error={items.error} />
      {toDeactivate && (
        <ConfirmDialog
          title={`Desactivar ${toDeactivate.name}`}
          description={`Código ${toDeactivate.code} · stock actual ${formatNumber(toDeactivate.current_stock, 3)} ${toDeactivate.unit}`}
          confirmLabel="Desactivar repuesto"
          pendingLabel="Desactivando…"
          destructive
          pending={deactivate.isPending}
          error={deactivate.error}
          onConfirm={() => deactivate.mutate(toDeactivate.id)}
          onClose={() => {
            setToDeactivate(null)
            deactivate.reset()
          }}
        >
          <p className="text-sm">
            No se elimina: se conserva su historial de movimientos, pero ya no podrá usarse en entradas, salidas ni
            mantenimientos.
          </p>
        </ConfirmDialog>
      )}
      {items.isLoading ? (
        <Loading />
      ) : (
        <Card className="mb-4">
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Código</TableHead>
                  <TableHead>Nombre</TableHead>
                  <TableHead>Categoría</TableHead>
                  <TableHead className="text-right">Stock</TableHead>
                  <TableHead>Estado</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.data?.items.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={6} className="text-muted-foreground text-center">
                      Sin repuestos registrados.
                    </TableCell>
                  </TableRow>
                )}
                {items.data?.items.map((item) => (
                  <TableRow key={item.id} data-state={item.id === selectedId ? 'selected' : undefined}>
                    <TableCell className="font-mono">{item.code}</TableCell>
                    <TableCell>{item.name}</TableCell>
                    <TableCell>{item.category.name}</TableCell>
                    <TableCell className="text-right tabular-nums">
                      {formatNumber(item.current_stock, 3)} {item.unit}
                      {item.low_stock && (
                        <Badge variant="warning" className="ml-2">
                          <AlertTriangle /> Bajo
                        </Badge>
                      )}
                    </TableCell>
                    <TableCell>{item.condition.replaceAll('_', ' ')}</TableCell>
                    <TableCell className="text-right">
                      <Button size="sm" variant="outline" onClick={() => setSelectedId(item.id === selectedId ? null : item.id)}>
                        Movimientos
                      </Button>
                      {canManage && (
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => setToDeactivate(item)}
                        >
                          Desactivar
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
      {selected && <ItemDetail item={selected} canManage={canManage} />}
    </>
  )
}
