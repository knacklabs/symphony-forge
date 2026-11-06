import { randomUUID } from 'node:crypto';
import { Body, Controller, Headers, HttpCode, Param, ParseUUIDPipe, Post, Res } from '@nestjs/common';
import { ApiCookieAuth, ApiHeader, ApiOperation, ApiParam, ApiResponse, ApiTags } from '@nestjs/swagger';
import type { Response } from 'express';
import { assistantMessageSchema, confirmDecisionSchema, type ConfirmDecision, type StreamEvent } from '@app/assistant-contracts';
import { ApiErrors, ApiZodBody, CurrentAccount, ErrorReporter, retryKeySchema, ZodValidationPipe,
  type AccountPrincipal } from '@app/core-server';
import { AssistantTurn } from './assistant.turn';

@ApiTags('Assistant')
@ApiCookieAuth('session')
@Controller('assistant/chats/:id')
export class AssistantTurnController {
  constructor(private readonly turns: AssistantTurn, private readonly errors: ErrorReporter) {}

  @Post('messages')
  @HttpCode(200)
  @ApiOperation({ summary: 'Ask the assistant a question.', description: 'Streams text, typed blocks and a confirm card before any change. A retry key starts one turn only.' })
  @ApiParam({ name: 'id', description: 'Your private chat identifier.', example: 'b3e1d349-1d8e-481c-8c69-99ea576f94c7' })
  @ApiHeader({ name: 'Idempotency-Key', required: true, description: 'Reuse this key when resending the same message.' })
  @ApiZodBody(assistantMessageSchema)
  @ApiResponse({ status: 200, description: 'Events: text, block, confirm, limit, error and done.', content: { 'text/event-stream': { schema: { type: 'string' } } } })
  @ApiErrors(400, 401, 403, 404, 409)
  async message(@CurrentAccount() account: AccountPrincipal, @Param('id', ParseUUIDPipe) id: string,
    @Body(new ZodValidationPipe(assistantMessageSchema)) input: { text: string },
    @Headers('idempotency-key') key: string, @Res() response: Response): Promise<void> {
    const validatedKey = new ZodValidationPipe(retryKeySchema, 'Idempotency-Key').transform(key);
    await this.stream(response, (emit) => this.turns.message(account, id, input.text, validatedKey, emit));
  }

  @Post('confirm')
  @HttpCode(200)
  @ApiOperation({ summary: 'Confirm or cancel the open change.', description: 'Resumes the answer. Only the chat owner can decide, and a repeated confirm saves no second change.' })
  @ApiParam({ name: 'id', description: 'Your private chat identifier.', example: 'b3e1d349-1d8e-481c-8c69-99ea576f94c7' })
  @ApiZodBody(confirmDecisionSchema)
  @ApiResponse({ status: 200, description: 'Events: text, block, confirm, limit, error and done.', content: { 'text/event-stream': { schema: { type: 'string' } } } })
  @ApiErrors(400, 401, 403, 404, 409)
  async confirm(@CurrentAccount() account: AccountPrincipal, @Param('id', ParseUUIDPipe) id: string,
    @Body(new ZodValidationPipe(confirmDecisionSchema)) input: ConfirmDecision, @Res() response: Response): Promise<void> {
    await this.stream(response, (emit) => this.turns.confirm(account, id, input, emit));
  }

  private async stream(response: Response, run: (emit: (event: StreamEvent) => void) => Promise<void>): Promise<void> {
    const emit = (event: StreamEvent) => {
      if (response.destroyed || response.writableEnded) return;
      if (!response.headersSent) {
        response.status(200).set({ 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no' });
        response.flushHeaders();
      }
      response.write(`event: ${event.event}\ndata: ${JSON.stringify(event.data)}\n\n`);
    };
    try { await run(emit); }
    catch (error) {
      if (!response.headersSent) throw error;
      this.errors.report({ errorId: randomUUID(), name: 'AssistantTurnError', source: 'api', path: '/api/v1/assistant/chats/:id' });
      emit({ event: 'error', data: { message: 'The assistant could not finish this answer. Try a new message.' } });
      emit({ event: 'done', data: {} });
    }
    response.end();
  }
}
