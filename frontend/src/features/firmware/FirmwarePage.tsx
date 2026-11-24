import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, CircleDashed, Clock, HardDriveUpload } from 'lucide-react'
import { useState } from 'react'

import { CardHead, EmptyState, ErrorAlert, Field, Loading, NativeSelect, Notice, PageHeader } from '@/components/common'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Textarea } from '@/components/ui/textarea'
import { refreshStations, useDevices } from '@/features/devices/api'
import { FirstInstallCard } from '@/features/firmware/FirstInstallCard'
import { imageError } from '@/features/firmware/rules'
import { api } from '@/lib/api'
import { formatDateTime, formatNumber, relativeTime } from '@/lib/format'
import type { Device, FirmwareRelease } from '@/types/api'

const RELEASES_KEY = ['firmware', 'releases']

function UploadForm() {
  const qc = useQueryClient()
  const [file, setFile] = useState<File | null>(null)
  const [notes, setNotes] = useState('')
  const [touched, setTouched] = useState(false)
  const error = imageError(file)
  const upload = useMutation({
    mutationFn: async () =>
      (
        await api.post<FirmwareRelease>('/firmware/releases', file, {
          headers: { 'Content-Type': 'application/octet-stream' },
          params: { notes: notes.trim() || undefined },
        })
      ).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: RELEASES_KEY })
      setFile(null)
      setNotes('')
      setTouched(false)
    },
  })

  return (
    <form
      className="grid gap-3"
      noValidate
      onSubmit={(e) => {
        e.preventDefault()
        setTouched(true)
        if (!error) upload.mutate()
      }}
    >
      <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
        <Field
          label="Archivo de firmware"
          htmlFor="fw-file"
          error={touched ? (error ?? undefined) : undefined}
          hint="firmware/.pio/build/esp32dev/firmware.bin · la versión se lee del archivo"
        >
          <Input
            id="fw-file"
            type="file"
            accept=".bin,application/octet-stream"
            key={upload.isSuccess ? upload.data.id : 'nuevo'}
            onChange={(e) => {
              setFile(e.target.files?.[0] ?? null)
              upload.reset()
            }}
          />
        </Field>
        <Field label="Notas de la versión (opcional)" htmlFor="fw-notes">
          <Textarea id="fw-notes" rows={2} maxLength={500} value={notes} onChange={(e) => setNotes(e.target.value)} />
        </Field>
      </div>
      <ErrorAlert error={upload.error} />
      {upload.isSuccess && (
        <Notice tone="success">
          Versión {upload.data.version} cargada. Asígnela primero a una estación de prueba y verifique que siga enviando
          datos antes de extenderla al resto.
        </Notice>
      )}
      <div>
        <Button type="submit" disabled={upload.isPending}>
          <HardDriveUpload /> {upload.isPending ? 'Cargando…' : 'Cargar versión'}
        </Button>
      </div>
    </form>
  )
}

function UpdateState({ device }: { device: Device }) {
  if (!device.target_firmware_version) {
    return (
      <Badge variant="secondary">
        <CircleDashed aria-hidden /> Sin actualización asignada
      </Badge>
    )
  }
  if (device.target_firmware_version === device.firmware_version) {
    return (
      <Badge variant="success">
        <CheckCircle2 aria-hidden /> Al día
      </Badge>
    )
  }
  return (
    <Badge variant="warning">
      <Clock aria-hidden /> Pendiente de instalar
    </Badge>
  )
}

