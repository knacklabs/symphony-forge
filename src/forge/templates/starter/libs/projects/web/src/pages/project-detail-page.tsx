import { useState } from 'react';
import { Link, useLocation, useMatch, useNavigate, useOutletContext } from 'react-router-dom';
import { Pencil, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import { formatDate, formatDateTime } from '@app/shared-util';
import type { Project, ProjectInput } from '@app/projects-contracts';
import { ApiError, useCan } from '@app/core-web';
import { Alert, AlertDescription } from '@app/shared-ui/components/ui/alert';
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
import { Badge } from '@app/shared-ui/components/ui/badge';
import { BreadcrumbItem, BreadcrumbLink, BreadcrumbPage, BreadcrumbSeparator } from '@app/shared-ui/components/ui/breadcrumb';
import { Button } from '@app/shared-ui/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@app/shared-ui/components/ui/card';
import { ProjectFormDialog } from './project-form-dialog';
import { STATUS_LABELS } from './projects-page';
import { useDeleteProject, useProject, useProjectChanges, useRestoreProject, useUpdateProject } from '../hooks/projects-hooks';

/** The list's search, filters, sort and page that the person came from, so going back keeps them. */
export type ProjectListState = { listSearch?: string } | null;

function useProjectId(): string {
  return useMatch('/projects/:id')?.params.id ?? '';
}

function useListPath(): string {
  return `/projects${(useLocation().state as ProjectListState)?.listSearch ?? ''}`;
}

/** The header breadcrumb `Projects › <name>`; `Projects` goes back to the list as the person left it. */
export function ProjectCrumbs() {
  const project = useProject(useProjectId());
  return (
    <>
      <BreadcrumbItem><BreadcrumbLink asChild><Link to={useListPath()}>Projects</Link></BreadcrumbLink></BreadcrumbItem>
      <BreadcrumbSeparator />
      <BreadcrumbItem><BreadcrumbPage>{project.data?.name ?? 'Project'}</BreadcrumbPage></BreadcrumbItem>
    </>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs font-medium text-muted-foreground">{label}</dt>
      <dd className="mt-1 tabular-nums">{children}</dd>
    </div>
  );
}

function When({ utc }: { utc: string }) {
  return <time dateTime={utc}>{formatDateTime(utc)}</time>;
}

function RecentChanges({ projectId, isAdmin }: { projectId: string; isAdmin: boolean }) {
  const changes = useProjectChanges(projectId);
  return (
    <Card role="region" aria-labelledby="recent-changes-title">
      <CardHeader>
        <CardTitle><h2 id="recent-changes-title">Recent changes</h2></CardTitle>
        <CardDescription>The last 5 changes to this project.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {changes.isPending && <p role="status" className="text-sm text-muted-foreground">Loading changes…</p>}
        {changes.isError && (
          <div role="alert" className="space-y-3">
            <p className="text-sm">Could not load the recent changes.</p>
            <Button variant="outline" size="sm" onClick={() => void changes.refetch()}>Try again</Button>
          </div>
        )}
        {changes.data && (
          <ol className="divide-y">
            {changes.data.map((change) => (
              <li key={change.id} className="py-3 first:pt-0 last:pb-0">
                <p className="text-sm">{change.summary}</p>
                <p className="mt-0.5 text-xs text-muted-foreground tabular-nums">{change.actorEmail} · <When utc={change.createdAtUtc} /></p>
              </li>
            ))}
          </ol>
        )}
        {isAdmin && <Link className="inline-block text-sm underline underline-offset-4" to="/history">Open the change history</Link>}
      </CardContent>
    </Card>
  );
}

function ProjectDetails({ project, isAdmin }: { project: Project; isAdmin: boolean }) {
  const navigate = useNavigate();
  const listPath = useListPath();
  const updateProject = useUpdateProject();
  const deleteProject = useDeleteProject();
  const restoreProject = useRestoreProject();
  const canEdit = useCan('projects.edit');
  const canDelete = useCan('projects.delete');
  const deleted = project.deletedAtUtc !== null;
  const [editing, setEditing] = useState(false);
  const [deleting, setDeleting] = useState(false);

  async function save(input: ProjectInput) {
    await updateProject.mutateAsync({ id: project.id, input });
    toast.success('Project updated.');
  }

  async function restore() {
    try {
      await restoreProject.mutateAsync(project.id);
      toast.success('Project restored.');
    } catch {
      toast.error('Could not restore this project. Try again.');
    }
  }

  async function confirmDelete() {
    try {
      await deleteProject.mutateAsync(project.id);
      setDeleting(false);
      toast.success('Project deleted.');
      void navigate(listPath);
    } catch {
      toast.error('Could not delete this project. Try again.');
    }
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold tracking-tight break-words">{project.name}</h1>
          <Badge variant="outline">{STATUS_LABELS[project.status]}</Badge>
          {deleted && <Badge variant="secondary">Deleted</Badge>}
        </div>
        {!deleted && (
          <div className="flex flex-wrap gap-2">
            {canEdit && <Button variant="outline" onClick={() => setEditing(true)}><Pencil aria-hidden="true" />Edit</Button>}
            {canDelete && <Button variant="outline" className="text-destructive hover:text-destructive" onClick={() => setDeleting(true)}><Trash2 aria-hidden="true" />Delete</Button>}
          </div>
        )}
      </div>

      {project.deletedAtUtc && (
        <Alert className="items-center [&>svg]:translate-y-0">
          <Trash2 aria-hidden="true" />
          <AlertDescription className="flex flex-wrap items-center justify-between gap-3 text-foreground">
            <span>This project was deleted on <time dateTime={project.deletedAtUtc}>{formatDate(project.deletedAtUtc)}</time> by {project.deletedByEmail}.</span>
            <Button variant="outline" size="sm" disabled={restoreProject.isPending} onClick={() => void restore()}>
              {restoreProject.isPending ? 'Restoring…' : 'Restore'}
            </Button>
          </AlertDescription>
        </Alert>
      )}

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
        <Card role="region" aria-labelledby="details-title">
          <CardHeader><CardTitle><h2 id="details-title">Details</h2></CardTitle></CardHeader>
          <CardContent className="space-y-5">
            <dl className="grid gap-x-6 gap-y-5 sm:grid-cols-2">
              <Field label="Name"><span className="break-words">{project.name}</span></Field>
              <Field label="Status">{STATUS_LABELS[project.status]}</Field>
            </dl>
            <dl className="grid gap-x-6 gap-y-5 border-t pt-5 sm:grid-cols-2">
              <Field label="Created"><When utc={project.createdAtUtc} /> by <span className="break-all">{project.createdByEmail}</span></Field>
              <Field label="Last changed"><When utc={project.updatedAtUtc} /> by <span className="break-all">{project.modifiedByEmail}</span></Field>
            </dl>
          </CardContent>
        </Card>
        <RecentChanges projectId={project.id} isAdmin={isAdmin} />
      </div>

      <ProjectFormDialog open={editing} project={project} onOpenChange={setEditing} onSave={save} />
      <AlertDialog open={deleting} onOpenChange={setDeleting}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete project?</AlertDialogTitle>
            <AlertDialogDescription>The project “{project.name}” will be deleted. You cannot undo this.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction variant="destructive" disabled={deleteProject.isPending} onClick={(event) => { event.preventDefault(); void confirmDelete(); }}>
              {deleteProject.isPending ? 'Deleting…' : 'Delete project'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

export function ProjectDetailPage() {
  const account = useOutletContext<{ role: string }>();
  const project = useProject(useProjectId());
  // An unreadable id gets 400 and a missing or deleted project 404: both read as not found.
  const missing = project.error instanceof ApiError && (project.error.status === 404 || project.error.status === 400);

  if (project.isPending) return <p role="status" className="text-sm text-muted-foreground">Loading project…</p>;
  if (missing) {
    return (
      <div className="mx-auto max-w-6xl space-y-3">
        <h1 className="text-2xl font-semibold tracking-tight">This project does not exist or was deleted.</h1>
        <Link className="inline-block text-sm underline underline-offset-4" to="/projects">Back to projects</Link>
      </div>
    );
  }
  if (project.isError) {
    return (
      <div role="alert" className="mx-auto max-w-6xl space-y-3">
        <p>Could not load this project. Check your connection and try again.</p>
        <Button variant="outline" onClick={() => void project.refetch()}>Try again</Button>
      </div>
    );
  }
  return <ProjectDetails project={project.data} isAdmin={account.role === 'admin'} />;
}
