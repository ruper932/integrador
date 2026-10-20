// Tipos de las respuestas de la API local (/api/v1).

export interface Page<T> {
  items: T[]
  total: number
  offset: number
  limit: number
}

export interface ApiErrorBody {
  error: { code: string; message: string; details: unknown }
}

export interface RoleSummary {
  id: number
  name: string
}

export interface Permission {
  code: string
  description: string
}

export interface Role extends RoleSummary {
  description: string
  is_system: boolean
  permissions: Permission[]
}

export type CiDepartment = 'LP' | 'CB' | 'SC' | 'OR' | 'PT' | 'CH' | 'TJ' | 'BE' | 'PD'

export interface Position {
  id: number
  code: string
  name: string
}

export interface AcademicLevel {
  id: number
  code: string
  name: string
  /** Edad mínima para egresar con este nivel (valida el año de egreso). */
  min_graduation_age: number
}

export type InstitutionType =
  | 'universidad_publica'
  | 'universidad_privada'
  | 'universidad_indigena'
  | 'escuela_formacion_maestros'
  | 'instituto_tecnico'
  | 'otra'

export interface Institution {
  id: number
  name: string
  acronym: string | null
  institution_type: InstitutionType
  city: string | null
  is_active: boolean
}

export interface Profile {
  first_names: string
  paternal_surname: string | null
  maternal_surname: string | null
  ci_number: string | null
  ci_complement: string | null
  ci_issued_in: CiDepartment | null
  institutional_email: string | null
  personal_email: string | null
  mobile_phone: string | null
  birth_date: string | null
  address: string | null
  position: Position | null
}

export interface ProfileInput {
  first_names: string
  paternal_surname: string | null
  maternal_surname: string | null
  ci_number: string
  ci_complement: string | null
  ci_issued_in: CiDepartment | null
  institutional_email: string | null
  personal_email: string | null
  mobile_phone: string
  birth_date: string
  address: string | null
  position_id: number | null
}

export interface Degree {
  id: number
  title: string
  graduation_year: number | null
  academic_level: AcademicLevel
  institution: { id: number; name: string; acronym: string | null }
}

export interface DegreeInput {
  academic_level_id: number
  title: string
  institution_id: number
  graduation_year: number | null
}

export interface User {
  id: number
  username: string
  full_name: string
  is_active: boolean
  must_change_password: boolean
  last_login_at: string | null
  created_at: string
  roles: RoleSummary[]
  profile_complete: boolean
  profile: Profile | null
  degrees: Degree[]
}

export interface Me extends User {
  permissions: string[]
}

export interface UserWithTemporaryPassword {
  user: User
  temporary_password: string | null
}

export type RecoveryStatus = 'pendiente' | 'aprobada' | 'rechazada'

export interface RecoveryRequest {
  id: number
  username_requested: string
  user_id: number | null
  user_full_name: string | null
  status: RecoveryStatus
  message: string | null
  requester_ip: string | null
  created_at: string
  resolved_at: string | null
  resolved_by_id: number | null
  resolution_note: string | null
}

export interface AuditLog {
  id: number
  user_id: number | null
  username: string | null
  action: string
  entity_type: string | null
  entity_id: string | null
  details: Record<string, unknown> | null
  ip_address: string | null
  created_at: string
}

export interface FogCollector {
  id: number
  code: string
  name: string
  location_id: number | null
  mesh_area_m2: string | null
  mesh_type: string | null
  installed_on: string | null
  is_active: boolean
}

export interface Tank {
  id: number
  code: string
  name: string
  location_id: number | null
  fog_collector_id: number | null
  capacity_liters: string | null
  height_cm: string | null
  is_active: boolean
}

export type ComponentStatus = 'activo' | 'inactivo' | 'mantenimiento'

export interface Device {
  id: number
  code: string
  name: string
  description: string | null
  firmware_version: string | null
  status: ComponentStatus
  fog_collector_id: number | null
  last_seen_at: string | null
  created_at: string
}

export interface DeviceWithKey {
  device: Device
  api_key: string
}

export interface SensorType {
  id: number
  code: string
  name: string
  unit: string
  min_value: number
  max_value: number
  aggregation: 'incremental' | 'instantaneo'
  description: string | null
}

export interface Sensor {
  id: number
  device_id: number
  sensor_type_id: number
  code: string
  model: string | null
  status: ComponentStatus
  fog_collector_id: number | null
  tank_id: number | null
  sensor_type: SensorType
}

export type ReadingQuality = 'valida' | 'sin_dato' | 'fuera_de_rango' | 'unidad_invalida' | 'invalida'

export interface Reading {
  id: number
  message_uid: string
  device_id: number
  sensor_id: number
  sensor_type_id: number
  measured_at: string
  received_at: string
  value: number | null
  unit: string
  quality: ReadingQuality
  quality_detail: string | null
}

export interface DeviceStatusItem {
  id: number
  code: string
  name: string
  status: ComponentStatus
  last_seen_at: string | null
  minutes_since_last_seen: number | null
  is_stale: boolean
}

