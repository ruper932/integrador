import { useQuery } from '@tanstack/react-query'
import {
  Boxes,
  ChevronUp,
  ClipboardList,
  CloudFog,
  Cpu,
  ChartColumn,
  History,
  KeyRound,
  LayoutDashboard,
  LifeBuoy,
  LogOut,
  Menu,
  MessageSquareWarning,
  Moon,
  Sun,
  UserRound,
  Users,
  Wrench,
  type LucideIcon,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { Navigate, NavLink, Outlet, useLocation, useNavigate } from 'react-router'

import { Loading, Notice } from '@/components/common'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { useLogout, useMe } from '@/features/auth/useAuth'
import { useIncidentSummary } from '@/features/incidents/api'
import { NotificationBell } from '@/features/incidents/NotificationBell'
import { useTheme } from '@/hooks/useTheme'
import { api } from '@/lib/api'
import { allowed, INCIDENT_PERMISSIONS } from '@/lib/permissions'
import { cn } from '@/lib/utils'
import type { InventoryItem, Me, Page, RecoveryRequest } from '@/types/api'

interface NavItem {
  to: string
  label: string
  icon: LucideIcon
  /** Permiso requerido; con una lista basta cualquiera de ellos. */
  permission: string | string[]
  badge?: 'lowStock' | 'pendingRecovery' | 'openIncidents'
}

interface NavGroup {
  label: string
  items: NavItem[]
}

// La visibilidad es solo una ayuda de interfaz: el backend valida cada permiso.
const NAV: NavGroup[] = [
  {
    label: 'Principal',
    items: [
      { to: '/', label: 'Resumen general', icon: LayoutDashboard, permission: 'dashboard.consultar' },
      { to: '/historicos', label: 'Histórico de lecturas', icon: History, permission: 'mediciones.consultar' },
      { to: '/analisis', label: 'Análisis estadístico', icon: ChartColumn, permission: 'reportes.generar' },
    ],
  },
  {
    label: 'Operaciones',
    items: [
      { to: '/atrapanieblas', label: 'Atrapanieblas', icon: CloudFog, permission: 'infraestructura.consultar' },
      { to: '/dispositivos', label: 'Dispositivos y sensores', icon: Cpu, permission: 'infraestructura.consultar' },
      { to: '/inventario', label: 'Inventario IoT', icon: Boxes, permission: 'inventario.consultar', badge: 'lowStock' },
      {
        to: '/incidencias',
        label: 'Reportes de incidencia',
        icon: MessageSquareWarning,
        permission: INCIDENT_PERMISSIONS,
        badge: 'openIncidents',
      },
      { to: '/mantenimiento', label: 'Mantenimiento', icon: Wrench, permission: 'mantenimiento.consultar' },
    ],
  },
  {
    label: 'Administración',
    items: [
      { to: '/usuarios', label: 'Usuarios y permisos', icon: Users, permission: 'usuarios.gestionar' },
      {
        to: '/recuperaciones',
        label: 'Recuperaciones',
        icon: LifeBuoy,
        permission: 'recuperacion.gestionar',
        badge: 'pendingRecovery',
      },
      { to: '/auditoria', label: 'Auditoría', icon: ClipboardList, permission: 'auditoria.consultar' },
    ],
  },
]

function initials(user: Me): string {
  const p = user.profile
  const parts = [p?.first_names?.split(' ')[0], p?.paternal_surname ?? p?.maternal_surname].filter(Boolean)
  const letters = (parts.length ? parts : [user.username]).map((s) => s!.charAt(0).toUpperCase())
  return letters.join('').slice(0, 2)
}

function useBadges(user: Me) {
  const canInventory = user.permissions.includes('inventario.consultar')
  const canRecovery = user.permissions.includes('recuperacion.gestionar')
  const canAttend = user.permissions.includes('incidencias.atender')
  const lowStock = useQuery({
    queryKey: ['inventory', 'alerts'],
    queryFn: async () => (await api.get<InventoryItem[]>('/inventory/alerts/low-stock')).data,
    enabled: canInventory,
    refetchInterval: 5 * 60_000,
  })
  const pending = useQuery({
    queryKey: ['recovery-requests', 'pending-count'],
    queryFn: async () =>
      (await api.get<Page<RecoveryRequest>>('/admin/recovery-requests', { params: { status: 'pendiente', limit: 1 } }))
        .data.total,
    enabled: canRecovery,
    refetchInterval: 2 * 60_000,
  })
  const incidents = useIncidentSummary(canAttend)
  return {
    lowStock: lowStock.data?.length ?? 0,
    pendingRecovery: pending.data ?? 0,
    openIncidents: canAttend ? (incidents.data?.open ?? 0) : 0,
  }
}

function useServerStatus() {
  return useQuery({
    queryKey: ['health', 'db'],
    queryFn: async () => (await api.get<{ status: string }>('/health/db')).data.status === 'ok',
    refetchInterval: 60_000,
    retry: false,
  })
}

function Avatar({ user, className }: { user: Me; className?: string }) {
  return (
    <span
      className={cn('bg-accent text-foreground grid size-9 shrink-0 place-items-center rounded-full text-sm font-semibold', className)}
      aria-hidden
    >
      {initials(user)}
    </span>
  )
}

export function AppLayout() {
  const me = useMe()
  const logout = useLogout()
  const navigate = useNavigate()
  const location = useLocation()
  const { theme, toggle } = useTheme()
  // Menú desplegado: se superpone al contenido (no cambia su ancho) y se cierra al navegar.
  const [open, setOpen] = useState(false)
  const [isMobile, setIsMobile] = useState(() => matchMedia('(max-width: 849px)').matches)

  useEffect(() => {
    const media = matchMedia('(max-width: 849px)')
    const onChange = () => {
      setIsMobile(media.matches)
      setOpen(false)
    }
    media.addEventListener('change', onChange)
    return () => media.removeEventListener('change', onChange)
  }, [])

  // Al navegar se cierra el menú; Escape también lo cierra.
  useEffect(() => setOpen(false), [location.pathname])
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [])

  if (me.isLoading) return <Loading label="Verificando sesión…" />
  if (!me.data) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  if (me.data.must_change_password) return <Navigate to="/cambiar-contrasena" replace />
  return (
    <Shell
      user={me.data}
      collapsed={!isMobile && !open}
      isMobile={isMobile}
      mobileOpen={open}
      theme={theme}
      onToggleTheme={toggle}
      onToggleMenu={() => setOpen((o) => !o)}
      onCloseMobile={() => setOpen(false)}
      onLogout={() => logout.mutate(undefined, { onSettled: () => navigate('/login', { replace: true }) })}
      onNavigate={(to) => navigate(to)}
      pathname={location.pathname}
    />
  )
}

