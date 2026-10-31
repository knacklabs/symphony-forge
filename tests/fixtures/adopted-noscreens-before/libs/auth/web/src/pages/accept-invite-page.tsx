import { useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';
import { acceptInviteSchema, signUpSchema, type AuthCredentials } from '@app/auth-contracts';
import { AuthPageFrame } from '@app/shared-ui/components/auth-page-frame';
import { Button } from '@app/shared-ui/components/ui/button';
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@app/shared-ui/components/ui/form';
import { Input } from '@app/shared-ui/components/ui/input';
import { ApiError } from '@app/core-web';
import { applyApiFieldErrors } from '@app/core-web';
import { useAcceptInvite } from '../hooks/auth-hooks';

export function AcceptInvitePage() {
  const [params] = useSearchParams();
  const token = params.get('token') ?? '';
  const acceptInvite = useAcceptInvite();
  const navigate = useNavigate();
  const [error, setError] = useState('');
  // The form checks only what the person types; the API checks the token and sends back its own message.
  const form = useForm<AuthCredentials>({
    resolver: zodResolver(signUpSchema),
    defaultValues: { email: '', password: '' },
  });

  async function submit(credentials: AuthCredentials) {
    setError('');
    try {
      await acceptInvite.mutateAsync({ ...credentials, token });
      navigate('/projects');
    } catch (cause) {
      if (!applyApiFieldErrors(cause, form.setError)) {
        setError(cause instanceof ApiError ? cause.message : 'Could not join. Check your connection and try again.');
      }
    }
  }

  // A cut-off token would fail as a field error on a field this form does not show, so say it here.
  const linkProblem = !token
    ? 'This invite link is not complete. Ask an admin for a new one.'
    : !acceptInviteSchema.shape.token.safeParse(token).success && 'This invite link is not valid. Ask an admin for a new one.';
  if (linkProblem) {
    return (
      <AuthPageFrame title="Join your team">
        <p role="alert" className="text-sm text-destructive">{linkProblem}</p>
      </AuthPageFrame>
    );
  }

  return (
    <AuthPageFrame title="Join your team">
      <p className="text-sm text-muted-foreground">Use the email address that got the invite.</p>
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
          <Button type="submit" className="w-full" disabled={acceptInvite.isPending}>{acceptInvite.isPending ? 'Joining…' : 'Join'}</Button>
        </form>
      </Form>
      <p className="text-sm text-muted-foreground">Already have an account? <Link className="underline underline-offset-4" to="/sign-in">Sign in</Link></p>
    </AuthPageFrame>
  );
}
