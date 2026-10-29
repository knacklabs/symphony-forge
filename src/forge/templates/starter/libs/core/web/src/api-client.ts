import type { ApiEnvelope } from '@app/shared-util';

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
    readonly code: string,
    readonly details: unknown,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

function csrfToken() {
  if (typeof document === 'undefined') return undefined;
  const cookie = document.cookie.split('; ').find((part) => part.startsWith('starter_csrf='));
  return cookie ? decodeURIComponent(cookie.slice('starter_csrf='.length)) : undefined;
}

export async function apiRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set('Accept', 'application/json');
  if (init.body) headers.set('Content-Type', 'application/json');
  if (init.method && init.method !== 'GET') {
    const token = csrfToken();
    if (token) headers.set('x-csrf-token', token);
  }

  const response = await fetch(`/api/v1${path}`, {
    ...init,
    headers,
    credentials: 'include',
  });
  // A proxy or gateway error page is not JSON; it still becomes an ApiError with the reply's status.
  const envelope = await response.json().catch(() => undefined) as ApiEnvelope<T> | undefined;
  if (!response.ok || !envelope?.success) {
    const error = envelope?.success ? undefined : envelope?.error;
    throw new ApiError(response.status, error?.message ?? 'The request failed. Try again.', error?.code ?? 'REQUEST_FAILED', error?.details);
  }
  return envelope.data;
}
