import { useMutation, useQueryClient } from '@tanstack/react-query'
import { KeyRound, Plus } from 'lucide-react'
import { useState } from 'react'
import { useForm } from 'react-hook-form'

import { ErrorAlert, Field, Loading, NativeSelect, PageHeader, SecretNotice, StatusBadge } from '@/components/common'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { useHasPermission } from '@/features/auth/useAuth'
import { ExportReportButton } from '@/features/reports/ExportReportButton'
import { useDevices, useFogCollectors, useSensors, useSensorTypes, useTanks } from '@/features/devices/api'
import { api } from '@/lib/api'
import { formatDateTime } from '@/lib/format'
import type { DeviceWithKey } from '@/types/api'

const optionalId = (v: string) => (v === '' ? null : Number(v))

function FogCollectorForm({ onDone }: { onDone: () => void }) {
  const qc = useQueryClient()
  const form = useForm({ defaultValues: { code: '', name: '', mesh_area_m2: '' } })
  const create = useMutation({
    mutationFn: (v: { code: string; name: string; mesh_area_m2: string }) =>
      api.post('/fog-collectors', { code: v.code, name: v.name, mesh_area_m2: v.mesh_area_m2 || null }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['fog-collectors'] })
      onDone()
    },
  })
  return (
    <form onSubmit={form.handleSubmit((v) => create.mutate(v))} className="grid gap-3 sm:grid-cols-4 sm:items-end">
      <Field label="Código" htmlFor="fc-code">
        <Input id="fc-code" required {...form.register('code')} placeholder="AN-01" />
      </Field>
      <Field label="Nombre" htmlFor="fc-name">
        <Input id="fc-name" required {...form.register('name')} />
      </Field>
      <Field label="Área de malla (m²)" htmlFor="fc-area">
        <Input id="fc-area" type="number" step="0.01" min="0" {...form.register('mesh_area_m2')} />
      </Field>
      <Button type="submit" disabled={create.isPending}>
        Guardar atrapanieblas
      </Button>
      <div className="sm:col-span-4">
        <ErrorAlert error={create.error} />
      </div>
    </form>
  )
}

function DeviceForm({ onCreated }: { onCreated: (r: DeviceWithKey) => void }) {
  const qc = useQueryClient()
  const fogCollectors = useFogCollectors()
  const form = useForm({ defaultValues: { code: '', name: '', fog_collector_id: '' } })
  const create = useMutation({
    mutationFn: async (v: { code: string; name: string; fog_collector_id: string }) =>
      (
        await api.post<DeviceWithKey>('/devices', {
          code: v.code,
          name: v.name,
          fog_collector_id: optionalId(v.fog_collector_id),
        })
      ).data,
    onSuccess: (r) => {
      qc.invalidateQueries({ queryKey: ['devices'] })
      form.reset()
      onCreated(r)
    },
  })
  return (
    <form onSubmit={form.handleSubmit((v) => create.mutate(v))} className="grid gap-3 sm:grid-cols-4 sm:items-end">
      <Field label="Identificador (X-Device-Id)" htmlFor="d-code">
        <Input id="d-code" required placeholder="esp32-01" {...form.register('code')} />
      </Field>
      <Field label="Nombre" htmlFor="d-name">
        <Input id="d-name" required {...form.register('name')} />
      </Field>
      <Field label="Atrapanieblas" htmlFor="d-fc">
        <NativeSelect id="d-fc" {...form.register('fog_collector_id')}>
          <option value="">Ninguno</option>
          {fogCollectors.data?.map((f) => (
            <option key={f.id} value={f.id}>
              {f.code} — {f.name}
            </option>
          ))}
        </NativeSelect>
      </Field>
      <Button type="submit" disabled={create.isPending}>
        Registrar dispositivo
      </Button>
      <div className="sm:col-span-4">
        <ErrorAlert error={create.error} />
      </div>
    </form>
  )
}

