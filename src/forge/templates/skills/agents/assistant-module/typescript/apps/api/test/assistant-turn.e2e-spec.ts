import { createHash, randomUUID } from 'node:crypto';
import { spawnSync } from 'node:child_process';
import request from 'supertest';
import { beforeAll, describe, expect, it, vi } from 'vitest';
import { apiBaseUrl, credentials, csrfToken, invite, logEvents } from './helpers';

// Audit: this suite owns the real assistant message and confirm HTTP boundary,
// including checkpoint state, project writes, permissions, cost and logs.
// It fails when a model result reaches the wrong stream block, a write runs
// before confirmation, an identity or permission leaks, or a replay duplicates
// work. Chat and model suites cover storage and settings, not these turns.
// The provider is faked only at its OpenAI HTTP edge; the app and database run.

type ApiClient = ReturnType<typeof request.agent>;
type SignedIn = { client: ApiClient; csrf: string; id: string; email: string };
type StreamEvent = { event: string; data: Record<string, unknown> };

const LIMIT_LINE = 'The assistant has reached its spending limit. Try again next month.';
const CONFIRM_TITLE = 'Create project';
const PROVIDER_URL = process.env.ASSISTANT_TEST_PROVIDER_URL;

let admin: SignedIn;
let person: SignedIn;
let sameOrgTeammate: SignedIn;
let otherPerson: SignedIn;
let personProjectId: string;
let personProjectName: string;
let otherProjectName: string;
let deletedProjectName: string;

async function signedIn(): Promise<SignedIn> {
  const client = request.agent(apiBaseUrl);
  const account = credentials();
  const response = await client.post('/api/v1/auth/sign-up').send(account).expect(201);
  return { client, csrf: csrfToken(response), id: response.body.data.id as string, email: account.email };
}

async function invitedMember(owner: SignedIn): Promise<SignedIn> {
  const account = credentials();
  const token = await invite(owner.client, owner.csrf, account.email);
  const client = request.agent(apiBaseUrl);
  const response = await client.post('/api/v1/auth/accept-invite').send({ ...account, token }).expect(201);
  return { client, csrf: csrfToken(response), id: response.body.data.id as string, email: account.email };
}

async function createChat(account: SignedIn): Promise<string> {
  const response = await account.client.post('/api/v1/assistant/chats')
    .set('x-csrf-token', account.csrf)
    .set('Idempotency-Key', randomUUID())
    .send({}).expect(201);
  return response.body.data.id as string;
}

async function createProject(account: SignedIn, name: string): Promise<string> {
  const response = await account.client.post('/api/v1/projects')
    .set('x-csrf-token', account.csrf)
    .send({ name, status: 'active' }).expect(201);
  return response.body.data.id as string;
}

async function deleteProject(account: SignedIn, id: string): Promise<void> {
  await account.client.delete(`/api/v1/projects/${id}`).set('x-csrf-token', account.csrf).expect(200);
}

function parseEvents(body: string): StreamEvent[] {
  return body.split(/\r?\n\r?\n/).flatMap((chunk) => {
    const event = chunk.match(/^event: (.+)$/m)?.[1];
    const data = chunk.match(/^data: (.+)$/m)?.[1];
    if (!event || !data) return [];
    const parsed: unknown = JSON.parse(data);
    return typeof parsed === 'object' && parsed !== null
      ? [{ event, data: parsed as Record<string, unknown> }]
      : [];
  });
}

async function ask(account: SignedIn, chatId: string, text: string, key = randomUUID()) {
  const response = await account.client.post(`/api/v1/assistant/chats/${chatId}/messages`)
    .set('x-csrf-token', account.csrf)
    .set('Idempotency-Key', key)
    .set('Accept', 'text/event-stream')
    .send({ text }).expect(200);
  expect(response.headers['content-type']).toContain('text/event-stream');
  return { response, events: parseEvents(response.text) };
}

