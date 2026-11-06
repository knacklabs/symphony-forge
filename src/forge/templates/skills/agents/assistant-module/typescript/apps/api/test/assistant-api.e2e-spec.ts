import { randomUUID } from 'node:crypto';
import { spawnSync } from 'node:child_process';
import request from 'supertest';
import { beforeAll, describe, expect, it } from 'vitest';
import { apiBaseUrl, credentials, csrfToken, invite } from './helpers';

type ApiClient = ReturnType<typeof request.agent>;
type SignedIn = { client: ApiClient; csrf: string };

const USER_TEXT = 'Can you check the project status?';
const ASSISTANT_TEXT = 'The project is active.';
const CONFIRM_TITLE = 'Change project status';
const CONFIRM_LINE = 'Set project status to archived';

let admin: SignedIn;
let person: SignedIn;
let otherPerson: SignedIn;
let chatId: string;
let otherChatId: string;
let chatKey: string;
let confirmId: string;
let confirmExpiresAt: string;

async function signedIn(): Promise<SignedIn> {
  const client = request.agent(apiBaseUrl);
  const response = await client.post('/api/v1/auth/sign-up').send(credentials()).expect(201);
  return { client, csrf: csrfToken(response) };
}

async function invitedMember(owner: SignedIn): Promise<SignedIn> {
  const account = credentials();
  const token = await invite(owner.client, owner.csrf, account.email);
  const client = request.agent(apiBaseUrl);
  const response = await client
    .post('/api/v1/auth/accept-invite')
    .send({ ...account, token })
    .expect(201);
  return { client, csrf: csrfToken(response) };
}

async function createChat(account: SignedIn, key: string): Promise<string> {
  const response = await account.client
    .post('/api/v1/assistant/chats')
    .set('x-csrf-token', account.csrf)
    .set('Idempotency-Key', key)
    .send({})
    .expect(201);
  return response.body.data.id as string;
}

function seedConversation(threadId: string, interruptId: string, expiresAt: string): void {
  const source = `
import 'reflect-metadata';
import { createRequire } from 'node:module';
import { NestFactory } from '@nestjs/core';
import { AppModule } from './apps/api/dist/app.module.js';
const require = createRequire(import.meta.url);
const assistantRequire = createRequire(new URL('./libs/assistant/server/package.json', import.meta.url));
const { PostgresSaver } = require('@langchain/langgraph-checkpoint-postgres');
const { HumanMessage, AIMessage, SystemMessage, ToolMessage } = assistantRequire('@langchain/core/messages');
const app = await NestFactory.createApplicationContext(AppModule, { logger: false, abortOnError: false });
try {
  const saver = app.get(PostgresSaver);
  const config = { configurable: { thread_id: ${JSON.stringify(threadId)}, checkpoint_ns: '' } };
  const checkpoint = {
    v: 1,
    id: ${JSON.stringify(randomUUID())},
    ts: new Date().toISOString(),
    channel_values: { messages: [
      new HumanMessage({ id: 'assistant-test-user-message', content: ${JSON.stringify(USER_TEXT)} }),
      new AIMessage({ id: 'assistant-test-ai-message', content: ${JSON.stringify(ASSISTANT_TEXT)} }),
      new SystemMessage({ content: 'system-only instruction' }),
      new ToolMessage({ tool_call_id: 'assistant-test-tool-call', content: 'private tool result' }),
    ] },
    channel_versions: { messages: '1' },
    versions_seen: {},
  };
  const saved = await saver.put(config, checkpoint, { source: 'input', step: -1, parents: {} }, { messages: '1' });
  await saver.putWrites(saved, [['__interrupt__', [{
    id: ${JSON.stringify(interruptId)},
    value: {
      title: ${JSON.stringify(CONFIRM_TITLE)},
      lines: [${JSON.stringify(CONFIRM_LINE)}],
      expiresAt: ${JSON.stringify(expiresAt)},
    },
  }]]], ${JSON.stringify(randomUUID())});
} finally {
  await app.close();
}
`;
  const result = spawnSync('docker', [
    'compose', '-f', 'compose.test.yml', 'exec', '-T', 'api', 'node', '--input-type=module', '-',
  ], { input: source, encoding: 'utf8', timeout: 30_000, killSignal: 'SIGKILL' });
  expect(result.status, `${result.error?.message ?? ''}${result.stdout}${result.stderr}`).toBe(0);
}

