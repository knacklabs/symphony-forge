import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { Project, ProjectChange, ProjectInput, ProjectStatus } from '@app/projects-contracts';
import { apiRequest } from '@app/core-web';

export type ProjectSortBy = 'name' | 'status' | 'createdAtUtc' | 'updatedAtUtc';
export type ProjectListQuery = {
  search?: string;
  status?: ProjectStatus;
  sortBy: ProjectSortBy;
  sortOrder: 'asc' | 'desc';
  after?: string;
  before?: string;
};
export type ProjectList = {
  items: Project[];
  paging: { limit: number; nextCursor: string | null; previousCursor: string | null; total: number; totalCapped: boolean };
};

export const projectKeys = {
  all: ['projects'] as const,
  list: (query: ProjectListQuery) => ['projects', 'list', query] as const,
  detail: (id: string) => ['projects', 'detail', id] as const,
  changes: (id: string) => ['projects', 'changes', id] as const,
};

export function useProjects(query: ProjectListQuery) {
  const parameters = new URLSearchParams(
    Object.entries(query).filter((entry): entry is [string, string] => typeof entry[1] === 'string' && entry[1] !== ''),
  );
  return useQuery({
    queryKey: projectKeys.list(query),
    queryFn: () => apiRequest<ProjectList>(`/projects?${parameters.toString()}`),
    // A page change keeps the old rows on screen until the new rows arrive.
    placeholderData: keepPreviousData,
  });
}

export function useProject(id: string) {
  return useQuery({
    queryKey: projectKeys.detail(id),
    queryFn: () => apiRequest<Project>(`/projects/${encodeURIComponent(id)}`),
    enabled: id.length > 0,
  });
}

/** The project's newest 5 changes, newest first. */
export function useProjectChanges(id: string) {
  return useQuery({
    queryKey: projectKeys.changes(id),
    queryFn: () => apiRequest<ProjectChange[]>(`/projects/${encodeURIComponent(id)}/changes`),
  });
}

export function useCreateProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: ProjectInput) => apiRequest<Project>('/projects', {
      method: 'POST',
      body: JSON.stringify(input),
    }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: projectKeys.all }),
  });
}

export function useUpdateProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, input }: { id: string; input: ProjectInput }) => apiRequest<Project>(`/projects/${encodeURIComponent(id)}`, {
      method: 'PUT',
      body: JSON.stringify(input),
    }),
    // The detail, its recent changes and the lists all sit under the projects key.
    onSuccess: () => queryClient.invalidateQueries({ queryKey: projectKeys.all }),
  });
}

export function useDeleteProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiRequest<null>(`/projects/${encodeURIComponent(id)}`, { method: 'DELETE' }),
    // Mark the lists stale without a refetch now: the open detail screen would read the deleted
    // project as missing before the list opens. Each screen refetches when it opens.
    onSuccess: () => queryClient.invalidateQueries({ queryKey: projectKeys.all, refetchType: 'none' }),
  });
}
