import { BadRequestException, ForbiddenException, Inject, Injectable, NotFoundException } from '@nestjs/common';
import type { Prisma, Project as ProjectRecord } from '@prisma/client';
import { PrismaService } from '@app/core-server';
import { hasPermission, type AccountPrincipal } from '@app/core-server';
import { AUTH_API, type AuthApi } from '@app/auth-contracts';
import { HISTORY_API, type HistoryApi } from '@app/history-contracts';
import { PROJECT_PERMISSIONS } from './projects.permissions';
import { projectStatusSchema, type Project, type ProjectExportQuery, type ProjectInput, type ProjectListQuery, type ProjectsApi } from '@app/projects-contracts';
// forge:feature:link-imports:start
// forge:feature:link-imports:end

/** The labels the change summaries use, in the order the form shows the fields. */
// forge:feature:field-labels:start
const FIELD_LABELS: Record<keyof ProjectInput, string> = { name: 'Name', status: 'Status' };
// forge:feature:field-labels:end

// forge:feature:change-summary:start
/** One "<Label> changed from <old> to <new>" per changed field, with values as the CSV shows them; empty when nothing changed. */
function changeSummary(before: ProjectRecord, input: ProjectInput): string {
  return (Object.keys(FIELD_LABELS) as (keyof ProjectInput)[])
    .filter((field) => before[field] !== input[field])
    .map((field) => `${FIELD_LABELS[field]} changed from ${before[field]} to ${input[field]}`)
    .join('; ');
}
// forge:feature:change-summary:end

/** The project's foreign keys keep every account it names, so a missing email is a crash. */
function emailOf(emails: Map<string, string>, accountId: string): string {
  const email = emails.get(accountId);
  if (email === undefined) throw new Error('A project names an account that does not exist.');
  return email;
}

/** The project with the emails of the accounts that created, last changed and deleted it, which auth gives. */
function toProjectResponse(project: ProjectRecord, emails: Map<string, string>): Project {
  return {
    id: project.id,
    // forge:feature:response-fields:start
    name: project.name,
    status: projectStatusSchema.parse(project.status),
    // forge:feature:response-fields:end
    createdAtUtc: project.createdAtUtc.toISOString(),
    updatedAtUtc: project.updatedAtUtc.toISOString(),
    createdByAccountId: project.createdByAccountId,
    modifiedByAccountId: project.modifiedByAccountId,
    createdByEmail: emailOf(emails, project.createdByAccountId),
    modifiedByEmail: emailOf(emails, project.modifiedByAccountId),
    deletedAtUtc: project.deletedAtUtc?.toISOString() ?? null,
    deletedByEmail: project.deletedByAccountId ? emailOf(emails, project.deletedByAccountId) : null,
  };
}

/** The changes route returns this many entries, newest first. */
const RECENT_CHANGES = 5;

/** The list counts up to this many matching projects; above it the screen says "More than 10,000". */
const TOTAL_CAP = 10_000;
type SortBy = ProjectListQuery['sortBy'];
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** A cursor is the sort column, its value and the id of a page's first or last row, as base64url JSON. */
function encodeCursor(sortBy: SortBy, project: ProjectRecord): string {
  const value = project[sortBy];
  return Buffer.from(JSON.stringify([sortBy, value instanceof Date ? value.toISOString() : value, project.id])).toString('base64url');
}

// forge:feature:cursor-decode:start
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
// forge:feature:cursor-decode:end

/** Only a caller who may restore projects sees deleted ones. */
function seesDeleted(account: AccountPrincipal): boolean {
  return hasPermission(account, PROJECT_PERMISSIONS.restore);
}

/** The organisation's projects that match the list's search and status filter; deleted ones too when asked for and allowed. */
function filterWhere(account: AccountPrincipal, filters: ProjectExportQuery): Prisma.ProjectWhereInput {
  return {
    organisationId: account.organisationId,
    ...(filters.deleted === 'yes' && seesDeleted(account) ? {} : { deletedAtUtc: null }),
    // forge:feature:field-filters:start
    // Prisma passes % and _ to ILIKE as wildcards, so escape them to search for the text itself.
    ...(filters.search ? { name: { contains: filters.search.replace(/[\\%_]/g, '\\$&'), mode: 'insensitive' as const } } : {}),
    ...(filters.status ? { status: filters.status } : {}),
    // forge:feature:field-filters:end
  };
}

/** The organisation's project with this id, unless it is deleted. */
function liveProject(account: AccountPrincipal, id: string): Prisma.ProjectWhereInput {
  return { id, organisationId: account.organisationId, deletedAtUtc: null };
}

/** The project the caller may read: a deleted one only for a caller who may restore it. */
function readableProject(account: AccountPrincipal, id: string): Prisma.ProjectWhereInput {
  return seesDeleted(account) ? { id, organisationId: account.organisationId } : liveProject(account, id);
}

/** The rows after the cursor row in this order: a later sort value, or the same value and a later id. */
// forge:feature:cursor-after:start
function afterCursor(sortBy: SortBy, order: 'asc' | 'desc', cursor: { value: string | Date; id: string }): Prisma.ProjectWhereInput {
  const beyond = order === 'asc' ? 'gt' : 'lt';
  return { OR: [{ [sortBy]: { [beyond]: cursor.value } }, { [sortBy]: cursor.value, id: { [beyond]: cursor.id } }] };
}
// forge:feature:cursor-after:end