async function decide(account: SignedIn, chatId: string, confirmId: string, decision: 'confirm' | 'cancel') {
  const response = await account.client.post(`/api/v1/assistant/chats/${chatId}/confirm`)
    .set('x-csrf-token', account.csrf)
    .set('Accept', 'text/event-stream')
    .send({ confirmId, decision }).expect(200);
  expect(response.headers['content-type']).toContain('text/event-stream');
  return { response, events: parseEvents(response.text) };
}

function deltas(events: StreamEvent[]): string {
  return events.flatMap(({ event, data }) => event === 'text' && typeof data.delta === 'string' ? [data.delta] : []).join('');
}

function blocks(events: StreamEvent[]): Record<string, unknown>[] {
  return events.flatMap(({ event, data }) => event === 'block' ? [data] : []);
}

function confirmations(events: StreamEvent[]): Record<string, unknown>[] {
  return events.flatMap(({ event, data }) => event === 'confirm' ? [data] : []);
}

function runInApi(source: string): string {
  const result = spawnSync('docker', [
    'compose', '-f', 'compose.test.yml', 'exec', '-T', 'api', 'node', '--input-type=module', '-',
  ], { input: source, encoding: 'utf8', timeout: 30_000, killSignal: 'SIGKILL' });
  expect(result.status, `${result.error?.message ?? ''}${result.stdout}${result.stderr}`).toBe(0);
  return result.stdout;
}

async function projectSearch(account: SignedIn) {
  return account.client.get('/api/v1/projects?sortBy=name&sortOrder=asc').expect(200);
}

async function projectNames(account: SignedIn): Promise<string[]> {
  const response = await projectSearch(account);
  return (response.body.data.items as { name: string }[]).map(({ name }) => name);
}

function writePrompt(caseName: string, name: string): string {
  return `${caseName} ${JSON.stringify({ name, status: 'active' })}`;
}

async function startWrite(account: SignedIn, caseName: string, name: string) {
  const chatId = await createChat(account);
  const { events } = await ask(account, chatId, writePrompt(caseName, name));
  const cards = confirmations(events);
  expect(cards).toHaveLength(1);
  const card = cards[0];
  expect(card).toMatchObject({
    title: CONFIRM_TITLE,
    lines: expect.arrayContaining([`name: ${name}`, 'status: active']),
    expiresAt: expect.any(String),
    confirmId: expect.any(String),
  });
  return { chatId, confirmId: card.confirmId as string };
}

async function providerCalls(caseName: string): Promise<number> {
  if (!PROVIDER_URL) throw new Error('The test provider URL is not set.');
  const url = new URL('/calls', PROVIDER_URL);
  url.searchParams.set('case', caseName);
  const response = await fetch(url);
  expect(response.ok).toBe(true);
  const result: unknown = await response.json();
  expect(result).toEqual(expect.objectContaining({ count: expect.any(Number) }));
  return (result as { count: number }).count;
}

async function releaseProvider(caseName: string): Promise<void> {
  if (!PROVIDER_URL) throw new Error('The test provider URL is not set.');
  const url = new URL('/release', PROVIDER_URL);
  url.searchParams.set('case', caseName);
  const response = await fetch(url, { method: 'POST' });
  expect(response.ok).toBe(true);
}

async function hasCheckpoint(chatId: string): Promise<boolean> {
  const source = `
import 'reflect-metadata';
import { createRequire } from 'node:module';
import { NestFactory } from '@nestjs/core';
import { AppModule } from './apps/api/dist/app.module.js';
const require = createRequire(import.meta.url);
const assistantRequire = createRequire(new URL('./libs/assistant/server/package.json', import.meta.url));
const { PostgresSaver } = assistantRequire('@langchain/langgraph-checkpoint-postgres');
const app = await NestFactory.createApplicationContext(AppModule, { logger: false, abortOnError: false });
try {
  const tuple = await app.get(PostgresSaver).getTuple({ configurable: { thread_id: ${JSON.stringify(chatId)} } });
  process.stdout.write(JSON.stringify({ exists: tuple !== null && tuple !== undefined }));
} finally { await app.close(); }
`;
  return (JSON.parse(runInApi(source)) as { exists: boolean }).exists;
}

