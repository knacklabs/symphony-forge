import { Injectable, NotFoundException } from '@nestjs/common';
import type { Project } from '@prisma/client';
import { PrismaService } from '@app/core';
import type { AccountPrincipal } from '@app/auth';
import type { ProjectInput } from '@app/shared';
import type { ProjectListQueryDto } from './projects.dto';

function toProjectResponse(project: Project) {
  return {
    id: project.id,
    name: project.name,
    status: project.status,
    createdAtUtc: project.createdAtUtc.toISOString(),
    updatedAtUtc: project.updatedAtUtc.toISOString(),
    createdByAccountId: project.createdByAccountId,
    modifiedByAccountId: project.modifiedByAccountId,
  };
}

@Injectable()
export class ProjectsService {
  constructor(private readonly prisma: PrismaService) {}

  async list(account: AccountPrincipal, query: ProjectListQueryDto) {
    const where = { accountId: account.id, deletedAtUtc: null };
    const [projects, totalItems] = await Promise.all([
      this.prisma.project.findMany({
        where,
        skip: (query.page - 1) * query.limit,
        take: query.limit,
        orderBy: [{ [query.sortBy]: query.sortOrder }, { id: 'asc' }],
      }),
      this.prisma.project.count({ where }),
    ]);
    return {
      items: projects.map(toProjectResponse),
      pagination: {
        page: query.page,
        limit: query.limit,
        totalItems,
        totalPages: Math.ceil(totalItems / query.limit),
      },
    };
  }

  async get(account: AccountPrincipal, id: string) {
    const project = await this.prisma.project.findFirst({ where: { id, accountId: account.id, deletedAtUtc: null } });
    if (!project) throw this.notFound();
    return toProjectResponse(project);
  }

  async create(account: AccountPrincipal, input: ProjectInput) {
    const project = await this.prisma.project.create({
      data: {
        accountId: account.id,
        name: input.name,
        status: input.status,
        createdByAccountId: account.id,
        modifiedByAccountId: account.id,
      },
    });
    return toProjectResponse(project);
  }

  async update(account: AccountPrincipal, id: string, input: ProjectInput) {
    const result = await this.prisma.project.updateMany({
      where: { id, accountId: account.id, deletedAtUtc: null },
      data: { name: input.name, status: input.status, modifiedByAccountId: account.id },
    });
    if (result.count === 0) throw this.notFound();
    return this.get(account, id);
  }

  async delete(account: AccountPrincipal, id: string): Promise<void> {
    const result = await this.prisma.project.updateMany({
      where: { id, accountId: account.id, deletedAtUtc: null },
      data: { deletedAtUtc: new Date(), deletedByAccountId: account.id, modifiedByAccountId: account.id },
    });
    if (result.count === 0) throw this.notFound();
  }

  private notFound(): NotFoundException {
    return new NotFoundException({ code: 'PROJECT_NOT_FOUND', message: 'The project was not found.', details: null });
  }
}
