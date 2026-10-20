import { useCallback, useEffect, useState } from 'react'

export type Theme = 'light' | 'dark'
const KEY = 'atina-theme'

function current(): Theme {
  return document.documentElement.classList.contains('dark') ? 'dark' : 'light'
}

/** Tema claro/oscuro. La preferencia se guarda solo en este navegador. */
export function useTheme(): { theme: Theme; toggle: () => void } {
  const [theme, setTheme] = useState<Theme>(current)

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark')
  }, [theme])

  const toggle = useCallback(() => {
    setTheme((t) => {
      const next = t === 'dark' ? 'light' : 'dark'
      try {
        localStorage.setItem(KEY, next)
      } catch {
        // Sin almacenamiento (p. ej. navegación privada): el cambio dura solo esta sesión.
      }
      return next
    })
  }, [])

  return { theme, toggle }
}
