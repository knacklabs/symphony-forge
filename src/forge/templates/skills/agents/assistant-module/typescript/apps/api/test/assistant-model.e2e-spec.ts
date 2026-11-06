import { ASSISTANT_PROMPT, containsSecret, PROMPT_VERSION } from '@app/assistant-server';
import { readdirSync, readFileSync } from 'node:fs';
import { basename, join, resolve } from 'node:path';
import { spawnSync } from 'node:child_process';
import request from 'supertest';
import { beforeAll, describe, expect, it } from 'vitest';
import { apiBaseUrl, credentials } from './helpers';

// Audit: this suite owns settings at Nest startup, provider requests at the
// provider edge, real Postgres cap rows, prompt bytes and secret detection.
// Wrong settings, month filters, prompt growth or a loose card check are real
// regressions. Existing assistant coverage owns chats and retention only. The
// copied-file check cannot catch these runtime contracts. No production seam.
const SETTINGS = {
  ASSISTANT_AI_KEY: 'provider-test-key',
  ASSISTANT_MODEL: 'configured-assistant-model',
  ASSISTANT_SPEND_CAP_USD: '0.0001',
  ASSISTANT_PRICE_INPUT_USD_PER_MTOK: '1',
  ASSISTANT_PRICE_OUTPUT_USD_PER_MTOK: '0',
};

let accountId: string;

beforeAll(async () => {
  const response = await request(apiBaseUrl).post('/api/v1/auth/sign-up').send(credentials()).expect(201);
  accountId = response.body.data.id as string;
});

function runInApi(source: string): unknown {
  const result = spawnSync('docker', [
    'compose', '-f', 'compose.test.yml', 'exec', '-T', 'api', 'node', '--input-type=module', '-',
  ], { input: source, encoding: 'utf8', timeout: 60_000, killSignal: 'SIGKILL' });
  const output = `${result.error?.message ?? ''}${result.stdout}${result.stderr}`;
  expect(result.status, output).toBe(0);
  return JSON.parse(result.stdout) as unknown;
}

function filesUnder(folder: string): string[] {
  return readdirSync(folder, { withFileTypes: true }).flatMap(entry => {
    const path = join(folder, entry.name);
    return entry.isDirectory() ? filesUnder(path) : entry.isFile() ? [path] : [];
  });
}

function testModuleSource(providers: string): string {
  return `
import 'reflect-metadata';
import { Module } from '@nestjs/common';
import { NestFactory } from '@nestjs/core';
import { AssistantModel, AssistantUsage } from './libs/assistant/server/dist/index.js';
import { ConfigService } from '@nestjs/config';
import { PrismaService } from './libs/core/server/dist/index.js';
${providers}
`;
}

