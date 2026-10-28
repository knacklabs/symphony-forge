import type { Request } from 'express';
import type { AccountPrincipal } from './account-principal';

export type AuthenticatedRequest = Request & {
  principal?: AccountPrincipal;
  csrfTokenHash?: string;
};
