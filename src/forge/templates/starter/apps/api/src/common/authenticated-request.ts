import type { Request } from 'express';

export type AccountPrincipal = { id: string; email: string };
export type AuthenticatedRequest = Request & {
  principal?: AccountPrincipal;
  csrfTokenHash?: string;
};
