import { createHash, randomBytes } from 'node:crypto';
import { BadRequestException, ForbiddenException, Inject, Injectable, NotFoundException, Optional, UnprocessableEntityException } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import type { Membership } from '@prisma/client';
import { MAIL_PROVIDER, PrismaService, type AccountPrincipal, type MailProvider } from '@app/core-server';
import { HISTORY_API, type HistoryApi } from '@app/history-contracts';
import { roleSchema, type AgentKey, type AgentTools, type Member, type MemberListQuery, type OrganisationAccount, type OrganisationInvite, type OrganisationPrincipal, type OrganisationsApi, type Role } from '@app/organisations-contracts';

function memberResponse(member: Membership): Member {
  return {
    id: member.id, accountId: member.accountId, email: member.email, role: roleSchema.parse(member.role),
    isAgent: member.isAgent, hasKey: member.agentKeyHash !== null, createdAtUtc: member.createdAtUtc.toISOString(),
  };
}

const ROLE_NAMES: Record<Role, string> = { admin: 'Admin', member: 'Member' };
type InviteOptions = NonNullable<Parameters<OrganisationsApi['invite']>[2]>;

function memberNotFound(): NotFoundException {
  return new NotFoundException({ code: 'MEMBER_NOT_FOUND', message: 'This member was not found.', details: null });
}

const INVITE_LIFETIME_MS = 7 * 24 * 60 * 60 * 1000;

function invalidInvite(): BadRequestException {
  return new BadRequestException({ code: 'INVITE_INVALID', message: 'This invite link is not valid. Ask an admin for a new one.', details: null });
}

@Injectable()
export class OrganisationsService implements OrganisationsApi {
  constructor(
    private readonly prisma: PrismaService,
    private readonly config: ConfigService,
    @Inject(HISTORY_API) private readonly history: HistoryApi,
    @Optional() @Inject(MAIL_PROVIDER) private readonly mailProvider: MailProvider | null = null,
  ) {}

  async invite(email: string, account: OrganisationPrincipal, options?: InviteOptions): Promise<string> {
    const mailProvider = this.mailProvider;
    if (!mailProvider) {
      throw new UnprocessableEntityException({ code: 'MAIL_NOT_CONFIGURED', message: 'Email is not set up for this app yet.', details: null });
    }
    const token = randomBytes(32).toString('base64url');
    const credentials = { tokenHash: createHash('sha256').update(token).digest('hex'), expiresAtUtc: new Date(Date.now() + INVITE_LIFETIME_MS), modifiedByAccountId: account.id };
    return this.prisma.$transaction(async (tx) => {
      const invite = await tx.invite.upsert({
        where: { organisationId_email: { organisationId: account.organisationId, email } },
        create: { organisationId: account.organisationId, email, createdByAccountId: account.id, ...credentials },
        update: credentials,
      });
      await options?.afterCreate(tx, invite.id);
      await this.history.record(account, 'member.invited', `Invited ${email}`, undefined, tx);
      const inviteUrl = new URL('/accept-invite', this.config.getOrThrow<string>('APP_ORIGIN'));
      inviteUrl.searchParams.set('token', token);
      await mailProvider.sendInvite(email, inviteUrl.toString());
      return invite.id;
    });
  }

  async openInvite(token: string): Promise<OrganisationInvite> {
    const invite = await this.prisma.invite.findUnique({ where: { tokenHash: createHash('sha256').update(token).digest('hex') }, include: { organisation: { select: { deletedAtUtc: true } } } });
    if (!invite || invite.expiresAtUtc <= new Date() || invite.organisation.deletedAtUtc) throw invalidInvite();
    return invite;
  }

  async joinFromInvite(invite: OrganisationInvite, account: { id: string; email: string }) {
    return this.prisma.$transaction(async (transaction) => {
      const claimed = await transaction.invite.deleteMany({ where: { id: invite.id, tokenHash: invite.tokenHash, expiresAtUtc: { gt: new Date() } } });
      if (claimed.count !== 1) throw invalidInvite();
      const membership = await transaction.membership.create({ data: {
        accountId: account.id, email: account.email, organisationId: invite.organisationId, role: 'member',
        createdByAccountId: account.id, modifiedByAccountId: account.id,
      } });
      return { ...membership, role: roleSchema.parse(membership.role) };
    });
  }

  async changeRole(account: AccountPrincipal, accountId: string, role: Member['role']): Promise<Member> {
    if (accountId === account.id) {
      throw new ForbiddenException({ code: 'CANNOT_CHANGE_OWN_ROLE', message: 'You cannot change your own role.', details: null });
    }
    const member = await this.prisma.membership.findFirst({ where: { accountId, organisationId: account.organisationId, deletedAtUtc: null } });
    if (!member) {
      throw new NotFoundException({ code: 'MEMBER_NOT_FOUND', message: 'This member was not found.', details: null });
    }
    const changed = await this.prisma.membership.updateMany({
      where: { accountId, organisationId: account.organisationId, deletedAtUtc: null },
      data: { role, modifiedByAccountId: account.id },
    });
    if (changed.count !== 1) {
      throw new NotFoundException({ code: 'MEMBER_NOT_FOUND', message: 'This member was not found.', details: null });
    }
    // ponytail: changing the role and its history are two calls; use a shared transaction if atomic history becomes required.
    await this.history.record(account, 'member.role_changed', `Changed ${member.email} from ${member.role} to ${role}`);
    return memberResponse({ ...member, role });
  }

