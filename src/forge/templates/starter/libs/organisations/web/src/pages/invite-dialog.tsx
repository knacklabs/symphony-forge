import { useState, type ReactNode } from 'react';
import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';
import { toast } from 'sonner';
import { inviteSchema, type InviteInput } from '@app/auth-contracts';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@app/shared-ui/components/ui/alert-dialog';
import { Button } from '@app/shared-ui/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@app/shared-ui/components/ui/dialog';
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@app/shared-ui/components/ui/form';
import { Input } from '@app/shared-ui/components/ui/input';
import { useInvite } from '../hooks/members-hooks';
import { ApiError } from '@app/core-web';
import { applyApiFieldErrors } from '@app/core-web';

const INVITE_ERRORS: Record<string, string> = {
  EMAIL_ALREADY_REGISTERED: 'That person already has an account.',
  MAIL_NOT_CONFIGURED: 'Email is not set up for this app yet.',
};

// The opener is the Dialog's trigger, so Radix gives it focus back when the dialog closes.
export function InviteDialog({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const invite = useInvite();
  const [error, setError] = useState('');
  const form = useForm<InviteInput>({ resolver: zodResolver(inviteSchema), defaultValues: { email: '' } });

  const [confirmDiscard, setConfirmDiscard] = useState(false);
  const { isDirty } = form.formState;

  function close() {
    form.reset();
    setError('');
    setOpen(false);
  }

  // Esc, a click outside and Cancel ask first when the form has typed text; while it sends, the form stays open,
  // so a failed send keeps the text.
  function changeOpen(nextOpen: boolean) {
    if (nextOpen) setOpen(true);
    else if (form.formState.isSubmitting) return;
    else if (isDirty) setConfirmDiscard(true);
    else close();
  }

  async function submit(input: InviteInput) {
    setError('');
    try {
      await invite.mutateAsync(input);
      toast.success(`Invite sent to ${input.email}.`);
      close();
    } catch (cause) {
      if (applyApiFieldErrors(cause, form.setError)) return;
      setError((cause instanceof ApiError && INVITE_ERRORS[cause.code]) || 'Could not send the invite. Try again.');
    }
  }

  return (
    <>
    <Dialog open={open} onOpenChange={changeOpen}>
      <DialogTrigger asChild>{children}</DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Invite person</DialogTitle>
          <DialogDescription>We will email them a link to join your organisation. The link works for 7 days.</DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form noValidate className="space-y-4" onSubmit={form.handleSubmit(submit)}>
            <FormField control={form.control} name="email" render={({ field }) => (
              <FormItem>
                <FormLabel>Email</FormLabel>
                <FormControl><Input type="email" autoComplete="off" {...field} /></FormControl>
                <FormMessage />
              </FormItem>
            )} />
            {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => changeOpen(false)}>Cancel</Button>
              <Button type="submit" disabled={form.formState.isSubmitting}>
                {form.formState.isSubmitting ? 'Sending…' : 'Send invite'}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
    <AlertDialog open={confirmDiscard} onOpenChange={setConfirmDiscard}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Discard this invite?</AlertDialogTitle>
          <AlertDialogDescription>The text you typed will be lost.</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Keep editing</AlertDialogCancel>
          <AlertDialogAction onClick={() => { setConfirmDiscard(false); close(); }}>Discard</AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
    </>
  );
}
