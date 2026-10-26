import { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';
import { resetPasswordSchema } from '@app/auth-contracts';
import { AuthPageFrame } from '@/components/auth-page-frame';
import { Button } from '@/components/ui/button';
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import { applyApiFieldErrors } from '@/lib/form-errors';
import { useResetPassword } from '@/features/auth/hooks/auth-hooks';

type ResetPasswordValues = { token: string; password: string };

export function ResetPasswordPage() {
  const [params] = useSearchParams();
  const token = params.get('token') ?? '';
  const resetPassword = useResetPassword();
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const form = useForm<ResetPasswordValues>({
    resolver: zodResolver(resetPasswordSchema),
    defaultValues: { token, password: '' },
  });

  async function submit(values: ResetPasswordValues) {
    setError('');
    setMessage('');
    try {
      await resetPassword.mutateAsync(values);
      setMessage('Password updated. Sign in with your new password.');
    } catch (cause) {
      if (!applyApiFieldErrors(cause, form.setError)) {
        setError(cause instanceof Error ? cause.message : 'That reset link is invalid or expired. Request a new one.');
      }
    }
  }

  return (
    <AuthPageFrame title="Reset password">
      {(token.length < 32 || token.length > 256) && <p role="alert" className="text-sm text-destructive">That reset link is missing or invalid. Request a new one.</p>}
      <Form {...form}>
        <form className="space-y-4" onSubmit={form.handleSubmit(submit)}>
          <FormField control={form.control} name="password" render={({ field }) => (
            <FormItem>
              <FormLabel>New password</FormLabel>
              <FormControl><Input type="password" autoComplete="new-password" {...field} /></FormControl>
              <FormMessage />
            </FormItem>
          )} />
          {message && <p role="status">{message}</p>}
          {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
          <Button type="submit" className="w-full" disabled={resetPassword.isPending}>{resetPassword.isPending ? 'Updating…' : 'Reset password'}</Button>
        </form>
      </Form>
      <Link className="text-sm underline underline-offset-4" to="/forgot-password">Request a new reset link</Link>
      <Link className="ml-4 text-sm underline underline-offset-4" to="/sign-in">Back to sign in</Link>
    </AuthPageFrame>
  );
}
