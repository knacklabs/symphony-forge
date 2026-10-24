import { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  flexRender,
  getCoreRowModel,
  useReactTable,
  type ColumnDef,
  type PaginationState,
  type SortingState,
} from '@tanstack/react-table';
import { ArrowDown, ArrowUp, ArrowUpDown, Pencil, Plus, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import type { Project, ProjectInput } from '@app/shared';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
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
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { ProjectFormDialog } from '@/features/projects/pages/project-form-dialog';
import {
  useCreateProject,
  useDeleteProject,
  useProjects,
  useUpdateProject,
  type ProjectListQuery,
  type ProjectSortBy,
} from '@/features/projects/hooks/projects-hooks';

const PAGE_SIZE = 20;
const SORT_COLUMNS: { label: string; key: ProjectSortBy }[] = [
  { label: 'Name', key: 'name' },
  { label: 'Status', key: 'status' },
  { label: 'Created', key: 'createdAtUtc' },
  { label: 'Updated', key: 'updatedAtUtc' },
];

function readListQuery(params: URLSearchParams): ProjectListQuery {
  const pageNumber = Number(params.get('page'));
  const requestedSort = params.get('sortBy');
  const sortBy = SORT_COLUMNS.some(({ key }) => key === requestedSort) ? requestedSort as ProjectSortBy : 'createdAtUtc';
  return {
    page: Number.isInteger(pageNumber) && pageNumber > 0 ? pageNumber : 1,
    limit: PAGE_SIZE,
    sortBy,
    sortOrder: params.get('sortOrder') === 'asc' ? 'asc' : 'desc',
  };
}

function SortLabel({ label, sorted }: { label: string; sorted: false | 'asc' | 'desc' }) {
  const Icon = sorted === 'asc' ? ArrowUp : sorted === 'desc' ? ArrowDown : ArrowUpDown;
  return <>{label}<Icon aria-hidden="true" className="size-3.5" /></>;
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(new Date(value));
}

export function ProjectsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const query = readListQuery(searchParams);
  const projects = useProjects(query);
  const createProject = useCreateProject();
  const updateProject = useUpdateProject();
  const deleteProject = useDeleteProject();
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Project>();
  const [deleting, setDeleting] = useState<Project>();

  function setQuery(next: Partial<ProjectListQuery>) {
    const value = { ...query, ...next };
    setSearchParams({ page: String(value.page), sortBy: value.sortBy, sortOrder: value.sortOrder });
  }

  async function save(input: ProjectInput) {
    if (editing) {
      await updateProject.mutateAsync({ id: editing.id, input });
      toast.success('Project updated.');
    } else {
      await createProject.mutateAsync(input);
      toast.success('Project created.');
    }
    setEditing(undefined);
  }

  async function confirmDelete() {
    if (!deleting) return;
    try {
      await deleteProject.mutateAsync(deleting.id);
      toast.success('Project deleted.');
      setDeleting(undefined);
    } catch {
      toast.error('Could not delete this project. Try again.');
    }
  }

  function openCreate() {
    setEditing(undefined);
    setFormOpen(true);
  }

  const columns: ColumnDef<Project>[] = [
    {
      accessorKey: 'name',
      header: ({ column }) => (
        <Button variant="ghost" size="sm" className="-ml-3 h-8 gap-2" onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}>
          <SortLabel label="Name" sorted={column.getIsSorted()} />
        </Button>
      ),
      cell: ({ row }) => <span className="font-medium">{row.original.name}</span>,
    },
    {
      accessorKey: 'status',
      header: ({ column }) => (
        <Button variant="ghost" size="sm" className="-ml-3 h-8 gap-2" onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}>
          <SortLabel label="Status" sorted={column.getIsSorted()} />
        </Button>
      ),
      cell: ({ row }) => <Badge variant="outline">{row.original.status}</Badge>,
    },
    {
      accessorKey: 'createdAtUtc',
      header: ({ column }) => (
        <Button variant="ghost" size="sm" className="-ml-3 h-8 gap-2" onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}>
          <SortLabel label="Created" sorted={column.getIsSorted()} />
        </Button>
      ),
      cell: ({ row }) => <div><time dateTime={row.original.createdAtUtc}>{formatDate(row.original.createdAtUtc)}</time><span className="block text-xs text-muted-foreground">by you</span></div>,
    },
    {
      accessorKey: 'updatedAtUtc',
      header: ({ column }) => (
        <Button variant="ghost" size="sm" className="-ml-3 h-8 gap-2" onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}>
          <SortLabel label="Updated" sorted={column.getIsSorted()} />
        </Button>
      ),
      cell: ({ row }) => <div><time dateTime={row.original.updatedAtUtc}>{formatDate(row.original.updatedAtUtc)}</time><span className="block text-xs text-muted-foreground">by you</span></div>,
    },
    {
      id: 'actions',
      header: () => <span className="sr-only">Actions</span>,
      enableSorting: false,
      cell: ({ row }) => (
        <div className="flex justify-end gap-1">
          <Button variant="ghost" size="icon" aria-label={`Edit ${row.original.name}`} onClick={() => { setEditing(row.original); setFormOpen(true); }}><Pencil aria-hidden="true" /></Button>
          <Button variant="ghost" size="icon" aria-label={`Delete ${row.original.name}`} disabled={deleteProject.isPending} onClick={() => setDeleting(row.original)}><Trash2 aria-hidden="true" /></Button>
        </div>
      ),
    },
  ];

  const currentSorting: SortingState = [{ id: query.sortBy, desc: query.sortOrder === 'desc' }];
  const currentPagination: PaginationState = { pageIndex: query.page - 1, pageSize: PAGE_SIZE };
  const table = useReactTable({
    data: projects.data?.items ?? [],
    columns,
    getCoreRowModel: getCoreRowModel(),
    manualSorting: true,
    manualPagination: true,
    pageCount: projects.data?.pagination.totalPages ?? 1,
    state: { sorting: currentSorting, pagination: currentPagination },
    onSortingChange: (updater) => {
      const next = typeof updater === 'function' ? updater(currentSorting) : updater;
      const sort = next[0];
      if (sort && SORT_COLUMNS.some(({ key }) => key === sort.id)) {
        setQuery({ page: 1, sortBy: sort.id as ProjectSortBy, sortOrder: sort.desc ? 'desc' : 'asc' });
      }
    },
    onPaginationChange: (updater) => {
      const next = typeof updater === 'function' ? updater(currentPagination) : updater;
      setQuery({ page: next.pageIndex + 1 });
    },
  });

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Projects</h1>
          <p className="mt-1 text-sm text-muted-foreground">Create and manage your projects.</p>
        </div>
        <Button onClick={openCreate}><Plus aria-hidden="true" />Create project</Button>
      </div>

      {projects.isPending && <p role="status" className="text-sm text-muted-foreground">Loading projects…</p>}
      {projects.isError && (
        <div role="alert" className="space-y-3">
          <p>Could not load projects. Check your connection and try again.</p>
          <Button variant="outline" onClick={() => void projects.refetch()}>Try again</Button>
        </div>
      )}
      {projects.data && projects.data.items.length === 0 && (
        <div className="rounded-md border p-6">
          <p className="font-medium">{projects.data.pagination.totalItems === 0 && query.page === 1 ? 'No projects yet.' : 'No projects on this page.'}</p>
          <p className="mt-1 text-sm text-muted-foreground">
            {projects.data.pagination.totalItems === 0 && query.page === 1
              ? 'Create a project to keep its status in one place.'
              : 'Use Previous to view the remaining projects.'}
          </p>
        </div>
      )}
      {projects.data && projects.data.items.length > 0 && (
        <div className="overflow-x-auto rounded-md border">
          <Table>
            <TableHeader>
              {table.getHeaderGroups().map((headerGroup) => (
                <TableRow key={headerGroup.id}>
                  {headerGroup.headers.map((header) => {
                    const sorted = header.column.getIsSorted();
                    return (
                      <TableHead key={header.id} aria-sort={sorted === 'asc' ? 'ascending' : sorted === 'desc' ? 'descending' : 'none'}>
                        {header.isPlaceholder ? null : flexRender(header.column.columnDef.header, header.getContext())}
                      </TableHead>
                    );
                  })}
                </TableRow>
              ))}
            </TableHeader>
            <TableBody>
              {table.getRowModel().rows.map((row) => (
                <TableRow key={row.id}>
                  {row.getVisibleCells().map((cell) => <TableCell key={cell.id}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</TableCell>)}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
      {projects.data && (projects.data.pagination.totalItems > 0 || query.page > 1) && (
        <div className="flex items-center justify-between gap-4 text-sm">
          <p className="text-muted-foreground">
            {projects.data.items.length === 0
              ? `${projects.data.pagination.totalItems} projects · Page ${query.page} is empty`
              : `${projects.data.pagination.totalItems} project${projects.data.pagination.totalItems === 1 ? '' : 's'} · Page ${query.page} of ${Math.max(projects.data.pagination.totalPages, 1)}`}
          </p>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" disabled={!table.getCanPreviousPage()} onClick={() => table.previousPage()}>Previous</Button>
            <Button variant="outline" size="sm" disabled={!table.getCanNextPage()} onClick={() => table.nextPage()}>Next</Button>
          </div>
        </div>
      )}

      <ProjectFormDialog
        open={formOpen}
        project={editing}
        onOpenChange={(open) => { setFormOpen(open); if (!open) setEditing(undefined); }}
        onSave={save}
      />
      <AlertDialog open={Boolean(deleting)} onOpenChange={(open) => { if (!open) setDeleting(undefined); }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete project?</AlertDialogTitle>
            <AlertDialogDescription>This action cannot be undone. The project “{deleting?.name}” will be deleted.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction disabled={deleteProject.isPending} onClick={(event) => { event.preventDefault(); void confirmDelete(); }}>
              {deleteProject.isPending ? 'Deleting…' : 'Delete project'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
