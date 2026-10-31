import { useEffect, useState } from 'react';
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import {
  flexRender,
  getCoreRowModel,
  useReactTable,
  type ColumnDef,
  type SortingState,
} from '@tanstack/react-table';
import { ArrowDown, ArrowUp, ArrowUpDown, Download, Plus, Search } from 'lucide-react';
import { toast } from 'sonner';
// forge:feature:list-imports:start
import { formatDate, formatNumber } from '@app/shared-util';
import { projectStatusSchema, type Project, type ProjectInput, type ProjectStatus } from '@app/projects-contracts';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@app/shared-ui/components/ui/select';
// forge:feature:list-imports:end
import { useCan } from '@app/core-web';
// forge:feature:mcp:start
import { AgentAccessDialog } from '@app/core-web';
// forge:feature:mcp:end
import { Badge } from '@app/shared-ui/components/ui/badge';
import { Button } from '@app/shared-ui/components/ui/button';
import { Input } from '@app/shared-ui/components/ui/input';
import { Label } from '@app/shared-ui/components/ui/label';
import { Switch } from '@app/shared-ui/components/ui/switch';
import { Skeleton } from '@app/shared-ui/components/ui/skeleton';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@app/shared-ui/components/ui/table';
import { ProjectFormDialog } from './project-form-dialog';
import type { ProjectListState } from './project-detail-page';
import { useCreateProject, useProjects, type ProjectListQuery, type ProjectSortBy } from '../hooks/projects-hooks';

const SEARCH_DELAY_MS = 300;
// forge:feature:list-fields:start
const SORT_KEYS: ProjectSortBy[] = ['name', 'status', 'createdAtUtc', 'updatedAtUtc'];
/** The list's filters other than the search and Show deleted. */
const FILTER_KEYS: (keyof ProjectListQuery)[] = ['status'];
const SEARCH_PLACEHOLDER = 'Search by name';
export const STATUS_LABELS: Record<ProjectStatus, string> = { active: 'Active', archived: 'Archived' };
// forge:feature:list-fields:end

function readListQuery(params: URLSearchParams): ProjectListQuery {
  const requestedSort = params.get('sortBy') as ProjectSortBy;
  return {
    search: params.get('search')?.trim() || undefined,
    // forge:feature:read-filters:start
    status: projectStatusSchema.safeParse(params.get('status')).data,
    // forge:feature:read-filters:end
    deleted: params.get('deleted') === 'yes' ? 'yes' : undefined,
    sortBy: SORT_KEYS.includes(requestedSort) ? requestedSort : 'updatedAtUtc',
    sortOrder: params.get('sortOrder') === 'asc' ? 'asc' : 'desc',
    after: params.get('after') || undefined,
    before: params.get('before') || undefined,
  };
}

/** Exact below 100, then rounded to the hundred; above the API's count limit, "More than 10,000". */
function totalText(total: number, capped: boolean, withDeleted: boolean): string {
  const count = capped ? `More than ${formatNumber(total)} projects`
    : total < 100 ? `${total} project${total === 1 ? '' : 's'}`
      : `About ${formatNumber(Math.round(total / 100) * 100)} projects`;
  return withDeleted ? `${count}, deleted ones included` : count;
}

function SortLabel({ label, sorted }: { label: string; sorted: false | 'asc' | 'desc' }) {
  const Icon = sorted === 'asc' ? ArrowUp : sorted === 'desc' ? ArrowDown : ArrowUpDown;
  return <>{label}<Icon aria-hidden="true" className="size-3.5" /></>;
}

// flexRender mounts these renderers as components, so they live outside ProjectsPage: a new
// function on each render would remount the header buttons and drop keyboard focus.
// React Compiler skips ProjectsPage because of useReactTable, so it cannot keep them stable.
type RowMeta = { listState: ProjectListState };

