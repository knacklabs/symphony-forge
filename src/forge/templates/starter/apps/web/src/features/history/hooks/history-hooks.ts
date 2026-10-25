import { useQuery } from '@tanstack/react-query';
import type { HistoryEntry } from '@app/shared';
import { apiRequest } from '@/lib/api-client';

export function useHistory(enabled: boolean) {
  return useQuery({
    queryKey: ['history'],
    // The API returns the newest 100 changes, newest first; the export has every change.
    queryFn: () => apiRequest<HistoryEntry[]>('/history'),
    enabled,
  });
}
