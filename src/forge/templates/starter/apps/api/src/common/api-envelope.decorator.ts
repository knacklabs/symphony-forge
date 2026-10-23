import { applyDecorators, type Type } from '@nestjs/common';
import { ApiExtraModels, ApiResponse, getSchemaPath } from '@nestjs/swagger';
import { ApiErrorResponseDto } from './api-response.dto';

export function ApiEnvelope(model: Type<unknown>, status: number): MethodDecorator {
  return applyDecorators(
    ApiExtraModels(model),
    ApiResponse({
      status,
      schema: {
        type: 'object',
        required: ['success', 'data', 'error'],
        properties: {
          success: { type: 'boolean', example: true },
          data: { $ref: getSchemaPath(model) },
          error: { type: 'object', nullable: true, example: null },
        },
      },
    }),
  );
}

export function ApiErrors(...statuses: number[]): MethodDecorator {
  return applyDecorators(
    ApiExtraModels(ApiErrorResponseDto),
    ...statuses.map((status) => ApiResponse({ status, type: ApiErrorResponseDto })),
  );
}