const columns: ColumnDef<Project>[] = [
  // forge:feature:columns:start
  {
    accessorKey: 'name',
    header: ({ column }) => (
      <Button variant="ghost" size="sm" className="-ml-3 h-8 gap-2" onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}>
        <SortLabel label="Name" sorted={column.getIsSorted()} />
      </Button>
    ),
    cell: ({ row, table }) => (
      <span className="inline-flex items-center gap-2">
        <Link className="font-medium underline-offset-4 hover:underline" to={`/projects/${row.original.id}`} state={(table.options.meta as RowMeta).listState}>{row.original.name}</Link>
        {row.original.deletedAtUtc && <Badge variant="secondary">Deleted</Badge>}
      </span>
    ),
  },
  {
    accessorKey: 'status',
    header: ({ column }) => (
      <Button variant="ghost" size="sm" className="-ml-3 h-8 gap-2" onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}>
        <SortLabel label="Status" sorted={column.getIsSorted()} />
      </Button>
    ),
    cell: ({ row }) => <Badge variant="outline">{STATUS_LABELS[row.original.status]}</Badge>,
  },
  // forge:feature:columns:end
  {
    accessorKey: 'updatedAtUtc',
    header: ({ column }) => (
      <Button variant="ghost" size="sm" className="-ml-3 h-8 gap-2" onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}>
        <SortLabel label="Updated" sorted={column.getIsSorted()} />
      </Button>
    ),
    cell: ({ row }) => <time dateTime={row.original.updatedAtUtc}>{formatDate(row.original.updatedAtUtc)}</time>,
  },
];