function SensorForm({ deviceId, onDone }: { deviceId: number; onDone: () => void }) {
  const qc = useQueryClient()
  const types = useSensorTypes()
  const tanks = useTanks()
  const fogCollectors = useFogCollectors()
  const form = useForm({ defaultValues: { sensor_type_id: '', code: '', model: '', tank_id: '', fog_collector_id: '' } })
  const create = useMutation({
    mutationFn: (v: { sensor_type_id: string; code: string; model: string; tank_id: string; fog_collector_id: string }) =>
      api.post('/sensors', {
        device_id: deviceId,
        sensor_type_id: Number(v.sensor_type_id),
        code: v.code,
        model: v.model || null,
        tank_id: optionalId(v.tank_id),
        fog_collector_id: optionalId(v.fog_collector_id),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['sensors'] })
      onDone()
    },
  })
  return (
    <form onSubmit={form.handleSubmit((v) => create.mutate(v))} className="grid gap-3 sm:grid-cols-3 sm:items-end">
      <Field label="Tipo" htmlFor="s-type">
        <NativeSelect id="s-type" required {...form.register('sensor_type_id')}>
          <option value="">Seleccione…</option>
          {types.data?.map((t) => (
            <option key={t.id} value={t.id}>
              {t.name} ({t.unit})
            </option>
          ))}
        </NativeSelect>
      </Field>
      <Field label="Código en firmware" htmlFor="s-code">
        <Input id="s-code" required placeholder="temp" {...form.register('code')} />
      </Field>
      <Field label="Modelo" htmlFor="s-model">
        <Input id="s-model" placeholder="SHT31" {...form.register('model')} />
      </Field>
      <Field label="Atrapanieblas (volumen)" htmlFor="s-fc" hint="Por defecto, el del dispositivo">
        <NativeSelect id="s-fc" {...form.register('fog_collector_id')}>
          <option value="">—</option>
          {fogCollectors.data?.map((f) => (
            <option key={f.id} value={f.id}>
              {f.code}
            </option>
          ))}
        </NativeSelect>
      </Field>
      <Field label="Tanque (nivel)" htmlFor="s-tank">
        <NativeSelect id="s-tank" {...form.register('tank_id')}>
          <option value="">—</option>
          {tanks.data?.map((t) => (
            <option key={t.id} value={t.id}>
              {t.code}
            </option>
          ))}
        </NativeSelect>
      </Field>
      <Button type="submit" disabled={create.isPending}>
        Agregar sensor
      </Button>
      <div className="sm:col-span-3">
        <ErrorAlert error={create.error} />
      </div>
    </form>
  )
}

export function DevicesPage() {
  const can = useHasPermission()
  const canManage = can('infraestructura.gestionar')
  const qc = useQueryClient()
  const devices = useDevices()
  const sensors = useSensors()
  const [panel, setPanel] = useState<'device' | 'fog' | null>(null)
  const [sensorFor, setSensorFor] = useState<number | null>(null)
  const [secret, setSecret] = useState<DeviceWithKey | null>(null)

  const rotate = useMutation({
    mutationFn: async (id: number) => (await api.post<DeviceWithKey>(`/devices/${id}/credentials`)).data,
    onSuccess: setSecret,
  })
  const setStatus = useMutation({
    mutationFn: ({ id, status }: { id: number; status: string }) => api.put(`/devices/${id}`, { status }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['devices'] }),
  })

  return (
    <>
      <PageHeader
        eyebrow="Operaciones"
        title="Dispositivos y sensores"
        description="Estaciones ESP32, sus credenciales y los sensores asociados."
        actions={
          <>
            <ExportReportButton kinds={['dispositivos']} />
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
        <div className="mb-4">
          <SecretNotice title={`API key de ${secret.device.code}`} secret={secret.api_key}>
            Cárguela en la configuración segura del firmware (no en el código fuente).
          </SecretNotice>
        </div>
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
      <ErrorAlert error={devices.error ?? rotate.error ?? setStatus.error} />
      {devices.isLoading && <Loading />}

      <div className="grid gap-4">
        {devices.data?.length === 0 && <p className="text-muted-foreground text-sm">No hay dispositivos registrados.</p>}
        {devices.data?.map((device) => {
          const deviceSensors = sensors.data?.filter((s) => s.device_id === device.id) ?? []
          return (
            <Card key={device.id}>
              <CardHeader>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <CardTitle className="flex items-center gap-2">
                      {device.name} <StatusBadge value={device.status} />
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
                        onClick={() => {
                          if (confirm('La API key actual dejará de funcionar. ¿Continuar?')) rotate.mutate(device.id)
                        }}
                      >
                        <KeyRound /> Nueva API key
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() =>
                          setStatus.mutate({ id: device.id, status: device.status === 'activo' ? 'inactivo' : 'activo' })
                        }
                      >
                        {device.status === 'activo' ? 'Desactivar' : 'Activar'}
                      </Button>
                    </div>
                  )}
                </div>
              </CardHeader>
              <CardContent className="grid gap-4">
                {sensorFor === device.id && <SensorForm deviceId={device.id} onDone={() => setSensorFor(null)} />}
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
                          <StatusBadge value={s.status} />
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
