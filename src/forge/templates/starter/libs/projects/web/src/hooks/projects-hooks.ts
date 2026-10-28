import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
// forge:feature:retry-key:start
import { useRef } from 'react';
// forge:feature:retry-key:end
import type { Project, ProjectChange, ProjectInput, ProjectListQuery as ProjectApiListQuery } from '@app/projects-contracts';
import { apiRequest } from '@app/core-web';

/** The list's search, filters, sort and cursor, as the API reads them; the API sets the page size. */
export type ProjectListQuery = Omit<ProjectApiListQuery, 'limit'>;
export type ProjectSortBy = ProjectListQuery['sortBy'];
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
  // forge:feature:retry-key:start
  const idempotencyKey = useRef(crypto.randomUUID());
  // forge:feature:retry-key:end
  return useMutation({
    mutationFn: (input: ProjectInput) => apiRequest<Project>('/projects', {
      method: 'POST',
      body: JSON.stringify(input),
      // forge:feature:retry-key:start
      headers: { 'Idempotency-Key': idempotencyKey.current },
      // forge:feature:retry-key:end
    }),
    onSuccess: () => {
      // forge:feature:retry-key:start
      idempotencyKey.current = crypto.randomUUID();
      // forge:feature:retry-key:end
      return queryClient.invalidateQueries({ queryKey: projectKeys.all });
    },
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

export function useRestoreProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiRequest<Project>(`/projects/${encodeURIComponent(id)}/restore`, { method: 'POST' }),
    // The detail, its recent changes and the lists all sit under the projects key.
    onSuccess: () => queryClient.invalidateQueries({ queryKey: projectKeys.all }),
  });
}

// forge:feature:link-hooks:start
// forge:feature:link-hooks:end
