export const NOTIFICATIONS_API = 'NotificationsApi';

export type NotificationsPrincipal = { id: string; organisationId: string };
export type NotificationEntry = {
  id: string;
  subjectId: string;
  subjectName: string;
  message: string;
  createdAtUtc: string;
};
export type NotificationsList = { count: number; items: NotificationEntry[] };

export interface NotificationsApi {
  /** Pass the feature's transaction so the change and waiting entry save together. */
  notify(principal: NotificationsPrincipal, recipientAccountId: string, subjectId: string,
    subjectName: string, message: string, tx?: unknown): Promise<void>;
  /** Close every open entry for this record in the caller's organisation, in the same save. */
  resolve(principal: NotificationsPrincipal, subjectId: string, tx?: unknown): Promise<void>;
}
