import { apiRequest } from './api-client';

export async function reportError(error: unknown): Promise<void> {
  try {
    await apiRequest('/error-reports', {
      method: 'POST',
      body: JSON.stringify({ name: error instanceof Error ? error.constructor.name : 'UnknownError', path: window.location.pathname }),
    });
  } catch {
    // Reporting must not crash the error page or retry a failed report.
  }
}