export interface LatestValue {
  sensor_id: number
  sensor_code: string
  device_id: number
  sensor_type_code: string
  sensor_type_name: string
  unit: string
  value: number | null
  measured_at: string
  is_stale: boolean
}

export interface DashboardSummary {
  generated_at: string
  stale_threshold_minutes: number
  last_communication_at: string | null
  has_stale_data: boolean
  devices: DeviceStatusItem[]
  latest: LatestValue[]
  volume: { today_liters: number; last_7_days_liters: number; month_liters: number }
}

export type Bucket = 'hour' | 'day' | 'week' | 'month'

export interface SeriesPoint {
  bucket: string
  value: number | null
  min: number | null
  max: number | null
  count: number
}

export interface Series {
  sensor_type: SensorType
  aggregation: 'incremental' | 'instantaneo'
  bucket: Bucket
  date_from: string
  date_to: string
  points: SeriesPoint[]
}

export interface InventoryCategory {
  id: number
  name: string
  description: string | null
  is_active: boolean
}

export type ItemCondition = 'nuevo' | 'usado' | 'reacondicionado' | 'en_revision' | 'danado'

export interface InventoryItem {
  id: number
  code: string
  name: string
  description: string | null
  category: InventoryCategory
  unit: string
  current_stock: string
  min_stock: string
  condition: ItemCondition
  storage_location: string | null
  is_active: boolean
  low_stock: boolean
  compatibilities: { device_id: number | null; sensor_id: number | null }[]
}

export interface InventoryMovement {
  id: number
  item_id: number
  movement_type: { code: string; name: string; direction: number }
  quantity: string
  stock_before: string
  stock_after: string
  reason: string
  user_id: number
  username: string | null
  maintenance_record_id: number | null
  unit_cost: string | null
  occurred_at: string
  created_at: string
}

export interface InventoryPeriod {
  id: number
  name: string
  start_date: string
  end_date: string
  status: 'abierto' | 'cerrado'
  notes: string | null
  created_at: string
  closed_at: string | null
  closed_by_id: number | null
}

export interface PeriodBalance {
  item: { id: number; code: string; name: string; unit: string; is_active: boolean }
  opening_quantity: string
  entries_quantity: string
  exits_quantity: string
  maintenance_exits_quantity: string
  adjustments_quantity: string
  theoretical_quantity: string
  counted_quantity: string | null
  difference: string | null
  closing_quantity: string
  opening_value: string | null
  entries_value: string | null
  average_unit_cost: string | null
  closing_value: string | null
}

export interface PeriodSummary {
  period: InventoryPeriod
  provisional: boolean
  counted_items: number
  pending_count_items: number
  total_value: string | null
  balances: PeriodBalance[]
}

export type MaintenanceType = 'preventivo' | 'correctivo' | 'reemplazo' | 'calibracion' | 'limpieza' | 'inspeccion'
export type FinalStatus = 'operativo' | 'operativo_con_observaciones' | 'fuera_de_servicio' | 'reemplazado'

export type MaintenanceStatus = 'aceptado' | 'en_progreso' | 'finalizado'

/** Mientras no esté finalizado, los detalles del trabajo pueden estar vacíos. */
export interface MaintenanceRecord {
  id: number
  status: MaintenanceStatus
  incident_report_id: number | null
  device_id: number | null
  device_code: string | null
  sensor_id: number | null
  sensor_code: string | null
  performed_at: string | null
  user_id: number
  username: string
  user_full_name: string
  maintenance_type: MaintenanceType | null
  description: string | null
  final_status: FinalStatus | null
  accepted_at: string | null
  started_at: string | null
  finished_at: string | null
  created_at: string
  items: { item_id: number; item_code: string; item_name: string; quantity: string; movement_id: number }[]
}

export type IncidentPriority = 'baja' | 'media' | 'alta'
export type IncidentStatus = 'abierto' | MaintenanceStatus
export type IncidentScope = 'mine' | 'open' | 'assigned' | 'all'

export interface Person {
  id: number
  username: string
  full_name: string
}

export interface Incident {
  id: number
  title: string
  description: string
  priority: IncidentPriority
  location_reference: string | null
  status: IncidentStatus
  device_id: number | null
  device_code: string | null
  device_name: string | null
  sensor_id: number | null
  sensor_code: string | null
  reporter: Person
  assignee: Person | null
  created_at: string
  maintenance: MaintenanceRecord | null
}

export interface IncidentSummary {
  mine: Partial<Record<IncidentStatus, number>> | null
  open: number | null
  assigned_active: number | null
  all: Partial<Record<IncidentStatus, number>> | null
}

export interface AppNotification {
  id: number
  title: string
  message: string
  incident_report_id: number | null
  created_at: string
  read_at: string | null
}

export interface ReportFilterDef {
  key: string
  label: string
  required: boolean
}

export interface ReportDefinition {
  kind: string
  module: string
  label: string
  description: string
  filters: ReportFilterDef[]
}

export interface ReportFilterOptions {
  responsibles: { id: number; full_name: string }[]
  reporters: { id: number; full_name: string }[]
  actors: { id: number; full_name: string }[] | null
  audit_actions: string[] | null
}
