import { z } from 'zod';

export { formatDate, formatDateTime, formatMoney, formatNumber, formatTime } from './format';

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

export const signUpSchema = z.object({
  email: z.string().trim().toLowerCase().email().max(254)
    .meta({ description: 'The account email address.', example: 'ada@example.com' }),
  password: z.string().min(12).max(128)
    .meta({ description: 'The account password.', example: 'correct-horse-battery-staple' }),
}).strict();
export const signInSchema = signUpSchema;
export const forgotPasswordSchema = z.object({
  email: z.string().trim().toLowerCase().email().max(254)
    .meta({ description: 'The email address for the account.', example: 'ada@example.com' }),
}).strict();
export const resetPasswordSchema = z.object({
  token: z.string().min(32).max(256)
    .meta({ description: 'The single-use token from the reset link.', example: 'a-43-character-token-value' }),
  password: z.string().min(12).max(128)
    .meta({ description: 'The new account password.', example: 'new-correct-horse-battery-staple' }),
}).strict();

export const errorReportSchema = z.object({
  name: z.string().max(200).meta({ description: 'The class name of the error.', example: 'TypeError' }),
  path: z.string().max(2000).meta({ description: 'The page path where the error happened, without its query.', example: '/projects' }),
}).strict();

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
export type AuthCredentials = z.infer<typeof signInSchema>;
export type ForgotPasswordInput = z.infer<typeof forgotPasswordSchema>;
export type ResetPasswordInput = z.infer<typeof resetPasswordSchema>;
export type ErrorReportInput = z.infer<typeof errorReportSchema>;
export type Account = { id: string; email: string; role: 'admin' | 'member' };

export const memberListQuerySchema = z.object({
  page: z.coerce.number().int().min(1).default(1)
    .meta({ description: 'The one-based page number.', example: 1 }),
  limit: z.coerce.number().int().min(1).max(100).default(20)
    .meta({ description: 'The number of members per page, up to 100.', example: 20 }),
}).strict();
export type MemberListQuery = z.infer<typeof memberListQuerySchema>;
export type Member = { id: string; accountId: string; email: string; role: Account['role']; createdAtUtc: string };

export const inviteSchema = forgotPasswordSchema;
export const acceptInviteSchema = signUpSchema.extend({
  token: resetPasswordSchema.shape.token.meta({ description: 'The single-use token from the invite link.', example: 'abcdefghijklmnopqrstuvwxyz0123456789ABCDEFG' }),
}).strict();
export const changeRoleSchema = z.object({
  role: z.enum(['admin', 'member']).meta({ description: 'The member’s new role.', example: 'member' }),
}).strict();
export type InviteInput = z.infer<typeof inviteSchema>;
export type AcceptInviteInput = z.infer<typeof acceptInviteSchema>;
export type ChangeRoleInput = z.infer<typeof changeRoleSchema>;
