import { z } from 'zod';

export const projectStatusSchema = z.enum(['active', 'archived']);

export const projectSchema = z.object({
  name: z.string().trim().min(1).max(120).meta({ description: 'The project name.', example: 'Migration plan' }),
  status: projectStatusSchema.meta({ description: 'The project status.', example: 'active' }),
}).strict();

export const projectListQuerySchema = z.object({
  search: z.string().trim().max(200).optional()
    .meta({ description: 'Text to find in the project name, up to 200 characters.', example: 'migration' }),
  status: projectStatusSchema.optional()
    .meta({ description: 'Show only projects with this status.', example: 'active' }),
  limit: z.coerce.number().int().min(1).max(100).default(20)
    .meta({ description: 'The number of projects per page, up to 100.', example: 20 }),
  sortBy: z.enum(['name', 'status', 'createdAtUtc', 'updatedAtUtc']).default('updatedAtUtc')
    .meta({ description: 'The project field used to sort the list.', example: 'updatedAtUtc' }),
  sortOrder: z.enum(['asc', 'desc']).default('desc')
    .meta({ description: 'The sort direction.', example: 'desc' }),
  after: z.string().regex(/^[\w-]{1,512}$/).optional()
    .meta({ description: 'The nextCursor of the page before, to read the next page.', example: 'WyJuYW1lIiwiQSJd' }),
  before: z.string().regex(/^[\w-]{1,512}$/).optional()
    .meta({ description: 'The previousCursor of the page after, to read the previous page.', example: 'WyJuYW1lIiwiQSJd' }),
}).strict().refine((query) => !(query.after && query.before), { path: ['before'], message: 'Use after or before, not both.' });

export type ProjectStatus = z.infer<typeof projectStatusSchema>;

export type ProjectInput = z.infer<typeof projectSchema>;

export type ProjectListQuery = z.infer<typeof projectListQuerySchema>;

export type Project = ProjectInput & {
  id: string;
  createdAtUtc: string;
  updatedAtUtc: string;
  createdByAccountId: string;
  modifiedByAccountId: string;
};
