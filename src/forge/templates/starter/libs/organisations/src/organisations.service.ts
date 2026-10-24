import { createHash, randomBytes } from 'node:crypto';
import { BadRequestException, ForbiddenException, Inject, Injectable, NotFoundException, Optional, UnprocessableEntityException } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import type { Invite, Membership } from '@prisma/client';
import { MAIL_PROVIDER, PrismaService, type AccountPrincipal, type MailProvider } from '@app/core';
import type { Member, MemberListQuery } from '@app/shared';

function memberResponse(member: Membership): Member {
  return { id: member.id, accountId: member.accountId, email: member.email, role: member.role, createdAtUtc: member.createdAtUtc.toISOString() };
}

const INVITE_LIFETIME_MS = 7 * 24 * 60 * 60 * 1000;

function invalidInvite(): BadRequestException {
  return new BadRequestException({ code: 'INVITE_INVALID', message: 'This invite link is not valid. Ask an admin for a new one.', details: null });
}

@Injectable()
export class OrganisationsService {
  constructor(
    private readonly prisma: PrismaService,
    private readonly config: ConfigService,
    @Optional() @Inject(MAIL_PROVIDER) private readonly mailProvider: MailProvider | null = null,
  ) {}

  async invite(email: string, account: AccountPrincipal): Promise<void> {
    if (!this.mailProvider) {
      throw new UnprocessableEntityException({ code: 'MAIL_NOT_CONFIGURED', message: 'Email is not set up for this app yet.', details: null });
    }
    const token = randomBytes(32).toString('base64url');
    const credentials = { tokenHash: createHash('sha256').update(token).digest('hex'), expiresAtUtc: new Date(Date.now() + INVITE_LIFETIME_MS), modifiedByAccountId: account.id };
    await this.prisma.invite.upsert({
      where: { organisationId_email: { organisationId: account.organisationId, email } },
      create: { organisationId: account.organisationId, email, createdByAccountId: account.id, ...credentials },
      update: credentials,
    });
    const inviteUrl = new URL('/accept-invite', this.config.getOrThrow<string>('APP_ORIGIN'));
    inviteUrl.searchParams.set('token', token);
    await this.mailProvider.sendInvite(email, inviteUrl.toString());
  }

  async openInvite(token: string): Promise<Invite> {
    const invite = await this.prisma.invite.findUnique({ where: { tokenHash: createHash('sha256').update(token).digest('hex') }, include: { organisation: { select: { deletedAtUtc: true } } } });
    if (!invite || invite.expiresAtUtc <= new Date() || invite.organisation.deletedAtUtc) throw invalidInvite();
    return invite;
  }

  async joinFromInvite(invite: Invite, account: { id: string; email: string }) {
    return this.prisma.$transaction(async (transaction) => {
      const claimed = await transaction.invite.deleteMany({ where: { id: invite.id, tokenHash: invite.tokenHash, expiresAtUtc: { gt: new Date() } } });
      if (claimed.count !== 1) throw invalidInvite();
      return transaction.membership.create({ data: {
        accountId: account.id, email: account.email, organisationId: invite.organisationId, role: 'member',
        createdByAccountId: account.id, modifiedByAccountId: account.id,
      } });
    });
  }

  async changeRole(account: AccountPrincipal, accountId: string, role: Member['role']): Promise<Member> {
    if (accountId === account.id) {
      throw new ForbiddenException({ code: 'CANNOT_CHANGE_OWN_ROLE', message: 'You cannot change your own role.', details: null });
    }
    const changed = await this.prisma.membership.updateMany({
      where: { accountId, organisationId: account.organisationId, deletedAtUtc: null },
      data: { role, modifiedByAccountId: account.id },
    });
    if (changed.count !== 1) {
      throw new NotFoundException({ code: 'MEMBER_NOT_FOUND', message: 'This member was not found.', details: null });
    }
    const member = await this.prisma.membership.findFirstOrThrow({ where: { accountId, organisationId: account.organisationId, deletedAtUtc: null } });
    return memberResponse(member);
  }

  async createForAccount(account: { id: string; email: string }) {
    const organisation = await this.prisma.organisation.create({
      data: {
        createdByAccountId: account.id, modifiedByAccountId: account.id,
        memberships: { create: { accountId: account.id, email: account.email, role: 'admin', createdByAccountId: account.id, modifiedByAccountId: account.id } },
      },
      include: { memberships: true },
    });
    return organisation.memberships[0];
  }

  membershipFor(accountId: string) {
    return this.prisma.membership.findFirst({
      where: { accountId, deletedAtUtc: null, organisation: { deletedAtUtc: null } },
      select: { organisationId: true, role: true },
    });
  }

  async list(organisationId: string, query: MemberListQuery) {
    const where = { organisationId, deletedAtUtc: null };
    const [members, totalItems] = await Promise.all([
      this.prisma.membership.findMany({ where, orderBy: [{ createdAtUtc: 'asc' }, { id: 'asc' }], skip: (query.page - 1) * query.limit, take: query.limit }),
      this.prisma.membership.count({ where }),
    ]);
    return { items: members.map(memberResponse), pagination: { page: query.page, limit: query.limit, totalItems, totalPages: Math.ceil(totalItems / query.limit) } };
  }

  async listAll(organisationId: string): Promise<Member[]> {
    const members = await this.prisma.membership.findMany({ where: { organisationId, deletedAtUtc: null }, orderBy: [{ createdAtUtc: 'asc' }, { id: 'asc' }] });
    return members.map(memberResponse);
  }
}
