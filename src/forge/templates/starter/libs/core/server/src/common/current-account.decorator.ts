import { createParamDecorator, ExecutionContext, UnauthorizedException } from '@nestjs/common';
import type { AuthenticatedRequest } from './authenticated-request';
import type { AccountPrincipal } from './account-principal';

export const CurrentAccount = createParamDecorator((_data: unknown, context: ExecutionContext): AccountPrincipal => {
  const request = context.switchToHttp().getRequest<AuthenticatedRequest>();
  if (!request.principal) {
    throw new UnauthorizedException({ code: 'UNAUTHENTICATED', message: 'Sign in to continue.', details: null });
  }
  return request.principal;
});
