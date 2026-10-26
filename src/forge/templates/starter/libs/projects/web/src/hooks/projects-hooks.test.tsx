import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useCreateProject, useDeleteProject, useProject, useProjects, useUpdateProject } from './projects-hooks';

const project = {
  id: 'project-1',
  name: 'Migration review',
  status: 'active' as const,
  createdAtUtc: '2026-10-23T00:00:00.000Z',
  updatedAtUtc: '2026-10-23T00:00:00.000Z',
  createdByAccountId: 'account-1',
  modifiedByAccountId: 'account-1',
};

function response(data: unknown, status = 200) {
  return new Response(JSON.stringify({ success: true, data, error: null }), {
    status,
    headers: { 'content-type': 'application/json' },
  });
}

function wrapper(client: QueryClient) {
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
}

describe('project hooks', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    document.cookie = 'starter_csrf=; Max-Age=0; path=/';
  });

  it('reads a project list and one project through the API envelope', async () => {
    const fetch = vi.fn()
      .mockResolvedValueOnce(response({ items: [project], paging: { limit: 20, nextCursor: null, previousCursor: null, total: 1, totalCapped: false } }))
      .mockResolvedValueOnce(response(project));
    vi.stubGlobal('fetch', fetch);
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const queryWrapper = wrapper(client);

    const list = renderHook(() => useProjects({ search: 'migration', status: 'active', sortBy: 'name', sortOrder: 'asc', after: 'cursor-1' }), { wrapper: queryWrapper });
    await waitFor(() => expect(list.result.current.data?.items).toEqual([project]));
    const detail = renderHook(() => useProject(project.id), { wrapper: queryWrapper });
    await waitFor(() => expect(detail.result.current.data).toEqual(project));

    expect(String(fetch.mock.calls[0][0])).toContain('/api/v1/projects?search=migration&status=active&sortBy=name&sortOrder=asc&after=cursor-1');
    expect(String(fetch.mock.calls[1][0])).toBe(`/api/v1/projects/${project.id}`);
  });

  it('creates, updates, and deletes projects with credentialed, CSRF-protected requests', async () => {
    document.cookie = 'starter_csrf=csrf-token; path=/';
    const fetch = vi.fn()
      .mockResolvedValueOnce(response(project, 201))
      .mockResolvedValueOnce(response({ ...project, name: 'Updated review' }))
      .mockResolvedValueOnce(response(null));
    vi.stubGlobal('fetch', fetch);
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const queryWrapper = wrapper(client);
    const create = renderHook(() => useCreateProject(), { wrapper: queryWrapper });
    const update = renderHook(() => useUpdateProject(), { wrapper: queryWrapper });
    const remove = renderHook(() => useDeleteProject(), { wrapper: queryWrapper });

    await act(async () => create.result.current.mutateAsync({ name: project.name, status: project.status }));
    await act(async () => update.result.current.mutateAsync({ id: project.id, input: { name: 'Updated review', status: project.status } }));
    await act(async () => remove.result.current.mutateAsync(project.id));

    expect(fetch).toHaveBeenCalledTimes(3);
    expect(fetch.mock.calls.map(([url, init]) => [String(url), init?.method])).toEqual([
      ['/api/v1/projects', 'POST'],
      [`/api/v1/projects/${project.id}`, 'PUT'],
      [`/api/v1/projects/${project.id}`, 'DELETE'],
    ]);
    for (const [, init] of fetch.mock.calls) {
      const headers = new Headers(init?.headers);
      expect(headers.get('x-csrf-token')).toBe('csrf-token');
      expect(init?.credentials).toBe('include');
    }
  });
});
