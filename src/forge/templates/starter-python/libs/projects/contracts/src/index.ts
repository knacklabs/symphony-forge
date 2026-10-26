import { z } from 'zod';
import type { components } from '@app/shared-api-types';

export const projectStatusSchema = z.enum(['active', 'archived']);

export const projectSchema = z.object({
  name: z.string().trim().min(1).max(120).meta({ description: 'The project name.', example: 'Migration plan' }),
  status: projectStatusSchema.meta({ description: 'The project status.', example: 'active' }),
}).strict();

export const projectListQuerySchema = z.object({
  page: z.coerce.number().int().min(1).default(1)
    .meta({ description: 'The one-based page number.', example: 1 }),
  limit: z.coerce.number().int().min(1).max(100).default(20)
    .meta({ description: 'The number of projects per page, up to 100.', example: 20 }),
  sortBy: z.enum(['name', 'status', 'createdAtUtc', 'updatedAtUtc']).default('createdAtUtc')
    .meta({ description: 'The project field used to sort the list.', example: 'createdAtUtc' }),
  sortOrder: z.enum(['asc', 'desc']).default('desc')
    .meta({ description: 'The sort direction.', example: 'desc' }),
}).strict();

export type ProjectStatus = components['schemas']['ProjectStatus'];

export type ProjectInput = z.infer<typeof projectSchema>;

export type ProjectListQuery = z.infer<typeof projectListQuerySchema>;

export type Project = components['schemas']['Project'];
