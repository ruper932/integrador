import { CloudFog, Droplets, Moon, ShieldCheck, Sun, Wifi } from 'lucide-react'
import type { ReactNode } from 'react'

import { Button } from '@/components/ui/button'
import { useTheme } from '@/hooks/useTheme'

const POINTS = [
  { icon: CloudFog, text: 'Captación de agua de niebla medida por las estaciones IoT.' },
  { icon: Wifi, text: 'Funciona en la red local de la institución, sin depender de Internet.' },
  { icon: ShieldCheck, text: 'Acceso por roles; la recuperación de cuenta es presencial con el administrador.' },
]

/** Marco común de las pantallas de acceso (inicio de sesión, recuperación y contraseña temporal). */
export function AuthShell({ title, description, children }: { title: string; description: string; children: ReactNode }) {
  const { theme, toggle } = useTheme()
  return (
    <div className="bg-background grid min-h-svh lg:grid-cols-[minmax(0,1.05fr)_minmax(0,1fr)]">
      {/* Panel lateral pastel claro, plano y sin degradados. */}
      <aside className="bg-accent text-accent-foreground relative hidden overflow-hidden p-12 lg:flex lg:flex-col">
        <div className="relative flex items-center gap-3">
          <span className="bg-primary text-primary-foreground grid size-11 place-items-center rounded-xl">
            <Droplets className="size-6" aria-hidden />
          </span>
          <span>
            <strong className="block text-xl">ATINA</strong>
            <small className="block text-xs opacity-75">Gestión hídrica · C.E.A.</small>
          </span>
        </div>
        <div className="relative mt-auto max-w-md">
          <p className="mb-4 text-xs font-medium">Monitoreo de atrapanieblas</p>
          <h2 className="font-heading text-4xl leading-tight font-semibold">El agua, en perspectiva.</h2>
          <p className="mt-3 text-sm opacity-80">
            Centro de Educación Alternativa “Ildefonso de las Muñecas” — Titicachi, Chuma, La Paz.
          </p>
          <ul className="mt-8 grid gap-3">
            {POINTS.map(({ icon: Icon, text }) => (
              <li key={text} className="flex items-start gap-3 text-sm opacity-90">
                <Icon className="text-accent-foreground mt-0.5 size-4 shrink-0" aria-hidden />
                {text}
              </li>
            ))}
          </ul>
        </div>
      </aside>

      <main className="relative flex items-center justify-center p-5 sm:p-10">
        <Button
          variant="outline"
          size="icon"
          className="absolute top-4 right-4"
          onClick={toggle}
          aria-pressed={theme === 'dark'}
          aria-label={theme === 'dark' ? 'Activar modo claro' : 'Activar modo oscuro'}
        >
          {theme === 'dark' ? <Sun /> : <Moon />}
        </Button>
        <div className="w-full max-w-sm">
          <div className="mb-8 flex items-center gap-3 lg:hidden">
            <span className="bg-primary text-primary-foreground grid size-10 place-items-center rounded-xl">
              <Droplets className="size-5" aria-hidden />
            </span>
            <span>
              <strong className="block">ATINA</strong>
              <small className="text-muted-foreground block text-xs">Gestión hídrica · C.E.A.</small>
            </span>
          </div>
          <h1 className="font-heading text-2xl font-semibold">{title}</h1>
          <p className="text-muted-foreground mt-1.5 mb-7 text-sm">{description}</p>
          {children}
        </div>
      </main>
    </div>
  )
}