async function usageRows(chatId: string): Promise<{
  accountId: string; inputTokens: number; outputTokens: number; costMicros: string;
}[]> {
  const source = `
import 'reflect-metadata';
import { NestFactory } from '@nestjs/core';
import { AppModule } from './apps/api/dist/app.module.js';
import { PrismaService } from './libs/core/server/dist/index.js';
const app = await NestFactory.createApplicationContext(AppModule, { logger: false, abortOnError: false });
try {
  const rows = await app.get(PrismaService).assistantUsage.findMany({
    where: { chatId: ${JSON.stringify(chatId)} },
    select: { accountId: true, inputTokens: true, outputTokens: true, costMicros: true },
  });
  process.stdout.write(JSON.stringify(rows.map((row) => ({ ...row, costMicros: String(row.costMicros) }))));
} finally { await app.close(); }
`;
  return JSON.parse(runInApi(source)) as {
    accountId: string; inputTokens: number; outputTokens: number; costMicros: string;
  }[];
}

function expireConfirm(chatId: string): void {
  const source = `
import 'reflect-metadata';
import { createRequire } from 'node:module';
import { NestFactory } from '@nestjs/core';
import { AppModule } from './apps/api/dist/app.module.js';
const require = createRequire(import.meta.url);
const assistantRequire = createRequire(new URL('./libs/assistant/server/package.json', import.meta.url));
const { PostgresSaver } = assistantRequire('@langchain/langgraph-checkpoint-postgres');
const app = await NestFactory.createApplicationContext(AppModule, { logger: false, abortOnError: false });
try {
  const saver = app.get(PostgresSaver);
  const tuple = await saver.getTuple({ configurable: { thread_id: ${JSON.stringify(chatId)}, checkpoint_ns: '' } });
  if (!tuple) throw new Error('The assistant turn did not save its pending confirmation.');
  const pending = tuple.pendingWrites.find(([, channel]) => channel === '__interrupt__');
  if (!pending) throw new Error('The assistant turn has no pending confirmation write.');
  const [taskId, channel, value] = pending;
  const expired = { ...value, value: { ...value.value, expiresAt: new Date(Date.now() - 16 * 60 * 1000).toISOString() } };
  await saver.putWrites(tuple.config, [[channel, expired]], taskId);
} finally { await app.close(); }
`;
  runInApi(source);
}

async function seedAtSpendCap(accountId: string, chatId: string): Promise<void> {
  const source = `
import 'reflect-metadata';
import { NestFactory } from '@nestjs/core';
import { AppModule } from './apps/api/dist/app.module.js';
import { AssistantUsage } from './libs/assistant/server/dist/index.js';
const app = await NestFactory.createApplicationContext(AppModule, { logger: false, abortOnError: false });
try {
  await app.get(AssistantUsage).record(${JSON.stringify(accountId)}, ${JSON.stringify(chatId)}, 10000000, 0);
} finally { await app.close(); }
`;
  runInApi(source);
}

