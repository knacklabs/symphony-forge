import { useEffect, useState } from 'react';
import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';
// forge:feature:form-imports:start
import { projectSchema, type Project, type ProjectInput } from '@app/projects-contracts';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@app/shared-ui/components/ui/select';
// forge:feature:form-imports:end
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
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@app/shared-ui/components/ui/dialog';
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@app/shared-ui/components/ui/form';
import { Input } from '@app/shared-ui/components/ui/input';
import { applyApiFieldErrors } from '@app/core-web';

// forge:feature:form-values:start
const formSchema = projectSchema;
type FormValues = ProjectInput;

function toValues(project?: Project): FormValues {
  return { name: project?.name ?? '', status: project?.status ?? 'active' };
}

function toInput(values: FormValues): ProjectInput {
  return values;
}
// forge:feature:form-values:end

type ProjectFormDialogProps = {
  open: boolean;
  project?: Project;
  onOpenChange: (open: boolean) => void;
  onSave: (input: ProjectInput) => Promise<void>;
};

export function ProjectFormDialog({ open, project, onOpenChange, onSave }: ProjectFormDialogProps) {
  const [error, setError] = useState('');
  const [confirmDiscard, setConfirmDiscard] = useState(false);
  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: toValues(),
  });
  const { isDirty } = form.formState;

  // The parent keeps the edited project fixed while the dialog is open, so this resets only on open.
  useEffect(() => {
    if (open) form.reset(toValues(project));
  }, [form, open, project]);

  async function submit(values: FormValues) {
    setError('');
    try {
      await onSave(toInput(values));
      form.reset(values);
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
    if (!nextOpen) setError('');
    onOpenChange(nextOpen);
  }

  const editing = Boolean(project);
  const title = editing ? 'Edit project' : 'New project';
  return (
    <>
    <Dialog open={open} onOpenChange={requestOpenChange}>
      <DialogContent className="max-h-[calc(100dvh-2rem)] overflow-y-auto sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{editing ? 'Change the project’s details.' : 'Add a project to your list.'}</DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form className="space-y-4" onSubmit={form.handleSubmit(submit)}>
            {/* forge:feature:form-fields:start */}
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
            {/* forge:feature:form-fields:end */}
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
            setError('');
            form.reset(toValues(project));
            onOpenChange(false);
          }}>Discard changes</AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
    </>
  );
}
