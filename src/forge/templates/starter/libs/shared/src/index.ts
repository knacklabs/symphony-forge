import { z } from 'zod';

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

export type ProjectStatus = z.infer<typeof projectStatusSchema>;
export type ProjectInput = z.infer<typeof projectSchema>;
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
export type Account = { id: string; email: string };