  async createForAccount(account: { id: string; email: string }) {
    const organisation = await this.prisma.organisation.create({
      data: {
        createdByAccountId: account.id, modifiedByAccountId: account.id,
        memberships: { create: { accountId: account.id, email: account.email, role: 'admin', createdByAccountId: account.id, modifiedByAccountId: account.id } },
      },
      include: { memberships: true },
    });
    const membership = organisation.memberships[0];
    return { ...membership, role: roleSchema.parse(membership.role) };
  }

  async membershipFor(accountId: string) {
    const membership = await this.prisma.membership.findFirst({
      where: { accountId, deletedAtUtc: null, organisation: { deletedAtUtc: null } },
      select: { organisationId: true, role: true },
    });
    return membership ? { ...membership, role: roleSchema.parse(membership.role) } : null;
  }

  async addAgent(account: OrganisationAccount, role: Role, admin: OrganisationPrincipal): Promise<Member> {
    return this.prisma.$transaction(async (tx) => {
      const membership = await tx.membership.create({ data: {
        accountId: account.id, email: account.email, organisationId: admin.organisationId, role, isAgent: true,
        createdByAccountId: admin.id, modifiedByAccountId: admin.id,
      } });
      await this.history.record(admin, 'agent.added', `Added the agent account ${account.email} as ${ROLE_NAMES[role]}`, undefined, tx);
      return memberResponse(membership);
    });
  }

  /** A new key replaces the agent's old one, which stops working at once. The app keeps only its hash. */
  async createKey(admin: AccountPrincipal, accountId: string): Promise<AgentKey> {
    const key = `agent_${randomBytes(32).toString('base64url')}`;
    await this.setKeyHash(admin, accountId, createHash('sha256').update(key).digest('hex'), 'agent.key-created', 'Created a key for');
    return { key };
  }

  async revokeKey(admin: AccountPrincipal, accountId: string): Promise<void> {
    await this.setKeyHash(admin, accountId, null, 'agent.key-revoked', 'Revoked the key for');
  }

  private async setKeyHash(admin: AccountPrincipal, accountId: string, agentKeyHash: string | null, action: string, summary: string): Promise<void> {
    await this.prisma.$transaction(async (tx) => {
      const where = { accountId, organisationId: admin.organisationId, isAgent: true, deletedAtUtc: null };
      const agent = await tx.membership.findFirst({ where });
      if (!agent) throw memberNotFound();
      await tx.membership.updateMany({ where, data: { agentKeyHash, modifiedByAccountId: admin.id } });
      await this.history.record(admin, action, `${summary} ${agent.email}`, undefined, tx);
    });
  }

  async agentForKey(keyHash: string) {
    const agent = await this.prisma.membership.findUnique({
      where: { agentKeyHash: keyHash },
      include: { organisation: { select: { agentDeleteRestore: true, deletedAtUtc: true } } },
    });
    if (!agent || !agent.isAgent || agent.deletedAtUtc || agent.organisation.deletedAtUtc) return null;
    return {
      principal: { id: agent.accountId, email: agent.email, organisationId: agent.organisationId, role: roleSchema.parse(agent.role) },
      deleteAndRestore: agent.organisation.agentDeleteRestore,
    };
  }

  async agentTools(organisationId: string): Promise<AgentTools> {
    const organisation = await this.prisma.organisation.findUniqueOrThrow({ where: { id: organisationId }, select: { agentDeleteRestore: true } });
    return { deleteAndRestore: organisation.agentDeleteRestore };
  }

  // ponytail: a feature name is checked only for its form; an unknown name is stored and does nothing.
  async setAgentTools(admin: AccountPrincipal, feature: string, deleteAndRestore: boolean): Promise<AgentTools> {
    return this.prisma.$transaction(async (tx) => {
      const { agentDeleteRestore } = await tx.organisation.findUniqueOrThrow({ where: { id: admin.organisationId }, select: { agentDeleteRestore: true } });
      if (agentDeleteRestore.includes(feature) === deleteAndRestore) return { deleteAndRestore: agentDeleteRestore };
      const next = deleteAndRestore ? [...agentDeleteRestore, feature] : agentDeleteRestore.filter((name) => name !== feature);
      await tx.organisation.update({ where: { id: admin.organisationId }, data: { agentDeleteRestore: next, modifiedByAccountId: admin.id } });
      await this.history.record(admin, 'agent-tools.changed', `Turned ${deleteAndRestore ? 'on' : 'off'} agent delete and restore for ${feature}`, undefined, tx);
      return { deleteAndRestore: next };
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
