import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';
import { signUpSchema, type AuthCredentials } from '@app/auth-contracts';
import { AuthPageFrame } from '@app/shared-ui/components/auth-page-frame';
import { Button } from '@app/shared-ui/components/ui/button';
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@app/shared-ui/components/ui/form';
import { Input } from '@app/shared-ui/components/ui/input';
import { applyApiFieldErrors } from '@app/core-web';
import { useAuthOptions, useSignUp } from '../hooks/auth-hooks';

export function SignUpPage() {
  const options = useAuthOptions();
  if (options.isPending) {
    return <main id="main-content" className="flex min-h-screen items-center justify-center p-6"><p role="status">Loading…</p></main>;
  }
  // ponytail: if the options fail to load, the form shows and the API still refuses a closed sign-up.
  if (options.data?.signUpOpen === false) {
    return (
      <AuthPageFrame title="Sign-up is closed">
        <p className="text-sm text-muted-foreground">This app is for one company. Ask an admin of your team for an invite.</p>
        <Link className="inline-block text-sm underline underline-offset-4" to="/sign-in">Sign in</Link>
      </AuthPageFrame>
    );
  }
  return <SignUpForm />;
}

function SignUpForm() {
  const signUp = useSignUp();
  const navigate = useNavigate();
  const [error, setError] = useState('');
  const form = useForm<AuthCredentials>({
    resolver: zodResolver(signUpSchema),
    defaultValues: { email: '', password: '' },
  });

  async function submit(credentials: AuthCredentials) {
    setError('');
    try {
      await signUp.mutateAsync(credentials);
      navigate('/projects');
    } catch (cause) {
      const hasFieldError = applyApiFieldErrors(cause, form.setError);
      if (!hasFieldError) setError('Could not create your account. Check the details and try again.');
    }
  }

  return (
    <AuthPageFrame title="Create account">
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
              <FormControl><Input type="password" autoComplete="new-password" {...field} /></FormControl>
              <FormMessage />
            </FormItem>
          )} />
          {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
          <Button type="submit" className="w-full" disabled={signUp.isPending}>{signUp.isPending ? 'Creating account…' : 'Create account'}</Button>
        </form>
      </Form>
      <p className="text-sm text-muted-foreground">Already have an account? <Link className="underline underline-offset-4" to="/sign-in">Sign in</Link></p>
    </AuthPageFrame>
  );
}
