import { useState } from 'react';
import { Link } from 'react-router-dom';
import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';
import { forgotPasswordSchema } from '@shared/index';
import { AuthPageFrame } from '@/components/auth-page-frame';
import { Button } from '@/components/ui/button';
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import { applyApiFieldErrors } from '@/lib/form-errors';
import { useForgotPassword } from '@/features/auth/hooks/auth-hooks';

type ForgotPasswordValues = { email: string };

export function ForgotPasswordPage() {
  const forgotPassword = useForgotPassword();
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const form = useForm<ForgotPasswordValues>({
    resolver: zodResolver(forgotPasswordSchema),
    defaultValues: { email: '' },
  });

  async function submit({ email }: ForgotPasswordValues) {
    setMessage('');
    setError('');
    try {
      const result = await forgotPassword.mutateAsync(email);
      setMessage(result.message);
    } catch (cause) {
      if (!applyApiFieldErrors(cause, form.setError)) setError('Could not send a reset request. Check your connection and try again.');
    }
  }

  return (
    <AuthPageFrame title="Forgot password">
      <p className="text-sm text-muted-foreground">Enter your email. We will tell you how to reset your password if an account exists.</p>
      <Form {...form}>
        <form className="space-y-4" onSubmit={form.handleSubmit(submit)}>
          <FormField control={form.control} name="email" render={({ field }) => (
            <FormItem>
              <FormLabel>Email</FormLabel>
              <FormControl><Input type="email" autoComplete="email" {...field} /></FormControl>
              <FormMessage />
            </FormItem>
          )} />
          {message && <p role="status" className="text-sm">{message}</p>}
          {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
          <Button type="submit" className="w-full" disabled={forgotPassword.isPending}>{forgotPassword.isPending ? 'Sending…' : 'Send reset link'}</Button>
        </form>
      </Form>
      <Link className="text-sm underline underline-offset-4" to="/sign-in">Back to sign in</Link>
    </AuthPageFrame>
  );
}
