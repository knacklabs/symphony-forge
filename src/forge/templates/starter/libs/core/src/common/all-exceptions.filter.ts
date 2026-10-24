import { randomUUID } from 'node:crypto';
import { ArgumentsHost, Catch, ExceptionFilter, HttpException } from '@nestjs/common';
import type { Request, Response } from 'express';
import { JsonLogger } from './json-logger';

type ApiErrorBody = { code: string; message: string; details: unknown; errorId: string };
type ErrorResponse = { success: false; data: null; error: ApiErrorBody };

@Catch()
export class AllExceptionsFilter implements ExceptionFilter {
  constructor(private readonly logger: JsonLogger) {}

  catch(exception: unknown, host: ArgumentsHost): void {
    const http = host.switchToHttp();
    const response = http.getResponse<Response>();
    const request = http.getRequest<Request>();
    const status = exception instanceof HttpException ? exception.getStatus() : 500;
    const errorId = randomUUID();
    const exceptionBody = exception instanceof HttpException ? exception.getResponse() : null;
    const body = typeof exceptionBody === 'object' && exceptionBody !== null ? exceptionBody : {};
    const suppliedCode = 'code' in body && typeof body.code === 'string' ? body.code : undefined;
    const suppliedMessage = 'message' in body && typeof body.message === 'string' ? body.message : undefined;
    const details = 'details' in body ? body.details : null;
    const error: ApiErrorBody = {
      code: suppliedCode ?? this.codeFor(status),
      message: status >= 500 ? 'Something went wrong. Try again.' : suppliedMessage ?? this.messageFor(status),
      details: status < 500 ? details : null,
      errorId,
    };
    const context = { errorId, status, method: request.method, path: request.path };
    if (status >= 500) this.logger.error('API request failed', 'AllExceptionsFilter', context);
    else this.logger.debug('API request rejected', 'AllExceptionsFilter', context);

    response.status(status).json({ success: false, data: null, error } satisfies ErrorResponse);
  }

  private codeFor(status: number): string {
    return ({ 400: 'BAD_REQUEST', 401: 'UNAUTHENTICATED', 403: 'FORBIDDEN', 404: 'NOT_FOUND', 409: 'CONFLICT', 429: 'RATE_LIMITED' } as Record<number, string>)[status]
      ?? 'INTERNAL_SERVER_ERROR';
  }

  private messageFor(status: number): string {
    return ({
      400: 'Check the request and try again.',
      401: 'Sign in to continue.',
      403: 'You do not have permission to do that.',
      404: 'The requested item was not found.',
      409: 'That change conflicts with existing data.',
      429: 'Too many requests. Wait and try again.',
    } as Record<number, string>)[status] ?? 'Something went wrong. Try again.';
  }
}
