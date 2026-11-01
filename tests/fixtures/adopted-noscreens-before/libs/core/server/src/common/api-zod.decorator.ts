import { applyDecorators } from '@nestjs/common';
import { ApiBody, ApiQuery } from '@nestjs/swagger';
import type { SchemaObject } from '@nestjs/swagger/dist/interfaces/open-api-spec.interface';
import { z } from 'zod';

export function ApiZodBody(schema: z.ZodType): MethodDecorator {
  const document = z.toJSONSchema(schema, { io: 'input', target: 'openapi-3.0' });
  return ApiBody({ schema: document as SchemaObject });
}

export function ApiZodQuery(schema: z.ZodObject): MethodDecorator {
  const document = z.toJSONSchema(schema, { io: 'input', target: 'openapi-3.0' });
  return applyDecorators(...Object.entries(document.properties ?? {}).map(([name, field]) =>
    ApiQuery({
      name,
      description: (field as SchemaObject).description,
      required: document.required?.includes(name) ?? false,
      schema: field as SchemaObject,
    }),
  ));
}
