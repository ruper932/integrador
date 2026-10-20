import { Eye, EyeOff } from 'lucide-react'
import { forwardRef, useState, type ComponentProps, type KeyboardEvent } from 'react'

import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'

/** Campo de contraseña con botón para mostrarla y aviso de Bloq Mayús activado. */
export const PasswordInput = forwardRef<HTMLInputElement, Omit<ComponentProps<'input'>, 'type'>>(function PasswordInput(
  { className, onKeyUp, onKeyDown, ...props },
  ref,
) {
  const [visible, setVisible] = useState(false)
  const [capsLock, setCapsLock] = useState(false)
  const track = (e: KeyboardEvent<HTMLInputElement>) => setCapsLock(e.getModifierState?.('CapsLock') ?? false)

  return (
    <div className="grid gap-1">
      <div className="relative">
        <Input
          ref={ref}
          type={visible ? 'text' : 'password'}
          className={cn('pr-10', className)}
          onKeyUp={(e) => {
            track(e)
            onKeyUp?.(e)
          }}
          onKeyDown={(e) => {
            track(e)
            onKeyDown?.(e)
          }}
          {...props}
        />
        <button
          type="button"
          className="text-muted-foreground hover:text-foreground absolute inset-y-0 right-0 grid w-10 place-items-center rounded-r-lg"
          onClick={() => setVisible((v) => !v)}
          aria-label={visible ? 'Ocultar contraseña' : 'Mostrar contraseña'}
          aria-pressed={visible}
        >
          {visible ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
        </button>
      </div>
      {capsLock && (
        <p className="text-warning text-xs" role="status">
          Bloq Mayús está activado.
        </p>
      )}
    </div>
  )
})
