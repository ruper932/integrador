import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { KeyRound, Plus } from 'lucide-react'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'

import { ConfirmDialog } from '@/components/ConfirmDialog'
import { ErrorAlert, Field, Loading, NativeSelect, PageHeader, SecretNotice, StatusBadge } from '@/components/common'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { useHasPermission } from '@/features/auth/useAuth'
import { FilterToolbar } from '@/features/reports/FilterToolbar'
import { listParams } from '@/features/reports/params'
import type { FilterValues } from '@/features/reports/ReportFilterField'
import {
  BADGE,
  connection,
  refreshStations,
  useFogCollectors,
  useStationSummary, useLocations, useSensors, useSensorTypes, useTanks } from '@/features/devices/api'
import { api } from '@/lib/api'
import { formatDateTime } from '@/lib/format'
import { code, name, numberOrNull, optionalNumber } from '@/lib/validation'
import type { Device, DeviceStatusItem, DeviceWithKey, FogCollector, SensorType, Tank } from '@/types/api'

const LIST_FILTERS = ['device_status', 'connection', 'fog_collector_id']

const optionalId = (v: string) => (v === '' ? null : Number(v))
const VOLUME = 'volumen_captado'
const TANK_LEVEL = 'nivel_almacenamiento'

const fogSchema = z.object({
  code: code,
  name: name(),
  location_id: z.string(),
  mesh_area_m2: optionalNumber(0, 10000, { exclusiveMin: true }),
})
type FogValues = z.infer<typeof fogSchema>

function FogCollectorForm({ onDone }: { onDone: () => void }) {
  const qc = useQueryClient()
  const locations = useLocations()
  const form = useForm<FogValues>({
    resolver: zodResolver(fogSchema),
    defaultValues: { code: '', name: '', location_id: '', mesh_area_m2: '' },
  })
  const create = useMutation({
    mutationFn: (v: FogValues) =>
      api.post('/fog-collectors', {
        code: v.code,
        name: v.name,
        location_id: optionalId(v.location_id),
        mesh_area_m2: numberOrNull(v.mesh_area_m2),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['fog-collectors'] })
      onDone()
    },
  })
  const { errors } = form.formState
  return (
    <form onSubmit={form.handleSubmit((v) => create.mutate(v))} className="grid gap-3 sm:grid-cols-5 sm:items-start" noValidate>
      <Field label="Código" htmlFor="fc-code" error={errors.code?.message}>
        <Input id="fc-code" {...form.register('code')} placeholder="AN-01" />
      </Field>
      <Field label="Nombre" htmlFor="fc-name" error={errors.name?.message}>
        <Input id="fc-name" {...form.register('name')} />
      </Field>
      <Field label="Ubicación" htmlFor="fc-loc">
        <NativeSelect id="fc-loc" {...form.register('location_id')}>
          <option value="">Sin registrar</option>
          {locations.data?.map((l) => (
            <option key={l.id} value={l.id}>
              {l.name}
            </option>
          ))}
        </NativeSelect>
      </Field>
      <Field label="Área de malla (m²)" htmlFor="fc-area" error={errors.mesh_area_m2?.message}>
        <Input id="fc-area" inputMode="decimal" {...form.register('mesh_area_m2')} />
      </Field>
      <div className="sm:pt-6">
        <Button type="submit" disabled={create.isPending}>
          Guardar atrapanieblas
        </Button>
      </div>
      <div className="sm:col-span-5">
        <ErrorAlert error={create.error} />
      </div>
    </form>
  )
}

const deviceSchema = z.object({
  code: code,
  name: name(),
  fog_collector_id: z.string(),
  location_id: z.string(),
})
type DeviceValues = z.infer<typeof deviceSchema>

