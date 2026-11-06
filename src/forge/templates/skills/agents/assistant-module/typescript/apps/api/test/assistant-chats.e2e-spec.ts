import { spawnSync } from 'node:child_process';
import request from 'supertest';
import { beforeAll, describe, expect, it } from 'vitest';
import { apiBaseUrl, credentials } from './helpers';

// Audit: the public clean-up service and real Postgres own retention, including
// vendor checkpoint copies. Wrong cutoff, missing deleteThread, or failure to
// advance activity breaks these cases. No existing test owns optional chats.
// Fixed time is the specified production clean-up argument, not a test hook.
describe('assistant chat retention', () => {
  let accountId: string;
  beforeAll(async () => {
    const response = await request(apiBaseUrl).post('/api/v1/auth/sign-up').send(credentials()).expect(201);
    accountId = response.body.data.id as string;
  });

  function retention(ageDays: number, sendMessage = false) {
    const source = `
import 'reflect-metadata';
import { createRequire } from 'node:module';
import { NestFactory } from '@nestjs/core';
import { AppModule } from './apps/api/dist/app.module.js';
import { PrismaService } from './libs/core/server/dist/index.js';
import { AssistantChatsService, AssistantCleanup } from './libs/assistant/server/dist/index.js';
const { PostgresSaver } = createRequire(import.meta.url)('@langchain/langgraph-checkpoint-postgres');
const app = await NestFactory.createApplicationContext(AppModule, { logger: false, abortOnError: false });
try {
  const prisma = app.get(PrismaService);
  const chats = app.get(AssistantChatsService);
  const cleanup = app.get(AssistantCleanup);
  const saver = app.get(PostgresSaver);
  const membership = await prisma.membership.findUniqueOrThrow({ where: { accountId: ${JSON.stringify(accountId)} } });
  const principal = { id: membership.accountId, organisationId: membership.organisationId, email: 'retention@example.test', role: 'admin' };
  const now = new Date();
  const then = new Date(now.getTime() - ${ageDays} * 86400000);
  const chat = await chats.create(principal, then);
  const config = { configurable: { thread_id: chat.id, checkpoint_ns: '' } };
  const checkpoint = { v: 1, id: '00000000-0000-6000-8000-000000000001', ts: then.toISOString(), channel_values: { text: 'private conversation' }, channel_versions: { text: '1' }, versions_seen: {} };
  const saved = await saver.put(config, checkpoint, { source: 'input', step: -1, parents: {} }, { text: '1' });
  await saver.putWrites(saved, [['pending', 'private write']], 'task');
  const before = await saver.getTuple(config);
  ${sendMessage ? 'await chats.touch(principal, chat.id, now);' : ''}
  await cleanup.deleteExpired(now);
  const owner = await prisma.assistantChat.findUnique({ where: { id: chat.id } });
  const after = await saver.getTuple(config);
  // Check every vendor copy, not just the latest visible checkpoint.
  const copies = await prisma.$queryRawUnsafe('SELECT (SELECT count(*) FROM assistant.checkpoints WHERE thread_id = $1) + (SELECT count(*) FROM assistant.checkpoint_blobs WHERE thread_id = $1) + (SELECT count(*) FROM assistant.checkpoint_writes WHERE thread_id = $1) AS count', chat.id);
  process.stdout.write(JSON.stringify({ before: !!before, exists: !!owner, checkpoint: !!after, copies: String(copies[0].count) }));
  await saver.deleteThread(chat.id);
  await prisma.assistantChat.deleteMany({ where: { id: chat.id } });
} finally { await app.close(); }
`;
    const result = spawnSync('docker', [
      'compose', '-f', 'compose.test.yml', 'exec', '-T', 'api', 'node', '--input-type=module', '-',
    ], { input: source, encoding: 'utf8', timeout: 30_000, killSignal: 'SIGKILL' });
    expect(result.status, `${result.error?.message ?? ''}${result.stdout}${result.stderr}`).toBe(0);
    return JSON.parse(result.stdout) as { before: boolean; exists: boolean; checkpoint: boolean; copies: string };
  }

  it('a chat 31 days after its last message is deleted with its checkpoints', () => {
    expect(retention(31)).toEqual({ before: true, exists: false, checkpoint: false, copies: '0' });
  });

  it('a chat 29 days after its last message stays', () => {
    const result = retention(29);
    expect(result.before && result.exists && result.checkpoint).toBe(true);
    expect(Number(result.copies)).toBeGreaterThan(0);
  });

  it('a new message moves the 30 days', () => {
    const result = retention(31, true);
    expect(result.before && result.exists && result.checkpoint).toBe(true);
    expect(Number(result.copies)).toBeGreaterThan(0);
  });
});
