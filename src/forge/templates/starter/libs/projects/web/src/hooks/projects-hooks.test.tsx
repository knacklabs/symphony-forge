import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useCreateProject, useDeleteProject, useProject, useProjects, useUpdateProject } from './projects-hooks';

const project = {
  id: 'project-1',
  // forge:feature:test-fields:start
  name: 'Migration review',
  status: 'active' as const,
  // forge:feature:test-fields:end
  createdAtUtc: '2026-10-23T00:00:00.000Z',
  updatedAtUtc: '2026-10-23T00:00:00.000Z',
  createdByAccountId: 'account-1',
  modifiedByAccountId: 'account-1',
};
// forge:feature:test-input:start
const input = { name: project.name, status: project.status };
const changed = { ...input, name: 'Updated review' };
const listQuery = { search: 'migration', status: 'active' as const, sortBy: 'name' as const };
const listPath = '/api/v1/projects?search=migration&status=active&sortBy=name&sortOrder=asc&after=cursor-1';
// forge:feature:test-input:end

function response(data: unknown, status = 200) {
  return new Response(JSON.stringify({ success: true, data, error: null }), {
    status,
    headers: { 'content-type': 'application/json' },
  });
}

function wrapper(queries: QueryClient) {
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queries}>{children}</QueryClientProvider>
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
    const queries = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const queryWrapper = wrapper(queries);

    const list = renderHook(() => useProjects({ ...listQuery, sortOrder: 'asc', after: 'cursor-1' }), { wrapper: queryWrapper });
    await waitFor(() => expect(list.result.current.data?.items).toEqual([project]));
    const detail = renderHook(() => useProject(project.id), { wrapper: queryWrapper });
    await waitFor(() => expect(detail.result.current.data).toEqual(project));

    expect(String(fetch.mock.calls[0][0])).toContain(listPath);
    expect(String(fetch.mock.calls[1][0])).toBe(`/api/v1/projects/${project.id}`);
  });

  it('creates, updates, and deletes projects with credentialed, CSRF-protected requests', async () => {
    document.cookie = 'starter_csrf=csrf-token; path=/';
    const fetch = vi.fn()
      .mockResolvedValueOnce(response(project, 201))
      .mockResolvedValueOnce(response({ ...project, ...changed }))
      .mockResolvedValueOnce(response(null));
    vi.stubGlobal('fetch', fetch);
    const queries = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const queryWrapper = wrapper(queries);
    const create = renderHook(() => useCreateProject(), { wrapper: queryWrapper });
    const update = renderHook(() => useUpdateProject(), { wrapper: queryWrapper });
    const remove = renderHook(() => useDeleteProject(), { wrapper: queryWrapper });

    await act(async () => create.result.current.mutateAsync(input));
    await act(async () => update.result.current.mutateAsync({ id: project.id, input: changed }));
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
