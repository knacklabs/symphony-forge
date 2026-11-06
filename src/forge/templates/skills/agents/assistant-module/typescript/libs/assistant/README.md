# TypeScript assistant module

This optional module stores private chats in the app's Postgres database. The app keeps a chat for 30 days after its last message. The hourly clean-up deletes the chat and its LangGraph checkpoints.

## Copy the module

Run these commands from the app root. Use `.codex/skills` or `.claude/skills`, as present in the app.

```sh
cp -R .codex/skills/agents/assistant-module/typescript/libs/assistant libs/assistant
cp .codex/skills/agents/assistant-module/typescript/apps/api/prisma/schema/assistant.prisma apps/api/prisma/schema/assistant.prisma
cp -R .codex/skills/agents/assistant-module/typescript/apps/api/prisma/migrations/20261106000000_assistant apps/api/prisma/migrations/20261106000000_assistant
cp -R .codex/skills/agents/assistant-module/typescript/apps/api/prisma/migrations/20261106010000_assistant_usage apps/api/prisma/migrations/20261106010000_assistant_usage
cp .codex/skills/agents/assistant-module/typescript/apps/api/test/assistant-chats.e2e-spec.ts apps/api/test/assistant-chats.e2e-spec.ts
cp .codex/skills/agents/assistant-module/typescript/apps/api/test/assistant-model.e2e-spec.ts apps/api/test/assistant-model.e2e-spec.ts
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
assistantUsage AssistantUsage[]
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

In `apps/api/test/database.e2e-spec.ts`, extend the expected catalog in `each module keeps its tables in its own schema` with these entries. Keep the existing entries and the exact equality assertion.

```ts
AssistantChat: 'assistant',
AssistantUsage: 'assistant',
checkpoints: 'assistant', checkpoint_blobs: 'assistant',
checkpoint_writes: 'assistant', checkpoint_migrations: 'assistant',
```

Keep these entries when the module is not imported. Its migration and storage setup still create the tables.

## Settings

When the app imports the assistant module, set `ASSISTANT_AI_KEY`, `ASSISTANT_MODEL`, `ASSISTANT_SPEND_CAP_USD`, `ASSISTANT_PRICE_INPUT_USD_PER_MTOK` and `ASSISTANT_PRICE_OUTPUT_USD_PER_MTOK`. Set `ASSISTANT_AI_URL` only for an OpenAI-compatible service with a custom address. Keep each value in the app's `.env` or its host settings. Do not put a key in code.

The starter validator returns only core settings. Keep the other values in the result from `ConfigModule.forRoot`. Set its `validate` option in `apps/api/src/app.module.ts` to:

```ts
values => ({ ...values, ...validateEnvironment(values) })
```

This keeps the assistant settings in `ConfigService` after the starter checks its settings.

`AssistantModule` provides `AssistantModel` and `AssistantUsage`. They check the settings at start-up. Dollar amounts must be non-negative decimal strings with at most six decimal places. Zero sets a used-up cap or a free token price. Prices use US dollars per million tokens. `AssistantUsage.cost` rounds the total cost up to one micro-dollar per turn.

The turn checks `AssistantUsage.canStart` before running the model and records its token counts and cost afterwards. These billing rows contain no message text. They remain after the chat expires, with an empty chat link. The cap counts the current UTC calendar month across the whole app.

Build the Assistant page in the app's design by the `The assistant page` section in the agents skill. The template contains no page or route.

## Storage calls

The turn uses the chat's `id` as LangGraph's `thread_id`. It checks ownership before any checkpoint read or model call and refuses secrets before saving a message. An advisory lock in Postgres permits one running turn per chat. It is released when the answer ends or pauses for a decision. The client builds the page; this template contains none.

## Chat API

The app's session and CSRF guards protect the routes under `/api/v1/assistant/chats`.
`POST` with an empty object creates a chat and returns `{ id }`. Use `Idempotency-Key` to retry without a second chat.
`GET` lists only the caller's chats, most recent message first, with `limit`, `after` and `before` for cursor paging.
`GET /:id` returns the chat's public dates, user and assistant text, and its open confirm card. It never returns system messages, tool arguments or model metadata. Another person's chat returns 404, even to an admin.

The contracts package defines the five blocks and the stream events. Each stream event uses `{ event, data }`; `done` has an empty data object. A pending interrupt carries `title`, `lines` and `expiresAt` in its value. The read endpoint uses the interrupt's own id as `confirmId`.

`POST /:id/messages` accepts `{ text }` with at most 4000 characters and requires an `Idempotency-Key`. A repeated key replays the saved answer without another model turn. `POST /:id/confirm` accepts `{ confirmId, decision }`, where the decision is `confirm` or `cancel`. The card expires after 15 minutes. A different card identifier returns 409. A repeated decision makes no second change.

Both endpoints return `text/event-stream`. A `text` event holds `{ delta }`, a `block` holds `{ kind, props }`, a `confirm` holds the card, and `limit` and `error` hold `{ message }`. `done` ends the answer. Text is plain text, even when it contains markup. The stream schema in the contracts package is the shared format for the chat hooks.

The prebuilt LangGraph agent calls the same `listTools` and `callTool` boundary as MCP, with the signed-in person's principal marked `viaAgent: 'the assistant'`. It offers at most 15 tools and disables parallel tool calls. If a provider still asks for more than one action, it runs the first and tells the model to request the remaining actions separately. Every write pauses at an interrupt first. A create's retry key comes from the chat and tool call identifiers, rather than the model.

`assistant.display.ts` maps validated tool results to blocks. Extend its `DISPLAY` entries when an app adds reports or other features. A tool without an entry streams its summary only. No block comes from model text. The model has a bounded wait and step count; a failed stream returns one plain error line. A chat that grows too long asks the person to start a new chat instead of removing earlier messages.

Run the app's normal test command after the copy. The starter's API test pattern includes the copied test files. To leave the module off, omit `AssistantModule` from the app's imports. The ordinary API needs no assistant settings in that state.

Forge runs `assistant-turn.e2e-spec.ts` through its copy-test fixture. That fixture supplies a fake model service and a stand-in report in the test app only. To use those cases in a client app, supply that app's test provider and report fixture first. Keep both outside its production build.
