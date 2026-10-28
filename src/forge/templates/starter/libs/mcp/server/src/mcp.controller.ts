import { createHash, randomUUID } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { All, Controller, Headers, Inject, Req, Res, UnauthorizedException } from '@nestjs/common';
import { SkipThrottle, ThrottlerStorage, type ThrottlerStorage as ThrottlerStorageType } from '@nestjs/throttler';
import { Prisma } from '@prisma/client';
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StreamableHTTPServerTransport } from '@modelcontextprotocol/sdk/server/streamableHttp.js';
import { CallToolRequestSchema, ListToolsRequestSchema } from '@modelcontextprotocol/sdk/types.js';
import type { Request, Response } from 'express';
import { callTool, ErrorReporter, listTools, PrismaService, Public, ToolError, toolFailure, type AccountPrincipal, type ToolContext } from '@app/core-server';
import { ORGANISATIONS_API, type OrganisationsApi } from '@app/organisations-contracts';

type Agent = NonNullable<Awaited<ReturnType<OrganisationsApi['agentForKey']>>>;
const CALLS_PER_MINUTE = 120;

@Controller('mcp')
@Public()
@SkipThrottle()
export class McpController {
  constructor(
    @Inject(ORGANISATIONS_API) private readonly organisations: OrganisationsApi,
    private readonly prisma: PrismaService,
    @Inject(ThrottlerStorage) private readonly throttle: ThrottlerStorageType,
    private readonly errorReporter: ErrorReporter,
  ) {}

  @All()
  async handle(
    @Headers('authorization') authorization: string | undefined,
    @Req() request: Request,
    @Res() response: Response,
  ): Promise<void> {
    const match = /^Bearer ([^\s]+)$/i.exec(authorization ?? '');
    if (!match) {
      response.setHeader('WWW-Authenticate', 'Bearer');
      throw this.unauthorized();
    }

    const keyHash = createHash('sha256').update(match[1]).digest('hex');
    const agent = await this.organisations.agentForKey(keyHash);
    if (!agent) {
      response.setHeader('WWW-Authenticate', 'Bearer');
      throw this.unauthorized();
    }

    const context = this.context(agent);
    const server = new Server({ name: this.appName(), version: '1.0.0' }, { capabilities: { tools: {} } });
    server.setRequestHandler(ListToolsRequestSchema, async () => ({ tools: listTools(context) }));
    server.setRequestHandler(CallToolRequestSchema, async ({ params }) => {
      const rate = await this.throttle.increment(`mcp:${keyHash}`, 60_000, CALLS_PER_MINUTE, 60_000, 'mcp');
      if (rate.isBlocked) {
        const retryAfterSeconds = Math.max(1, Math.min(60, rate.timeToBlockExpire));
        return toolFailure(new ToolError('rate_limited', `This agent key made ${CALLS_PER_MINUTE} calls in the last minute. Wait ${retryAfterSeconds} seconds and try again.`, true, retryAfterSeconds));
      }
      return callTool(params.name, params.arguments ?? {}, context);
    });

    const transport = new StreamableHTTPServerTransport({ sessionIdGenerator: undefined, enableJsonResponse: true });
    response.once('close', () => {
      void server.close().catch((error: unknown) => this.reportError(error));
    });
    await server.connect(transport);
    await transport.handleRequest(request, response, request.body);
  }

  private context(agent: Agent): ToolContext {
    return {
      account: agent.principal,
      deleteAndRestore: agent.deleteAndRestore,
      createOnce: (feature, key, create) => this.createOnce(agent.principal, feature, key, create),
      reportError: (error) => this.reportError(error),
    };
  }

  private async createOnce(
    account: AccountPrincipal,
    tool: string,
    key: string,
    create: Parameters<ToolContext['createOnce']>[2],
  ): Promise<string> {
    const where = { accountId_tool_key: { accountId: account.id, tool, key } };
    const existing = await this.prisma.idempotencyKey.findUnique({ where });
    if (existing) return existing.itemId;

    try {
      return await create((tx, itemId) => tx.idempotencyKey.create({
        data: { accountId: account.id, organisationId: account.organisationId, tool, key, itemId },
      }).then(() => undefined));
    } catch (error) {
      if (!(error instanceof Prisma.PrismaClientKnownRequestError) || error.code !== 'P2002') throw error;
      const winner = await this.prisma.idempotencyKey.findUnique({ where });
      if (!winner) throw error;
      return winner.itemId;
    }
  }

  private reportError(error: unknown): void {
    this.errorReporter.report({
      source: 'api',
      name: error instanceof Error ? error.constructor.name : 'UnknownError',
      method: 'POST',
      path: '/mcp',
      status: 500,
      errorId: randomUUID(),
    });
  }

  private appName(): string {
    const manifest: unknown = JSON.parse(readFileSync(join(process.cwd(), 'package.json'), 'utf8'));
    if (typeof manifest !== 'object' || manifest === null || !('name' in manifest) || typeof manifest.name !== 'string') {
      throw new Error('The app package.json must have a name.');
    }
    return manifest.name;
  }

  private unauthorized(): UnauthorizedException {
    return new UnauthorizedException({ code: 'UNAUTHENTICATED', message: 'Send a valid agent key.', details: null });
  }
}
