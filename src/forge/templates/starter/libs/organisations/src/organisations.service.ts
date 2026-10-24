import { Injectable } from '@nestjs/common';
import type { Membership } from '@prisma/client';
import { PrismaService } from '@app/core';
import type { Member, MemberListQuery } from '@app/shared';

function memberResponse(member: Membership): Member {
  return { id: member.id, accountId: member.accountId, email: member.email, role: member.role, createdAtUtc: member.createdAtUtc.toISOString() };
}

@Injectable()
export class OrganisationsService {
  constructor(private readonly prisma: PrismaService) {}

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
