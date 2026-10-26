import { z } from 'zod';

// forge:feature:status-schema:start
export const projectStatusSchema = z.enum(['active', 'archived']);
// forge:feature:status-schema:end

export const projectSchema = z.object({
  // forge:feature:schema-fields:start
  name: z.string().trim().min(1).max(120).meta({ description: 'The project name.', example: 'Migration plan' }),
  status: projectStatusSchema.meta({ description: 'The project status.', example: 'active' }),
  // forge:feature:schema-fields:end
}).strict();

// forge:feature:filters:start
const projectFilters = {
  search: z.string().trim().max(200).optional()
    .meta({ description: 'Text to find in the project name, up to 200 characters.', example: 'migration' }),
  status: projectStatusSchema.optional()
    .meta({ description: 'Show only projects with this status.', example: 'active' }),
  deleted: z.enum(['yes']).optional()
    .meta({ description: 'Show deleted projects too; only a caller with the restore permission gets them.', example: 'yes' }),
};
// forge:feature:filters:end

/** The export takes the list's search and filters, so it downloads what the list shows. */
export const projectExportQuerySchema = z.object(projectFilters).strict();

// A cursor holds a whole project name, which can be 120 characters of any script.
const cursorSchema = z.string().regex(/^[\w-]{1,2048}$/);

export const projectListQuerySchema = z.object({
  ...projectFilters,
  limit: z.coerce.number().int().min(1).max(100).default(20)
    .meta({ description: 'The number of projects per page, up to 100.', example: 20 }),
  sortBy: z.enum([
    // forge:feature:sort-fields:start
    'name', 'status',
    // forge:feature:sort-fields:end
    'createdAtUtc', 'updatedAtUtc',
  ]).default('updatedAtUtc')
    .meta({ description: 'The project field used to sort the list.', example: 'updatedAtUtc' }),
  sortOrder: z.enum(['asc', 'desc']).default('desc')
    .meta({ description: 'The sort direction.', example: 'desc' }),
  after: cursorSchema.optional()
    .meta({ description: 'The nextCursor of the page before, to read the next page.', example: 'WyJuYW1lIiwiQSJd' }),
  before: cursorSchema.optional()
    .meta({ description: 'The previousCursor of the page after, to read the previous page.', example: 'WyJuYW1lIiwiQSJd' }),
}).strict().refine((query) => !(query.after && query.before), { path: ['before'], message: 'Use after or before, not both.' });

// forge:feature:status-type:start
export type ProjectStatus = z.infer<typeof projectStatusSchema>;
// forge:feature:status-type:end

export type ProjectInput = z.infer<typeof projectSchema>;

export type ProjectListQuery = z.infer<typeof projectListQuerySchema>;

export type ProjectExportQuery = z.infer<typeof projectExportQuerySchema>;

export type Project = {
  // forge:feature:response-fields:start
  name: string;
  status: ProjectStatus;
  // forge:feature:response-fields:end
  id: string;
  createdAtUtc: string;
  updatedAtUtc: string;
  createdByAccountId: string;
  modifiedByAccountId: string;
  createdByEmail: string;
  modifiedByEmail: string;
  /** Set only on a deleted project, which only a caller with the restore permission reads. */
  deletedAtUtc: string | null;
  deletedByEmail: string | null;
};

/** One entry in a project's recent changes. */
export type ProjectChange = { id: string; actorEmail: string; summary: string; createdAtUtc: string };

export type ProjectsPrincipal = { id: string; email: string; organisationId: string; role: 'admin' | 'member' };

export const PROJECTS_API = 'ProjectsApi';

/** What other feature modules may ask projects about an item. */
export interface ProjectsApi {
  get(principal: ProjectsPrincipal, id: string): Promise<Project>;
}
