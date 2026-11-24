import type { Incident, Relocation } from '@/types/api'

/** Quién mira el proceso: su id y si puede atender (aceptar) casos nuevos. */
export interface Viewer {
  id: number | undefined
  canAttend: boolean
}

/** Siguiente paso de un proceso visto por una persona concreta. */
export interface NextStep {
  /** Le toca a quien mira: hay un botón que puede usar ahora. */
  yourTurn: boolean
  /** Acción que espera el proceso (corta, para la lista). */
  action: 'aceptar' | 'iniciar' | 'finalizar'
  title: string
  text: string
}

export const ACTION_LABELS: Record<NextStep['action'], string> = {
  aceptar: 'Aceptar',
  iniciar: 'Iniciar',
  finalizar: 'Finalizar',
}

/** Paso pendiente de un reporte de incidencia; null cuando ya terminó. */
export function incidentNextStep(incident: Incident, viewer: Viewer): NextStep | null {
  const who = incident.assignee?.full_name ?? 'El personal asignado'
  const mine = incident.assignee !== null && incident.assignee.id === viewer.id
  switch (incident.status) {
    case 'abierto':
      return viewer.canAttend
        ? {
            yourTurn: true,
            action: 'aceptar',
            title: 'Acepte el reporte para atenderlo',
            text:
              incident.source === 'sistema'
                ? 'Quedará asignado a usted.'
                : 'Quedará asignado a usted y se avisará a quien lo reportó.',
          }
        : {
            yourTurn: false,
            action: 'aceptar',
            title: 'Esperando al personal de mantenimiento',
            text: 'Nadie lo aceptó todavía. Recibirá un aviso cuando alguien lo tome.',
          }
    case 'aceptado':
      return mine
        ? {
            yourTurn: true,
            action: 'iniciar',
            title: 'Inicie el mantenimiento al llegar al lugar',
            text: 'Quien lo reportó verá que el trabajo está en curso.',
          }
        : { yourTurn: false, action: 'iniciar', title: `${who} aceptó el reporte`, text: 'Falta que inicie el mantenimiento.' }
    case 'en_progreso':
      return mine
        ? {
            yourTurn: true,
            action: 'finalizar',
            title: 'Registre el trabajo y finalice',
            text: 'Indique qué hizo, cómo quedó el componente y los repuestos usados (se descuentan del inventario).',
          }
        : { yourTurn: false, action: 'finalizar', title: `${who} está realizando el mantenimiento`, text: 'Se avisará cuando lo finalice.' }
    default:
      return null
  }
}

/** Paso pendiente de una solicitud de reubicación; null cuando ya terminó o fue rechazada. */
export function relocationNextStep(relocation: Relocation, viewer: Viewer): NextStep | null {
  const who = relocation.assignee?.full_name ?? 'El personal asignado'
  const mine = relocation.assignee !== null && relocation.assignee.id === viewer.id
  switch (relocation.status) {
    case 'pendiente':
      return viewer.canAttend
        ? {
            yourTurn: true,
            action: 'aceptar',
            title: 'Acepte o rechace la solicitud',
            text: 'Si la acepta, el traslado queda asignado a usted y se avisa a quien la pidió.',
          }
        : {
            yourTurn: false,
            action: 'aceptar',
            title: 'Esperando al personal de mantenimiento',
            text: 'Nadie revisó la solicitud todavía. Recibirá un aviso cuando la acepten o la rechacen.',
          }
    case 'aceptado':
      return mine
        ? {
            yourTurn: true,
            action: 'iniciar',
            title: 'Inicie el traslado cuando comience el desmontaje',
            text: 'Mientras tanto, todavía puede rechazar la solicitud si no hay un lugar adecuado.',
          }
        : { yourTurn: false, action: 'iniciar', title: `${who} aceptó la solicitud`, text: 'Falta que inicie el traslado.' }
    case 'en_progreso':
      return mine
        ? {
            yourTurn: true,
            action: 'finalizar',
            title: 'Registre la nueva ubicación y finalice',
            text: 'El atrapanieblas y sus estaciones pasarán a la nueva ubicación.',
          }
        : { yourTurn: false, action: 'finalizar', title: `${who} está trasladando el atrapanieblas`, text: 'Se avisará cuando termine.' }
    default:
      return null
  }
}
