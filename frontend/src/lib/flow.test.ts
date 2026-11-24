import { incidentNextStep, relocationNextStep } from '@/lib/flow'
import type { Incident, Person, Relocation } from '@/types/api'

const tecnico: Person = { id: 7, username: 'tecnico1', full_name: 'Rosa Tola' }
const attender = { id: 7, canAttend: true }
const otherAttender = { id: 8, canAttend: true }
const teacher = { id: 3, canAttend: false }

const incident = (status: Incident['status'], assignee: Person | null = tecnico) =>
  ({ status, assignee, source: 'usuario' }) as Incident
const relocation = (status: Relocation['status'], assignee: Person | null = tecnico) => ({ status, assignee }) as Relocation

test('un reporte abierto le toca a quien puede atender; quien reportó espera', () => {
  expect(incidentNextStep(incident('abierto', null), attender)).toMatchObject({ yourTurn: true, action: 'aceptar' })
  expect(incidentNextStep(incident('abierto', null), teacher)).toMatchObject({ yourTurn: false })
})

test('aceptado y en progreso le tocan solo al asignado; los demás ven quién lo tiene', () => {
  expect(incidentNextStep(incident('aceptado'), attender)).toMatchObject({ yourTurn: true, action: 'iniciar' })
  expect(incidentNextStep(incident('en_progreso'), attender)).toMatchObject({ yourTurn: true, action: 'finalizar' })
  const other = incidentNextStep(incident('en_progreso'), otherAttender)
  expect(other?.yourTurn).toBe(false)
  expect(other?.title).toContain('Rosa Tola')
})

test('un proceso terminado no tiene siguiente paso', () => {
  expect(incidentNextStep(incident('finalizado'), attender)).toBeNull()
  expect(relocationNextStep(relocation('finalizado'), attender)).toBeNull()
  expect(relocationNextStep(relocation('rechazado'), attender)).toBeNull()
})

test('la reubicación sigue el mismo reparto de turnos', () => {
  expect(relocationNextStep(relocation('pendiente', null), attender)).toMatchObject({ yourTurn: true, action: 'aceptar' })
  expect(relocationNextStep(relocation('pendiente', null), teacher)).toMatchObject({ yourTurn: false })
  expect(relocationNextStep(relocation('aceptado'), otherAttender)).toMatchObject({ yourTurn: false, action: 'iniciar' })
  expect(relocationNextStep(relocation('en_progreso'), attender)).toMatchObject({ yourTurn: true, action: 'finalizar' })
})
