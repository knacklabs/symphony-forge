import { createParamDecorator, ExecutionContext, UnauthorizedException } from '@nestjs/common';
import type { AuthenticatedRequest, AccountPrincipal } from './authenticated-request';

export const CurrentAccount = createParamDecorator((_data: unknown, context: ExecutionContext): AccountPrincipal => {
  const request = context.switchToHttp().getRequest<AuthenticatedRequest>();
  if (!request.principal) {
    throw new UnauthorizedException({ code: 'UNAUTHENTICATED', message: 'Sign in to continue.', details: null });
  }
  return request.principal;
});
