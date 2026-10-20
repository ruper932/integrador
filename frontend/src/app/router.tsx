import { createBrowserRouter } from 'react-router'

import { AppLayout, HomeRoute, RequirePermission } from '@/app/AppLayout'
import { AuditPage } from '@/features/admin/AuditPage'
import { AnalysisPage } from '@/features/analysis/AnalysisPage'
import { RecoveryRequestsPage } from '@/features/admin/RecoveryRequestsPage'
import { UsersPage } from '@/features/admin/UsersPage'
import { ChangePasswordPage } from '@/features/auth/ChangePasswordPage'
import { LoginPage } from '@/features/auth/LoginPage'
import { ProfilePage } from '@/features/auth/ProfilePage'
import { RecoveryRequestPage } from '@/features/auth/RecoveryRequestPage'
import { DashboardPage } from '@/features/dashboard/DashboardPage'
import { DevicesPage } from '@/features/devices/DevicesPage'
import { FogCollectorsPage } from '@/features/fog-collectors/FogCollectorsPage'
import { IncidentsPage } from '@/features/incidents/IncidentsPage'
import { InventoryPage } from '@/features/inventory/InventoryPage'
import { MaintenancePage } from '@/features/maintenance/MaintenancePage'
import { MeasurementsPage } from '@/features/measurements/MeasurementsPage'
import { INCIDENT_PERMISSIONS } from '@/lib/permissions'

function guarded(permission: string | string[], element: React.ReactNode) {
  return <RequirePermission permission={permission}>{element}</RequirePermission>
}

export const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  { path: '/recuperar-cuenta', element: <RecoveryRequestPage /> },
  { path: '/cambiar-contrasena', element: <ChangePasswordPage /> },
  {
    path: '/',
    element: <AppLayout />,
    children: [
      { index: true, element: <HomeRoute dashboard={<DashboardPage />} /> },
      { path: 'perfil', element: <ProfilePage /> },
      { path: 'analisis', element: guarded('reportes.generar', <AnalysisPage />) },
      { path: 'historicos', element: guarded('mediciones.consultar', <MeasurementsPage />) },
      { path: 'atrapanieblas', element: guarded('infraestructura.consultar', <FogCollectorsPage />) },
      { path: 'dispositivos', element: guarded('infraestructura.consultar', <DevicesPage />) },
      { path: 'inventario', element: guarded('inventario.consultar', <InventoryPage />) },
      { path: 'incidencias', element: guarded(INCIDENT_PERMISSIONS, <IncidentsPage />) },
      { path: 'mantenimiento', element: guarded('mantenimiento.consultar', <MaintenancePage />) },
      { path: 'usuarios', element: guarded('usuarios.gestionar', <UsersPage />) },
      { path: 'recuperaciones', element: guarded('recuperacion.gestionar', <RecoveryRequestsPage />) },
      { path: 'auditoria', element: guarded('auditoria.consultar', <AuditPage />) },
    ],
  },
])
