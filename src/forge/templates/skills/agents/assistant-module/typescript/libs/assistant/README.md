# TypeScript assistant module

This optional module stores private chats in the app's Postgres database. The app keeps a chat for 30 days after its last message. The hourly clean-up deletes the chat and its LangGraph checkpoints.

## Copy the module

Run these commands from the app root. Use `.codex/skills` or `.claude/skills`, as present in the app.

```sh
cp -R .codex/skills/agents/assistant-module/typescript/libs/assistant libs/assistant
cp .codex/skills/agents/assistant-module/typescript/apps/api/prisma/schema/assistant.prisma apps/api/prisma/schema/assistant.prisma
cp -R .codex/skills/agents/assistant-module/typescript/apps/api/prisma/migrations/20261106000000_assistant apps/api/prisma/migrations/20261106000000_assistant
cp .codex/skills/agents/assistant-module/typescript/apps/api/test/assistant-chats.e2e-spec.ts apps/api/test/assistant-chats.e2e-spec.ts
cp .codex/skills/agents/assistant-module/typescript/apps/api/test/assistant-api.e2e-spec.ts apps/api/test/assistant-api.e2e-spec.ts
```

For a Claude app, replace `.codex/skills` with `.claude/skills` in each command.

## Edit the app

In `apps/api/prisma/schema/base.prisma`, add `"assistant"` to the `schemas` list.

Add these properties to `defineConfig` in `prisma.config.ts`.
LangGraph owns these tables. Prisma must leave them unchanged during later migrations.
See the [Prisma configuration reference](https://www.prisma.io/docs/orm/v7/reference/prisma-config-reference).

```ts
experimental: { externalTables: true },
tables: { external: [
  'assistant.checkpoints', 'assistant.checkpoint_blobs',
  'assistant.checkpoint_writes', 'assistant.checkpoint_migrations',
] },
```

In `apps/api/prisma/schema/organisations.prisma`, add this field to `Organisation`:

```prisma
assistantChats AssistantChat[]
```

In `apps/api/prisma/schema/auth.prisma`, add these fields to `Account`:

```prisma
createdChats  AssistantChat[] @relation("ChatCreatedBy")
modifiedChats AssistantChat[] @relation("ChatModifiedBy")
```

Add `@app/assistant-server` as a `workspace:*` dependency in `apps/api/package.json`. Add `../../libs/assistant/server` to the references in `apps/api/tsconfig.json`. Add the assistant scope rule to `eslint.config.mjs`. Permit assistant code to use assistant, core, shared and contracts libraries.

Add `@langchain/langgraph-checkpoint-postgres` at version `1.1.2` to the root and `apps/api/package.json`. Import `AssistantModule` from `@app/assistant-server` in `apps/api/src/app.module.ts` and add it to `imports`. The module provides the chat service, clean-up timer and Postgres checkpointer. It closes the checkpointer connection when the app stops.

Raise the app's `zod` version to `4.3.6`. The server package pins all its libraries:

| Library | Version |
| --- | --- |
| `langchain` | 1.6.1 |
| `@langchain/langgraph` | 1.5.3 |
| `@langchain/langgraph-checkpoint-postgres` | 1.1.2 |
| `@langchain/langgraph-checkpoint` | 1.2.2 |
| `@langchain/core` | 1.3.5 |
| `@langchain/openai` | 1.8.0 |
| `zod` | 4.3.6 |

LangChain 1.6.1 requires `@langchain/core` 1.3.4 or newer. The template uses the compatible 1.3.5 release.

Run `corepack pnpm install --no-frozen-lockfile` to update the lock file. Use this command in CI too.

Add the `assistant:setup` script to the root `package.json`:

```json
{
  "assistant:setup": "pnpm --filter @app/assistant-server exec node --input-type=module -e \"import { PostgresSaver } from '@langchain/langgraph-checkpoint-postgres'; const saver = PostgresSaver.fromConnString(process.env.DATABASE_URL, { schema: 'assistant' }); try { await saver.setup(); } finally { await saver.end(); }\""
}
```

Add `corepack pnpm run assistant:setup` after `prisma migrate deploy` in the `CMD` in `Dockerfile`. The setup command creates LangGraph's tables before the API starts.

## Settings

When the app imports the assistant module, set `ASSISTANT_AI_KEY`, `ASSISTANT_MODEL`, `ASSISTANT_SPEND_CAP_USD`, `ASSISTANT_PRICE_INPUT_USD_PER_MTOK` and `ASSISTANT_PRICE_OUTPUT_USD_PER_MTOK`. Set `ASSISTANT_AI_URL` only for an OpenAI-compatible service with a custom address. Keep each value in the app's `.env` or its host settings. Do not put a key in code.

Build the Assistant page in the app's design by the `The assistant page` section in the agents skill. The template contains no page or route.

## Storage calls

Use the chat's `id` as LangGraph's `thread_id`. Call `ownChat` before any checkpoint read or model call. Call `touch` when the turn accepts a new message. The turn must refuse secrets before this call. Model calls and the page belong to later assistant parts.

## Chat API

The app's session and CSRF guards protect the routes under `/api/v1/assistant/chats`.
`POST` with an empty object creates a chat and returns `{ id }`. Use `Idempotency-Key` to retry without a second chat.
`GET` lists only the caller's chats, most recent message first, with `limit`, `after` and `before` for cursor paging.
`GET /:id` returns the chat's public dates, user and assistant text, and its open confirm card. It never returns system messages, tool arguments or model metadata. Another person's chat returns 404, even to an admin.

The contracts package defines the five blocks and the stream events. Each stream event uses `{ event, data }`; `done` has an empty data object. A pending interrupt carries `title`, `lines` and `expiresAt` in its value. The read endpoint uses the interrupt's own id as `confirmId`.

Run the app's normal test command after the copy. The starter's API test pattern includes both copied test files. To leave the module off, omit `AssistantModule` from the app's imports. The ordinary API needs no assistant settings in that state.
