import { QueryClient } from '@tanstack/react-query';

export const queryClient = new QueryClient({
  defaultOptions: {
    // 'always': an offline request fails at once, so each screen shows its error and Try again, not endless loading.
    queries: { retry: false, refetchOnWindowFocus: false, networkMode: 'always' },
    // The same for changes: an offline save fails at once with its own message, instead of waiting unseen.
    mutations: { networkMode: 'always' },
  },
});