describe('assistant turn API', () => {
  beforeAll(async () => {
    admin = await signedIn();
    person = await invitedMember(admin);
    sameOrgTeammate = await invitedMember(admin);
    otherPerson = await signedIn();
    personProjectName = `Person project ${randomUUID()}`;
    otherProjectName = `Other account project ${randomUUID()}`;
    deletedProjectName = `Deleted admin project ${randomUUID()}`;
    personProjectId = await createProject(person, personProjectName);
    await createProject(otherPerson, otherProjectName);
    await deleteProject(admin, await createProject(admin, deletedProjectName));
  }, 60_000);

  it("a question about projects streams text and a table block of the person's own projects", async () => {
    const chatId = await createChat(person);
    const { events } = await ask(person, chatId, 'case:projects');
    expect(deltas(events)).toContain('Here are your projects.');
    expect(blocks(events)).toEqual([expect.objectContaining({
      kind: 'table', props: expect.objectContaining({
        rows: [expect.objectContaining({ name: personProjectName })],
      }),
    })]);
    expect(JSON.stringify(blocks(events))).not.toContain(otherProjectName);
    expect(events.at(-1)).toEqual({ event: 'done', data: {} });
  });

  it('a stand-in report tool streams a chart block and stat tiles', async () => {
    const chatId = await createChat(person);
    const { events } = await ask(person, chatId, 'case:report');
    expect(blocks(events)).toEqual(expect.arrayContaining([
      expect.objectContaining({ kind: 'chart', props: expect.objectContaining({
        type: 'line', xKey: 'month', series: [{ key: 'total', label: 'Total' }],
      }) }),
      expect.objectContaining({ kind: 'stats', props: { tiles: [{ label: 'Total projects', value: 3, unit: 'projects' }] } }),
    ]));
  });

  it('a question about one project streams its detail card', async () => {
    const chatId = await createChat(person);
    const { events } = await ask(person, chatId, `case:detail ${personProjectId}`);
    expect(deltas(events)).toContain('Here are the project details.');
    expect(blocks(events)).toEqual([expect.objectContaining({
      kind: 'detail', props: expect.objectContaining({
        title: personProjectName,
        fields: [expect.objectContaining({ label: 'Status', value: 'Active' })],
      }),
    })]);
  });

  it('a tool with no display entry streams its summary text only', async () => {
    const chatId = await createChat(person);
    const { events } = await ask(person, chatId, 'case:summary');
    expect(deltas(events)).toContain('This tool has no display entry.');
    expect(blocks(events)).toEqual([]);
  });

  it('the stream never carries markup that the model wrote', async () => {
    const chatId = await createChat(person);
    const { events } = await ask(person, chatId, 'case:markup');
    expect(deltas(events)).toContain('<script>alert("xss")</script>');
    expect(JSON.stringify(blocks(events))).not.toContain('<script>');
  });

  it('a message over 4000 characters gets 400 VALIDATION_ERROR', async () => {
    const chatId = await createChat(person);
    const response = await person.client.post(`/api/v1/assistant/chats/${chatId}/messages`)
      .set('x-csrf-token', person.csrf)
      .set('Idempotency-Key', randomUUID())
      .send({ text: 'x'.repeat(4001) }).expect(400);
    expect(response.body.error.code).toBe('VALIDATION_ERROR');
    expect((await person.client.get(`/api/v1/assistant/chats/${chatId}`).expect(200)).body.data.messages).toEqual([]);
  });

  it('a password or a card number is refused and reaches no model call or checkpoint', async () => {
    const before = await providerCalls('secret');
    for (const text of ['password: assistant-private-value', 'card number: 4111 1111 1111 1111']) {
      const chatId = await createChat(person);
      const response = await person.client.post(`/api/v1/assistant/chats/${chatId}/messages`)
        .set('x-csrf-token', person.csrf)
        .set('Idempotency-Key', randomUUID())
        .send({ text }).expect(400);
      expect(response.body.error.code).toBe('VALIDATION_ERROR');
      expect((await person.client.get(`/api/v1/assistant/chats/${chatId}`).expect(200)).body.data.messages).toEqual([]);
      expect(await hasCheckpoint(chatId)).toBe(false);
    }
    expect(await providerCalls('secret')).toBe(before);
  });

  it('a write stops at a confirm card and changes nothing', async () => {
    const name = `Assistant pending ${randomUUID()}`;
    const { chatId, confirmId } = await startWrite(person, 'case:write', name);
    expect(await projectNames(person)).not.toContain(name);
    const chat = (await person.client.get(`/api/v1/assistant/chats/${chatId}`).expect(200)).body.data;
    expect(chat.confirm).toMatchObject({ confirmId, title: CONFIRM_TITLE, lines: expect.any(Array) });
    expect(chat.messages.map(({ role }: { role: string }) => role)).toContain('user');
  });

  it('confirm makes the change once', async () => {
    const name = `Assistant confirmed ${randomUUID()}`;
    const { chatId, confirmId } = await startWrite(person, 'case:write', name);
    const result = await decide(person, chatId, confirmId, 'confirm');
    expect(result.events.at(-1)).toEqual({ event: 'done', data: {} });
    expect(await projectNames(person)).toContain(name);
  });

  it('confirm sent twice makes one change', async () => {
    const name = `Assistant one change ${randomUUID()}`;
    const { chatId, confirmId } = await startWrite(person, 'case:write', name);
    await decide(person, chatId, confirmId, 'confirm');
    const callsAfterFirst = await providerCalls('write');
    await decide(person, chatId, confirmId, 'confirm');
    expect(await providerCalls('write')).toBe(callsAfterFirst);
    expect((await projectNames(person)).filter((value) => value === name)).toHaveLength(1);
  });

  it('a message sent again with the same Idempotency-Key runs one turn', async () => {
    const chatId = await createChat(person);
    const key = randomUUID();
    const before = await providerCalls('usage');
    const first = await ask(person, chatId, 'case:usage', key);
    const afterFirst = await providerCalls('usage');
    const replay = await ask(person, chatId, 'case:usage', key);
    expect(deltas(replay.events)).toBe(deltas(first.events));
    expect(afterFirst).toBe(before + 1);
    expect(await providerCalls('usage')).toBe(afterFirst);
    const messages = (await person.client.get(`/api/v1/assistant/chats/${chatId}`).expect(200)).body.data.messages;
    expect(messages.filter(({ role, text }: { role: string; text: string }) => role === 'user' && text === 'case:usage')).toHaveLength(1);
  });

  it('cancel changes nothing and tells the model', async () => {
    const name = `Assistant cancelled ${randomUUID()}`;
    const { chatId, confirmId } = await startWrite(person, 'case:cancel', name);
    const result = await decide(person, chatId, confirmId, 'cancel');
    expect(deltas(result.events)).toContain('I left the project unchanged.');
    expect(await projectNames(person)).not.toContain(name);
  });

  it('a confirm after 15 minutes runs nothing', async () => {
    const name = `Assistant expired ${randomUUID()}`;
    const { chatId, confirmId } = await startWrite(person, 'case:write', name);
    const open = (await person.client.get(`/api/v1/assistant/chats/${chatId}`).expect(200)).body.data.confirm;
    const remaining = Date.parse(open.expiresAt) - Date.now();
    expect(remaining).toBeGreaterThan(14 * 60 * 1000);
    expect(remaining).toBeLessThan(15 * 60 * 1000 + 5_000);
    expireConfirm(chatId);
    const before = await providerCalls('write');
    const response = await person.client.post(`/api/v1/assistant/chats/${chatId}/confirm`)
      .set('x-csrf-token', person.csrf)
      .send({ confirmId, decision: 'confirm' }).expect(409);
    expect(response.body.error.code).toBe('CONFIRM_EXPIRED');
    expect(await providerCalls('write')).toBe(before);
    expect(await projectNames(person)).not.toContain(name);
  });

  it('a second message while a turn runs gets 409', async () => {
    const chatId = await createChat(person);
    const before = await providerCalls('concurrent');
    const first = ask(person, chatId, 'case:concurrent');
    try {
      await vi.waitFor(async () => expect(await providerCalls('concurrent')).toBe(before + 1), { timeout: 10_000 });
      const second = await person.client.post(`/api/v1/assistant/chats/${chatId}/messages`)
        .set('x-csrf-token', person.csrf)
        .set('Idempotency-Key', randomUUID())
        .send({ text: 'case:concurrent second message' }).expect(409);
      expect(second.body.error.code).toEqual(expect.any(String));
    } finally {
      await releaseProvider('concurrent');
    }
    const result = await first;
    expect(result.events.at(-1)).toEqual({ event: 'done', data: {} });
  });

  it('two changes asked at once give one card at a time: confirm the first, cancel the second, and only the first is saved', async () => {
    const firstName = `Assistant first ${randomUUID()}`;
    const secondName = `Assistant second ${randomUUID()}`;
    const chatId = await createChat(person);
    const prompt = `case:two-writes ${JSON.stringify({ firstName, secondName })}`;
    const firstTurn = await ask(person, chatId, prompt);
    const firstCards = confirmations(firstTurn.events);
    expect(firstCards).toHaveLength(1);
    expect(firstCards[0].lines).toEqual(expect.arrayContaining([`name: ${firstName}`]));

    const afterFirst = await decide(person, chatId, firstCards[0].confirmId as string, 'confirm');
    const secondCards = confirmations(afterFirst.events);
    expect(secondCards).toHaveLength(1);
    expect(secondCards[0].lines).toEqual(expect.arrayContaining([`name: ${secondName}`]));
    await decide(person, chatId, secondCards[0].confirmId as string, 'cancel');

    const names = await projectNames(person);
    expect(names).toContain(firstName);
    expect(names).not.toContain(secondName);
  });

  it('a confirmId that is not the open one gets 409 and runs nothing', async () => {
    const name = `Assistant protected ${randomUUID()}`;
    const { chatId, confirmId } = await startWrite(person, 'case:write', name);
    const before = await providerCalls('write');
    const response = await person.client.post(`/api/v1/assistant/chats/${chatId}/confirm`)
      .set('x-csrf-token', person.csrf)
      .send({ confirmId: randomUUID(), decision: 'confirm' }).expect(409);
    expect(response.body.error.code).toBe('CONFIRM_CHANGED');
    expect(await providerCalls('write')).toBe(before);
    expect(await projectNames(person)).not.toContain(name);
    await decide(person, chatId, confirmId, 'cancel');
  });

  it("the assistant lists only what the person's role allows", async () => {
    const memberChatId = await createChat(person);
    const memberResult = await ask(person, memberChatId, `case:projects ${JSON.stringify({ include_deleted: true })}`);
    const memberRows = (blocks(memberResult.events)[0].props as { rows: { name: string }[] }).rows;
    expect(memberRows.map(({ name }) => name)).toContain(personProjectName);
    expect(memberRows.map(({ name }) => name)).not.toContain(deletedProjectName);

    const adminChatId = await createChat(admin);
    const adminResult = await ask(admin, adminChatId, `case:projects ${JSON.stringify({ include_deleted: true })}`);
    const adminRows = (blocks(adminResult.events)[0].props as { rows: { name: string }[] }).rows;
    expect(adminRows.map(({ name }) => name)).toContain(deletedProjectName);
  });

  it("a person without the permission gets the tool's plain refusal", async () => {
    const chatId = await createChat(person);
    const { events } = await ask(person, chatId, `case:permission ${JSON.stringify({
      project_id: personProjectId, name: 'Denied edit', status: 'archived',
    })}`);
    expect(deltas(events)).toContain("Your agent account's role cannot use projects_update. An admin can change its role on the Members screen.");
    expect((await person.client.get(`/api/v1/projects/${personProjectId}`).expect(200)).body.data)
      .toMatchObject({ name: personProjectName, status: 'active' });
  });

  it('a change made through the assistant is in the history as the person, via the assistant', async () => {
    const name = `Assistant history ${randomUUID()}`;
    const { chatId, confirmId } = await startWrite(person, 'case:write', name);
    await decide(person, chatId, confirmId, 'confirm');
    const history = await admin.client.get('/api/v1/history').expect(200);
    const entry = history.body.data.find(({ summary }: { summary: string }) => summary.includes(name));
    expect(entry).toEqual(expect.objectContaining({ actorEmail: person.email, viaAgent: 'the assistant' }));
    const csv = (await admin.client.get('/api/v1/history/export').expect(200)).text;
    expect(csv).toContain(`,"${person.email}, via the assistant",`);
  });

  it('the model cannot choose another user', async () => {
    const chatId = await createChat(person);
    const { events } = await ask(person, chatId, `case:other-user ${JSON.stringify({ account_id: otherPerson.id })}`);
    expect(deltas(events)).toContain('Received tool input did not match expected schema');
    expect(blocks(events)).toEqual([]);
  });

  it("another person's chat id on the message endpoint gets 404 before any model call", async () => {
    const chatId = await createChat(person);
    const before = await providerCalls('write');
    for (const reader of [sameOrgTeammate, admin, otherPerson]) {
      const response = await reader.client.post(`/api/v1/assistant/chats/${chatId}/messages`)
        .set('x-csrf-token', reader.csrf)
        .set('Idempotency-Key', randomUUID())
        .send({ text: 'case:write' }).expect(404);
      expect(response.body.error.code).toBe('NOT_FOUND');
    }
    expect(await providerCalls('write')).toBe(before);
  });

  it("another person's chat id and confirmId on the confirm endpoint get 404 and the pending write does not run", async () => {
    const name = `Assistant private write ${randomUUID()}`;
    const { chatId, confirmId } = await startWrite(person, 'case:write', name);
    const before = await providerCalls('write');
    for (const reader of [sameOrgTeammate, admin, otherPerson]) {
      const response = await reader.client.post(`/api/v1/assistant/chats/${chatId}/confirm`)
        .set('x-csrf-token', reader.csrf)
        .send({ confirmId, decision: 'confirm' }).expect(404);
      expect(response.body.error.code).toBe('NOT_FOUND');
    }
    expect(await providerCalls('write')).toBe(before);
    expect(await projectNames(person)).not.toContain(name);
    await decide(person, chatId, confirmId, 'cancel');
  });

  it('each turn writes one usage row for the person with its cost', async () => {
    const chatId = await createChat(person);
    const { events } = await ask(person, chatId, 'case:usage');
    expect(events.at(-1)).toEqual({ event: 'done', data: {} });
    const rows = await usageRows(chatId);
    expect(rows).toHaveLength(1);
    expect(rows[0]).toMatchObject({ accountId: person.id, inputTokens: 30, outputTokens: 10, costMicros: '40' });
  });

  it('each turn logs one line with the prompt version and a hashed account id and no message text', async () => {
    const chatId = await createChat(person);
    const marker = `no-log-${randomUUID()}`;
    const before = logEvents('api').filter(({ message, context }) =>
      message === 'Assistant turn' && context?.accountHash === createHash('sha256').update(person.id).digest('hex')).length;
    await ask(person, chatId, `case:usage ${marker}`);
    await vi.waitFor(() => expect(logEvents('api').filter(({ message, context }) =>
      message === 'Assistant turn' && context?.accountHash === createHash('sha256').update(person.id).digest('hex')).length).toBe(before + 1), { timeout: 10_000 });
    const matching = logEvents('api').filter(({ message, context }) =>
      message === 'Assistant turn' && context?.accountHash === createHash('sha256').update(person.id).digest('hex'));
    expect(matching).toHaveLength(before + 1);
    expect(matching.at(-1)?.context).toMatchObject({
      promptVersion: expect.any(String),
      accountHash: createHash('sha256').update(person.id).digest('hex'),
    });
    expect(JSON.stringify(matching.at(-1))).not.toContain(marker);
    expect(JSON.stringify(matching.at(-1))).not.toContain(person.id);
    expect(JSON.stringify(matching.at(-1))).not.toContain(person.email);
  });

  it("a used-up cap streams the limit line and the app's other routes still work", async () => {
    const chatId = await createChat(person);
    await seedAtSpendCap(person.id, chatId);
    const before = await providerCalls('limit');
    const { events } = await ask(person, chatId, 'case:limit');
    expect(events.filter(({ event }) => event === 'limit')).toEqual([
      { event: 'limit', data: { message: LIMIT_LINE } },
    ]);
    expect(events.at(-1)).toEqual({ event: 'done', data: {} });
    expect(await providerCalls('limit')).toBe(before);
    await person.client.get('/health').expect(200);
  });
});
