import {
  AlertTriangle,
  ArrowRight,
  Check,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Circle,
  Copy,
  Info,
  Loader2,
  XCircle,
  type LucideIcon,
} from 'lucide-react'
import type { ReactNode, SelectHTMLAttributes } from 'react'
import { forwardRef, useState } from 'react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { errorMessage } from '@/lib/api'
import { cn } from '@/lib/utils'

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow?: string
  title: string
  description?: ReactNode
  actions?: ReactNode
}) {
  return (
    <div className="mb-6 flex flex-col justify-between gap-4 md:flex-row md:items-end">
      <div className="min-w-0">
        {eyebrow && (
          <div className="text-muted-foreground mb-1 text-xs font-medium">{eyebrow}</div>
        )}
        <h1 className="font-heading text-2xl leading-tight font-semibold md:text-[28px]">{title}</h1>
        {description && <p className="text-muted-foreground mt-1 max-w-[70ch] text-sm">{description}</p>}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
    </div>
  )
}

type Tone = 'info' | 'success' | 'warning' | 'danger'

const TONE: Record<Tone, { box: string; icon: LucideIcon }> = {
  info: { box: 'bg-accent text-accent-foreground border-primary/20', icon: Info },
  success: { box: 'bg-success-soft text-success border-success/20', icon: CheckCircle2 },
  warning: { box: 'bg-warning-soft text-warning border-warning/25', icon: AlertTriangle },
  danger: { box: 'bg-danger-soft text-danger border-danger/25', icon: XCircle },
}

/** Aviso con tono semántico; el icono acompaña al color para no depender solo de él. */
export function Notice({
  tone = 'info',
  title,
  children,
  action,
  className,
}: {
  tone?: Tone
  title?: ReactNode
  children?: ReactNode
  action?: ReactNode
  className?: string
}) {
  const { box, icon: Icon } = TONE[tone]
  return (
    <div
      role={tone === 'danger' || tone === 'warning' ? 'alert' : 'status'}
      className={cn('flex gap-3 rounded-xl border px-4 py-3 text-sm', box, className)}
    >
      <Icon className="mt-0.5 size-4 shrink-0" aria-hidden />
      <div className="min-w-0 flex-1">
        {title && <div className="font-semibold">{title}</div>}
        {children && <div className={cn(title && 'mt-0.5')}>{children}</div>}
      </div>
      {action && <div className="shrink-0 self-center">{action}</div>}
    </div>
  )
}

export function ErrorAlert({ error, title = 'No se pudo completar la operación' }: { error: unknown; title?: string }) {
  if (!error) return null
  return (
    <Notice tone="danger" title={title}>
      {errorMessage(error)}
    </Notice>
  )
}

export function Loading({ label = 'Cargando…' }: { label?: string }) {
  return (
    <div className="text-muted-foreground flex items-center gap-2 py-6 text-sm" role="status">
      <Loader2 className="size-4 animate-spin" /> {label}
    </div>
  )
}

