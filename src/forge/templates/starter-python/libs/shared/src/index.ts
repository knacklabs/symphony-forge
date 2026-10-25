import { z } from 'zod';
import type { components } from './api-types';

export { formatDate, formatDateTime, formatMoney, formatNumber, formatTime } from './format';

export const projectStatusSchema = z.enum(['active', 'archived']);
export const projectSchema = z.object({
  name: z.string().trim().min(1).max(120),
  status: projectStatusSchema,
}).strict();

export const signUpSchema = z.object({
  email: z.string().trim().toLowerCase().email().max(254),
  password: z.string().min(12).max(128),
}).strict();
export const signInSchema = signUpSchema;
export const forgotPasswordSchema = z.object({ email: z.string().trim().toLowerCase().email().max(254) }).strict();
export const resetPasswordSchema = z.object({ token: z.string().min(32).max(256), password: z.string().min(12).max(128) }).strict();

export const errorReportSchema = z.object({ name: z.string().max(200), path: z.string().max(2000) }).strict();

export type ProjectStatus = components['schemas']['ProjectStatus'];
export type ProjectInput = z.infer<typeof projectSchema>;
export type Project = components['schemas']['Project'];
export type AuthCredentials = z.infer<typeof signInSchema>;
export type ForgotPasswordInput = z.infer<typeof forgotPasswordSchema>;
export type ResetPasswordInput = z.infer<typeof resetPasswordSchema>;
export type ErrorReportInput = z.infer<typeof errorReportSchema>;
export type Account = components['schemas']['Account'];
export const memberListQuerySchema = z.object({
  page: z.coerce.number().int().min(1).default(1),
  limit: z.coerce.number().int().min(1).max(100).default(20),
}).strict();
export type MemberListQuery = z.infer<typeof memberListQuerySchema>;
export type Member = components['schemas']['Member'];
