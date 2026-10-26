import { createHash } from 'node:crypto';
import { CanActivate, ExecutionContext, Inject, Injectable, UnauthorizedException } from '@nestjs/common';
import { Reflector } from '@nestjs/core';
import { PrismaService, PUBLIC_ROUTE, type AuthenticatedRequest } from '@app/core-server';
import { ORGANISATIONS_API, type OrganisationsApi } from '@app/organisations-contracts';

const SESSION_COOKIE = 'starter_session';

@Injectable()
export class SessionGuard implements CanActivate {
  constructor(
    private readonly reflector: Reflector,
    private readonly prisma: PrismaService,
    @Inject(ORGANISATIONS_API) private readonly organisations: OrganisationsApi,
  ) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const isPublic = this.reflector.getAllAndOverride<boolean>(PUBLIC_ROUTE, [context.getHandler(), context.getClass()]);
    if (isPublic) return true;

    const request = context.switchToHttp().getRequest<AuthenticatedRequest>();
    const sessionToken = request.cookies?.[SESSION_COOKIE] as string | undefined;
    if (!sessionToken) throw this.unauthorized();

    const session = await this.prisma.session.findUnique({
      where: { tokenHash: createHash('sha256').update(sessionToken).digest('hex') },
      include: { account: { select: { id: true, email: true } } },
    });
    if (!session || session.expiresAtUtc <= new Date()) {
      if (session) await this.prisma.session.deleteMany({ where: { id: session.id } });
      throw this.unauthorized();
    }

    const membership = await this.organisations.membershipFor(session.account.id);
    if (!membership) throw this.unauthorized();
    request.principal = { ...session.account, organisationId: membership.organisationId, role: membership.role };
    request.csrfTokenHash = session.csrfTokenHash;
    return true;
  }

  private unauthorized(): UnauthorizedException {
    return new UnauthorizedException({ code: 'UNAUTHENTICATED', message: 'Sign in to continue.', details: null });
  }
}

export const sessionOptions = (environment: string, expiresAtUtc: Date) => ({
  httpOnly: true,
  sameSite: 'lax' as const,
  secure: environment !== 'development' && environment !== 'test',
  path: '/',
  expires: expiresAtUtc,
});
