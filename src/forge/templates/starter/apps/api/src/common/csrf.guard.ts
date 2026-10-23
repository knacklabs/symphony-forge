import { createHash, timingSafeEqual } from 'node:crypto';
import { CanActivate, ExecutionContext, ForbiddenException, Injectable } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import type { AuthenticatedRequest } from './authenticated-request';

const STATE_CHANGING_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);

@Injectable()
export class CsrfGuard implements CanActivate {
  constructor(private readonly config: ConfigService) {}

  canActivate(context: ExecutionContext): boolean {
    const request = context.switchToHttp().getRequest<AuthenticatedRequest>();
    if (!STATE_CHANGING_METHODS.has(request.method)) return true;

    const origin = request.header('origin');
    if (origin && origin !== this.config.getOrThrow<string>('APP_ORIGIN')) throw this.forbidden();
    if (!request.principal) return true;

    const cookieToken = request.cookies?.starter_csrf as string | undefined;
    const headerToken = request.header('x-csrf-token');
    if (!cookieToken || !headerToken || cookieToken !== headerToken || !request.csrfTokenHash) {
      throw this.forbidden();
    }

    const actualHash = Buffer.from(createHash('sha256').update(headerToken).digest('hex'));
    const expectedHash = Buffer.from(request.csrfTokenHash);
    if (actualHash.length !== expectedHash.length || !timingSafeEqual(actualHash, expectedHash)) throw this.forbidden();
    return true;
  }

  private forbidden(): ForbiddenException {
    return new ForbiddenException({ code: 'CSRF_CHECK_FAILED', message: 'Refresh the page and try again.', details: null });
  }
}