function DeviceForm({ onCreated }: { onCreated: (r: DeviceWithKey) => void }) {
  const qc = useQueryClient()
  const fogCollectors = useFogCollectors()
  const locations = useLocations()
  const form = useForm<DeviceValues>({
    resolver: zodResolver(deviceSchema),
    defaultValues: { code: '', name: '', fog_collector_id: '', location_id: '' },
  })
  const create = useMutation({
    mutationFn: async (v: DeviceValues) =>
      (
        await api.post<DeviceWithKey>('/devices', {
          code: v.code,
          name: v.name,
          fog_collector_id: optionalId(v.fog_collector_id),
          location_id: optionalId(v.location_id),
        })
      ).data,
    onSuccess: (r) => {
      refreshStations(qc)
      form.reset()
      onCreated(r)
    },
  })
  const { errors } = form.formState
  return (
    <form onSubmit={form.handleSubmit((v) => create.mutate(v))} className="grid gap-3 sm:grid-cols-5 sm:items-start" noValidate>
      <Field label="Identificador (X-Device-Id)" htmlFor="d-code" error={errors.code?.message}>
        <Input id="d-code" placeholder="esp32-01" {...form.register('code')} />
      </Field>
      <Field label="Nombre" htmlFor="d-name" error={errors.name?.message}>
        <Input id="d-name" {...form.register('name')} />
      </Field>
      <Field label="Atrapanieblas" htmlFor="d-fc">
        <NativeSelect
          id="d-fc"
          {...form.register('fog_collector_id', {
            // La estación se monta en el atrapanieblas: toma su ubicación (se puede cambiar).
            onChange: (e) => {
              const fc = fogCollectors.data?.find((f) => String(f.id) === e.target.value)
              form.setValue('location_id', fc?.location_id ? String(fc.location_id) : '')
            },
          })}
        >
          <option value="">Ninguno</option>
          {fogCollectors.data?.map((f) => (
            <option key={f.id} value={f.id}>
              {f.code} — {f.name}
            </option>
          ))}
        </NativeSelect>
      </Field>
      <Field label="Ubicación" htmlFor="d-loc" hint="Por defecto, la del atrapanieblas">
        <NativeSelect id="d-loc" {...form.register('location_id')}>
          <option value="">Sin registrar</option>
          {locations.data?.map((l) => (
            <option key={l.id} value={l.id}>
              {l.name}
            </option>
          ))}
        </NativeSelect>
      </Field>
      <div className="sm:pt-6">
        <Button type="submit" disabled={create.isPending}>
          Registrar dispositivo
        </Button>
      </div>
      <div className="sm:col-span-5">
        <ErrorAlert error={create.error} />
      </div>
    </form>
  )
}

const sensorSchema = z.object({
  sensor_type_id: z.string().min(1, 'Seleccione el tipo'),
  code: code,
  model: z.string().trim().max(80, 'Máximo 80 caracteres'),
  fog_collector_id: z.string(),
  tank_id: z.string(),
})
type SensorValues = z.infer<typeof sensorSchema>

function SensorForm({ device, existingCodes, onDone }: { device: Device; existingCodes: string[]; onDone: () => void }) {
  const types = useSensorTypes()
  const tanks = useTanks()
  const fogCollectors = useFogCollectors()
  if (!types.data || !tanks.data || !fogCollectors.data) {
    const error = types.error ?? tanks.error ?? fogCollectors.error
    return error ? <ErrorAlert error={error} /> : <Loading />
  }
  return (
    <SensorFields
      device={device}
      existingCodes={existingCodes}
      types={types.data}
      tanks={tanks.data}
      fogCollectors={fogCollectors.data}
      onDone={onDone}
    />
  )
}

