import { useQuery } from '@tanstack/react-query'

import { Field, NativeSelect } from '@/components/common'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { usePositions, useRoles } from '@/features/admin/catalogs'
import { useDevices, useFogCollectors, useSensorTypes } from '@/features/devices/api'
import { PRIORITY_LABELS, STATUS_LABELS } from '@/features/incidents/labels'
import { FINAL_LABELS, TYPE_LABELS } from '@/features/maintenance/labels'
import { api } from '@/lib/api'
import type { InventoryCategory, InventoryItem, InventoryPeriod, Page, ReportFilterDef, ReportFilterOptions } from '@/types/api'

export type FilterValues = Record<string, string>

const QUALITY = { valida: 'Válida', sin_dato: 'Sin dato', fuera_de_rango: 'Fuera de rango', unidad_invalida: 'Unidad inválida', invalida: 'Inválida' }
const DEVICE_STATUS = { activo: 'Activo', inactivo: 'Inactivo', mantenimiento: 'En mantenimiento' }
const CONDITIONS = { nuevo: 'Nuevo', usado: 'Usado', reacondicionado: 'Reacondicionado', en_revision: 'En revisión', danado: 'Dañado' }
const ORIGINS = { incidencia: 'Atención de reportes de incidencia', directo: 'Registro directo' }
const BUCKETS = { hour: 'Hora', day: 'Día', week: 'Semana', month: 'Mes' }
const ACCOUNT = { true: 'Activas', false: 'Desactivadas' }

interface FieldProps {
  def: ReportFilterDef
  values: FilterValues
  set: (key: string, value: string) => void
  options?: ReportFilterOptions
}

function toInput(date: Date): string {
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000)
  return local.toISOString().slice(0, 16)
}

/** Atajos frecuentes; las fechas se pueden ajustar después. */
const PRESETS: { label: string; range: () => [Date, Date] }[] = [
  { label: 'Últimos 7 días', range: () => [new Date(Date.now() - 7 * 86_400_000), new Date()] },
  { label: 'Últimos 30 días', range: () => [new Date(Date.now() - 30 * 86_400_000), new Date()] },
  {
    label: 'Este mes',
    range: () => {
      const now = new Date()
      return [new Date(now.getFullYear(), now.getMonth(), 1), now]
    },
  },
  {
    label: 'Mes anterior',
    range: () => {
      const now = new Date()
      return [new Date(now.getFullYear(), now.getMonth() - 1, 1), new Date(now.getFullYear(), now.getMonth(), 1)]
    },
  },
  { label: 'Esta gestión', range: () => [new Date(new Date().getFullYear(), 0, 1), new Date()] },
]

function DateRange({ values, set }: FieldProps) {
  const invalid = values.date_from && values.date_to && values.date_from >= values.date_to
  return (
    <div className="grid gap-2 sm:col-span-2">
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Desde" htmlFor="rf-from" hint="Vacío: sin límite">
          <Input id="rf-from" type="datetime-local" value={values.date_from ?? ''} onChange={(e) => set('date_from', e.target.value)} />
        </Field>
        <Field label="Hasta" htmlFor="rf-to" error={invalid ? 'Debe ser posterior a «Desde»' : undefined} hint="Vacío: ahora">
          <Input id="rf-to" type="datetime-local" value={values.date_to ?? ''} onChange={(e) => set('date_to', e.target.value)} />
        </Field>
      </div>
      <div className="flex flex-wrap gap-1.5" aria-label="Periodos frecuentes">
        {PRESETS.map((p) => (
          <Button
            key={p.label}
            type="button"
            size="sm"
            variant="outline"
            className="h-7 text-xs"
            onClick={() => {
              const [from, to] = p.range()
              set('date_from', toInput(from))
              set('date_to', toInput(to))
            }}
          >
            {p.label}
          </Button>
        ))}
      </div>
    </div>
  )
}

function Select({
  def,
  values,
  set,
  choices,
  allLabel = 'Todos',
}: FieldProps & { choices: [string, string][] | undefined; allLabel?: string }) {
  const id = `rf-${def.key}`
  return (
    <Field label={def.required ? `${def.label} *` : def.label} htmlFor={id}>
      <NativeSelect id={id} value={values[def.key] ?? ''} onChange={(e) => set(def.key, e.target.value)}>
        <option value="">{def.required ? 'Seleccione…' : allLabel}</option>
        {choices?.map(([value, label]) => (
          <option key={value} value={value}>
            {label}
          </option>
        ))}
      </NativeSelect>
    </Field>
  )
}

function Toggle({ def, values, set }: FieldProps) {
  const id = `rf-${def.key}`
  return (
    <label htmlFor={id} className="flex items-center gap-2 self-end pb-2 text-sm">
      <Checkbox id={id} checked={values[def.key] === 'true'} onCheckedChange={(c) => set(def.key, c ? 'true' : '')} />
      {def.label}
    </label>
  )
}

const entries = (labels: Record<string, string>): [string, string][] => Object.entries(labels)

function DeviceSelect(props: FieldProps) {
  const devices = useDevices()
  return <Select {...props} choices={devices.data?.map((d) => [String(d.id), `${d.name} (${d.code})`])} />
}

function FogSelect(props: FieldProps) {
  const fog = useFogCollectors()
  return <Select {...props} choices={fog.data?.map((f) => [String(f.id), `${f.name} (${f.code})`])} />
}

