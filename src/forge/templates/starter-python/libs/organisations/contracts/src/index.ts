import { z } from 'zod';
import type { components } from '@app/shared-api-types';

export const memberListQuerySchema = z.object({
  page: z.coerce.number().int().min(1).default(1)
    .meta({ description: 'The one-based page number.', example: 1 }),
  limit: z.coerce.number().int().min(1).max(100).default(20)
    .meta({ description: 'The number of members per page, up to 100.', example: 20 }),
}).strict();

export type MemberListQuery = z.infer<typeof memberListQuerySchema>;

export type Member = components['schemas']['Member'];

export const changeRoleSchema = z.object({
  role: z.enum(['admin', 'member']).meta({ description: 'The member’s new role.', example: 'member' }),
}).strict();

export type ChangeRoleInput = z.infer<typeof changeRoleSchema>;