export function EmptyState({
  icon: Icon = Circle,
  title,
  description,
  action,
}: {
  icon?: LucideIcon
  title: string
  description?: string
  action?: ReactNode
}) {
  return (
    <div className="flex flex-col items-center gap-2 px-4 py-10 text-center">
      <span className="bg-accent text-foreground grid size-11 place-items-center rounded-xl">
        <Icon className="size-5" aria-hidden />
      </span>
      <div className="font-medium">{title}</div>
      {description && <p className="text-muted-foreground max-w-sm text-sm">{description}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  )
}

export type ToneColor = 'blue' | 'mint' | 'peach' | 'lavender' | 'rose'

const TONE_COLOR: Record<ToneColor, string> = {
  blue: 'bg-tone-blue text-tone-blue-foreground',
  mint: 'bg-tone-mint text-tone-mint-foreground',
  peach: 'bg-tone-peach text-tone-peach-foreground',
  lavender: 'bg-tone-lavender text-tone-lavender-foreground',
  rose: 'bg-tone-rose text-tone-rose-foreground',
}

export function StatCard({
  label,
  value,
  unit,
  icon: Icon,
  foot,
  tone,
  color = 'blue',
}: {
  label: string
  value: ReactNode
  unit?: string
  icon?: LucideIcon
  foot?: ReactNode
  tone?: 'success' | 'warning'
  color?: ToneColor
}) {
  return (
    <div className="bg-card shadow-card min-w-0 rounded-xl border p-4 sm:p-5">
      <div className="text-muted-foreground flex items-center justify-between gap-2 text-sm">
        <span>{label}</span>
        {Icon && (
          <span className={cn('hidden rounded-lg p-2 sm:inline-flex', TONE_COLOR[color])}>
            <Icon className="size-5" aria-hidden />
          </span>
        )}
      </div>
      <div className="font-heading my-2 text-2xl leading-none font-semibold tabular-nums sm:text-[28px]">
        {value}
        {unit && <span className="text-muted-foreground ml-1 text-sm font-normal">{unit}</span>}
      </div>
      {foot && (
        <div
          className={cn(
            'flex items-center gap-1.5 text-xs',
            tone === 'warning' ? 'text-warning' : tone === 'success' ? 'text-success' : 'text-muted-foreground',
          )}
        >
          {foot}
        </div>
      )}
    </div>
  )
}

/** Encabezado de tarjeta al estilo de la plantilla: título, subtítulo y acciones con separador. */
export function CardHead({ title, subtitle, actions }: { title: ReactNode; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="-mt-(--card-spacing) bg-muted/60 flex flex-wrap items-center justify-between gap-3 border-b px-5 py-4">
      <div className="min-w-0">
        <h2 className="text-sm font-semibold">{title}</h2>
        {subtitle && <div className="text-muted-foreground mt-0.5 text-xs">{subtitle}</div>}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
    </div>
  )
}

export function Field({
  label,
  htmlFor,
  error,
  hint,
  children,
}: {
  label: string
  htmlFor: string
  error?: string
  hint?: string
  children: ReactNode
}) {
  return (
    <div className="grid content-start gap-1.5">
      <Label htmlFor={htmlFor}>{label}</Label>
      {children}
      {hint && !error && <p className="text-muted-foreground text-xs">{hint}</p>}
      {error && (
        <p className="text-destructive text-xs" role="alert">
          {error}
        </p>
      )}
    </div>
  )
}

export const NativeSelect = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(
  function NativeSelect({ className, ...props }, ref) {
    return (
      <select
        ref={ref}
        className={cn(
          'border-input bg-card focus-visible:border-ring focus-visible:ring-ring/40 h-9 w-full rounded-lg border px-2.5 text-sm outline-none focus-visible:ring-3 disabled:opacity-60',
          className,
        )}
        {...props}
      />
    )
  },
)

export function Pagination({
  offset,
  limit,
  total,
  onChange,
}: {
  offset: number
  limit: number
  total: number
  onChange: (offset: number) => void
}) {
  if (total === 0) return null
  const page = Math.floor(offset / limit) + 1
  const pages = Math.max(1, Math.ceil(total / limit))
  const from = offset + 1
  const to = Math.min(offset + limit, total)
  return (
    <div className="text-muted-foreground mt-3 flex flex-wrap items-center justify-between gap-2 border-t pt-3 text-xs">
      <span>
        {from}–{to} de {total} registros
      </span>
      {pages > 1 && (
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={offset === 0}
            onClick={() => onChange(Math.max(0, offset - limit))}
            aria-label="Página anterior"
          >
            <ChevronLeft /> Anterior
          </Button>
          <span>
            Página {page} de {pages}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= pages}
            onClick={() => onChange(offset + limit)}
            aria-label="Página siguiente"
          >
            Siguiente <ChevronRight />
          </Button>
        </div>
      )}
    </div>
  )
}

