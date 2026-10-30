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

export const addAgentSchema = z.object({
  name: z.string().min(1, 'Enter a name.')
    .regex(/^[a-z][a-z0-9-]{1,39}$/, 'Use 2 to 40 lower-case letters, numbers or hyphens, starting with a letter.')
    .meta({ description: 'The start of the agent account’s email: lower-case letters, numbers and hyphens.', example: 'gantry' }),
  role: z.enum(['admin', 'member']).meta({ description: 'The agent account’s role.', example: 'member' }),
}).strict();

export type AddAgentInput = z.infer<typeof addAgentSchema>;

export type AgentKey = components['schemas']['AgentKey'];
