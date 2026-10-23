import { useEffect, useState } from 'react';
import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';
import { projectSchema, type Project, type ProjectInput } from '@shared/index';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { applyApiFieldErrors } from '@/lib/form-errors';

type ProjectFormDialogProps = {
  open: boolean;
  project?: Project;
  onOpenChange: (open: boolean) => void;
  onSave: (input: ProjectInput) => Promise<void>;
};

export function ProjectFormDialog({ open, project, onOpenChange, onSave }: ProjectFormDialogProps) {
  const [error, setError] = useState('');
  const [confirmDiscard, setConfirmDiscard] = useState(false);
  const form = useForm<ProjectInput>({
    resolver: zodResolver(projectSchema),
    defaultValues: { name: '', status: 'active' },
  });
  const { isDirty } = form.formState;

  useEffect(() => {
    if (open) {
      setError('');
      form.reset({ name: project?.name ?? '', status: project?.status ?? 'active' });
    }
  }, [form, open, project?.id]);

  async function submit(input: ProjectInput) {
    setError('');
    try {
      await onSave(input);
      form.reset(input);
      onOpenChange(false);
    } catch (cause) {
      if (!applyApiFieldErrors(cause, form.setError)) {
        setError('Could not save this project. Check the details and try again.');
      }
    }
  }

  function requestOpenChange(nextOpen: boolean) {
    if (!nextOpen && isDirty && !form.formState.isSubmitting) {
      setConfirmDiscard(true);
      return;
    }
    onOpenChange(nextOpen);
  }

  const editing = Boolean(project);
  const title = editing ? 'Edit project' : 'Create project';
  return (
    <>
    <Dialog open={open} onOpenChange={requestOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{editing ? 'Update the project name or status.' : 'Add a project to your list.'}</DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form className="space-y-4" onSubmit={form.handleSubmit(submit)}>
            <FormField control={form.control} name="name" render={({ field }) => (
              <FormItem>
                <FormLabel>Name</FormLabel>
                <FormControl><Input autoComplete="off" {...field} /></FormControl>
                <FormMessage />
              </FormItem>
            )} />
            <FormField control={form.control} name="status" render={({ field }) => (
              <FormItem>
                <FormLabel>Status</FormLabel>
                <Select value={field.value} onValueChange={field.onChange}>
                  <FormControl><SelectTrigger aria-label="Status"><SelectValue placeholder="Choose a status" /></SelectTrigger></FormControl>
                  <SelectContent>
                    <SelectItem value="active">Active</SelectItem>
                    <SelectItem value="archived">Archived</SelectItem>
                  </SelectContent>
                </Select>
                <FormMessage />
              </FormItem>
            )} />
            {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => requestOpenChange(false)}>Cancel</Button>
              <Button type="submit" disabled={form.formState.isSubmitting}>
                {form.formState.isSubmitting ? 'Saving…' : editing ? 'Save changes' : 'Create project'}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
    <AlertDialog open={confirmDiscard} onOpenChange={setConfirmDiscard}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Discard project changes?</AlertDialogTitle>
          <AlertDialogDescription>Your unsaved project changes will be lost.</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Keep editing</AlertDialogCancel>
          <AlertDialogAction onClick={(event) => {
            event.preventDefault();
            setConfirmDiscard(false);
            form.reset({ name: project?.name ?? '', status: project?.status ?? 'active' });
            onOpenChange(false);
          }}>Discard changes</AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
    </>
  );
}
