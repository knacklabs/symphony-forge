export const HISTORY_API = 'HistoryApi';

export type HistoryPrincipal = { id: string; email: string; organisationId: string };

export interface HistoryApi {
  record(principal: HistoryPrincipal, action: 'member.invited' | 'member.role_changed', summary: string): Promise<void>;
}