type BadgeTone = 'success' | 'warning' | 'danger' | 'info' | 'secondary'

const STATUS: Record<string, BadgeTone> = {
  activo: 'success',
  valida: 'success',
  aprobada: 'success',
  operativo: 'success',
  cerrado: 'secondary',
  abierto: 'info',
  mantenimiento: 'warning',
  pendiente: 'warning',
  operativo_con_observaciones: 'warning',
  sin_datos_recientes: 'warning',
  sin_estacion: 'secondary',
  sin_dato: 'secondary',
  inactivo: 'secondary',
  rechazada: 'danger',
  fuera_de_rango: 'danger',
  unidad_invalida: 'danger',
  invalida: 'danger',
  fuera_de_servicio: 'danger',
}

const BADGE_ICON: Partial<Record<BadgeTone, LucideIcon>> = {
  success: CheckCircle2,
  warning: AlertTriangle,
  danger: XCircle,
}

export function StatusBadge({ value, label }: { value: string; label?: string }) {
  const tone = STATUS[value] ?? 'secondary'
  const Icon = BADGE_ICON[tone]
  return (
    <Badge variant={tone}>
      {Icon && <Icon aria-hidden />}
      {label ?? value.replaceAll('_', ' ')}
    </Badge>
  )
}

async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch {
    // En la red local (http) el portapapeles moderno puede no estar disponible.
    const area = document.createElement('textarea')
    area.value = text
    area.style.position = 'fixed'
    area.style.opacity = '0'
    document.body.appendChild(area)
    area.select()
    const ok = document.execCommand('copy')
    area.remove()
    return ok
  }
}

/** Muestra un secreto una sola vez (contraseña temporal o API key), con botón para copiarlo. */
export function SecretNotice({ title, secret, children }: { title: string; secret: string; children?: ReactNode }) {
  const [copied, setCopied] = useState(false)
  return (
    <Notice tone="warning" title={title}>
      <div className="mt-1.5 flex flex-wrap items-center gap-2">
        <code className="bg-card text-foreground rounded-md border px-2 py-1 font-mono text-sm break-all select-all">
          {secret}
        </code>
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={async () => setCopied(await copyText(secret))}
          aria-live="polite"
        >
          {copied ? <Check /> : <Copy />} {copied ? 'Copiado' : 'Copiar'}
        </Button>
      </div>
      <span className="mt-1.5 block text-xs">Se muestra una sola vez. {children}</span>
    </Notice>
  )
}

/**
 * Recuadro «Siguiente paso» de un proceso: dice a quién le toca y qué ocurrirá, con las acciones al alcance
 * (arriba del detalle, no al final). Cuando le toca a otra persona se muestra atenuado y sin acciones.
 */
export function NextStepCard({
  yourTurn,
  title,
  children,
  actions,
}: {
  yourTurn: boolean
  title: ReactNode
  children?: ReactNode
  actions?: ReactNode
}) {
  return (
    <section
      aria-label="Siguiente paso"
      className={cn('grid gap-3 rounded-xl border p-4', yourTurn ? 'bg-attention-soft border-attention/40 border-l-4 border-l-attention' : 'bg-muted/50')}
    >
      <div>
        <div className={cn('flex items-center gap-1.5 text-sm font-semibold', yourTurn && 'text-attention-ink')}>
          {yourTurn ? <ArrowRight className="size-3.5" aria-hidden /> : <Circle className="size-3" aria-hidden />}
          {yourTurn ? 'Le toca a usted' : 'Siguiente paso'}
        </div>
        <div className="mt-1 font-semibold">{title}</div>
        {children && <div className="mt-0.5 text-sm">{children}</div>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </section>
  )
}

/** Marca de la lista para los casos en que la persona debe actuar. */
export function YourTurnBadge({ action }: { action: string }) {
  return (
    <Badge className="bg-attention text-attention-foreground">
      <ArrowRight aria-hidden />
      Su turno: {action.toLowerCase()}
    </Badge>
  )
}