export function ProjectsPage() {
  const navigate = useNavigate();
  // The detail screen's breadcrumb and Delete come back to this list as the person left it.
  const listState: ProjectListState = { listSearch: useLocation().search };
  const [searchParams, setSearchParams] = useSearchParams();
  const query = readListQuery(searchParams);
  const projects = useProjects(query);
  const createProject = useCreateProject();
  const canCreate = useCan('projects.create');
  const canRestore = useCan('projects.restore');
  const [formOpen, setFormOpen] = useState(false);
  const urlSearch = query.search ?? '';
  const [searchText, setSearchText] = useState(urlSearch);
  const [shownSearch, setShownSearch] = useState(urlSearch);
  // Back, forward or the clear button can change the address; the search box follows it then.
  if (urlSearch !== shownSearch) {
    setShownSearch(urlSearch);
    if (searchText.trim() !== urlSearch) setSearchText(urlSearch);
  }

  /** Writes the list query to the address. A change without a cursor goes back to the first page. */
  function setQuery(next: Partial<ProjectListQuery>) {
    setSearchParams((current) => {
      const value = { ...readListQuery(current), after: undefined, before: undefined, ...next };
      return Object.fromEntries(Object.entries(value).filter((entry): entry is [string, string] => Boolean(entry[1])));
    });
  }

  // The search waits until the person stops typing.
  useEffect(() => {
    const term = searchText.trim();
    if (term === urlSearch) return;
    const timer = setTimeout(() => setQuery({ search: term || undefined }), SEARCH_DELAY_MS);
    return () => clearTimeout(timer);
  });

  // A new project opens on its own detail screen.
  async function create(input: ProjectInput) {
    const project = await createProject.mutateAsync(input);
    toast.success('Project created.');
    void navigate(`/projects/${project.id}`, { state: listState });
  }

  function clearSearchAndFilters() {
    setSearchText('');
    setQuery({ search: undefined, deleted: undefined, ...Object.fromEntries(FILTER_KEYS.map((key) => [key, undefined])) });
  }

  const currentSorting: SortingState = [{ id: query.sortBy, desc: query.sortOrder === 'desc' }];
  const table = useReactTable({
    data: projects.data?.items ?? [],
    columns,
    getCoreRowModel: getCoreRowModel(),
    meta: { listState } satisfies RowMeta,
    manualSorting: true,
    state: { sorting: currentSorting },
    onSortingChange: (updater) => {
      const next = typeof updater === 'function' ? updater(currentSorting) : updater;
      const sort = next[0];
      if (sort && SORT_KEYS.includes(sort.id as ProjectSortBy)) {
        setQuery({ sortBy: sort.id as ProjectSortBy, sortOrder: sort.desc ? 'desc' : 'asc' });
      }
    },
  });
  const paging = projects.data?.paging;
  // Malformed list data must reach the screen's error page, so no fallback for a missing items array.
  const items = projects.data ? projects.data.items : [];
  const filtered = Boolean(query.search) || FILTER_KEYS.some((key) => Boolean(query[key]));
  const paged = Boolean(query.after || query.before);
  // While a new sort or filter loads, the old rows stay on screen, but their cursors belong to
  // the old query, so Previous and Next wait for the new page.
  const stale = projects.isPlaceholderData;
  // Export CSV downloads what the list shows: the same search and filter, every page.
  const exportParameters = new URLSearchParams(Object.entries({ search: query.search, ...Object.fromEntries(FILTER_KEYS.map((key) => [key, query[key]])), deleted: query.deleted })
    .filter((entry): entry is [string, string] => Boolean(entry[1])));

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Projects</h1>
          <p className="mt-1 text-sm text-muted-foreground">Create and manage your projects.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {/* forge:feature:mcp:start */}
          <AgentAccessDialog feature="projects" one="project" label="projects" />
          {/* forge:feature:mcp:end */}
          <Button variant="outline" asChild><a href={`/api/v1/projects/export?${exportParameters.toString()}`} download><Download aria-hidden="true" />Export CSV</a></Button>
          {canCreate && <Button onClick={() => setFormOpen(true)}><Plus aria-hidden="true" />New project</Button>}
        </div>
      </div>

      <div role="search" className="flex flex-wrap items-center gap-2">
        <div className="relative w-full sm:w-72">
          <Search aria-hidden="true" className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            type="search"
            aria-label="Search projects"
            placeholder={SEARCH_PLACEHOLDER}
            className="pl-8"
            maxLength={200}
            value={searchText}
            onChange={(event) => setSearchText(event.target.value)}
          />
        </div>
        {/* forge:feature:filter-controls:start */}
        <Select value={query.status ?? 'all'} onValueChange={(value) => setQuery({ status: value === 'all' ? undefined : value as ProjectStatus })}>
          <SelectTrigger aria-label="Status" className="w-full sm:w-44"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All statuses</SelectItem>
            {projectStatusSchema.options.map((status) => <SelectItem key={status} value={status}>{STATUS_LABELS[status]}</SelectItem>)}
          </SelectContent>
        </Select>
        {/* forge:feature:filter-controls:end */}
        {canRestore && (
          <div className="flex items-center gap-2 sm:ml-2">
            <Switch id="show-deleted" checked={query.deleted === 'yes'} onCheckedChange={(checked) => setQuery({ deleted: checked ? 'yes' : undefined })} />
            <Label htmlFor="show-deleted">Show deleted</Label>
          </div>
        )}
      </div>

      {projects.isPending && (
        <div role="status" aria-label="Loading projects" className="space-y-2">
          {[0, 1, 2].map((row) => <Skeleton key={row} className="h-10 w-full" />)}
        </div>
      )}
      {projects.isError && (
        <div role="alert" className="space-y-3">
          <p>Could not load projects. Check your connection and try again.</p>
          <Button variant="outline" onClick={() => void projects.refetch()}>Try again</Button>
        </div>
      )}
      {projects.data && items.length === 0 && (
        <div className="rounded-md border p-6">
          {paged && paging && paging.total > 0 ? (
            <>
              <p className="font-medium">No projects on this page.</p>
              <p className="mt-1 text-sm text-muted-foreground">The projects on it were changed or deleted.</p>
              <Button variant="outline" className="mt-4" onClick={() => setQuery({})}>Go to the first page</Button>
            </>
          ) : filtered ? (
            <>
              <p className="font-medium">No projects match this search.</p>
              <p className="mt-1 text-sm text-muted-foreground">Try other words or clear the filters.</p>
              <Button variant="outline" className="mt-4" onClick={clearSearchAndFilters}>Clear search and filters</Button>
            </>
          ) : (
            <>
              <p className="font-medium">No projects yet.</p>
              <p className="mt-1 text-sm text-muted-foreground">Create a project to keep its status in one place.</p>
            </>
          )}
        </div>
      )}
      {items.length > 0 && (
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
                <TableRow
                  key={row.id}
                  className={row.original.deletedAtUtc ? 'cursor-pointer text-muted-foreground' : 'cursor-pointer'}
                  // The name link is the keyboard target; a click elsewhere on the row opens the same screen.
                  onClick={(event) => {
                    if (!(event.target as HTMLElement).closest('a, button')) void navigate(`/projects/${row.original.id}`, { state: listState });
                  }}
                >
                  {row.getVisibleCells().map((cell) => <TableCell key={cell.id}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</TableCell>)}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
      {paging && items.length > 0 && (
        <div className="flex items-center justify-between gap-4 text-sm">
          <p className="text-muted-foreground">{totalText(paging.total, paging.totalCapped, canRestore && query.deleted === 'yes')}</p>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" disabled={!paging.previousCursor || stale} onClick={() => setQuery({ before: paging.previousCursor ?? undefined })}>Previous</Button>
            <Button variant="outline" size="sm" disabled={!paging.nextCursor || stale} onClick={() => setQuery({ after: paging.nextCursor ?? undefined })}>Next</Button>
          </div>
        </div>
      )}

      <ProjectFormDialog open={formOpen} onOpenChange={setFormOpen} onSave={create} />
    </div>
  );
}
