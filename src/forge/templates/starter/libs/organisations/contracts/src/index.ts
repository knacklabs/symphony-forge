import { z } from 'zod';

export const roleSchema = z.enum(['admin', 'member']);
export type Role = z.infer<typeof roleSchema>;

export const memberListQuerySchema = z.object({
  page: z.coerce.number().int().min(1).default(1)
    .meta({ description: 'The one-based page number.', example: 1 }),
  limit: z.coerce.number().int().min(1).max(100).default(20)
    .meta({ description: 'The number of members per page, up to 100.', example: 20 }),
}).strict();

export type MemberListQuery = z.infer<typeof memberListQuerySchema>;

/** `isAgent` marks an agent account; `hasKey` says whether it has a working key. */
export type Member = { id: string; accountId: string; email: string; role: Role; isAgent: boolean; hasKey: boolean; createdAtUtc: string };

export const changeRoleSchema = z.object({
  role: roleSchema.meta({ description: 'The member’s new role.', example: 'member' }),
}).strict();

export type ChangeRoleInput = z.infer<typeof changeRoleSchema>;

export const addAgentSchema = z.object({
  name: z.string().min(1, 'Enter a name.')
    .regex(/^[a-z][a-z0-9-]{1,39}$/, 'Use 2 to 40 lower-case letters, numbers or hyphens, starting with a letter.')
    .meta({ description: 'The start of the agent account’s email: lower-case letters, numbers and hyphens.', example: 'gantry' }),
  role: roleSchema.meta({ description: 'The agent account’s role.', example: 'member' }),
}).strict();

export type AddAgentInput = z.infer<typeof addAgentSchema>;

/** The agent's new key, which the API returns this one time only. */
export type AgentKey = { key: string };

export const agentToolsChangeSchema = z.object({
  deleteAndRestore: z.boolean().meta({ description: 'Whether agents can use the feature’s delete and restore tools.', example: true }),
}).strict();

export type AgentToolsChange = z.infer<typeof agentToolsChangeSchema>;

/** A feature's plural in kebab case, such as `projects` or `work-orders`. */
export const agentToolsFeatureSchema = z.string().max(100).regex(/^[a-z][a-z0-9-]*$/, 'Use the feature’s plural in lower-case letters, numbers and hyphens, such as projects.');

/** The features whose delete and restore tools agents can use. */
export type AgentTools = { deleteAndRestore: string[] };
export { ORGANISATIONS_API } from './service';
export type {
  OrganisationAccount,
  OrganisationInvite,
  OrganisationMembership,
  OrganisationPrincipal,
  OrganisationsApi,
} from './service';
