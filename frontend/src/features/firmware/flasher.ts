/**
 * Primera instalación del ESP32 desde el navegador (Web Serial + esptool-js), sin herramientas en la PC.
 *
 * 1. Escribe por USB el bootloader, la tabla de particiones, boot_app0 y el firmware elegido (verificados
 *    con SHA-256 contra el servidor).
 * 2. Tras reiniciar, el firmware espera su configuración por el puerto serie (`set <clave> <valor>` y
 *    `save`, ver firmware/README.md); se la envía el navegador. La API key y la contraseña Wi-Fi no se
 *    muestran ni se registran en el historial de la pantalla.
 */
import { ESPLoader, Transport } from 'esptool-js'

import { api } from '@/lib/api'

export interface FlashPart {
  name: string
  address: number
  size: number
  sha256: string
}

export interface StationSettings {
  ssid: string
  wifiPassword: string
  apiUrl: string
  ntp: string
  deviceCode: string
  apiKey: string
  sampleSeconds: number
}

export type Log = (line: string) => void

/** Comandos de configuración en el formato que acepta el firmware; `save` al final la guarda en NVS. */
export function configCommands(s: StationSettings): string[] {
  const lines: [string, string | number][] = [
    ['ssid', s.ssid],
    ['wifi_pass', s.wifiPassword],
    ['api_url', s.apiUrl],
    ['device_id', s.deviceCode],
    ['device_key', s.apiKey],
    ['ntp', s.ntp],
    ['sample_s', s.sampleSeconds],
  ]
  for (const [key, value] of lines) {
    if (/[\r\n]/.test(String(value))) throw new Error(`El valor de ${key} no puede tener saltos de línea.`)
  }
  return [...lines.filter(([key, value]) => key !== 'wifi_pass' || value !== '').map(([k, v]) => `set ${k} ${v}`), 'save']
}

async function sha256(data: Uint8Array): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', data as BufferSource)
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, '0')).join('')
}

/** Descarga las imágenes y comprueba que lleguen íntegras antes de tocar el ESP32. */
export async function downloadImages(releaseId: number): Promise<{ part: FlashPart; data: Uint8Array }[]> {
  const plan = (await api.get<FlashPart[]>(`/firmware/releases/${releaseId}/flash-plan`)).data
  return Promise.all(
    plan.map(async (part) => {
      const url = part.name === 'firmware' ? `/firmware/releases/${releaseId}/image` : `/firmware/base/${part.name}`
      const data = new Uint8Array((await api.get<ArrayBuffer>(url, { responseType: 'arraybuffer' })).data)
      if ((await sha256(data)) !== part.sha256) throw new Error(`La imagen «${part.name}» llegó dañada; vuelva a intentarlo.`)
      return { part, data }
    }),
  )
}

/** Escribe las imágenes (borra antes toda la memoria) y reinicia el ESP32. */
export async function flash(
  port: SerialPort,
  images: { part: FlashPart; data: Uint8Array }[],
  log: Log,
  progress: (percent: number) => void,
): Promise<void> {
  const transport = new Transport(port, false)
  const terminal = { clean() {}, writeLine: log, write() {} }
  const loader = new ESPLoader({ transport, baudrate: 460800, romBaudrate: 115200, terminal })
  try {
    const chip = await loader.main()
    log(`Chip detectado: ${chip}`)
    if (loader.chip.CHIP_NAME !== 'ESP32') {
      throw new Error(`Este firmware es para ESP32 (placa esp32dev); el chip conectado es ${loader.chip.CHIP_NAME}.`)
    }
    const total = images.reduce((sum, i) => sum + i.data.length, 0)
    const done = images.map(() => 0)
    await loader.writeFlash({
      fileArray: images.map((i) => ({ data: i.data, address: i.part.address })),
      flashMode: 'keep',
      flashFreq: 'keep',
      flashSize: 'keep',
      eraseAll: true,
      compress: true,
      reportProgress: (index, written, size) => {
        done[index] = (written / size) * images[index]!.data.length
        progress(Math.round((done.reduce((a, b) => a + b, 0) / total) * 100))
      },
    })
    await loader.after('hard_reset')
  } finally {
    await transport.disconnect()
  }
}

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

/**
 * Reinicia el ESP32, espera a que pida su configuración y recién entonces obtiene los datos (la
 * credencial se emite solo si el ESP32 responde), los envía y confirma que se guardaron.
 */
export async function configure(
  port: SerialPort,
  getSettings: () => Promise<StationSettings>,
  log: Log,
): Promise<string | null> {
  await port.open({ baudRate: 115200 })
  // El navegador abre el puerto con DTR/RTS activos y, en placas con reinicio automático (CP2102/CH340),
  // RTS mantiene al ESP32 en reinicio. Se sueltan y se da un pulso de reinicio normal (sin modo de carga).
  await port.setSignals({ dataTerminalReady: false, requestToSend: false })
  await sleep(50)
  await port.setSignals({ requestToSend: true })
  await sleep(120)
  await port.setSignals({ requestToSend: false })
  const reader = port.readable!.getReader()
  const writer = port.writable!.getWriter()
  const decoder = new TextDecoder()
  let buffer = ''
  // Una sola lectura pendiente a la vez: si vence la espera, la misma lectura se reutiliza (no se pierden datos).
  let pending: Promise<ReadableStreamReadResult<Uint8Array>> | null = null
  const waitFor = async (pattern: RegExp, ms: number): Promise<RegExpMatchArray | null> => {
    const deadline = Date.now() + ms
    while (Date.now() < deadline) {
      const match = buffer.match(pattern)
      if (match) return match
      pending ??= reader.read()
      const chunk = await Promise.race([pending, new Promise<null>((resolve) => setTimeout(() => resolve(null), 300))])
      if (chunk === null) continue
      pending = null
      if (chunk.done) break
      buffer += decoder.decode(chunk.value, { stream: true })
    }
    return buffer.match(pattern)
  }
  try {
    // El primer arranque tras borrar la memoria formatea LittleFS: puede tardar varios segundos.
    if (!(await waitFor(/Configuración incompleta/, 30_000))) {
      throw new Error('El ESP32 no respondió por el puerto serie. Cierre otros programas que usen el puerto (monitor serie), desconecte y vuelva a conectar el ESP32 y use «Solo configurar».')
    }
    log('El ESP32 respondió y espera su configuración.')
    const settings = await getSettings()
    log('Enviando la configuración…')
    for (const line of configCommands(settings)) {
      await writer.write(new TextEncoder().encode(`${line}\n`))
      await sleep(150)
    }
    if (!(await waitFor(/Configuración guardada\./, 10_000))) throw new Error('El ESP32 no confirmó que guardó la configuración.')
    log('Configuración guardada en el ESP32.')
    // Al arrancar con la configuración completa, el firmware informa su versión.
    const version = await waitFor(/ATINA-FW:([^;\s]+);/, 15_000)
    return version?.[1] ?? null
  } finally {
    await reader.cancel().catch(() => undefined)
    reader.releaseLock()
    writer.releaseLock()
    await port.close()
  }
}
