# APIs (NestJS)

How the standards page's API rules look in NestJS. Read it when your task adds or changes an
endpoint.

An app made before this layout keeps its own folders and schema; follow the folders it has.

## Start-up

```ts
app.setGlobalPrefix('api/v1');
app.useGlobalFilters(new AllExceptionsFilter(logger));
app.useGlobalInterceptors(new EnvelopeInterceptor());
SwaggerModule.setup('api/docs', app, SwaggerModule.createDocument(app, swaggerConfig));
```

`EnvelopeInterceptor` wraps each result as `{ success: true, data: result ?? null, error: null }`,
so a delete, which returns nothing, still gets a body; the exception filter writes
`{ success: false, data: null, error: { code, message, details, errorId } }`.

## Controllers and DTOs

```ts
// common/api-envelope.decorator.ts: Swagger shows the envelope the interceptor really sends.
export const ApiEnvelope = (model: Type<unknown>) =>
  applyDecorators(
    ApiExtraModels(model),
    ApiOkResponse({
      schema: {
        properties: {
          success: { type: 'boolean', example: true },
          data: { $ref: getSchemaPath(model) },
          error: { type: 'object', nullable: true, example: null },
        },
      },
    }),
  );

@ApiTags('Orders')
@Controller('orders')
export class OrderController {
  constructor(private readonly orders: OrderService) {}

  @Post(':id/cancel')
  @HttpCode(200)  // an action changes an existing order, so 200, not Nest's default 201 for POST
  @ApiOperation({ summary: 'Cancel an order that has not shipped.' })
  @ApiEnvelope(OrderResponseDto)
  @ApiConflictResponse({ description: 'ORDER_ALREADY_SHIPPED' })
  cancel(@Param('id', ParseUUIDPipe) id: string, @CurrentAccount() account: Account) {
    return this.orders.cancel(id, account);
  }
}
```

- One controller per resource. It reads parameters, lets the pipe validate, calls one service
  method and returns a response DTO.
- Request input is a zod schema in `@app/<module>-contracts`: one for each body and one for each list query,
  and the web form uses the same schema. Check it with `@Body(new ZodValidationPipe(schema))` or
  `@Query(new ZodValidationPipe(schema))`, and document it with `@ApiZodBody(schema)` or
  `@ApiZodQuery(schema)`. Each schema is `.strict()`, gives every string a maximum length, and
  gives every field `.meta({ description, example })`. A request schema has no `.transform()`,
  because the documentation cannot show one.
- Response DTOs have a static `from(record)` that picks the fields the caller may see.
- Status codes: 200 read, update or delete (a delete answers `{ success: true, data: null,
  error: null }`, never a bodiless 204), 201 create, 400 invalid input, 401 not signed in,
  403 not allowed, 404 not found (including another account's record), 409 conflict, 429 too many
  requests, 500 our fault.

A create sent again with the same `Idempotency-Key` answers 201 with the first item.
Document the header with `@ApiHeader`.

## Lists

```ts
import { z } from 'zod';

// In @app/projects-contracts; name the allowed sort fields for each resource.
export const listQuerySchema = z.object({
  page: z.coerce.number().int().min(1).default(1)
    .meta({ description: 'The one-based page number.', example: 1 }),
  limit: z.coerce.number().int().min(1).max(100).default(20)
    .meta({ description: 'The number of projects per page, up to 100.', example: 20 }),
  sortBy: z.enum(['name', 'status', 'createdAtUtc', 'updatedAtUtc']).default('createdAtUtc')
    .meta({ description: 'The project field used to sort the list.', example: 'createdAtUtc' }),
  sortOrder: z.enum(['asc', 'desc']).default('desc')
    .meta({ description: 'The sort direction.', example: 'desc' }),
}).strict();
```

A list returns `{ items, pagination: { page, limit, totalItems, totalPages } }` as its `data`.
Allow `sortBy` only on the columns the endpoint names, since any other value reaches the query.

In an app that has `libs/organisations`, each list has a `GET /<list>/export` route. It uses
`sendCsv` from `@app/core-server` to export every matching row in the caller's organisation, with the
same permissions as the list. The response is a CSV download, rather than the JSON envelope.

## Swagger

The spec is generated from the decorators, so it can't drift from the code. Every endpoint has a
summary, its success type inside the envelope (`@ApiEnvelope`) and its error responses; every
request schema field and response DTO field has a description and an example; protected routes
carry `@ApiBearerAuth()`.

Request documentation comes from the same schema the pipe checks. If the app does not have the
decorators, copy this into `libs/core/server/src/common/api-zod.decorator.ts` and export them from
`@app/core-server`:

```ts
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
      required: document.required?.includes(name) ?? false,
      schema: field as SchemaObject,
    }),
  ));
}
```

- Give each endpoint a 1-4 line description besides its summary.
- Use one PascalCase tag per module, never `Misc` or `General`.
- Document every path and query param with its type and whether it is required.
- Type error responses with an `ErrorResponseDto`, and keep every error code in one error-code list.

## In an app set up before this release

An app's current request DTOs and its global ValidationPipe stay as they are, and the review does
not flag them. In an app with zod, new request input follows this page. An app without zod keeps
its own validation for new code too.
