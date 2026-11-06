import { Body, Controller, Get, Headers, Param, ParseUUIDPipe, Post, Query } from '@nestjs/common';
import { ApiCookieAuth, ApiHeader, ApiOperation, ApiParam, ApiResponse, ApiTags } from '@nestjs/swagger';
import type { SchemaObject } from '@nestjs/swagger/dist/interfaces/open-api-spec.interface';
import { z } from 'zod';
import { ApiErrors, ApiZodBody, ApiZodQuery, CurrentAccount, RetryKeys, retryKeySchema,
  ZodValidationPipe, type AccountPrincipal } from '@app/core-server';
import { chatListQuerySchema, chatListSchema, chatSchema, createChatSchema, type ChatListQuery } from '@app/assistant-contracts';
import { AssistantChatsService } from './assistant.chats.service';

const envelope = (schema: z.ZodType) => z.toJSONSchema(z.object({
  success: z.literal(true), data: schema, error: z.null(),
}), { target: 'openapi-3.0' }) as SchemaObject;

@ApiTags('Assistant')
@ApiCookieAuth('session')
@Controller('assistant/chats')
export class AssistantChatsController {
  constructor(private readonly chats: AssistantChatsService, private readonly retryKeys: RetryKeys) {}

  @Post()
  @ApiOperation({ summary: 'Start a private chat.', description: 'Only the signed-in person can read this chat.' })
  @ApiZodBody(createChatSchema)
  @ApiHeader({ name: 'Idempotency-Key', required: false, description: 'Reuse this key to return the same chat after a retry.' })
  @ApiResponse({ status: 201, schema: envelope(z.object({ id: z.uuid() })) })
  @ApiErrors(400, 401, 403)
  async create(@CurrentAccount() account: AccountPrincipal,
    @Body(new ZodValidationPipe(createChatSchema)) _input: Record<string, never>,
    @Headers('idempotency-key') idempotencyKey?: string) {
    const key = new ZodValidationPipe(retryKeySchema.optional(), 'Idempotency-Key').transform(idempotencyKey);
    const id = key ? await this.retryKeys.once(account, 'assistant_chats_create', key,
      async (afterCreate) => (await this.chats.create(account, new Date(), { afterCreate })).id)
      : (await this.chats.create(account)).id;
    return { id: (await this.chats.ownChat(account, id)).id };
  }

  @Get()
  @ApiOperation({ summary: 'List your private chats.', description: 'Chats appear newest first. Other people’s chats never appear.' })
  @ApiZodQuery(chatListQuerySchema)
  @ApiResponse({ status: 200, schema: envelope(chatListSchema) })
  @ApiErrors(400, 401)
  list(@CurrentAccount() account: AccountPrincipal,
    @Query(new ZodValidationPipe(chatListQuerySchema)) query: ChatListQuery) {
    return this.chats.list(account, query);
  }

  @Get(':id')
  @ApiOperation({ summary: 'Read your private chat.', description: 'Returns messages and the open confirm card. Another person’s chat returns 404, including for an admin.' })
  @ApiParam({ name: 'id', description: 'The chat identifier.', example: 'b3e1d349-1d8e-481c-8c69-99ea576f94c7' })
  @ApiResponse({ status: 200, schema: envelope(chatSchema) })
  @ApiErrors(400, 401, 404)
  get(@CurrentAccount() account: AccountPrincipal, @Param('id', ParseUUIDPipe) id: string) {
    return this.chats.get(account, id);
  }
}
