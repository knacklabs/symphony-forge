# APIs (NestJS)

How the standards page's API rules look in NestJS. Read it when your task adds or changes an
endpoint.

## Start-up

```ts
app.setGlobalPrefix('api/v1');
app.useGlobalPipes(new ValidationPipe({ whitelist: true, forbidNonWhitelisted: true, transform: true }));
app.useGlobalFilters(new AllExceptionsFilter(logger));
app.useGlobalInterceptors(new EnvelopeInterceptor());
SwaggerModule.setup('api/docs', app, SwaggerModule.createDocument(app, swaggerConfig));
```

`EnvelopeInterceptor` wraps each result as `{ success: true, data, error: null }`; the exception
filter writes `{ success: false, data: null, error: { code, message, details, errorId } }`.

## Controllers and DTOs

```ts
@ApiTags('Orders')
@Controller('orders')
export class OrderController {
  constructor(private readonly orders: OrderService) {}

  @Post(':id/cancel')
  @ApiOperation({ summary: 'Cancel an order that has not shipped.' })
  @ApiOkResponse({ type: OrderResponseDto })
  @ApiConflictResponse({ description: 'ORDER_ALREADY_SHIPPED' })
  cancel(@Param('id', ParseUUIDPipe) id: string, @CurrentAccount() account: Account) {
    return this.orders.cancel(id, account);
  }
}
```

- One controller per resource. It reads parameters, lets the pipe validate, calls one service
  method and returns a response DTO.
- Request DTOs carry class-validator rules and `@ApiProperty({ description, example })` on every
  field, with a maximum length on every string.
- Response DTOs have a static `from(record)` that picks the fields the caller may see.
- Status codes: 200 read or update, 201 create, 204 delete, 400 invalid input, 401 not signed in,
  403 not allowed, 404 not found, 409 conflict, 429 too many requests, 500 our fault.

## Lists

```ts
export class ListQueryDto {
  @IsOptional() @Type(() => Number) @IsInt() @Min(1) page = 1;
  @IsOptional() @Type(() => Number) @IsInt() @Min(1) @Max(100) limit = 20;
  @IsOptional() @IsString() sortBy?: string;
  @IsOptional() @IsIn(['asc', 'desc']) sortOrder: 'asc' | 'desc' = 'desc';
}
```

A list returns `{ items, pagination: { page, limit, totalItems, totalPages } }` as its `data`.
Allow `sortBy` only on the columns the endpoint names, since any other value reaches the query.

## Swagger

The spec is generated from the decorators, so it can't drift from the code. Every endpoint has a
summary, its success type and its error responses; every DTO field has a description and an
example; protected routes carry `@ApiBearerAuth()`.