function SensorFields({
  device,
  existingCodes,
  types,
  tanks,
  fogCollectors,
  onDone,
}: {
  device: Device
  existingCodes: string[]
  types: SensorType[]
  tanks: Tank[]
  fogCollectors: FogCollector[]
  onDone: () => void
}) {
  const qc = useQueryClient()
  // Si el dispositivo está montado en un atrapanieblas, el sensor pertenece a ese atrapanieblas.
  const fixedFc = device.fog_collector_id ? String(device.fog_collector_id) : null
  const typeCode = (id: string) => types.find((t) => String(t.id) === id)?.code
  const form = useForm<SensorValues>({
    resolver: zodResolver(
      sensorSchema.superRefine((v, ctx) => {
        if (existingCodes.includes(v.code.trim())) {
          ctx.addIssue({ code: 'custom', path: ['code'], message: 'El dispositivo ya tiene un sensor con ese código' })
        }
        if (typeCode(v.sensor_type_id) === VOLUME && !v.fog_collector_id) {
          ctx.addIssue({ code: 'custom', path: ['fog_collector_id'], message: 'El volumen captado requiere un atrapanieblas' })
        }
        if (typeCode(v.sensor_type_id) === TANK_LEVEL && !v.tank_id) {
          ctx.addIssue({ code: 'custom', path: ['tank_id'], message: 'El nivel de almacenamiento requiere un tanque' })
        }
      }),
    ),
    defaultValues: { sensor_type_id: '', code: '', model: '', fog_collector_id: fixedFc ?? '', tank_id: '' },
  })
  const fcId = form.watch('fog_collector_id')
  // Solo los tanques sin atrapanieblas o del atrapanieblas del sensor.
  const tankOptions = tanks.filter((t) => t.fog_collector_id === null || String(t.fog_collector_id) === fcId)
  const create = useMutation({
    mutationFn: (v: SensorValues) =>
      api.post('/sensors', {
        device_id: device.id,
        sensor_type_id: Number(v.sensor_type_id),
        code: v.code,
        model: v.model || null,
        tank_id: optionalId(v.tank_id),
        fog_collector_id: optionalId(fixedFc ?? v.fog_collector_id),
      }),
    onSuccess: () => {
      refreshStations(qc)
      onDone()
    },
  })
  const { errors } = form.formState
  return (
    <form onSubmit={form.handleSubmit((v) => create.mutate(v))} className="grid gap-3 sm:grid-cols-3 sm:items-start" noValidate>
      <Field label="Tipo" htmlFor="s-type" error={errors.sensor_type_id?.message}>
        <NativeSelect id="s-type" {...form.register('sensor_type_id')}>
          <option value="">Seleccione…</option>
          {types.map((t) => (
            <option key={t.id} value={t.id}>
              {t.name} ({t.unit})
            </option>
          ))}
        </NativeSelect>
      </Field>
      <Field label="Código en firmware" htmlFor="s-code" error={errors.code?.message}>
        <Input id="s-code" placeholder="temp" {...form.register('code')} />
      </Field>
      <Field label="Modelo" htmlFor="s-model" error={errors.model?.message}>
        <Input id="s-model" placeholder="SHT31" {...form.register('model')} />
      </Field>
      <Field
        label="Atrapanieblas"
        htmlFor="s-fc"
        error={errors.fog_collector_id?.message}
        hint={fixedFc ? 'El del dispositivo' : undefined}
      >
        <NativeSelect
          id="s-fc"
          disabled={Boolean(fixedFc)}
          {...form.register('fog_collector_id', {
            // Un tanque de otro atrapanieblas deja de ser válido.
            onChange: (e) => {
              const tank = tanks.find((t) => String(t.id) === form.getValues('tank_id'))
              if (tank?.fog_collector_id && String(tank.fog_collector_id) !== e.target.value) form.setValue('tank_id', '')
            },
          })}
        >
          <option value="">—</option>
          {fogCollectors.map((f) => (
            <option key={f.id} value={f.id}>
              {f.code} — {f.name}
            </option>
          ))}
        </NativeSelect>
      </Field>
      <Field label="Tanque" htmlFor="s-tank" error={errors.tank_id?.message}>
        <NativeSelect id="s-tank" {...form.register('tank_id')}>
          <option value="">—</option>
          {tankOptions.map((t) => (
            <option key={t.id} value={t.id}>
              {t.code} — {t.name}
            </option>
          ))}
        </NativeSelect>
      </Field>
      <div className="sm:pt-6">
        <Button type="submit" disabled={create.isPending}>
          Agregar sensor
        </Button>
      </div>
      <div className="sm:col-span-3">
        <ErrorAlert error={create.error} />
      </div>
    </form>
  )
}

