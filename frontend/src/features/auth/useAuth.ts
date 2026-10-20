import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api, httpStatus } from '@/lib/api'
import type { Me } from '@/types/api'

export const ME_KEY = ['auth', 'me'] as const

async function fetchMe(): Promise<Me | null> {
  try {
    const { data } = await api.get<Me>('/auth/me')
    return data
  } catch (error) {
    if (httpStatus(error) === 401) return null
    throw error
  }
}

export function useMe() {
  return useQuery({ queryKey: ME_KEY, queryFn: fetchMe, retry: false, staleTime: 60_000 })
}

export function useHasPermission(): (permission: string) => boolean {
  const { data } = useMe()
  return (permission) => Boolean(data?.permissions.includes(permission))
}

export function useLogin() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (input: { username: string; password: string }) => {
      const { data } = await api.post<{ user: Me }>('/auth/login', input)
      return data.user
    },
    onSuccess: (user) => queryClient.setQueryData(ME_KEY, user),
  })
}

export function useLogout() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => api.post('/auth/logout'),
    onSettled: () => {
      queryClient.clear()
      queryClient.setQueryData(ME_KEY, null)
    },
  })
}
