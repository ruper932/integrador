import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, Trash2 } from 'lucide-react'
import { useFieldArray, useForm } from 'react-hook-form'
import { z } from 'zod'

import { ErrorAlert, Field, Loading, NativeSelect } from '@/components/common'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { refreshStations, useDevices, useSensors } from '@/features/devices/api'
import { FINAL_LABELS, FINAL_STATUSES, MAINTENANCE_TYPES, TYPE_LABELS } from '@/features/maintenance/labels'
import { api } from '@/lib/api'
import { formatNumber, localInputToIso, nowForInput } from '@/lib/format'
import type { Device, Incident, InventoryItem, Page, Sensor } from '@/types/api'

const schema = z
  .object({
    device_id: z.string().min(1, 'Seleccione el dispositivo'),
    sensor_id: z.string(),
    performed_at: z
      .string()
      .min(1, 'Indique la fecha')
      .refine((v) => new Date(v).getTime() <= Date.now() + 60_000, 'No puede estar en el futuro'),
    maintenance_type: z.enum(MAINTENANCE_TYPES),
    final_status: z.enum(FINAL_STATUSES),
    description: z.string().trim().min(5, 'Describa el trabajo realizado').max(4000, 'Máximo 4000 caracteres'),
    parts: z.array(
      z.object({
        item_id: z.string().min(1, 'Seleccione el repuesto'),
        quantity: z.string().regex(/^\d+(\.\d{1,3})?$/, 'Cantidad inválida').refine((v) => Number(v) > 0, 'Mayor que cero'),
      }),
    ),
  })
  .refine((v) => v.maintenance_type !== 'reemplazo' || v.parts.length > 0, {
    message: 'Un reemplazo debe indicar los repuestos utilizados',
    path: ['parts'],
  })
type FormValues = z.infer<typeof schema>

/**
 * Detalle del trabajo de mantenimiento. Sin `incident` registra un mantenimiento ya realizado;
 * con `incident` finaliza la atención de ese reporte (la fecha es la del momento de finalizar).
 */
export function MaintenanceForm(props: { onDone: () => void; incident?: Incident }) {
  const devices = useDevices()
  const sensors = useSensors()
  const items = useQuery({
    queryKey: ['inventory', 'items', 'active'],
    queryFn: async () => (await api.get<Page<InventoryItem>>('/inventory/items', { params: { limit: 500 } })).data.items,
  })
  // Los catálogos se cargan antes de montar el formulario para que los valores iniciales se muestren.
  if (!devices.data || !sensors.data || !items.data) {
    const error = devices.error ?? sensors.error ?? items.error
    return error ? <ErrorAlert error={error} /> : <Loading />
  }
  return <WorkForm {...props} devices={devices.data} sensors={sensors.data} items={items.data} />
}

/** Qué le pasa al componente atendido según el estado final (lo aplica el backend al guardar). */
export function finalStatusEffect(status: FormValues['final_status'], target: 'sensor' | 'dispositivo'): string {
  if (status === 'fuera_de_servicio')
    return `El ${target} pasará a «mantenimiento» y no aceptará lecturas hasta otro mantenimiento que lo deje operativo.`
  if (status === 'reemplazado')
    return `El ${target} quedará inactivo; vuelva a activarlo en «Dispositivos y sensores» al instalar la unidad nueva.`
  return `Si el ${target} estaba en mantenimiento, vuelve a quedar activo.`
}

