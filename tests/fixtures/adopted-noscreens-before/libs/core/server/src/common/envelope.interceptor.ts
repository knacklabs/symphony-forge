import { CallHandler, ExecutionContext, Injectable, NestInterceptor } from '@nestjs/common';
import { map, Observable } from 'rxjs';
import type { ApiEnvelope } from '@app/shared-util';

@Injectable()
export class EnvelopeInterceptor implements NestInterceptor {
  intercept(_context: ExecutionContext, next: CallHandler): Observable<ApiEnvelope<unknown>> {
    return next.handle().pipe(map((data: unknown): ApiEnvelope<unknown> => ({ success: true, data: data ?? null, error: null })));
  }
}
