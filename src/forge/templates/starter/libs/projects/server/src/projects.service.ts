import { BadRequestException, Injectable, NotFoundException } from '@nestjs/common';
import type { Prisma, Project } from '@prisma/client';
import { PrismaService } from '@app/core-server';
import type { AccountPrincipal } from '@app/core-server';
import { projectStatusSchema, type ProjectExportQuery, type ProjectInput, type ProjectListQuery } from '@app/projects-contracts';

function toProjectResponse(project: Project) {
  return {
    id: project.id,
    name: project.name,
    status: projectStatusSchema.parse(project.status),
    createdAtUtc: project.createdAtUtc.toISOString(),
    updatedAtUtc: project.updatedAtUtc.toISOString(),
    createdByAccountId: project.createdByAccountId,
    modifiedByAccountId: project.modifiedByAccountId,
  };
}

/** The list counts up to this many matching projects; above it the screen says "More than 10,000". */
const TOTAL_CAP = 10_000;
type SortBy = ProjectListQuery['sortBy'];
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** A cursor is the sort column, its value and the id of a page's first or last row, as base64url JSON. */
function encodeCursor(sortBy: SortBy, project: Project): string {
  const value = project[sortBy];
  return Buffer.from(JSON.stringify([sortBy, value instanceof Date ? value.toISOString() : value, project.id])).toString('base64url');
}

function decodeCursor(sortBy: SortBy, cursor: string, backward: boolean): { value: string | Date; id: string } {
  try {
    const [cursorSort, value, id] = JSON.parse(Buffer.from(cursor, 'base64url').toString('utf8')) as unknown[];
    if (cursorSort === sortBy && typeof value === 'string' && typeof id === 'string' && UUID.test(id)) {
      if (!sortBy.endsWith('AtUtc')) return { value, id };
      const time = new Date(value);
      if (!Number.isNaN(time.getTime())) return { value: time, id };
    }
  } catch {
    // An unreadable cursor gets the same field error as one for another sort.
  }
  throw new BadRequestException({
    code: 'VALIDATION_ERROR',
    message: 'Check the fields and try again.',
    details: { fieldErrors: [{ field: backward ? 'before' : 'after', reason: 'Open the first page of the list again.' }] },
  });
}

/** The organisation's live projects that match the list's search and status filter. */
function filterWhere(account: AccountPrincipal, filters: ProjectExportQuery): Prisma.ProjectWhereInput {
  return {
    organisationId: account.organisationId,
    deletedAtUtc: null,
    // Prisma passes % and _ to ILIKE as wildcards, so escape them to search for the text itself.
    ...(filters.search ? { name: { contains: filters.search.replace(/[\\%_]/g, '\\$&'), mode: 'insensitive' as const } } : {}),
    ...(filters.status ? { status: filters.status } : {}),
  };
}

/** The rows after the cursor row in this order: a later sort value, or the same value and a later id. */
function afterCursor(sortBy: SortBy, order: 'asc' | 'desc', cursor: { value: string | Date; id: string }): Prisma.ProjectWhereInput {
  const beyond = order === 'asc' ? 'gt' : 'lt';
  return { OR: [{ [sortBy]: { [beyond]: cursor.value } }, { [sortBy]: cursor.value, id: { [beyond]: cursor.id } }] };
}

@Injectable()
export class ProjectsService {
  constructor(private readonly prisma: PrismaService) {}

  async list(account: AccountPrincipal, query: ProjectListQuery) {
    const where = filterWhere(account, query);
    // A previous page reads backwards from its cursor, then flips its rows back into list order.
    const backward = query.before !== undefined;
    const cursor = query.before ?? query.after;
    const order = backward ? (query.sortOrder === 'asc' ? 'desc' : 'asc') : query.sortOrder;
    const [rows, total] = await Promise.all([
      this.prisma.project.findMany({
        where: cursor ? { AND: [where, afterCursor(query.sortBy, order, decodeCursor(query.sortBy, cursor, backward))] } : where,
        orderBy: [{ [query.sortBy]: order }, { id: order }],
        take: query.limit + 1,
      }),
      this.prisma.project.count({ where, take: TOTAL_CAP + 1 }),
    ]);
    const more = rows.length > query.limit;
    const projects = rows.slice(0, query.limit);
    if (backward) projects.reverse();
    const first = projects.at(0);
    const last = projects.at(-1);
    return {
      items: projects.map(toProjectResponse),
      paging: {
        limit: query.limit,
        nextCursor: last && (backward || more) ? encodeCursor(query.sortBy, last) : null,
        previousCursor: first && (backward ? more : cursor !== undefined) ? encodeCursor(query.sortBy, first) : null,
        total: Math.min(total, TOTAL_CAP),
        totalCapped: total > TOTAL_CAP,
      },
    };
  }

  /** The projects the list shows for this search and filter, newest first, for the CSV export; it ignores the screen's sort and page. */
  async listAll(account: AccountPrincipal, filters: ProjectExportQuery) {
    const projects = await this.prisma.project.findMany({
      where: filterWhere(account, filters),
      orderBy: [{ createdAtUtc: 'desc' }, { id: 'asc' }],
    });
    return projects.map(toProjectResponse);
  }

  async get(account: AccountPrincipal, id: string) {
    const project = await this.prisma.project.findFirst({ where: { id, organisationId: account.organisationId, deletedAtUtc: null } });
    if (!project) throw this.notFound();
    return toProjectResponse(project);
  }

  async create(account: AccountPrincipal, input: ProjectInput) {
    const project = await this.prisma.project.create({
      data: {
        organisationId: account.organisationId,
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
      where: { id, organisationId: account.organisationId, deletedAtUtc: null },
      data: { name: input.name, status: input.status, modifiedByAccountId: account.id },
    });
    if (result.count === 0) throw this.notFound();
    return this.get(account, id);
  }

  async delete(account: AccountPrincipal, id: string): Promise<void> {
    const result = await this.prisma.project.updateMany({
      where: { id, organisationId: account.organisationId, deletedAtUtc: null },
      data: { deletedAtUtc: new Date(), deletedByAccountId: account.id, modifiedByAccountId: account.id },
    });
    if (result.count === 0) throw this.notFound();
  }

  private notFound(): NotFoundException {
    return new NotFoundException({ code: 'PROJECT_NOT_FOUND', message: 'The project was not found.', details: null });
  }
}