function DevicesCard({ releases }: { releases: FirmwareRelease[] }) {
  const qc = useQueryClient()
  const devices = useDevices()
  const assign = useMutation({
    mutationFn: ({ deviceId, releaseId }: { deviceId: number; releaseId: number | null }) =>
      api.put('/firmware/assignments', { release_id: releaseId, device_ids: [deviceId] }),
    onSuccess: () => {
      refreshStations(qc)
      qc.invalidateQueries({ queryKey: RELEASES_KEY })
    },
  })
  const idByVersion = new Map(releases.map((r) => [r.version, r.id]))

  return (
    <Card>
      <CardHead
        title="Estaciones"
        subtitle="Cada estación consulta cada hora si tiene una versión asignada; la descarga, la verifica (MD5) y se reinicia con ella."
      />
      <CardContent className="grid gap-3">
        <ErrorAlert error={devices.error ?? assign.error} />
        {devices.isLoading ? (
          <Loading />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Estación</TableHead>
                <TableHead>Versión instalada</TableHead>
                <TableHead>Versión a instalar</TableHead>
                <TableHead>Estado</TableHead>
                <TableHead>Última comunicación</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {devices.data?.map((d) => (
                <TableRow key={d.id}>
                  <TableCell>
                    {d.name} <span className="text-muted-foreground">({d.code})</span>
                    {d.status !== 'activo' && <span className="text-muted-foreground block text-xs">{d.status}</span>}
                  </TableCell>
                  <TableCell className="tabular-nums">{d.firmware_version ?? '—'}</TableCell>
                  <TableCell>
                    <NativeSelect
                      aria-label={`Versión a instalar en ${d.name}`}
                      className="h-8 w-44"
                      value={d.target_firmware_version ? String(idByVersion.get(d.target_firmware_version) ?? '') : ''}
                      disabled={assign.isPending}
                      onChange={(e) =>
                        assign.mutate({ deviceId: d.id, releaseId: e.target.value ? Number(e.target.value) : null })
                      }
                    >
                      <option value="">No actualizar</option>
                      {releases.map((r) => (
                        <option key={r.id} value={r.id}>
                          {r.version}
                        </option>
                      ))}
                    </NativeSelect>
                  </TableCell>
                  <TableCell>
                    <UpdateState device={d} />
                  </TableCell>
                  <TableCell className="text-muted-foreground text-sm">{relativeTime(d.last_seen_at)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  )
}

export function FirmwarePage() {
  const releases = useQuery({
    queryKey: RELEASES_KEY,
    queryFn: async () => (await api.get<FirmwareRelease[]>('/firmware/releases')).data,
  })

  return (
    <>
      <PageHeader
        eyebrow="Operaciones"
        title="Firmware de estaciones"
        description="Cargue el firmware compilado del ESP32 (DHT11 + BME280), instálelo por USB en una estación nueva y actualice las demás por la red local."
      />
      <div className="grid gap-5">
        <Card>
          <CardHead title="Cargar versión" subtitle="Antes de compilar, aumente FIRMWARE_VERSION en include/config.h." />
          <CardContent>
            <UploadForm />
          </CardContent>
        </Card>

        <Card>
          <CardHead title="Versiones cargadas" subtitle="No se eliminan: quedan como historial y permiten volver atrás." />
          <CardContent>
            <ErrorAlert error={releases.error} />
            {releases.isLoading ? (
              <Loading />
            ) : releases.data?.length === 0 ? (
              <EmptyState icon={HardDriveUpload} title="Todavía no se cargó ninguna versión" />
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Versión</TableHead>
                    <TableHead>Cargada</TableHead>
                    <TableHead className="text-right">Tamaño</TableHead>
                    <TableHead>SHA-256</TableHead>
                    <TableHead>Notas</TableHead>
                    <TableHead className="text-right">Estaciones</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {releases.data?.map((r) => (
                    <TableRow key={r.id}>
                      <TableCell className="font-medium">{r.version}</TableCell>
                      <TableCell>
                        {formatDateTime(r.created_at)}
                        <span className="text-muted-foreground block text-xs">{r.uploaded_by}</span>
                      </TableCell>
                      <TableCell className="text-right tabular-nums">{formatNumber(r.size_bytes / 1024, 0)} KB</TableCell>
                      <TableCell>
                        <code className="text-xs" title={r.sha256}>
                          {r.sha256.slice(0, 12)}…
                        </code>
                      </TableCell>
                      <TableCell className="max-w-xs whitespace-normal">{r.notes ?? '—'}</TableCell>
                      <TableCell className="text-right tabular-nums">{r.assigned_devices}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>

        <FirstInstallCard releases={releases.data ?? []} />

        <DevicesCard releases={releases.data ?? []} />
      </div>
    </>
  )
}
