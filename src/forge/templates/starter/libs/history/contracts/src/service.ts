export const HISTORY_API = 'HistoryApi';

export type HistoryPrincipal = { id: string; email: string; organisationId: string };

/** The changed item; its name prefixes the summary on the Change history screen. */
export type HistorySubject = { id: string; name: string };

export type HistoryEntry = { id: string; actorEmail: string; summary: string; createdAtUtc: string };

export interface HistoryApi {
  /** `tx` is the caller's open transaction, so the change and its history row commit together. */
  record(principal: HistoryPrincipal, action: string, summary: string, subject?: HistorySubject, tx?: unknown): Promise<void>;
  /** The newest changes to one item in the caller's organisation, newest first. */
  listForSubject(principal: HistoryPrincipal, subjectId: string, limit: number): Promise<HistoryEntry[]>;
}
