import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { Project, ProjectInput } from '@app/projects-contracts';
import { apiRequest } from '@app/core-web';

export type ProjectSortBy = 'name' | 'status' | 'createdAtUtc' | 'updatedAtUtc';
export type ProjectListQuery = {
  page: number;
  limit: number;
  sortBy: ProjectSortBy;
  sortOrder: 'asc' | 'desc';
};
export type ProjectList = {
  items: Project[];
  pagination: { page: number; limit: number; totalItems: number; totalPages: number };
};

export const projectKeys = {
  all: ['projects'] as const,
  list: (query: ProjectListQuery) => ['projects', 'list', query] as const,
  detail: (id: string) => ['projects', 'detail', id] as const,
};

export function useProjects(query: ProjectListQuery) {
  const parameters = new URLSearchParams({
    page: String(query.page),
    limit: String(query.limit),
    sortBy: query.sortBy,
    sortOrder: query.sortOrder,
  });
  return useQuery({
    queryKey: projectKeys.list(query),
    queryFn: () => apiRequest<ProjectList>(`/projects?${parameters.toString()}`),
  });
}

export function useProject(id: string) {
  return useQuery({
    queryKey: projectKeys.detail(id),
    queryFn: () => apiRequest<Project>(`/projects/${encodeURIComponent(id)}`),
    enabled: id.length > 0,
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
    onSuccess: (_, { id }) => {
      void queryClient.invalidateQueries({ queryKey: projectKeys.all });
      return queryClient.invalidateQueries({ queryKey: projectKeys.detail(id) });
    },
  });
}

export function useDeleteProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiRequest<null>(`/projects/${encodeURIComponent(id)}`, { method: 'DELETE' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: projectKeys.all }),
  });
}
