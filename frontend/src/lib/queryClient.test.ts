import { AxiosError, type AxiosResponse } from 'axios'

import { ME_KEY } from '@/features/auth/useAuth'
import { createQueryClient } from '@/lib/queryClient'

const unauthorized = () =>
  new AxiosError('401', 'ERR_BAD_REQUEST', undefined, undefined, { status: 401, data: {} } as AxiosResponse)

test('un 401 con sesión abierta olvida al usuario y los datos en memoria', async () => {
  const client = createQueryClient()
  client.setQueryData(ME_KEY, { username: 'ana', permissions: [] })
  client.setQueryData(['inventario'], ['dato privado'])
  await client.fetchQuery({ queryKey: ['x'], queryFn: () => Promise.reject(unauthorized()), retry: false }).catch(() => {})
  expect(client.getQueryData(ME_KEY)).toBeNull()
  expect(client.getQueryData(['inventario'])).toBeUndefined()
})

test('un 401 sin sesión (credenciales incorrectas en el login) no altera nada', async () => {
  const client = createQueryClient()
  client.setQueryData(['otra'], 1)
  await client.fetchQuery({ queryKey: ['x'], queryFn: () => Promise.reject(unauthorized()), retry: false }).catch(() => {})
  expect(client.getQueryData(['otra'])).toBe(1)
})
