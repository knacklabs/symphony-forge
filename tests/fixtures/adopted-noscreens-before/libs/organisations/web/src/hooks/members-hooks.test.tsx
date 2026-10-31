import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useInvite } from './members-hooks';

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

describe('member hooks', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    document.cookie = 'starter_csrf=; Max-Age=0; path=/';
  });

  it('the invite hook keeps one Idempotency-Key until an invite succeeds', async () => {
    const failedResponse = new Response(JSON.stringify({
      success: false,
      data: null,
      error: { code: 'REQUEST_FAILED', message: 'Try again.', details: null },
    }), {
      status: 500,
      headers: { 'content-type': 'application/json' },
    });
    const fetch = vi.fn()
      .mockResolvedValueOnce(failedResponse)
      .mockResolvedValueOnce(response({ message: 'Invite sent.' }, 201))
      .mockResolvedValueOnce(response({ message: 'Invite sent.' }, 201));
    vi.stubGlobal('fetch', fetch);
    const queries = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    const invite = renderHook(() => useInvite(), { wrapper: wrapper(queries) });
    const input = { email: 'member@example.com' };

    await act(async () => {
      await expect(invite.result.current.mutateAsync(input)).rejects.toMatchObject({ status: 500 });
    });
    await act(async () => invite.result.current.mutateAsync(input));
    await act(async () => invite.result.current.mutateAsync(input));

    const keys = fetch.mock.calls.map(([, init]) => new Headers(init?.headers).get('Idempotency-Key'));
    expect(keys[0]).toBeTruthy();
    expect(keys[1]).toBe(keys[0]);
    expect(keys[2]).toBeTruthy();
    expect(keys[2]).not.toBe(keys[1]);
  });
});
