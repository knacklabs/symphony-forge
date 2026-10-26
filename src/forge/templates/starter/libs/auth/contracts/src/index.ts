import { z } from 'zod';
import type { Role } from '@app/organisations-contracts';

export const signUpSchema = z.object({
  email: z.string().trim().toLowerCase().email().max(254)
    .meta({ description: 'The account email address.', example: 'ada@example.com' }),
  password: z.string().min(12).max(128)
    .meta({ description: 'The account password.', example: 'correct-horse-battery-staple' }),
}).strict();

export const signInSchema = signUpSchema;

export const authOptionsSchema = z.object({
  signUpOpen: z.boolean().meta({ description: 'Whether anyone can create an account.', example: true }),
}).strict();

export type AuthOptions = z.infer<typeof authOptionsSchema>;

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

export type AuthCredentials = z.infer<typeof signInSchema>;

export type ForgotPasswordInput = z.infer<typeof forgotPasswordSchema>;

export type ResetPasswordInput = z.infer<typeof resetPasswordSchema>;

export type Account = { id: string; email: string; role: Role };

export const inviteSchema = forgotPasswordSchema;

export const acceptInviteSchema = signUpSchema.extend({
  token: resetPasswordSchema.shape.token.meta({ description: 'The single-use token from the invite link.', example: 'abcdefghijklmnopqrstuvwxyz0123456789ABCDEFG' }),
}).strict();

export type InviteInput = z.infer<typeof inviteSchema>;

export type AcceptInviteInput = z.infer<typeof acceptInviteSchema>;
