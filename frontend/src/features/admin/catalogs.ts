import { useQuery } from '@tanstack/react-query'

import { api } from '@/lib/api'
import type { AcademicLevel, CiDepartment, Institution, InstitutionType, Position, Role } from '@/types/api'

/** Solo para administradores (el endpoint exige `usuarios.gestionar`). */
export function useRoles(enabled = true) {
  return useQuery({ queryKey: ['roles'], queryFn: async () => (await api.get<Role[]>('/roles')).data, enabled })
}

export function useAcademicLevels() {
  return useQuery({
    queryKey: ['catalogs', 'academic-levels'],
    queryFn: async () => (await api.get<AcademicLevel[]>('/catalogs/academic-levels')).data,
    staleTime: Infinity,
  })
}

export function useInstitutions() {
  return useQuery({
    queryKey: ['catalogs', 'institutions'],
    queryFn: async () => (await api.get<Institution[]>('/catalogs/institutions')).data,
  })
}

export function usePositions() {
  return useQuery({
    queryKey: ['catalogs', 'positions'],
    queryFn: async () => (await api.get<Position[]>('/catalogs/positions')).data,
    staleTime: Infinity,
  })
}

export const CI_DEPARTMENTS: { value: CiDepartment; label: string }[] = [
  { value: 'LP', label: 'La Paz' },
  { value: 'CB', label: 'Cochabamba' },
  { value: 'SC', label: 'Santa Cruz' },
  { value: 'OR', label: 'Oruro' },
  { value: 'PT', label: 'Potosí' },
  { value: 'CH', label: 'Chuquisaca' },
  { value: 'TJ', label: 'Tarija' },
  { value: 'BE', label: 'Beni' },
  { value: 'PD', label: 'Pando' },
]

export const INSTITUTION_TYPES: { value: InstitutionType; label: string }[] = [
  { value: 'universidad_publica', label: 'Universidad pública' },
  { value: 'universidad_privada', label: 'Universidad privada' },
  { value: 'universidad_indigena', label: 'Universidad indígena' },
  { value: 'escuela_formacion_maestros', label: 'Escuela Superior de Formación de Maestros' },
  { value: 'instituto_tecnico', label: 'Instituto técnico / tecnológico' },
  { value: 'otra', label: 'Otra' },
]