@Injectable()
export class ProjectsService implements ProjectsApi {
  constructor(
    private readonly prisma: PrismaService,
    @Inject(HISTORY_API) private readonly history: HistoryApi,
    @Inject(AUTH_API) private readonly auth: AuthApi,
    // forge:feature:link-injections:start
    // forge:feature:link-injections:end
  ) {}

  /** Auth owns the accounts, so their emails come through its public API, one call per page. */
  private async responses(projects: ProjectRecord[]) {
    const emails = await this.auth.emailsFor(projects.flatMap((project) => [
      project.createdByAccountId, project.modifiedByAccountId, ...(project.deletedByAccountId ? [project.deletedByAccountId] : []),
    ]));
    return projects.map((project) => toProjectResponse(project, emails));
  }

  private async response(project: ProjectRecord): Promise<Project> {
    const [response] = await this.responses([project]);
    return response;
  }

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
      items: await this.responses(projects),
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
    return this.responses(projects);
  }

  async get(account: AccountPrincipal, id: string): Promise<Project> {
    if (!hasPermission(account, PROJECT_PERMISSIONS.view)) {
      throw new ForbiddenException({
        code: 'PERMISSION_DENIED',
        message: 'You do not have permission to do this.',
        details: null,
      });
    }
    const project = await this.prisma.project.findFirst({ where: readableProject(account, id) });
    if (!project) throw this.notFound();
    return this.response(project);
  }

  /** The project's newest changes; a project the caller may not read is not found. */
  async changes(account: AccountPrincipal, id: string) {
    const project = await this.prisma.project.findFirst({ where: readableProject(account, id), select: { id: true } });
    if (!project) throw this.notFound();
    return this.history.listForSubject(account, id, RECENT_CHANGES);
  }

  // Each change and its Change history row commit together: a failed history write rolls back the change.
  // forge:feature:link-validation:start
  // forge:feature:link-validation:end

  async create(account: AccountPrincipal, input: ProjectInput,
    // forge:feature:mcp:start
    options?: { afterCreate: (tx: Prisma.TransactionClient, id: string) => Promise<void> },
    // forge:feature:mcp:end
  ) {
    // forge:feature:link-validation-create:start
    // forge:feature:link-validation-create:end
    return this.prisma.$transaction(async (tx) => {
      const project = await tx.project.create({
        data: {
          organisationId: account.organisationId,
          // forge:feature:create-fields:start
          name: input.name,
          status: input.status,
          // forge:feature:create-fields:end
          createdByAccountId: account.id,
          modifiedByAccountId: account.id,
        },
      });
      await this.history.record(account, 'project.created', 'Created the project', { id: project.id,
        // forge:feature:history-created-name:start
        name: project.name,
        // forge:feature:history-created-name:end
      }, tx);
      // forge:feature:mcp:start
      await options?.afterCreate(tx, project.id);
      // forge:feature:mcp:end
      return this.response(project);
    });
  }

  async update(account: AccountPrincipal, id: string, input: ProjectInput) {
    // forge:feature:link-validation-update:start
    // forge:feature:link-validation-update:end
    return this.prisma.$transaction(async (tx) => {
      const before = await tx.project.findFirst({ where: liveProject(account, id) });
      if (!before) throw this.notFound();
      // forge:feature:mcp:start
      if (!changeSummary(before, input)) return this.response(before);
      // forge:feature:mcp:end
      const project = await tx.project.update({
        where: { id },
        data: {
          // forge:feature:update-fields:start
          name: input.name,
          status: input.status,
          // forge:feature:update-fields:end
          modifiedByAccountId: account.id,
        },
      });
      // A replace that changes no field adds no history row.
      const summary = changeSummary(before, input);
      if (summary) await this.history.record(account, 'project.changed', summary, { id,
        // forge:feature:history-changed-name:start
        name: project.name,
        // forge:feature:history-changed-name:end
      }, tx);
      return this.response(project);
    });
  }

  async delete(account: AccountPrincipal, id: string): Promise<void> {
    await this.prisma.$transaction(async (tx) => {
      const project = await tx.project.findFirst({ where: liveProject(account, id), select: {
        // forge:feature:delete-name:start
        name: true,
        // forge:feature:delete-name:end
      } });
      if (!project) throw this.notFound();
      await tx.project.update({
        where: { id },
        data: { deletedAtUtc: new Date(), deletedByAccountId: account.id, modifiedByAccountId: account.id },
      });
      await this.history.record(account, 'project.deleted', 'Deleted the project', { id,
        // forge:feature:history-deleted-name:start
        name: project.name,
        // forge:feature:history-deleted-name:end
      }, tx);
    });
  }

  async restore(account: AccountPrincipal, id: string) {
    return this.prisma.$transaction(async (tx) => {
      const deleted = await tx.project.findFirst({
        where: { id, organisationId: account.organisationId, deletedAtUtc: { not: null } },
        select: { id: true },
      });
      if (!deleted) throw this.notFound();
      const project = await tx.project.update({
        where: { id },
        data: { deletedAtUtc: null, deletedByAccountId: null, modifiedByAccountId: account.id },
      });
      await this.history.record(account, 'project.restored', 'Restored the project', { id,
        // forge:feature:history-restored-name:start
        name: project.name,
        // forge:feature:history-restored-name:end
      }, tx);
      return this.response(project);
    });
  }

  private notFound(): NotFoundException {
    return new NotFoundException({ code: 'PROJECT_NOT_FOUND', message: 'The project was not found.', details: null });
  }
}
