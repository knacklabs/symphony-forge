import type { Request } from 'express';

export type AuthenticatedRequest = Request & {
  principal?: { id: string; email: string };
  csrfTokenHash?: string;
};
