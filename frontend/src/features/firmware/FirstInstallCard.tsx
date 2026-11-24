import { AxiosError } from 'axios'
import { CheckCircle2, CircleDashed, Loader2, Usb, XCircle } from 'lucide-react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { CardHead, Field, NativeSelect, Notice } from '@/components/common'
import { PasswordInput } from '@/components/PasswordInput'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { refreshStations, useDevices } from '@/features/devices/api'
import { api, errorMessage } from '@/lib/api'
import type { FirmwareRelease } from '@/types/api'

/** Web Serial solo existe en Chrome/Edge/Chromium y en páginas seguras (HTTPS o localhost); Brave lo trae apagado. */
function serialSupport(): 'ok' | 'navegador' | 'brave' | 'inseguro' {
  if (!window.isSecureContext) return 'inseguro'
  if ('serial' in navigator) return 'ok'
  return 'brave' in navigator ? 'brave' : 'navegador'
}

const SUPPORT_HELP = {
  inseguro: 'Abra el sistema con su dirección https:// (o http://localhost en el propio servidor): el acceso USB solo se permite en páginas seguras.',
  brave:
    'Brave trae el acceso USB desactivado. Escriba brave://flags/#brave-web-serial en la barra de direcciones, elija «Enabled» y reinicie el navegador; o use Chromium, Chrome o Edge.',
  navegador: 'Use Chromium, Google Chrome o Microsoft Edge en una computadora (no está disponible en Firefox, Safari ni en celulares).',
}

interface StationDefaults {
  wifi_ssid: string
  wifi_password_saved: boolean
  api_url: string
  ntp_server: string
}

type StepState = 'pendiente' | 'en_curso' | 'listo' | 'error'
const STEPS = ['Conectar el ESP32', 'Descargar y verificar las imágenes', 'Escribir el firmware', 'Comprobar el ESP32 y emitir la credencial', 'Enviar la configuración'] as const

const LOCAL_HOSTS = /^(localhost|127\.|\[?::1\]?$)/

function defaults() {
  const host = typeof window === 'undefined' ? '' : window.location.hostname
  const local = LOCAL_HOSTS.test(host)
  // Las estaciones envían por HTTP (puerto 80) aunque el navegador use HTTPS.
  return { apiUrl: local ? '' : `http://${host}/api/v1/iot/measurements/batch`, ntp: local ? '' : host }
}

function StepIcon({ state }: { state: StepState }) {
  if (state === 'listo') return <CheckCircle2 className="text-success size-4" aria-hidden />
  if (state === 'en_curso') return <Loader2 className="size-4 animate-spin" aria-hidden />
  if (state === 'error') return <XCircle className="text-danger size-4" aria-hidden />
  return <CircleDashed className="text-muted-foreground size-4" aria-hidden />
}

