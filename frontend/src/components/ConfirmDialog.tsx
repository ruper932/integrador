import type { ReactNode } from 'react'

import { ErrorAlert } from '@/components/common'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'

/**
 * Confirmación de una acción con consecuencias (restablecer, desactivar, cerrar…), con la estética del sistema
 * en lugar del `confirm()` del navegador. El botón dice exactamente lo que hace.
 * Con `done` la acción ya se completó: se muestra ese contenido (p. ej. una contraseña temporal) y solo «Listo».
 */
export function ConfirmDialog({
  title,
  description,
  children,
  confirmLabel,
  pendingLabel = 'Procesando…',
  destructive = false,
  pending = false,
  disabled = false,
  error,
  done,
  onConfirm,
  onClose,
}: {
  title: string
  description?: ReactNode
  children?: ReactNode
  confirmLabel: ReactNode
  pendingLabel?: string
  destructive?: boolean
  pending?: boolean
  disabled?: boolean
  error?: unknown
  done?: ReactNode
  onConfirm: () => void
  onClose: () => void
}) {
  return (
    // Mientras la acción está en curso no se cierra: el resultado podría perderse.
    <Dialog open onOpenChange={(open) => !open && !pending && onClose()}>
      <DialogContent className="sm:max-w-md" showCloseButton={!pending}>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          {description && <DialogDescription>{description}</DialogDescription>}
        </DialogHeader>
        {done ?? children}
        {!done && <ErrorAlert error={error} />}
        <DialogFooter>
          {done ? (
            <Button onClick={onClose}>Listo</Button>
          ) : (
            <>
              <Button variant="outline" onClick={onClose} disabled={pending}>
                Cancelar
              </Button>
              <Button variant={destructive ? 'destructive' : 'default'} onClick={onConfirm} disabled={pending || disabled}>
                {pending ? pendingLabel : confirmLabel}
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
