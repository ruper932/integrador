import { MutationCache, QueryCache, QueryClient } from '@tanstack/react-query'

import { ME_KEY } from '@/features/auth/useAuth'
import { httpStatus } from '@/lib/api'

/**
 * Cliente de consultas de la aplicación. Si el servidor responde 401 con una sesión abierta (expiró, se cerró
 * en otro equipo o el administrador restableció la contraseña), se descartan los datos en memoria y se olvida
 * el usuario: la interfaz vuelve al inicio de sesión en lugar de mostrar errores sueltos.
 */
export function createQueryClient(): QueryClient {
  const onError = (error: unknown) => {
    if (httpStatus(error) !== 401 || !client.getQueryData(ME_KEY)) return
    client.clear()
    client.setQueryData(ME_KEY, null)
  }
  const client: QueryClient = new QueryClient({
    queryCache: new QueryCache({ onError }),
    mutationCache: new MutationCache({ onError }),
    defaultOptions: { queries: { refetchOnWindowFocus: false, retry: 1 } },
  })
  return client
}
