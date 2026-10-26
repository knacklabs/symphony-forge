import { useQuery } from '@tanstack/react-query';
import type { HistoryEntry } from '@app/history-contracts';
import { apiRequest } from '@app/core-web';

export function useHistory(enabled: boolean) {
  return useQuery({
    queryKey: ['history'],
    // The API returns the newest 100 changes, newest first; the export has every change.
    queryFn: () => apiRequest<HistoryEntry[]>('/history'),
    enabled,
  });
}
