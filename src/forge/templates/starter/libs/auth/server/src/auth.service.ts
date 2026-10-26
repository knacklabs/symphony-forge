import { randomBytes, createHash, scrypt, timingSafeEqual } from 'node:crypto';
import { Inject, Injectable, Optional, BadRequestException, ConflictException, ForbiddenException, UnauthorizedException } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { Prisma, type Account } from '@prisma/client';
import { MAIL_PROVIDER, permissionsFor, PrismaService, type AccountPrincipal, type MailProvider } from '@app/core-server';
import { ORGANISATIONS_API, roleSchema, type OrganisationsApi } from '@app/organisations-contracts';
import type { Account as AccountResponse, AuthOptions } from '@app/auth-contracts';

const PASSWORD_KEY_BYTES = 64;
const PASSWORD_SALT_BYTES = 16;
// OWASP's scrypt baseline uses 128 MiB; Node also needs room for its working buffers.
const PASSWORD_SCRYPT_OPTIONS = { N: 2 ** 17, r: 8, p: 1, maxmem: 256 * 1024 * 1024 };
const SESSION_LIFETIME_MS = 30 * 24 * 60 * 60 * 1000;
const RESET_TOKEN_LIFETIME_MS = 60 * 60 * 1000;
const RESET_MESSAGE = 'If an account exists, a reset link has been sent.';

export type SessionCookies = { sessionToken: string; csrfToken: string; expiresAtUtc: Date };

function sha256(value: string): string {
  return createHash('sha256').update(value).digest('hex');
}

function derivePasswordKey(password: string, salt: Buffer): Promise<Buffer> {
  return new Promise((resolve, reject) => {
    scrypt(password, salt, PASSWORD_KEY_BYTES, PASSWORD_SCRYPT_OPTIONS, (error, derivedKey) => {
      if (error) reject(error);
      else resolve(derivedKey);
    });
  });
}

async function hashPassword(password: string): Promise<string> {
  const salt = randomBytes(PASSWORD_SALT_BYTES);
  const key = await derivePasswordKey(password, salt);
  return `scrypt$${salt.toString('base64url')}$${key.toString('base64url')}`;
}

async function verifyPassword(password: string, storedHash: string): Promise<boolean> {
  const [scheme, saltValue, keyValue] = storedHash.split('$');
  if (scheme !== 'scrypt' || !saltValue || !keyValue) return false;
  const salt = Buffer.from(saltValue, 'base64url');
  const expected = Buffer.from(keyValue, 'base64url');
  if (salt.length !== PASSWORD_SALT_BYTES || expected.length !== PASSWORD_KEY_BYTES) return false;
  const actual = await derivePasswordKey(password, salt);
  return timingSafeEqual(actual, expected);
}

function accountResponse(account: Pick<Account, 'id' | 'email'>, role: AccountResponse['role']): AccountResponse {
  const parsedRole = roleSchema.parse(role);
  return { id: account.id, email: account.email, role: parsedRole, permissions: permissionsFor(parsedRole) };
}

@Injectable()
export class AuthService {
  constructor(
    private readonly prisma: PrismaService,
    private readonly config: ConfigService,
    @Inject(ORGANISATIONS_API) private readonly organisations: OrganisationsApi,
    @Optional() @Inject(MAIL_PROVIDER) private readonly mailProvider: MailProvider | null = null,
  ) {}

  async signUp(email: string, password: string): Promise<{ account: AccountResponse; cookies: SessionCookies }> {
    if (!this.options().signUpOpen) {
      throw new ForbiddenException({ code: 'SIGN_UP_CLOSED', message: 'This app is for one company. Ask an admin of your team for an invite.', details: null });
    }
    const account = await this.setUpCompany(email, password);
    return { account, cookies: await this.createSession(account.id) };
  }

  options(): AuthOptions {
    return { signUpOpen: this.config.getOrThrow<string>('APP_COMPANIES') === 'many' };
  }

  async setUpCompany(email: string, password: string): Promise<AccountResponse> {
    const account = await this.createAccount(email, password);
    // ponytail: account and organisation creation are two module calls; add recovery if sign-up needs retries across failures.
    const membership = await this.organisations.createForAccount(account);
    return accountResponse(account, membership.role);
  }

  async invite(email: string, account: AccountPrincipal): Promise<{ message: string }> {
    if (await this.prisma.account.findUnique({ where: { email }, select: { id: true } })) {
      throw new ConflictException({ code: 'EMAIL_ALREADY_REGISTERED', message: 'That person already has an account.', details: null });
    }
    await this.organisations.invite(email, account);
    return { message: 'Invite sent.' };
  }

