import { useMutation, useQuery, useQueryClient, type QueryClient } from '@tanstack/react-query';
import { authOptionsSchema, type AcceptInviteInput, type Account, type AuthCredentials } from '@app/auth-contracts';
import { ApiError, apiRequest } from '@app/core-web';

const accountKey = ['account'] as const;

// Every query except the account belongs to one account, so an account change drops them all.
const accountData = { predicate: ({ queryKey }: { queryKey: readonly unknown[] }) => queryKey[0] !== accountKey[0] };

async function clearAccountData(queryClient: QueryClient) {
  await queryClient.cancelQueries(accountData);
  queryClient.removeQueries(accountData);
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

// The app's normal query defaults, so each page load reads the options again.
export function useAuthOptions() {
  return useQuery({
    queryKey: ['auth-options'],
    queryFn: async () => authOptionsSchema.parse(await apiRequest<unknown>('/auth/options')),
  });
}

function useStartSession<T extends AuthCredentials>(path: '/auth/sign-in' | '/auth/sign-up' | '/auth/accept-invite') {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (credentials: T) => apiRequest<Account>(path, {
      method: 'POST',
      body: JSON.stringify(credentials),
    }),
    onSuccess: async (account) => {
      await clearAccountData(queryClient);
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

export function useAcceptInvite() {
  return useStartSession<AcceptInviteInput>('/auth/accept-invite');
}

export function useSignOut() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => apiRequest<{ message: string }>('/auth/sign-out', { method: 'POST' }),
    onSuccess: async () => {
      await clearAccountData(queryClient);
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
      await clearAccountData(queryClient);
      queryClient.setQueryData(accountKey, null);
    },
  });
}
