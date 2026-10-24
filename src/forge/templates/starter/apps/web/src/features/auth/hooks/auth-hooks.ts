import { useMutation, useQuery, useQueryClient, type QueryClient } from '@tanstack/react-query';
import type { Account, AuthCredentials } from '@app/shared';
import { ApiError, apiRequest } from '@/lib/api-client';

const accountKey = ['account'] as const;

async function clearProjectCache(queryClient: QueryClient) {
  await queryClient.cancelQueries({ queryKey: ['projects'] });
  queryClient.removeQueries({ queryKey: ['projects'] });
}

export function useAccount() {
  return useQuery({
    queryKey: accountKey,
    queryFn: async () => {
      try {
        return await apiRequest<Account>('/auth/me');
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) return null;
        throw error;
      }
    },
    retry: false,
    refetchOnWindowFocus: false,
  });
}

function useStartSession(path: '/auth/sign-in' | '/auth/sign-up') {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (credentials: AuthCredentials) => apiRequest<Account>(path, {
      method: 'POST',
      body: JSON.stringify(credentials),
    }),
    onSuccess: async (account) => {
      await clearProjectCache(queryClient);
      queryClient.setQueryData(accountKey, account);
    },
  });
}

export function useSignIn() {
  return useStartSession('/auth/sign-in');
}

export function useSignUp() {
  return useStartSession('/auth/sign-up');
}

export function useSignOut() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => apiRequest<{ message: string }>('/auth/sign-out', { method: 'POST' }),
    onSuccess: async () => {
      await clearProjectCache(queryClient);
      queryClient.setQueryData(accountKey, null);
    },
  });
}

export function useForgotPassword() {
  return useMutation({
    mutationFn: (email: string) => apiRequest<{ message: string }>('/auth/forgot-password', {
      method: 'POST',
      body: JSON.stringify({ email }),
    }),
  });
}

export function useResetPassword() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ token, password }: { token: string; password: string }) => apiRequest<{ message: string }>('/auth/reset-password', {
      method: 'POST',
      body: JSON.stringify({ token, password }),
    }),
    onSuccess: async () => {
      await clearProjectCache(queryClient);
      queryClient.setQueryData(accountKey, null);
    },
  });
}