function WorkForm({
  onDone,
  incident,
  devices,
  sensors,
  items,
}: {
  onDone: () => void
  incident?: Incident
  devices: Device[]
  sensors: Sensor[]
  items: InventoryItem[]
}) {
  const qc = useQueryClient()
  const form = useForm<FormValues>({
    // Los repuestos dependen del inventario: sin repetir y sin superar el stock disponible.
    resolver: zodResolver(
      schema.superRefine((v, ctx) => {
        const seen = new Set<string>()
        v.parts.forEach((p, index) => {
          if (!p.item_id) return
          if (seen.has(p.item_id)) {
            ctx.addIssue({ code: 'custom', path: ['parts', index, 'item_id'], message: 'Este repuesto ya está en la lista' })
          }
          seen.add(p.item_id)
          const item = items.find((i) => String(i.id) === p.item_id)
          if (item && Number(p.quantity) > Number(item.current_stock)) {
            ctx.addIssue({
              code: 'custom',
              path: ['parts', index, 'quantity'],
              message: `Disponible: ${formatNumber(item.current_stock, 3)} ${item.unit}`,
            })
          }
        })
      }),
    ),
    defaultValues: {
      device_id: incident?.device_id ? String(incident.device_id) : '',
      sensor_id: incident?.sensor_id ? String(incident.sensor_id) : '',
      performed_at: nowForInput(),
      maintenance_type: incident ? 'correctivo' : 'preventivo',
      final_status: 'operativo',
      description: '',
      parts: [],
    },
  })
  const parts = useFieldArray({ control: form.control, name: 'parts' })
  const deviceId = form.watch('device_id')
  const save = useMutation({
    mutationFn: async (v: FormValues) => {
      const work = {
        device_id: Number(v.device_id),
        sensor_id: v.sensor_id ? Number(v.sensor_id) : null,
        maintenance_type: v.maintenance_type,
        final_status: v.final_status,
        description: v.description,
        parts: v.parts.map((p) => ({ item_id: Number(p.item_id), quantity: p.quantity })),
      }
      if (incident) await api.post(`/incidents/${incident.id}/finish`, work)
      else await api.post('/maintenance', { ...work, performed_at: localInputToIso(v.performed_at) })
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['maintenance'] })
      qc.invalidateQueries({ queryKey: ['inventory'] })
      qc.invalidateQueries({ queryKey: ['incidents'] })
      refreshStations(qc) // el estado final cambia el del sensor o la estación
      onDone()
    },
  })
  const { errors } = form.formState
  const itemById = new Map(items.map((i) => [String(i.id), i]))
  const prefix = incident ? `fin-${incident.id}` : 'mt'

  return (
    <form onSubmit={form.handleSubmit((v) => save.mutate(v))} className="grid gap-3" noValidate>
      <div className="grid gap-3 sm:grid-cols-3">
        <Field label="Dispositivo atendido" htmlFor={`${prefix}-device`} error={errors.device_id?.message}>
          <NativeSelect
            id={`${prefix}-device`}
            {...form.register('device_id', { onChange: () => form.setValue('sensor_id', '') })}
          >
            <option value="">Seleccione…</option>
            {devices.map((d) => (
              <option key={d.id} value={d.id}>
                {d.code} — {d.name}
              </option>
            ))}
          </NativeSelect>
        </Field>
        <Field label="Sensor (opcional)" htmlFor={`${prefix}-sensor`}>
          <NativeSelect id={`${prefix}-sensor`} {...form.register('sensor_id')} disabled={!deviceId}>
            <option value="">Todo el dispositivo</option>
            {sensors
              .filter((s) => String(s.device_id) === deviceId)
              .map((s) => (
                <option key={s.id} value={s.id}>
                  {s.code} — {s.sensor_type.name}
                </option>
              ))}
          </NativeSelect>
        </Field>
        {!incident && (
          <Field label="Fecha y hora" htmlFor={`${prefix}-date`} error={errors.performed_at?.message}>
            <Input id={`${prefix}-date`} type="datetime-local" max={nowForInput()} {...form.register('performed_at')} />
          </Field>
        )}
        <Field label="Tipo" htmlFor={`${prefix}-type`}>
          <NativeSelect id={`${prefix}-type`} {...form.register('maintenance_type')}>
            {MAINTENANCE_TYPES.map((t) => (
              <option key={t} value={t}>
                {TYPE_LABELS[t]}
              </option>
            ))}
          </NativeSelect>
        </Field>
        <Field
          label="Estado final del componente"
          htmlFor={`${prefix}-final`}
          hint={finalStatusEffect(form.watch('final_status'), form.watch('sensor_id') ? 'sensor' : 'dispositivo')}
        >
          <NativeSelect id={`${prefix}-final`} {...form.register('final_status')}>
            {FINAL_STATUSES.map((t) => (
              <option key={t} value={t}>
                {FINAL_LABELS[t]}
              </option>
            ))}
          </NativeSelect>
        </Field>
      </div>
      <Field label="Trabajo realizado" htmlFor={`${prefix}-desc`} error={errors.description?.message}>
        <Textarea id={`${prefix}-desc`} rows={3} {...form.register('description')} />
      </Field>

      <div className="grid gap-2">
        <div className="flex items-center justify-between gap-2">
          <span className="text-sm font-medium">Repuestos utilizados (se descuentan del inventario)</span>
          <Button type="button" size="sm" variant="outline" onClick={() => parts.append({ item_id: '', quantity: '1' })}>
            <Plus /> Repuesto
          </Button>
        </div>
        {errors.parts?.message && <p className="text-destructive text-xs">{errors.parts.message}</p>}
        {parts.fields.map((field, index) => {
          const selected = itemById.get(form.watch(`parts.${index}.item_id`))
          return (
            <div key={field.id} className="grid gap-2 sm:grid-cols-[1fr_10rem_auto] sm:items-start">
              <Field label="Repuesto" htmlFor={`${prefix}-p-${index}`} error={errors.parts?.[index]?.item_id?.message}>
                <NativeSelect id={`${prefix}-p-${index}`} {...form.register(`parts.${index}.item_id`)}>
                  <option value="">Seleccione…</option>
                  {items.map((i) => (
                    <option key={i.id} value={i.id} disabled={Number(i.current_stock) <= 0}>
                      {i.code} — {i.name} (disp. {formatNumber(i.current_stock, 3)} {i.unit})
                    </option>
                  ))}
                </NativeSelect>
              </Field>
              <Field
                label={`Cantidad${selected ? ` (${selected.unit})` : ''}`}
                htmlFor={`${prefix}-q-${index}`}
                error={errors.parts?.[index]?.quantity?.message}
              >
                <Input id={`${prefix}-q-${index}`} inputMode="decimal" {...form.register(`parts.${index}.quantity`)} />
              </Field>
              <Button type="button" variant="ghost" className="sm:mt-6" aria-label="Quitar repuesto" onClick={() => parts.remove(index)}>
                <Trash2 />
              </Button>
            </div>
          )
        })}
      </div>
      <ErrorAlert error={save.error} />
      <div>
        <Button type="submit" disabled={save.isPending}>
          {incident ? 'Finalizar mantenimiento' : 'Registrar mantenimiento'}
        </Button>
      </div>
    </form>
  )
}