describe('assistant model settings and safeguards', () => {
  it('only the model file reads the provider key and the module contains no key', () => {
    const moduleRoot = resolve(process.cwd(), 'libs/assistant');
    const sourceRoot = resolve(moduleRoot, 'server/src');
    const sourceFiles = filesUnder(sourceRoot).filter(path => path.endsWith('.ts'));
    const readers = sourceFiles.filter(path => readFileSync(path, 'utf8').includes('ASSISTANT_AI_KEY'));
    expect(readers.map(path => basename(path))).toEqual(['assistant.model.ts']);

    const keyShape = /\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b/;
    for (const path of filesUnder(moduleRoot)) {
      expect(readFileSync(path, 'utf8').match(keyShape), path).toBeNull();
    }
  });

  it('missing required settings stop startup with a plain message', () => {
    const source = testModuleSource(`
const valid = ${JSON.stringify(SETTINGS)};
const missingSettings = [
  'ASSISTANT_AI_KEY', 'ASSISTANT_MODEL', 'ASSISTANT_SPEND_CAP_USD',
  'ASSISTANT_PRICE_INPUT_USD_PER_MTOK', 'ASSISTANT_PRICE_OUTPUT_USD_PER_MTOK',
];
const messages = {};
for (const missing of missingSettings) {
  const settings = { ...valid };
  delete settings[missing];
  class SettingsModule {}
  Module({ providers: [
    AssistantModel,
    AssistantUsage,
    { provide: PrismaService, useValue: {} },
    { provide: ConfigService, useValue: { get: (name) => settings[name] } },
  ] })(SettingsModule);
  try {
    const app = await NestFactory.createApplicationContext(SettingsModule, { logger: false, abortOnError: false });
    await app.close();
    messages[missing] = null;
  } catch (error) {
    messages[missing] = error instanceof Error ? error.message : String(error);
  }
}
process.stdout.write(JSON.stringify(messages));
`);
    const messages = runInApi(source) as Record<string, string | null>;
    for (const setting of [
      'ASSISTANT_AI_KEY', 'ASSISTANT_MODEL', 'ASSISTANT_SPEND_CAP_USD',
      'ASSISTANT_PRICE_INPUT_USD_PER_MTOK', 'ASSISTANT_PRICE_OUTPUT_USD_PER_MTOK',
    ]) {
      expect(messages[setting]).toContain(setting);
      expect(messages[setting]).not.toMatch(/\n\s+at\s/);
    }
  });

  it('the model uses the configured provider, key and address', () => {
    const source = testModuleSource(`
import { createServer } from 'node:http';
const provider = createServer((request, response) => {
  let body = '';
  request.setEncoding('utf8');
  request.on('data', chunk => { body += chunk; });
  request.on('end', () => {
    globalThis.providerRequest = { path: request.url, authorization: request.headers.authorization, body: JSON.parse(body) };
    response.writeHead(200, { 'content-type': 'application/json' });
    response.end(JSON.stringify({
      id: 'chatcmpl-test', object: 'chat.completion', created: 1,
      model: 'configured-assistant-model',
      choices: [{ index: 0, message: { role: 'assistant', content: 'ready' }, finish_reason: 'stop' }],
      usage: { prompt_tokens: 1, completion_tokens: 1, total_tokens: 2 },
    }));
  });
});
await new Promise((resolve, reject) => {
  provider.once('error', reject);
  provider.listen(0, '127.0.0.1', resolve);
});
let context;
try {
  const address = provider.address();
  const settings = ${JSON.stringify(SETTINGS)};
  settings.ASSISTANT_AI_URL = 'http://127.0.0.1:' + address.port + '/v1';
  class ProviderModule {}
  Module({ providers: [
    AssistantModel,
    { provide: ConfigService, useValue: { get: (name) => settings[name] } },
  ] })(ProviderModule);
  context = await NestFactory.createApplicationContext(ProviderModule, { logger: false, abortOnError: false });
  const result = await context.get(AssistantModel).client.invoke('Say hello.');
  process.stdout.write(JSON.stringify({ reply: result.content, request: globalThis.providerRequest }));
} finally {
  if (context) await context.close();
  await new Promise((resolve, reject) => provider.close(error => error ? reject(error) : resolve()));
}
`);
    const result = runInApi(source) as {
      reply: string;
      request: { path: string; authorization: string; body: { model: string } };
    };
    expect(result.reply).toBe('ready');
    expect(result.request).toMatchObject({
      path: '/v1/chat/completions',
      authorization: `Bearer ${SETTINGS.ASSISTANT_AI_KEY}`,
      body: { model: SETTINGS.ASSISTANT_MODEL },
    });
  });

  it('monthly spend stops at the cap and last month does not count', () => {
    const source = `
import 'reflect-metadata';
import { Module } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { NestFactory } from '@nestjs/core';
import { AppModule } from './apps/api/dist/app.module.js';
import { PrismaService } from './libs/core/server/dist/index.js';
import { AssistantChatsService, AssistantUsage } from './libs/assistant/server/dist/index.js';
const app = await NestFactory.createApplicationContext(AppModule, { logger: false, abortOnError: false });
let usageContext;
let chatId;
try {
  const prisma = app.get(PrismaService);
  const chats = app.get(AssistantChatsService);
  const membership = await prisma.membership.findUniqueOrThrow({ where: { accountId: ${JSON.stringify(accountId)} } });
  const principal = { id: membership.accountId, organisationId: membership.organisationId, email: 'usage@example.test', role: 'admin' };
  const chat = await chats.create(principal);
  chatId = chat.id;
  class UsageModule {}
  Module({ providers: [
    AssistantUsage,
    { provide: PrismaService, useValue: prisma },
    { provide: ConfigService, useValue: { get: (name) => ({
      ASSISTANT_SPEND_CAP_USD: '0.000102',
      ASSISTANT_PRICE_INPUT_USD_PER_MTOK: '1.01',
      ASSISTANT_PRICE_OUTPUT_USD_PER_MTOK: '2.01',
    })[name] } },
  ] })(UsageModule);
  usageContext = await NestFactory.createApplicationContext(UsageModule, { logger: false, abortOnError: false });
  const usage = usageContext.get(AssistantUsage);
  const belowCap = await usage.canStart();
  await usage.record(membership.accountId, chat.id, 59, 21);
  const row = await prisma.assistantUsage.findFirstOrThrow({ where: { chatId: chat.id } });
  const currentMonth = await usage.canStart(row.createdAtUtc);
  await prisma.assistantUsage.update({
    where: { id: row.id },
    data: { createdAtUtc: new Date(Date.UTC(row.createdAtUtc.getUTCFullYear(), row.createdAtUtc.getUTCMonth() - 1, 15)) },
  });
  const previousMonth = await usage.canStart(row.createdAtUtc);
  process.stdout.write(JSON.stringify({
    belowCap, currentMonth, previousMonth, accountMatches: row.accountId === membership.accountId,
    chatMatches: row.chatId === chat.id, kind: row.kind, inputTokens: row.inputTokens,
    outputTokens: row.outputTokens, costMicros: String(row.costMicros),
  }));
} finally {
  if (usageContext) await usageContext.close();
  const prisma = app.get(PrismaService);
  if (chatId) {
    await prisma.assistantUsage.deleteMany({ where: { chatId } });
    await prisma.assistantChat.deleteMany({ where: { id: chatId } });
  }
  await app.close();
}
`;
    const result = runInApi(source) as {
      belowCap: boolean;
      currentMonth: boolean;
      previousMonth: boolean;
      accountMatches: boolean;
      chatMatches: boolean;
      kind: string;
      inputTokens: number;
      outputTokens: number;
      costMicros: string;
    };
    expect(result).toEqual({
      belowCap: true,
      currentMonth: false,
      previousMonth: true,
      accountMatches: true,
      chatMatches: true,
      kind: 'llm',
      inputTokens: 59,
      outputTokens: 21,
      costMicros: '102',
    });
  });

  it('the prompt stays within its UTF-8 byte budget and has a version', () => {
    expect(PROMPT_VERSION).toBeTruthy();
    expect(Buffer.byteLength(ASSISTANT_PROMPT, 'utf8')).toBeLessThanOrEqual(12 * 1024);
  });

  it('the secret check finds labelled secrets and valid cards but not plain text', () => {
    expect(containsSecret('My password is example-value')).toBe(true);
    expect(containsSecret('The one-time code: 123456')).toBe(true);
    expect(containsSecret('Card number 4111 1111 1111 1111')).toBe(true);
    expect(containsSecret('Card number 4111-1111-1111-1111')).toBe(true);
    expect(containsSecret('Card number 4111 1111 1111 1112')).toBe(false);
    expect(containsSecret('Tell me about my projects and recent activity.')).toBe(false);
  });
});