/** Un componente activo muestra si su estación comunica; el resto, su estado administrativo. */
function LiveStatus({ status, station }: { status: string; station: DeviceStatusItem | undefined }) {
  if (status !== 'activo' || !station) return <StatusBadge value={status} />
  const state = BADGE[connection(station)]
  return <Badge variant={state.variant}>{state.label}</Badge>
}

export function DevicesPage() {
  const can = useHasPermission()
  const canManage = can('infraestructura.gestionar')
  const qc = useQueryClient()
  const [filters, setFilters] = useState<FilterValues>({})
  // Prefijo ['devices']: las invalidaciones existentes también refrescan la lista filtrada.
  const devices = useQuery({
    queryKey: ['devices', filters],
    queryFn: async () =>
      (await api.get<Device[]>('/devices', { params: listParams(LIST_FILTERS, filters, { device_status: 'status' }) }))
        .data,
    // Se refresca como el resumen: la «última comunicación» y el filtro «Comunicación» no quedan congelados.
    refetchInterval: 30_000,
  })
  const sensors = useSensors()
  const summary = useStationSummary()
  const [panel, setPanel] = useState<'device' | 'fog' | null>(null)
  const [sensorFor, setSensorFor] = useState<number | null>(null)
  const [secret, setSecret] = useState<DeviceWithKey | null>(null)
  const [action, setAction] = useState<{ kind: 'rotate' | 'deactivate'; device: Device } | null>(null)

  const rotate = useMutation({
    mutationFn: async (id: number) => (await api.post<DeviceWithKey>(`/devices/${id}/credentials`)).data,
  })
  const setStatus = useMutation({
    mutationFn: ({ id, status }: { id: number; status: string }) => api.put(`/devices/${id}`, { status }),
    onSuccess: () => {
      refreshStations(qc)
      setAction(null)
    },
  })
  const closeAction = () => {
    setAction(null)
    rotate.reset()
    setStatus.reset()
  }

  return (
    <>
      <PageHeader
        eyebrow="Operaciones"
        title="Dispositivos y sensores"
        description="Estaciones ESP32, sus credenciales y los sensores asociados."
        actions={
          <>
            {canManage && (
            <>
              <Button variant="outline" onClick={() => setPanel(panel === 'fog' ? null : 'fog')}>
                <Plus /> Atrapanieblas
              </Button>
              <Button onClick={() => setPanel(panel === 'device' ? null : 'device')}>
                <Plus /> Dispositivo
              </Button>
            </>
            )}
          </>
        }
      />

      {secret && (
        <ConfirmDialog
          title={`Dispositivo ${secret.device.code} registrado`}
          confirmLabel="Listo"
          onConfirm={() => setSecret(null)}
          onClose={() => setSecret(null)}
          done={
            <SecretNotice title="API key" secret={secret.api_key}>
              Cárguela en la configuración segura del firmware (no en el código fuente).
            </SecretNotice>
          }
        />
      )}
      {action?.kind === 'rotate' && (
        <ConfirmDialog
          title={`Nueva API key para ${action.device.name}`}
          description={action.device.code}
          confirmLabel={
            <>
              <KeyRound /> Generar nueva API key
            </>
          }
          pendingLabel="Generando…"
          destructive
          pending={rotate.isPending}
          error={rotate.error}
          onConfirm={() => rotate.mutate(action.device.id)}
          onClose={closeAction}
          done={
            rotate.data && (
              <SecretNotice title="API key nueva" secret={rotate.data.api_key}>
                Cárguela en la estación; hasta entonces no podrá enviar mediciones.
              </SecretNotice>
            )
          }
        >
          <p className="text-sm">
            La API key actual dejará de funcionar de inmediato: la estación no podrá enviar mediciones hasta que cargue la
            nueva en su configuración.
          </p>
        </ConfirmDialog>
      )}
      {action?.kind === 'deactivate' && (
        <ConfirmDialog
          title={`Desactivar ${action.device.name}`}
          description="El dispositivo no se elimina: se conserva su historial y puede activarse más adelante."
          confirmLabel="Desactivar dispositivo"
          pendingLabel="Desactivando…"
          destructive
          pending={setStatus.isPending}
          error={setStatus.error}
          onConfirm={() => setStatus.mutate({ id: action.device.id, status: 'inactivo' })}
          onClose={closeAction}
        >
          <p className="text-sm">Mientras esté inactivo, el servidor rechazará las mediciones que envíe.</p>
        </ConfirmDialog>
      )}
      {panel && (
        <Card className="mb-4">
          <CardContent>
            {panel === 'fog' ? (
              <FogCollectorForm onDone={() => setPanel(null)} />
            ) : (
              <DeviceForm
                onCreated={(r) => {
                  setSecret(r)
                  setPanel(null)
                }}
              />
            )}
          </CardContent>
        </Card>
      )}
      <FilterToolbar kinds={['dispositivos']} keys={LIST_FILTERS} values={filters} onChange={setFilters} />
      <ErrorAlert error={devices.error ?? (action ? null : setStatus.error)} />
      {devices.isLoading && <Loading />}

      <div className="grid gap-4">
        {devices.data?.length === 0 && <p className="text-muted-foreground text-sm">No hay dispositivos registrados.</p>}
        {devices.data?.map((device) => {
          const deviceSensors = sensors.data?.filter((s) => s.device_id === device.id) ?? []
          const station = summary.data?.devices.find((d) => d.id === device.id)
          return (
            <Card key={device.id}>
              <CardHeader>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <CardTitle className="flex items-center gap-2">
                      {device.name} <LiveStatus status={device.status} station={station} />
                    </CardTitle>
                    <CardDescription>
                      {device.code} · Firmware {device.firmware_version ?? '—'} · Última comunicación{' '}
                      {formatDateTime(device.last_seen_at)}
                    </CardDescription>
                  </div>
                  {canManage && (
                    <div className="flex flex-wrap gap-2">
                      <Button size="sm" variant="outline" onClick={() => setSensorFor(sensorFor === device.id ? null : device.id)}>
                        <Plus /> Sensor
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => setAction({ kind: 'rotate', device })}
                      >
                        <KeyRound /> Nueva API key
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        // Desactivar se confirma; activar (o salir de mantenimiento) no tiene consecuencias que advertir.
                        onClick={() =>
                          device.status === 'activo'
                            ? setAction({ kind: 'deactivate', device })
                            : setStatus.mutate({ id: device.id, status: 'activo' })
                        }
                      >
                        {device.status === 'activo' ? 'Desactivar' : 'Activar'}
                      </Button>
                    </div>
                  )}
                </div>
              </CardHeader>
              <CardContent className="grid gap-4">
                {sensorFor === device.id && (
                  <SensorForm device={device} existingCodes={deviceSensors.map((s) => s.code)} onDone={() => setSensorFor(null)} />
                )}
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Código</TableHead>
                      <TableHead>Variable</TableHead>
                      <TableHead>Unidad / rango</TableHead>
                      <TableHead>Modelo</TableHead>
                      <TableHead>Estado</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {deviceSensors.length === 0 && (
                      <TableRow>
                        <TableCell colSpan={5} className="text-muted-foreground">
                          Sin sensores.
                        </TableCell>
                      </TableRow>
                    )}
                    {deviceSensors.map((s) => (
                      <TableRow key={s.id}>
                        <TableCell className="font-mono">{s.code}</TableCell>
                        <TableCell>{s.sensor_type.name}</TableCell>
                        <TableCell>
                          {s.sensor_type.unit} [{s.sensor_type.min_value}, {s.sensor_type.max_value}]
                        </TableCell>
                        <TableCell>{s.model ?? '—'}</TableCell>
                        <TableCell>
                          <LiveStatus status={s.status} station={device.status === 'activo' ? station : undefined} />
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          )
        })}
      </div>
    </>
  )
}
