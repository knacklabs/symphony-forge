import { ForbiddenException, Injectable, UseGuards, type CanActivate, type ExecutionContext } from '@nestjs/common';
import type { AuthenticatedRequest } from './authenticated-request';

@Injectable()
class AdminOnlyGuard implements CanActivate {
  canActivate(context: ExecutionContext): boolean {
    const request = context.switchToHttp().getRequest<AuthenticatedRequest>();
    if (request.principal?.role === 'admin') return true;

    throw new ForbiddenException({
      code: 'ADMIN_ONLY',
      message: 'Only an admin can do this.',
      details: null,
    });
  }
}

export const AdminOnly = () => UseGuards(AdminOnlyGuard);
