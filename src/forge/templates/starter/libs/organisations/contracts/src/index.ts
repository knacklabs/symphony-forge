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

export type Member = { id: string; accountId: string; email: string; role: Role; createdAtUtc: string };

export const changeRoleSchema = z.object({
  role: roleSchema.meta({ description: 'The member’s new role.', example: 'member' }),
}).strict();

export type ChangeRoleInput = z.infer<typeof changeRoleSchema>;
export { ORGANISATIONS_API } from './service';
export type {
  OrganisationAccount,
  OrganisationInvite,
  OrganisationMembership,
  OrganisationPrincipal,
  OrganisationsApi,
} from './service';
