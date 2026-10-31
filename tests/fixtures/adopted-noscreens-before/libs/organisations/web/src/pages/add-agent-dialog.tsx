import { useState, type ReactNode } from 'react';
import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';
import { toast } from 'sonner';
import { addAgentSchema, type AddAgentInput } from '@app/organisations-contracts';
import { applyApiFieldErrors } from '@app/core-web';
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
import { Form, FormControl, FormDescription, FormField, FormItem, FormLabel, FormMessage } from '@app/shared-ui/components/ui/form';
import { Input } from '@app/shared-ui/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@app/shared-ui/components/ui/select';
import { useAddAgent } from '../hooks/members-hooks';

// The opener is the Dialog's trigger, so Radix gives it focus back when the dialog closes.
export function AddAgentDialog({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const [error, setError] = useState('');
  const addAgent = useAddAgent();
  const form = useForm<AddAgentInput>({ resolver: zodResolver(addAgentSchema), defaultValues: { name: '', role: 'member' } });

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

  async function submit(input: AddAgentInput) {
    setError('');
    try {
      await addAgent.mutateAsync(input);
      toast.success('Agent account added.');
      close();
    } catch (cause) {
      if (applyApiFieldErrors(cause, form.setError)) return;
      setError('Could not add the agent account. Try again.');
    }
  }

  return (
    <>
    <Dialog open={open} onOpenChange={changeOpen}>
      <DialogTrigger asChild>{children}</DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add agent account</DialogTitle>
          <DialogDescription>An agent uses this app's tools with this role. You create its key next.</DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form noValidate className="space-y-4" onSubmit={form.handleSubmit(submit)}>
            <FormField control={form.control} name="name" render={({ field }) => (
              <FormItem>
                <FormLabel>Name</FormLabel>
                <FormControl><Input autoComplete="off" spellCheck={false} {...field} /></FormControl>
                <FormDescription>Lower-case letters, numbers and hyphens, such as gantry.</FormDescription>
                <FormMessage />
              </FormItem>
            )} />
            <FormField control={form.control} name="role" render={({ field }) => (
              <FormItem>
                <FormLabel>Role</FormLabel>
                <Select value={field.value} onValueChange={field.onChange}>
                  <FormControl><SelectTrigger className="w-full"><SelectValue /></SelectTrigger></FormControl>
                  <SelectContent>
                    <SelectItem value="member">Member</SelectItem>
                    <SelectItem value="admin">Admin</SelectItem>
                  </SelectContent>
                </Select>
                <FormMessage />
              </FormItem>
            )} />
            {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => changeOpen(false)}>Cancel</Button>
              <Button type="submit" disabled={form.formState.isSubmitting}>
                {form.formState.isSubmitting ? 'Adding…' : 'Add agent account'}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
    <AlertDialog open={confirmDiscard} onOpenChange={setConfirmDiscard}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Discard this agent account?</AlertDialogTitle>
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
