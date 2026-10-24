import { randomUUID } from 'node:crypto';
import { AsyncLocalStorage } from 'node:async_hooks';
import type { NextFunction, Request, Response } from 'express';

export const correlationStorage = new AsyncLocalStorage<string>();

export function correlationMiddleware(request: Request, response: Response, next: NextFunction): void {
  const incoming = request.header('x-correlation-id');
  const correlationId = incoming && incoming.length <= 128 ? incoming : randomUUID();
  response.setHeader('x-correlation-id', correlationId);
  correlationStorage.run(correlationId, next);
}
