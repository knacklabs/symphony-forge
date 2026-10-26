import { BadRequestException, Inject, Injectable, NotFoundException } from '@nestjs/common';
import type { Prisma, Project } from '@prisma/client';
import { PrismaService } from '@app/core-server';
import type { AccountPrincipal } from '@app/core-server';
import { HISTORY_API, type HistoryApi } from '@app/history-contracts';
import { projectStatusSchema, type ProjectExportQuery, type ProjectInput, type ProjectListQuery } from '@app/projects-contracts';

/** Every read loads the emails of the accounts that created and last changed the project. */
const WITH_EMAILS = { createdByAccount: { select: { email: true } }, modifiedByAccount: { select: { email: true } } } as const;
type ProjectWithEmails = Prisma.ProjectGetPayload<{ include: typeof WITH_EMAILS }>;

/** The labels the change summaries use, in the order the form shows the fields. */
const FIELD_LABELS: Record<keyof ProjectInput, string> = { name: 'Name', status: 'Status' };

/** One "<Label> changed from <old> to <new>" per changed field, with values as the CSV shows them; empty when nothing changed. */
function changeSummary(before: Project, input: ProjectInput): string {
  return (Object.keys(FIELD_LABELS) as (keyof ProjectInput)[])
    .filter((field) => before[field] !== input[field])
    .map((field) => `${FIELD_LABELS[field]} changed from ${before[field]} to ${input[field]}`)
    .join('; ');
}

function toProjectResponse(project: ProjectWithEmails) {
  return {
    id: project.id,
    name: project.name,
    status: projectStatusSchema.parse(project.status),
    createdAtUtc: project.createdAtUtc.toISOString(),
    updatedAtUtc: project.updatedAtUtc.toISOString(),
    createdByAccountId: project.createdByAccountId,
    modifiedByAccountId: project.modifiedByAccountId,
    createdByEmail: project.createdByAccount.email,
    modifiedByEmail: project.modifiedByAccount.email,
  };
}

/** The changes route returns this many entries, newest first. */
const RECENT_CHANGES = 5;

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

/** The organisation's project with this id, unless it is deleted. */
function liveProject(account: AccountPrincipal, id: string): Prisma.ProjectWhereInput {
  return { id, organisationId: account.organisationId, deletedAtUtc: null };
}

/** The rows after the cursor row in this order: a later sort value, or the same value and a later id. */
function afterCursor(sortBy: SortBy, order: 'asc' | 'desc', cursor: { value: string | Date; id: string }): Prisma.ProjectWhereInput {
  const beyond = order === 'asc' ? 'gt' : 'lt';
  return { OR: [{ [sortBy]: { [beyond]: cursor.value } }, { [sortBy]: cursor.value, id: { [beyond]: cursor.id } }] };
}

@Injectable()
export class ProjectsService {
  constructor(
    private readonly prisma: PrismaService,
    @Inject(HISTORY_API) private readonly history: HistoryApi,
  ) {}

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
        include: WITH_EMAILS,
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
      include: WITH_EMAILS,
    });
    return projects.map(toProjectResponse);
  }

  async get(account: AccountPrincipal, id: string) {
    const project = await this.prisma.project.findFirst({ where: liveProject(account, id), include: WITH_EMAILS });
    if (!project) throw this.notFound();
    return toProjectResponse(project);
  }

  /** The project's newest changes; a deleted project or one of another organisation is not found. */
  async changes(account: AccountPrincipal, id: string) {
    const project = await this.prisma.project.findFirst({ where: liveProject(account, id), select: { id: true } });
    if (!project) throw this.notFound();
    return this.history.listForSubject(account, id, RECENT_CHANGES);
  }

  // Each change and its Change history row commit together: a failed history write rolls back the change.
  async create(account: AccountPrincipal, input: ProjectInput) {
    return this.prisma.$transaction(async (tx) => {
      const project = await tx.project.create({
        data: {
          organisationId: account.organisationId,
          name: input.name,
          status: input.status,
          createdByAccountId: account.id,
          modifiedByAccountId: account.id,
        },
        include: WITH_EMAILS,
      });
      await this.history.record(account, 'project.created', 'Created the project', { id: project.id, name: project.name }, tx);
      return toProjectResponse(project);
    });
  }

  async update(account: AccountPrincipal, id: string, input: ProjectInput) {
    return this.prisma.$transaction(async (tx) => {
      const before = await tx.project.findFirst({ where: liveProject(account, id) });
      if (!before) throw this.notFound();
      const project = await tx.project.update({
        where: { id },
        data: { name: input.name, status: input.status, modifiedByAccountId: account.id },
        include: WITH_EMAILS,
      });
      // A replace that changes no field adds no history row.
      const summary = changeSummary(before, input);
      if (summary) await this.history.record(account, 'project.changed', summary, { id, name: project.name }, tx);
      return toProjectResponse(project);
    });
  }

  async delete(account: AccountPrincipal, id: string): Promise<void> {
    await this.prisma.$transaction(async (tx) => {
      const project = await tx.project.findFirst({ where: liveProject(account, id), select: { name: true } });
      if (!project) throw this.notFound();
      await tx.project.update({
        where: { id },
        data: { deletedAtUtc: new Date(), deletedByAccountId: account.id, modifiedByAccountId: account.id },
      });
      await this.history.record(account, 'project.deleted', 'Deleted the project', { id, name: project.name }, tx);
    });
  }

  private notFound(): NotFoundException {
    return new NotFoundException({ code: 'PROJECT_NOT_FOUND', message: 'The project was not found.', details: null });
  }
}