describe('assistant chat API', () => {
  beforeAll(async () => {
    admin = await signedIn();
    person = await invitedMember(admin);
    otherPerson = await invitedMember(admin);
    chatKey = randomUUID();
    chatId = await createChat(person, chatKey);
    otherChatId = await createChat(otherPerson, randomUUID());
    confirmId = randomUUID();
    confirmExpiresAt = new Date(Date.now() + 15 * 60 * 1000).toISOString();
    seedConversation(chatId, confirmId, confirmExpiresAt);
  }, 60_000);

  it('a person lists only their own chats', async () => {
    // Audit: real HTTP auth and Postgres own chat privacy. Retention tests do not
    // cover a same-organisation member or admin reading another person's chat.
    // No test-only production seam is needed.
    const replayedChatId = await createChat(person, chatKey);
    expect(replayedChatId).toBe(chatId);

    const secondChatId = await createChat(person, randomUUID());
    const firstPage = await person.client.get('/api/v1/assistant/chats?limit=1').expect(200);
    const firstItems = firstPage.body.data.items as { id: string }[];
    expect(firstItems).toHaveLength(1);
    expect(firstPage.body.data.paging).toMatchObject({ limit: 1, total: 2, totalCapped: false });
    expect(firstPage.body.data.paging.nextCursor).toEqual(expect.any(String));

    const nextCursor = encodeURIComponent(firstPage.body.data.paging.nextCursor as string);
    const secondPage = await person.client
      .get(`/api/v1/assistant/chats?limit=1&after=${nextCursor}`)
      .expect(200);
    const secondItems = secondPage.body.data.items as { id: string }[];
    expect(secondItems).toHaveLength(1);
    expect(secondPage.body.data.paging).toMatchObject({ limit: 1, nextCursor: null, total: 2 });
    expect(secondPage.body.data.paging.previousCursor).toEqual(expect.any(String));
    expect(firstItems[0].id).toBe(secondChatId);
    expect(secondItems[0].id).toBe(chatId);
    expect([firstItems[0].id, secondItems[0].id]).not.toContain(otherChatId);

    const previousCursor = encodeURIComponent(secondPage.body.data.paging.previousCursor as string);
    const back = await person.client
      .get(`/api/v1/assistant/chats?limit=1&before=${previousCursor}`)
      .expect(200);
    expect((back.body.data.items as { id: string }[]).map(({ id }) => id)).toEqual([firstItems[0].id]);

    await person.client
      .post('/api/v1/assistant/chats')
      .set('x-csrf-token', person.csrf)
      .set('Idempotency-Key', randomUUID())
      .send({ unexpected: true })
      .expect(400);
    await person.client.get('/api/v1/assistant/chats?unexpected=true').expect(400);
    await person.client.get('/api/v1/assistant/chats?after=invalid').expect(400).expect(({ body }) => {
      expect(body).toMatchObject({
        success: false,
        data: null,
        error: {
          code: 'VALIDATION_ERROR',
          message: 'The chat cursor is not valid. Load the list again.',
          details: {
            fieldErrors: [{ field: 'after', reason: 'Load the list again to get a valid cursor.' }],
          },
        },
      });
    });
    await request(apiBaseUrl).get('/api/v1/assistant/chats').expect(401);
  });

  it('a person reads messages and a pending confirmation', async () => {
    const response = await person.client.get(`/api/v1/assistant/chats/${chatId}`).expect(200);
    expect(response.body.data.messages).toEqual([
      { role: 'user', text: USER_TEXT },
      { role: 'assistant', text: ASSISTANT_TEXT },
    ]);
    expect(response.body.data.confirm).toEqual({
      confirmId,
      title: CONFIRM_TITLE,
      lines: [CONFIRM_LINE],
      expiresAt: confirmExpiresAt,
    });
    expect(JSON.stringify(response.body.data)).not.toContain('system-only instruction');
    expect(JSON.stringify(response.body.data)).not.toContain('private tool result');
  });

  it('another person and an admin get 404 for a chat', async () => {
    await otherPerson.client.get(`/api/v1/assistant/chats/${chatId}`).expect(404);
    await admin.client.get(`/api/v1/assistant/chats/${chatId}`).expect(404);
  });
});