  async acceptInvite(token: string, email: string, password: string): Promise<{ account: AccountResponse; cookies: SessionCookies }> {
    const invite = await this.organisations.openInvite(token);
    if (invite.email !== email) {
      throw new BadRequestException({ code: 'INVITE_INVALID', message: 'This invite link is not valid. Ask an admin for a new one.', details: null });
    }
    const account = await this.createAccount(email, password, 'An account already uses that email, so it cannot join this organisation.');
    // ponytail: a failure between these module calls leaves an account with no membership and 401; support must remove it before another attempt.
    const membership = await this.organisations.joinFromInvite(invite, account);
    return { account: accountResponse(account, membership.role), cookies: await this.createSession(account.id) };
  }

  private async createAccount(email: string, password: string, conflictMessage = 'An account already uses that email.'): Promise<Account> {
    const passwordHash = await hashPassword(password);
    let account: Account;
    try {
      account = await this.prisma.$transaction(async (transaction) => {
        // The account's audit fields refer to itself, so obtain its database id first.
        const [{ id }] = await transaction.$queryRaw<{ id: string }[]>`SELECT uuidv7()::text AS id`;
        return transaction.account.create({
          data: { id, email, passwordHash, createdByAccountId: id, modifiedByAccountId: id },
        });
      });
    } catch (error) {
      if (error instanceof Prisma.PrismaClientKnownRequestError && error.code === 'P2002') {
        throw new ConflictException({ code: 'EMAIL_ALREADY_REGISTERED', message: conflictMessage, details: null });
      }
      throw error;
    }
    return account;
  }

  async signIn(email: string, password: string): Promise<{ account: AccountResponse; cookies: SessionCookies }> {
    const account = await this.prisma.account.findUnique({ where: { email } });
    if (!account || !(await verifyPassword(password, account.passwordHash))) {
      throw new UnauthorizedException({ code: 'INVALID_CREDENTIALS', message: 'The email or password is incorrect.', details: null });
    }
    const membership = await this.organisations.membershipFor(account.id);
    if (!membership) {
      throw new UnauthorizedException({ code: 'UNAUTHENTICATED', message: 'Sign in to continue.', details: null });
    }
    return { account: accountResponse(account, membership.role), cookies: await this.createSession(account.id) };
  }

  async signOut(accountId: string, sessionToken: string | undefined): Promise<void> {
    if (!sessionToken) return;
    await this.prisma.session.deleteMany({ where: { accountId, tokenHash: sha256(sessionToken) } });
  }

  async forgotPassword(email: string): Promise<{ message: string }> {
    const account = await this.prisma.account.findUnique({ where: { email }, select: { id: true, email: true } });
    if (!account || !this.mailProvider) return { message: RESET_MESSAGE };

    const token = randomBytes(32).toString('base64url');
    await this.prisma.passwordResetToken.deleteMany({ where: { accountId: account.id } });
    await this.prisma.passwordResetToken.create({
      data: { accountId: account.id, tokenHash: sha256(token), expiresAtUtc: new Date(Date.now() + RESET_TOKEN_LIFETIME_MS) },
    });
    const resetUrl = new URL('/reset-password', this.config.getOrThrow<string>('APP_ORIGIN'));
    resetUrl.searchParams.set('token', token);
    await this.mailProvider.sendPasswordReset(account.email, resetUrl.toString());
    return { message: RESET_MESSAGE };
  }

  async resetPassword(token: string, newPassword: string): Promise<{ message: string }> {
    const tokenHash = sha256(token);
    const passwordHash = await hashPassword(newPassword);
    await this.prisma.$transaction(async (transaction) => {
      const reset = await transaction.passwordResetToken.findUnique({ where: { tokenHash } });
      const now = new Date();
      if (!reset || reset.expiresAtUtc <= now) {
        throw new BadRequestException({ code: 'RESET_TOKEN_INVALID', message: 'This reset link has expired. Request a new one.', details: null });
      }
      const claimed = await transaction.passwordResetToken.deleteMany({
        where: { id: reset.id, expiresAtUtc: { gt: now } },
      });
      if (claimed.count !== 1) {
        throw new BadRequestException({ code: 'RESET_TOKEN_INVALID', message: 'This reset link has expired. Request a new one.', details: null });
      }
      await transaction.account.update({ where: { id: reset.accountId }, data: { passwordHash } });
      await transaction.passwordResetToken.deleteMany({ where: { accountId: reset.accountId } });
      await transaction.session.deleteMany({ where: { accountId: reset.accountId } });
    });
    return { message: 'Your password has been reset. Sign in with your new password.' };
  }

  private async createSession(accountId: string): Promise<SessionCookies> {
    const sessionToken = randomBytes(32).toString('base64url');
    const csrfToken = randomBytes(32).toString('base64url');
    const expiresAtUtc = new Date(Date.now() + SESSION_LIFETIME_MS);
    await this.prisma.session.create({
      data: { accountId, tokenHash: sha256(sessionToken), csrfTokenHash: sha256(csrfToken), expiresAtUtc },
    });
    return { sessionToken, csrfToken, expiresAtUtc };
  }
}
