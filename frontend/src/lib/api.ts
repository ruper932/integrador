import axios, { AxiosError } from 'axios'

import type { ApiErrorBody } from '@/types/api'

// La sesión viaja en una cookie HttpOnly emitida por la API; el frontend nunca maneja el token.
export const api = axios.create({
  baseURL: '/api/v1',
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
  timeout: 20_000,
})

export function errorMessage(error: unknown, fallback = 'Ocurrió un error inesperado.'): string {
  if (error instanceof AxiosError) {
    const body = error.response?.data as ApiErrorBody | undefined
    if (body?.error?.message) return body.error.message
    if (!error.response) return 'No hay conexión con el servidor local.'
  }
  return fallback
}

export function errorCode(error: unknown): string | undefined {
  if (error instanceof AxiosError) {
    return (error.response?.data as ApiErrorBody | undefined)?.error?.code
  }
  return undefined
}

export function httpStatus(error: unknown): number | undefined {
  return error instanceof AxiosError ? error.response?.status : undefined
}

/** Descarga un archivo generado por el backend (los reportes se generan en el servidor). */
export async function downloadFile(url: string, params: Record<string, unknown>, filename: string): Promise<void> {
  let response
  try {
    response = await api.get<Blob>(url, { params, responseType: 'blob' })
  } catch (error) {
    // Con responseType 'blob' el error JSON llega como Blob: se convierte para mostrar el mensaje.
    const data = (error as { response?: { data?: unknown } }).response?.data
    if (data instanceof Blob && data.type.includes('json')) {
      try {
        ;(error as { response: { data: unknown } }).response.data = JSON.parse(await data.text())
      } catch {
        // se muestra el mensaje genérico
      }
    }
    throw error
  }
  const href = URL.createObjectURL(response.data)
  const link = document.createElement('a')
  link.href = href
  link.download = filename
  link.click()
  URL.revokeObjectURL(href)
}
