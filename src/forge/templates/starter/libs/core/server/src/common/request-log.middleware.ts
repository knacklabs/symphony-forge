import { AsyncLocalStorage } from 'node:async_hooks';
import type { NextFunction, Request, Response } from 'express';
import { JsonLogger } from './json-logger';

export function requestLogMiddleware(request: Request, response: Response, next: NextFunction): void {
  if (request.path.startsWith('/api/') || request.path === '/mcp' || request.path.startsWith('/mcp/')) {
    const startedAt = performance.now();
    response.once('finish', AsyncLocalStorage.bind(() => {
      const route: unknown = request.route?.path;
      new JsonLogger().log('API request', {
        method: request.method,
        route: typeof route === 'string' ? route : null,
        status: response.statusCode,
        durationMs: Math.round(performance.now() - startedAt),
      });
    }));
  }
  next();
}