function Shell({
  user,
  collapsed,
  isMobile,
  mobileOpen,
  theme,
  pathname,
  onToggleTheme,
  onToggleMenu,
  onCloseMobile,
  onLogout,
  onNavigate,
}: {
  user: Me
  collapsed: boolean
  isMobile: boolean
  mobileOpen: boolean
  theme: 'light' | 'dark'
  pathname: string
  onToggleTheme: () => void
  onToggleMenu: () => void
  onCloseMobile: () => void
  onLogout: () => void
  onNavigate: (to: string) => void
}) {
  const badges = useBadges(user)
  const server = useServerStatus()
  const online = server.data === true
  const groups = NAV.map((g) => ({ ...g, items: g.items.filter((i) => allowed(user.permissions, i.permission)) })).filter(
    (g) => g.items.length > 0,
  )
  const menuExpanded = isMobile ? mobileOpen : !collapsed
  const showLabels = !collapsed

  return (
    // El ancho del contenido es siempre el mismo: en escritorio se reserva solo el riel contraído (84 px).
    <div className={cn('grid min-h-svh', isMobile ? 'grid-cols-1' : 'grid-cols-[84px_minmax(0,1fr)]')}>
      <a
        href="#contenido"
        className="bg-primary text-primary-foreground sr-only z-50 rounded-md px-3 py-2 focus:not-sr-only focus:fixed focus:top-3 focus:left-3"
      >
        Saltar al contenido
      </a>
      {mobileOpen && (
        <button
          type="button"
          aria-label="Cerrar menú"
          className="fixed inset-0 z-30 cursor-default"
          onClick={onCloseMobile}
        />
      )}
      {!isMobile && <div aria-hidden />}

      <aside
        id="barra-lateral"
        aria-label="Navegación principal"
        inert={isMobile && !mobileOpen}
        className={cn(
          'bg-sidebar border-sidebar-border fixed inset-y-0 left-0 z-40 flex h-dvh flex-col overflow-x-hidden overflow-y-auto border-r px-3.5 py-5',
          isMobile
            ? cn('w-72 transition-transform duration-200', mobileOpen ? 'translate-x-0' : '-translate-x-full')
            : cn('transition-[width] duration-200', collapsed ? 'w-[84px]' : 'w-[280px]'),
        )}
      >
        <div className={cn('mb-3 flex items-center gap-1', collapsed ? 'flex-col' : 'px-1')}>
          <Button
            variant="ghost"
            size="icon-lg"
            className="hover:bg-transparent hover:shadow-[var(--hover-shadow)] aria-expanded:bg-transparent"
            onClick={onToggleMenu}
            aria-controls="barra-lateral"
            aria-expanded={menuExpanded}
            aria-label={isMobile ? 'Cerrar menú lateral' : menuExpanded ? 'Contraer menú lateral' : 'Desplegar menú lateral'}
          >
            <Menu className="size-5" />
          </Button>
          <NotificationBell
            side={collapsed ? 'right' : 'bottom'}
            onOpenIncident={(id) => onNavigate(`/incidencias?reporte=${id}`)}
          />
        </div>

        {groups.map((g) => (
          <nav key={g.label} aria-label={g.label} className="mb-1">
            {showLabels ? (
              <div className="text-muted-foreground mx-3 mt-4 mb-2 text-[10px] font-semibold tracking-[0.15em] uppercase">
                {g.label}
              </div>
            ) : (
              <div className="bg-sidebar-border mx-3 my-4 h-px" aria-hidden />
            )}
            {g.items.map(({ to, label, icon: Icon, badge }) => {
              const count = badge ? badges[badge] : 0
              return (
                <NavLink
                  key={to}
                  to={to}
                  end={to === '/'}
                  title={collapsed ? label : undefined}
                  aria-label={collapsed ? label : undefined}
                  className={({ isActive }) =>
                    cn(
                      'text-sidebar-foreground hover:text-foreground hover:bg-transparent hover:shadow-[var(--hover-shadow)] relative my-0.5 flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm',
                      collapsed && 'justify-center px-0',
                      isActive &&
                        'bg-sidebar-accent text-sidebar-accent-foreground hover:bg-sidebar-accent font-medium shadow-[inset_3px_0_0_var(--highlight)] hover:shadow-[inset_3px_0_0_var(--highlight),var(--hover-shadow)]',
                    )
                  }
                >
                  <Icon className="size-4.5 shrink-0" aria-hidden />
                  {showLabels && <span className="truncate">{label}</span>}
                  {count > 0 &&
                    (showLabels ? (
                      <span className="bg-warning-soft text-warning ml-auto rounded-md px-1.5 text-[11px] font-medium">
                        {count}
                        <span className="sr-only"> pendientes</span>
                      </span>
                    ) : (
                      <span className="bg-warning absolute top-2 right-4 size-2 rounded-full" aria-label={`${count} pendientes`} />
                    ))}
                </NavLink>
              )
            })}
          </nav>
        ))}

        <div className="mt-auto pt-6">
          <div
            className={cn('text-xs', collapsed ? 'flex justify-center py-2' : 'bg-muted rounded-xl border p-3')}
            title={collapsed ? (online ? 'Servidor local conectado' : 'Sin conexión con el servidor') : undefined}
          >
            <span
              className={cn('inline-block size-2 rounded-full', online ? 'bg-success' : 'bg-warning', showLabels && 'mr-2')}
              aria-hidden
            />
            {showLabels && (
              <>
                <span className="font-medium">{online ? 'Servidor local · en línea' : 'Sin conexión con el servidor'}</span>
                <small className="text-muted-foreground mt-1 ml-4 block">Sin servicios externos</small>
              </>
            )}
          </div>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                type="button"
                aria-label="Menú de usuario"
                title={collapsed ? user.full_name : undefined}
                className={cn(
                  'hover:bg-transparent hover:shadow-[var(--hover-shadow)] mt-3 flex w-full items-center gap-3 rounded-lg p-2 text-left',
                  collapsed && 'justify-center',
                  pathname === '/perfil' && 'bg-sidebar-accent',
                )}
              >
                <Avatar user={user} />
                {showLabels && (
                  <>
                    <span className="min-w-0 flex-1 text-sm">
                      <span className="block truncate font-medium">{user.full_name}</span>
                      <small className="text-muted-foreground block truncate">{user.username}</small>
                    </span>
                    <ChevronUp className="text-muted-foreground size-4 shrink-0" aria-hidden />
                  </>
                )}
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent side={collapsed ? 'right' : 'top'} align={collapsed ? 'end' : 'start'} className="w-60">
              <DropdownMenuLabel className="font-normal">
                <div className="truncate text-sm font-medium">{user.full_name}</div>
                <div className="text-muted-foreground truncate text-xs">
                  {user.username} · {user.roles.map((r) => r.name.replaceAll('_', ' ')).join(', ')}
                </div>
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem onSelect={() => onNavigate('/perfil')}>
                <UserRound /> Mi perfil
              </DropdownMenuItem>
              <DropdownMenuItem onSelect={() => onNavigate('/perfil#contrasena')}>
                <KeyRound /> Cambiar contraseña
              </DropdownMenuItem>
              <DropdownMenuItem onSelect={onToggleTheme}>
                {theme === 'dark' ? <Sun /> : <Moon />} {theme === 'dark' ? 'Modo claro' : 'Modo oscuro'}
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem variant="destructive" onSelect={onLogout}>
                <LogOut /> Cerrar sesión
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </aside>

      <div className="flex min-w-0 flex-col">
        {isMobile && !mobileOpen && (
          <Button
            variant="ghost"
            size="icon-lg"
            className="bg-background fixed top-3 left-3 z-20 hover:bg-transparent hover:shadow-[var(--hover-shadow)]"
            onClick={onToggleMenu}
            aria-controls="barra-lateral"
            aria-expanded={false}
            aria-label="Desplegar menú lateral"
          >
            <Menu className="size-5" />
            {badges.openIncidents > 0 && (
              <span className="bg-warning absolute top-1.5 right-1.5 size-2 rounded-full" aria-hidden />
            )}
          </Button>
        )}

        <main
          id="contenido"
          tabIndex={-1}
          className={cn('mx-auto w-full max-w-[1600px] flex-1 px-4 py-6 outline-none md:px-7 md:py-8', isMobile && 'pt-18')}
        >
          {!online && server.isFetched && (
            <Notice tone="warning" title="Sin conexión con el servidor local" className="mb-5">
              Los datos mostrados pueden no estar actualizados. Verifique la red de la institución.
            </Notice>
          )}
          <Outlet />
          <footer className="text-muted-foreground mt-8 flex flex-wrap justify-between gap-2 border-t pt-4 text-[11px]">
            <span>ATINA · C.E.A. “Ildefonso de las Muñecas” · Titicachi, Chuma, La Paz</span>
            <span>Funcionamiento local · sin servicios externos</span>
          </footer>
        </main>
      </div>
    </div>
  )
}

/** Inicio: el dashboard si el usuario puede verlo; si no, la primera sección permitida. */
export function HomeRoute({ dashboard }: { dashboard: React.ReactNode }) {
  const me = useMe()
  const permissions = me.data?.permissions ?? []
  if (permissions.includes('dashboard.consultar')) return <>{dashboard}</>
  const first = NAV.flatMap((g) => g.items).find((i) => allowed(permissions, i.permission))
  return <Navigate to={first?.to ?? '/perfil'} replace />
}

export function RequirePermission({
  permission,
  children,
}: {
  permission: string | string[]
  children: React.ReactNode
}) {
  const me = useMe()
  if (!allowed(me.data?.permissions ?? [], permission)) {
    return (
      <Notice tone="warning" title="Acceso restringido">
        No tiene permiso para ver esta sección. Si lo necesita, solicítelo al administrador del sistema.
      </Notice>
    )
  }
  return <>{children}</>
}
