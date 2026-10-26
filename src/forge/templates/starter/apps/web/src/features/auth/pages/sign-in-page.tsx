import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';
import { signInSchema, type AuthCredentials } from '@app/auth-contracts';
import { AuthPageFrame } from '@/components/auth-page-frame';
import { Button } from '@/components/ui/button';
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import { applyApiFieldErrors } from '@/lib/form-errors';
import { useSignIn } from '@/features/auth/hooks/auth-hooks';

export function SignInPage() {
  const signIn = useSignIn();
  const navigate = useNavigate();
  const [error, setError] = useState('');
  const form = useForm<AuthCredentials>({
    resolver: zodResolver(signInSchema),
    defaultValues: { email: '', password: '' },
  });

  async function submit(credentials: AuthCredentials) {
    setError('');
    try {
      await signIn.mutateAsync(credentials);
      navigate('/projects');
    } catch (cause) {
      const hasFieldError = applyApiFieldErrors(cause, form.setError);
      if (!hasFieldError) setError('Could not sign in. Check your email and password, then try again.');
    }
  }

  return (
    <AuthPageFrame title="Sign in">
      <Form {...form}>
        <form className="space-y-4" onSubmit={form.handleSubmit(submit)}>
          <FormField control={form.control} name="email" render={({ field }) => (
            <FormItem>
              <FormLabel>Email</FormLabel>
              <FormControl><Input type="email" autoComplete="email" {...field} /></FormControl>
              <FormMessage />
            </FormItem>
          )} />
          <FormField control={form.control} name="password" render={({ field }) => (
            <FormItem>
              <FormLabel>Password</FormLabel>
              <FormControl><Input type="password" autoComplete="current-password" {...field} /></FormControl>
              <FormMessage />
            </FormItem>
          )} />
          {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
          <div className="flex flex-col gap-3">
            <Button type="submit" disabled={signIn.isPending}>{signIn.isPending ? 'Signing in…' : 'Sign in'}</Button>
            <Link className="text-sm underline underline-offset-4" to="/forgot-password">Forgot password?</Link>
          </div>
        </form>
      </Form>
      <p className="text-sm text-muted-foreground">New here? <Link className="underline underline-offset-4" to="/sign-up">Create an account</Link></p>
    </AuthPageFrame>
  );
}
