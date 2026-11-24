import { formatNumber } from '@/lib/format'

// Igual que el backend: ranura de aplicación OTA de la tabla de particiones por defecto (0x140000).
export const MAX_IMAGE_BYTES = 0x140000

/** Validación previa al envío; el backend además revisa el contenido (cabecera ESP32 y versión). */
export function imageError(file: File | null): string | null {
  if (!file) return 'Seleccione el archivo firmware.bin'
  if (!file.name.toLowerCase().endsWith('.bin')) return 'El archivo debe ser .bin (el firmware.bin generado por PlatformIO)'
  if (file.size > MAX_IMAGE_BYTES) return `Supera el máximo de ${formatNumber(MAX_IMAGE_BYTES / 1024, 0)} KB de una ranura OTA`
  return null
}
