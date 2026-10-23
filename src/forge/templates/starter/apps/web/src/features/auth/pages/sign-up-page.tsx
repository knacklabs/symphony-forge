import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';
import { signUpSchema, type AuthCredentials } from '@shared/index';
import { AuthPageFrame } from '@/components/auth-page-frame';
import { Button } from '@/components/ui/button';
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import { applyApiFieldErrors } from '@/lib/form-errors';
import { useSignUp } from '@/features/auth/hooks/auth-hooks';

export function SignUpPage() {
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