function SensorTypeSelect(props: FieldProps) {
  const types = useSensorTypes()
  return <Select {...props} allLabel="Todas" choices={types.data?.map((t) => [t.code, t.name])} />
}

function CategorySelect(props: FieldProps) {
  const categories = useQuery({
    queryKey: ['inventory', 'categories'],
    queryFn: async () => (await api.get<InventoryCategory[]>('/inventory/categories')).data,
  })
  return <Select {...props} allLabel="Todas" choices={categories.data?.map((c) => [String(c.id), c.name])} />
}

function ItemSelect(props: FieldProps) {
  const items = useQuery({
    queryKey: ['inventory', 'items', 'report'],
    queryFn: async () => (await api.get<Page<InventoryItem>>('/inventory/items', { params: { limit: 500 } })).data.items,
  })
  const category = props.values.category_id
  const choices = items.data
    ?.filter((i) => !category || String(i.category.id) === category)
    .map((i): [string, string] => [String(i.id), `${i.code} — ${i.name}`])
  return <Select {...props} choices={choices} />
}

function MovementTypeSelect(props: FieldProps) {
  const types = useQuery({
    queryKey: ['inventory', 'movement-types'],
    queryFn: async () => (await api.get<{ code: string; name: string }[]>('/inventory/movement-types')).data,
  })
  return <Select {...props} choices={types.data?.map((t) => [t.code, t.name])} />
}

function PeriodSelect(props: FieldProps) {
  const periods = useQuery({
    queryKey: ['inventory', 'periods'],
    queryFn: async () => (await api.get<InventoryPeriod[]>('/inventory/periods')).data,
  })
  return <Select {...props} choices={periods.data?.map((p) => [String(p.id), `${p.name} (${p.status})`])} />
}

function RoleSelect(props: FieldProps) {
  const roles = useRoles()
  return <Select {...props} choices={roles.data?.map((r) => [String(r.id), r.name.replaceAll('_', ' ')])} />
}

function PositionSelect(props: FieldProps) {
  const positions = usePositions()
  return <Select {...props} choices={positions.data?.map((p) => [String(p.id), p.name])} />
}

function ActionSelect(props: FieldProps) {
  const actions = props.options?.audit_actions ?? []
  const modules = [...new Set(actions.map((a) => a.split('.')[0] ?? a))]
  const id = `rf-${props.def.key}`
  return (
    <Field label={props.def.label} htmlFor={id}>
      <NativeSelect id={id} value={props.values.action ?? ''} onChange={(e) => props.set('action', e.target.value)}>
        <option value="">Todas</option>
        <optgroup label="Por módulo">
          {modules.map((m) => (
            <option key={m} value={m}>
              {m.replaceAll('_', ' ')} (todas)
            </option>
          ))}
        </optgroup>
        <optgroup label="Acción específica">
          {actions.map((a) => (
            <option key={a} value={a}>
              {a}
            </option>
          ))}
        </optgroup>
      </NativeSelect>
    </Field>
  )
}

const people = (list: { id: number; full_name: string }[] | null | undefined): [string, string][] | undefined =>
  list?.map((p) => [String(p.id), p.full_name])

/** Control de un filtro del catálogo de reportes, según su clave. */
export function ReportFilterField(props: FieldProps) {
  switch (props.def.key) {
    case 'date_range':
      return <DateRange {...props} />
    case 'bucket':
      return <Select {...props} choices={entries(BUCKETS).filter(([k]) => k !== 'day')} allLabel="Día" />
    case 'device_id':
      return <DeviceSelect {...props} />
    case 'fog_collector_id':
      return <FogSelect {...props} />
    case 'sensor_type':
      return <SensorTypeSelect {...props} />
    case 'quality':
      return <Select {...props} choices={entries(QUALITY)} allLabel="Todas" />
    case 'device_status':
      return <Select {...props} choices={entries(DEVICE_STATUS)} />
    case 'category_id':
      return <CategorySelect {...props} />
    case 'item_id':
      return <ItemSelect {...props} />
    case 'condition':
      return <Select {...props} choices={entries(CONDITIONS)} />
    case 'low_stock_only':
    case 'include_inactive':
      return <Toggle {...props} />
    case 'movement_type':
      return <MovementTypeSelect {...props} />
    case 'period_id':
      return <PeriodSelect {...props} />
    case 'maintenance_type':
      return <Select {...props} choices={entries(TYPE_LABELS)} />
    case 'final_status':
      return <Select {...props} choices={entries(FINAL_LABELS)} />
    case 'responsible_id':
      return <Select {...props} choices={people(props.options?.responsibles)} />
    case 'reporter_id':
      return <Select {...props} choices={people(props.options?.reporters)} />
    case 'actor_id':
      return <Select {...props} choices={people(props.options?.actors)} />
    case 'origin':
      return <Select {...props} choices={entries(ORIGINS)} />
    case 'incident_status':
      return <Select {...props} choices={entries(STATUS_LABELS)} />
    case 'priority':
      return <Select {...props} choices={entries(PRIORITY_LABELS)} allLabel="Todas" />
    case 'role_id':
      return <RoleSelect {...props} />
    case 'position_id':
      return <PositionSelect {...props} />
    case 'is_active':
      return <Select {...props} choices={entries(ACCOUNT)} allLabel="Todas" />
    case 'action':
      return <ActionSelect {...props} />
    default:
      return null
  }
}
