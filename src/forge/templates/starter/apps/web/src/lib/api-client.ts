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

type ApiEnvelope<T> = {
  success: true;
  data: T;
  error: null;
} | {
  success: false;
  data: null;
  error: { code: string; message: string; details: unknown; errorId?: string };
};

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
  const envelope = await response.json() as ApiEnvelope<T>;
  if (!response.ok || !envelope.success) {
    const error = envelope.success ? undefined : envelope.error;
    throw new ApiError(response.status, error?.message ?? 'The request failed. Try again.', error?.code ?? 'REQUEST_FAILED', error?.details);
  }
  return envelope.data;
}
