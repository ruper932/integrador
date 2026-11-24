export const INCIDENT_PERMISSIONS = ['incidencias.reportar', 'incidencias.atender', 'incidencias.supervisar']
export const RELOCATION_PERMISSIONS = ['reubicaciones.solicitar', 'reubicaciones.atender', 'reubicaciones.supervisar']

/** Con una lista de permisos basta cualquiera de ellos (el backend valida cada operación). */
export function allowed(permissions: string[], required: string | string[]): boolean {
  return (Array.isArray(required) ? required : [required]).some((p) => permissions.includes(p))
}