/** Primera instalación por USB desde el navegador: firmware + configuración de la estación. */
export function FirstInstallCard({ releases }: { releases: FirmwareRelease[] }) {
  const qc = useQueryClient()
  const devices = useDevices()
  const support = serialSupport()
  const saved = useQuery({
    queryKey: ['firmware', 'station-defaults'],
    queryFn: async () => (await api.get<StationDefaults>('/firmware/station-defaults')).data,
  })
  // null = usar el dato precargado (configuración del servidor o, si falta, la dirección de esta página).
  const [chosenRelease, setReleaseId] = useState<string | null>(null)
  const [chosenDevice, setDeviceId] = useState<string | null>(null)
  const [ssidInput, setSsid] = useState<string | null>(null)
  const [wifiPassword, setWifiPassword] = useState('')
  const [apiUrlInput, setApiUrl] = useState<string | null>(null)
  const [ntpInput, setNtp] = useState<string | null>(null)
  const [steps, setSteps] = useState<StepState[]>(STEPS.map(() => 'pendiente'))
  const [percent, setPercent] = useState(0)
  const [log, setLog] = useState<string[]>([])
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [flashed, setFlashed] = useState(false)
  const [result, setResult] = useState<string | null>(null)

  const active = (devices.data ?? []).filter((d) => d.status !== 'inactivo')
  const fallback = defaults()
  const releaseId = chosenRelease ?? (releases[0] ? String(releases[0].id) : '')
  const deviceId = chosenDevice ?? (active.length === 1 ? String(active[0]!.id) : '')
  const ssid = ssidInput ?? saved.data?.wifi_ssid ?? ''
  const apiUrl = apiUrlInput ?? (saved.data?.api_url || fallback.apiUrl)
  const ntp = ntpInput ?? (saved.data?.ntp_server || fallback.ntp)
  const passwordSaved = Boolean(saved.data?.wifi_password_saved)
  const release = releases.find((r) => String(r.id) === releaseId)
  const invalid = {
    apiUrl: !/^http:\/\/[^/\s]+\/api\/v1\/iot\/measurements\/batch$/.test(apiUrl)
      ? 'Use http://<IP del servidor>/api/v1/iot/measurements/batch (la estación no usa HTTPS)'
      : LOCAL_HOSTS.test(new URL(apiUrl).hostname)
        ? 'Indique la IP del servidor en la red: el ESP32 no llega a «localhost»'
        : undefined,
    ntp: !ntp.trim() || LOCAL_HOSTS.test(ntp.trim()) ? 'Indique la IP del servidor en la red local' : undefined,
    ssid: ssid.trim() ? undefined : 'Indique el nombre de la red Wi-Fi',
  }
  const ready = Boolean(releaseId && deviceId && !invalid.apiUrl && !invalid.ntp && !invalid.ssid)

  const mark = (index: number, state: StepState) => setSteps((s) => s.map((v, i) => (i === index ? state : v)))
  const write = (line: string) => setLog((l) => [...l.slice(-40), line])

  async function run(withFlash: boolean) {
    setBusy(true)
    setError(null)
    setResult(null)
    if (withFlash) {
      setSteps(STEPS.map(() => 'pendiente'))
      setPercent(0)
      setLog([])
    }
    let step = 0
    try {
      // requestPort debe llamarse primero, dentro del clic del usuario.
      mark(0, 'en_curso')
      const port = await navigator.serial.requestPort()
      mark(0, 'listo')
      // esptool-js solo se descarga al usarlo (no pesa en el resto del sistema).
      const { configure, downloadImages, flash } = await import('@/features/firmware/flasher')
      if (withFlash) {
        step = 1
        mark(1, 'en_curso')
        const images = await downloadImages(Number(releaseId))
        mark(1, 'listo')
        step = 2
        mark(2, 'en_curso')
        await flash(port, images, write, setPercent)
        mark(2, 'listo')
        setFlashed(true)
      }
      step = 3
      mark(3, 'en_curso')
      write('Reiniciando el ESP32 y esperando su respuesta…')
      let code = ''
      const running = await configure(
        port,
        async () => {
          // La credencial se emite solo cuando el ESP32 ya respondió (un intento fallido no deja credenciales de más).
          const credential = (
            await api.post<{ device_code: string; api_key: string; sample_interval_s: number; version: string; wifi_password: string | null }>(
              '/firmware/first-install',
              { device_id: Number(deviceId), release_id: Number(releaseId) },
            )
          ).data
          code = credential.device_code
          refreshStations(qc) // versión asignada y credencial nueva
          void qc.invalidateQueries({ queryKey: ['firmware', 'releases'] })
          mark(3, 'listo')
          write(`Credencial nueva emitida para ${credential.device_code} (no se muestra).`)
          step = 4
          mark(4, 'en_curso')
          return {
            ssid: ssid.trim(),
            // Si no se escribe otra, se usa la guardada en el servidor (llega con la credencial, sin mostrarse).
            wifiPassword: wifiPassword || credential.wifi_password || '',
            apiUrl,
            ntp: ntp.trim(),
            deviceCode: credential.device_code,
            apiKey: credential.api_key,
            sampleSeconds: credential.sample_interval_s,
          }
        },
        write,
      )
      mark(4, 'listo')
      setWifiPassword('')
      setResult(
        running
          ? `La estación ${code} quedó con el firmware ${running} y su configuración. Debería aparecer «En línea» en unos minutos.`
          : `Configuración guardada en ${code}. Debería aparecer «En línea» en unos minutos.`,
      )
    } catch (e) {
      // Cerrar la ventana de selección del puerto no es un error.
      if (e instanceof DOMException && e.name === 'NotFoundError') {
        mark(0, 'pendiente')
      } else {
        mark(step, 'error')
        setError(e instanceof AxiosError || !(e instanceof Error) ? errorMessage(e) : e.message)
      }
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card>
      <CardHead
        title="Primera instalación por USB"
        subtitle="Para un ESP32 nuevo: escribe la versión elegida y deja la estación configurada, sin herramientas en la PC."
      />
      <CardContent className="grid gap-4">
        {support !== 'ok' ? (
          <Notice tone="warning" title="Este navegador no puede usar el puerto USB">
            {SUPPORT_HELP[support]}
          </Notice>
        ) : (
          <>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Versión a instalar" htmlFor="fi-release">
                <NativeSelect id="fi-release" value={releaseId} onChange={(e) => setReleaseId(e.target.value)} disabled={busy}>
                  <option value="">Seleccione…</option>
                  {releases.map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.version}
                    </option>
                  ))}
                </NativeSelect>
              </Field>
              <Field label="Estación (registrada en Dispositivos)" htmlFor="fi-device" hint="Se le emite una API key nueva; la anterior deja de funcionar">
                <NativeSelect id="fi-device" value={deviceId} onChange={(e) => setDeviceId(e.target.value)} disabled={busy}>
                  <option value="">Seleccione…</option>
                  {active.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name} ({d.code})
                    </option>
                  ))}
                </NativeSelect>
              </Field>
              <Field label="Red Wi-Fi" htmlFor="fi-ssid" error={ssid ? invalid.ssid : undefined}>
                <Input id="fi-ssid" value={ssid} onChange={(e) => setSsid(e.target.value)} disabled={busy} autoComplete="off" />
              </Field>
              <Field
                label="Contraseña de la red Wi-Fi"
                htmlFor="fi-pass"
                hint={passwordSaved ? 'Guardada en el servidor: déjela vacía para usarla (no se muestra)' : 'Se envía solo al ESP32; no se muestra ni se registra'}
              >
                <PasswordInput
                  id="fi-pass"
                  value={wifiPassword}
                  onChange={(e) => setWifiPassword(e.target.value)}
                  disabled={busy}
                  autoComplete="off"
                  placeholder={passwordSaved ? '•••••••• (guardada)' : undefined}
                />
              </Field>
              <Field label="Dirección de envío de mediciones" htmlFor="fi-url" error={apiUrl ? invalid.apiUrl : undefined}>
                <Input id="fi-url" value={apiUrl} onChange={(e) => setApiUrl(e.target.value)} disabled={busy} placeholder="http://192.168.1.10/api/v1/iot/measurements/batch" />
              </Field>
              <Field label="Servidor de hora (NTP)" htmlFor="fi-ntp" error={ntp ? invalid.ntp : undefined} hint="Normalmente, la IP del servidor institucional">
                <Input id="fi-ntp" value={ntp} onChange={(e) => setNtp(e.target.value)} disabled={busy} placeholder="192.168.1.10" />
              </Field>
            </div>
            <p className="text-muted-foreground text-xs">
              Conecte el ESP32 por USB. Se borra toda su memoria y se escriben el arranque, la tabla de particiones y la versión
              {release ? ` ${release.version}` : ' elegida'}. Si la conexión falla, mantenga presionado el botón BOOT del ESP32 al
              iniciar.
            </p>
            <div className="flex flex-wrap gap-2">
              <Button onClick={() => run(true)} disabled={!ready || busy}>
                <Usb /> {busy ? 'Instalando…' : 'Conectar e instalar'}
              </Button>
              <Button
                variant="outline"
                onClick={() => run(false)}
                disabled={!ready || busy}
                title="Para un ESP32 que ya tiene el firmware: solo le carga la configuración"
              >
                {flashed && (steps[3] === 'error' || steps[4] === 'error') ? 'Reintentar configuración' : 'Solo configurar'}
              </Button>
            </div>
            {steps.some((s) => s !== 'pendiente') && (
              <ol className="grid gap-1.5 text-sm" aria-live="polite">
                {STEPS.map((label, i) => (
                  <li key={label} className="flex items-center gap-2">
                    <StepIcon state={steps[i]!} />
                    <span className={steps[i] === 'pendiente' ? 'text-muted-foreground' : undefined}>
                      {label}
                      {i === 2 && steps[2] === 'en_curso' && ` (${percent} %)`}
                    </span>
                  </li>
                ))}
              </ol>
            )}
            {steps[2] === 'en_curso' && (
              <div className="bg-muted h-2 overflow-hidden rounded-full" role="progressbar" aria-valuenow={percent} aria-valuemin={0} aria-valuemax={100} aria-label="Escritura del firmware">
                <div className="bg-emphasis h-full transition-[width]" style={{ width: `${percent}%` }} />
              </div>
            )}
            {error && <Notice tone="danger" title="No se completó la instalación">{error}</Notice>}
            {result && <Notice tone="success" title="Instalación completa">{result}</Notice>}
            {log.length > 0 && (
              <details className="text-xs">
                <summary className="text-muted-foreground cursor-pointer">Detalle técnico</summary>
                <pre className="bg-muted mt-2 max-h-48 overflow-auto rounded-md p-2 whitespace-pre-wrap">{log.join('\n')}</pre>
              </details>
            )}
          </>
        )}
      </CardContent>
    </Card>
  )
}
