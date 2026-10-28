# Client apps get an optional in-app assistant

4 parts · Risks: none one-way · New moving parts: the LangGraph libraries, a daily clean-up timer in each API, the Mainline model client

## What changes for you

- Both starters hold an assistant module that is off. A client that asks for it gets it turned on in its own app, and only then does the app show an Assistant page. Apps that never ask carry the code and run as before. The story is planned now and built when the first client asks. (Source: your decision, 28 Oct 2026)
- On the Assistant page, a signed-in person types a question in plain words. The assistant answers in text. When the answer is data, it shows one of five fixed parts from the app's design system: a table, a chart, stat tiles, a detail card or a confirm card. Code picks the part from the typed result of the tool that ran. The model never writes page markup. (Source: your decision, 28 Oct 2026)
- The assistant runs in the app's own API, in NestJS and in FastAPI. It uses LangGraph's prebuilt tool-calling agent and nothing custom: no hand-made graph. It works through the app's own MCP tools. (Source: your decision, 28 Oct 2026)
- The assistant acts as the signed-in person, with that person's permissions. It cannot read or change what the person cannot. Each change it makes appears in the change history as the person, marked "via the assistant". This uses the rule from the agent-ready story. (Source: your decision, 28 Oct 2026)
- Reads run at once. Every write first shows a confirm card with the plain-words change. Nothing is saved until the person confirms. A write carries a retry key, so a repeated confirm or a resent message makes one change. A confirm card expires after 15 minutes. (Source: your decision, 28 Oct 2026; the 15 minutes is the agents skill's default)
- Questions about numbers (totals, trends, counts) use the app's report services, which the agent-ready story defines. The assistant does not run its own queries. (Source: your decision, 28 Oct 2026)
- The model, the key, the allowed models and the spend budget come from Mainline. The app holds `MAINLINE_AI_KEY` and no provider key. The models the assistant may use are the ones on the app's Can use list. When the budget is used up, the person sees one plain line and the rest of the app works. (Source: your decision, 28 Oct 2026)
- Each person's chats are kept 30 days after the last message in the chat, in the app's Postgres through LangGraph's Postgres checkpointer. Then they are deleted. Nobody else reads them: not another person, not an admin, not an agent tool. (Source: your decision, 28 Oct 2026; counting from the last message is the planner's choice)
- Voice input and spoken replies are not in this story. They can be added later through Mainline's voice service on the app's Can use list. (Source: your decision, 28 Oct 2026)
- A new app from either starter has the module, off. An existing app gets nothing on upgrade, and adding the assistant to it later is a separate choice. (Source: your decision, 28 Oct 2026)
- The build follows the agents skill, web chat only. Its rules for the shape of the agent, the turn, tool design, output and side effects, safety, cost and tracing, and testing apply. Where the plan does not meet a Must rule, it says why, in the builders' section. (Source: your decision, 28 Oct 2026)

Design: none (the screens are starter screens made from the design system's existing components, and each client app's own design applies to them; owner rule, 28 Oct 2026)

## Why

A client that wants to ask its app a question in plain words would build its own assistant: its own model keys, its own chat storage, its own write checks. Each build would choose these rules by hand. The starters already have what an assistant needs: one door for every action, MCP tools with the person's permissions after the agent-ready story, and report services. This story adds the one module that joins them, so a client's assistant is a switch and not a project.

## Done when

1. **In an app that has turned the assistant on, a signed-in person asks a question and reads the answer as text, with a table, chart, stat tiles or detail card from the design system when the answer is data.**
2. **Every change that the assistant would make shows a confirm card first. Nothing is saved until the person confirms. A repeated confirm, or a message sent again with the same key, makes one change.**
3. **The assistant acts as the signed-in person: it sees and changes only what that person's permissions allow, and each change is recorded in the change history as that person, via the assistant.**
4. **Each person's chats are kept 30 days after their last message, then deleted, and no one else can read them.**
5. **The model, the key, the allowed models and the budget come from Mainline. The app holds no provider key, and a used-up budget shows one plain line without breaking the app.**
6. **A new app from either starter has the module off and its screens unchanged. An existing app gets no file and no change on upgrade.**

## Risks

Risks: none one-way. Each part reverts with its pull request. The assistant tables are new and hold only chats that the module makes.

Trade-off: the module and its libraries are in every new app, off. This adds install size to apps that never ask. The alternative (copy the module in when a client asks) needs a new command, and the command ceiling says no new command without a story.

Trade-off: a chat is deleted 30 days after its last message, so an active chat can live longer than 30 days from its start.

Trade-off: the clean-up runs on a timer inside the API. If the API is down for a day, the deletion runs when it is back.

## For the builders

<!-- Everything from here down is for the agents. The owner doesn't see it when approving, and
tightening it needs no new approval. -->

This story waits for FORGE-AGENTREADY-1 (one door, agents that act for a person, retry keys, report services) and FORGE-AGENTS-1 (the agents skill). Neither has merged. Every name below that comes from them is quoted from `plans/FORGE-AGENTREADY-1.md`, and a part checks it against the merged code before it starts.

Each new test file starts with `STORY = "FORGE-ASSIST-1"`. Tests run the forge command and never import forge. For app behaviour, they name the cases that the app's own run reports, through `live_run`, `live_python_starter` and `_require_cases`, as `tests/test_mcp.py` does. Live tests carry `@pytest.mark.platform` and `@pytest.mark.timeout(1800)`. `.github/workflows/starter-smoke.yml` lists and runs `tests/test_assistant.py` in both jobs. The existing-repo case uses `_adopted_files_after_sync` from `tests/test_mcp.py`.

### What exists (evidence)

- Tools. `defineTool`, `listTools(context)` and `callTool(name, args, context)` are in `starter/libs/core/server/src/common/tools.ts`. A `Tool` carries MCP annotations, including `readOnlyHint`. `ToolContext` holds `account`, `deleteAndRestore`, `createOnce` and `reportError`. Python has `ToolContext`, `ToolResult` and `call_tool` in `starter-python/apps/api/app/core/tools.py`. Each feature's tools file, such as `libs/projects/server/src/projects.tools.ts`, calls its service.
- The MCP server. `McpController` in `starter/libs/mcp/server/src/mcp.controller.ts` builds a `ToolContext` for an agent account. Python builds one in `app/mcp/server.py`. After FORGE-AGENTREADY-1 the person's sign-in can build the principal, with `viaAgent` (Python `via_agent`).
- Sign-in. `SessionGuard`, `CsrfGuard` and `ThrottlerGuard` are app-wide guards in `starter/apps/api/src/app.module.ts`. `@CurrentAccount()` gives the person's `AccountPrincipal`.
- History. `HistoryService.record(principal, ...)` writes the actor from the principal. FORGE-AGENTREADY-1 adds `viaAgent` to it and to `history."ChangeRecord"`.
- Web. `apps/web/src/components/app-shell.tsx` holds the sidebar; routes are in `apps/web/src/app.tsx`. `libs/shared/ui/src/components/ui/` has `card`, `table`, `button`, `input`, `alert-dialog`, `skeleton`, `badge` and others. It has no chart component.
- Schemas. Each module has its own Postgres schema file, such as `apps/api/prisma/schema/mcp.prisma`. Python modules have `models.py` and Alembic revisions.
- No timer or job runner exists in either starter (`git grep -i "cron\|schedule\|pg-boss\|apscheduler"` over both finds nothing).
- No model library exists in either starter. `starter/package.json` pins `zod` 4.1.12. Python needs `>=3.14` (`pyproject.toml`).
- `src/forge/templates/conventions/deploy.md` says Mainline shows an app's MCP path under Connectors and that its gateway sends the agent key. Nothing in the repo describes Mainline's model service. So the wire shape of the Mainline client is not known here (see Planner choices).

### Libraries this story pins

Checked on 28 Oct 2026 against npm and the Python index. A part checks the current releases again when it starts and keeps these unless a security notice says otherwise.

- TypeScript: `langchain` 1.6.0 (its `createAgent` is the prebuilt tool-calling agent), `@langchain/langgraph` 1.5.3, `@langchain/langgraph-checkpoint-postgres` 1.1.2, `@langchain/core` 1.3.1. For the chart, the shadcn `chart` component, which uses `recharts` 3.10.1.
- Conflict to settle first: `@langchain/langgraph` 1.5.3 asks for `zod` `^3.25.32 || ^4.2.0`, and the starter pins 4.1.12. The part raises `zod` in the starter to the newest 4.x and runs the starter's whole test run before it adds the rest.
- Python: `langchain` 1.4.7 (its `create_agent` is the prebuilt agent), `langgraph` 1.2.18, `langgraph-checkpoint-postgres` 3.2.0, `psycopg-pool` 3.3.3. The starter's `psycopg` 3.3.6 and `pydantic` 2.14.0 stay. The chat model class comes from `langchain-openai` 1.7.3 only if Mainline's model service is OpenAI-compatible (see Planner choices).
- If the first client asks later and these have moved, the build uses the newest release that passes the starter's tests, and its plan notes the change.

### Words this story pins

ASSIST pins each name. ASSISTPY follows it.

- Module: TypeScript `libs/assistant/{contracts,server,web}` (`@app/assistant-contracts`, `@app/assistant-server`, `@app/assistant-web`). Python `app/assistant/` and `libs/assistant/contracts` (the TypeScript types of the API, as `libs/projects/contracts` does there).
- Off by default. The module's code, schema file, migration and libraries are in the tree. It is not imported in `app.module.ts` (Python `app/main.py`), and `app-shell.tsx` and `app.tsx` have no Assistant entry. `libs/assistant/README.md` lists the steps to turn it on: add the module import, add the route and the sidebar entry, set `MAINLINE_AI_KEY` and its settings in `.env`, then deploy. Python's `app/assistant/README.md` lists the same. The README is the only place that lists the steps.
- Settings: `MAINLINE_AI_KEY` (the owner's name) and `MAINLINE_AI_URL`, `ASSISTANT_MODEL`. The module reads them only when it is imported. `validateEnvironment` requires them only then.
- Permission: `assistant.use`, held by every role that can sign in, so the module needs no role change. An admin can remove it from a role.
- Endpoints, under `/api/v1/assistant`:
  - `POST /chats` makes a chat. It answers `{ id }`.
  - `GET /chats` lists the caller's own chats, newest first.
  - `GET /chats/:id` gives the caller's own chat with its messages and any open confirm card. Another person's chat answers `404 NOT_FOUND`, for an admin too.
  - `POST /chats/:id/messages` takes `{ text }` (1 to 4,000 characters) and the `Idempotency-Key` header. It answers `text/event-stream`.
  - `POST /chats/:id/confirm` takes `{ confirmId, decision: 'confirm' | 'cancel' }` and answers the same stream.
- Stream events: `text` (`{ delta }`), `block` (`{ kind, props }`), `confirm` (`{ confirmId, title, lines, expiresAt }`), `limit` (`{ message }`), `error` (`{ message }`) and `done`.
- The five blocks, in `@app/assistant-contracts` as zod schemas (Python generates the same JSON shape from Pydantic models, and `libs/assistant/contracts` holds the TypeScript types):
  - `table`: `{ columns: { key, label }[], rows: Record<string, string | number | null>[], total?: number }`.
  - `chart`: `{ type: 'bar' | 'line', xKey, series: { key, label }[], rows: Record<string, string | number>[], unit? }`.
  - `stats`: `{ tiles: { label, value, unit? }[] }`.
  - `detail`: `{ title, fields: { label, value }[] }`.
  - `confirm`: `{ confirmId, title, lines: string[], expiresAt }`.
- Choosing a block. `libs/assistant/server/src/assistant.display.ts` (Python `app/assistant/display.py`) holds one map from tool name to a function that turns that tool's typed result into block props. A search tool maps to `table`, a get tool to `detail`, a report tool to `chart` or `stats`, as its result fields say. A tool with no entry shows its summary text only. Code makes the block. The model's text sits beside it and cannot change it.
- Writes. A tool whose annotations say `readOnlyHint: false` stops at `interrupt()` with `{ confirmId, tool, args }` before it runs. The stream sends a `confirm` event. `confirm` resumes with `Command(resume=...)`; `cancel` resumes with a refusal that the model sees as the tool's result. The retry key for the write is `<chatId>:<toolCallId>`, which is the same on every re-run of the node. A create tool takes it as `idempotency_key`. An update, delete or restore has no key and is safe to run again.
- Expiry. `confirm` after `expiresAt` (15 minutes after the card is made) answers with the stream's `error` event "That change expired. Ask again." and runs nothing.
- Tables, in the `assistant` schema: `chat` (`id` uuidv7, `accountId` link, `threadId`, `createdAt`, `lastMessageAt`), `usage` (`id`, `accountId`, `chatId` link, `kind` text with a named check (`llm`), `inputTokens`, `outputTokens`, `costMicros` nullable, `createdAt`). The checkpointer's own tables sit in the `assistant` schema too (`PostgresSaver.setup()` run in the module's migration step, not at start). All columns follow the database skill: uuidv7 ids, `timestamptz`, named checks.
- Clean-up. The module starts one timer when it is imported. Each hour it deletes chats whose `lastMessageAt` is more than 30 days old: `deleteThread(threadId)` on the checkpointer, then the `chat` row, inside one transaction where the driver allows it. `usage` rows stay (they hold no text). The timer is idempotent, so two API instances running it do no harm. The 30 days and the hour are named constants.
- The agent. One `createAgent` (Python `create_agent`) per turn, with the Mainline chat model, the tools from `listTools(context)` turned into LangChain tools whose `func` calls `callTool(name, args, context)`, the Postgres checkpointer, the person's `thread_id`, and `recursion_limit` 6. The run context holds the person's principal with `viaAgent: 'the assistant'` (Python `via_agent="the assistant"`); the model cannot pass a user id. The system prompt is one file, `assistant.prompt.ts` (Python `prompt.py`), at most 12 KB, with a `PROMPT_VERSION` constant. Tool definitions stay in the first part of the prompt and `tool_choice` stays auto.
- The Mainline client: one file, `mainline.ts` (Python `mainline.py`). It builds the chat model from `MAINLINE_AI_URL` and `MAINLINE_AI_KEY`, checks that `ASSISTANT_MODEL` is on the app's Can use list when the module starts (a model not on it stops the start with a plain message), and turns a refusal for budget into the stream's `limit` event with the line "The assistant is paused for now. The rest of the app works as usual." No other file reads `MAINLINE_AI_KEY`.

### How the build meets the agents skill

These sections of the agents skill apply: Agent shape, The turn, Tool design, Output and side effects, Safety and privacy, Cost and tracing, Testing and prompt changes. The sections Fast decisions before the model, Context and the prompt cache, Memory: writing, Memory: recall and Spoken chat do not apply, because this story has no classifier, no memory notes and no speech; a later story that adds one takes that section. A Must rule about a thing the change does not have (an image, a file, a note) is not broken. The rules that need a decision here:

- **Agent shape.** The prebuilt agent loop only, behind one `handleTurn` function (owner decision). A step limit of 6 per turn, as the skill's default says. After two failed tries at one goal, the assistant says it cannot do it and points the person to the matching screen. The dev log writes the exact model request for one turn in ten.
- **The turn.**
  - Fail once quietly: a `RetryPolicy` on the model node, one retry, a 20 s provider wait, and one honest error line when it fails again.
  - Speed target: first text within 7 s for 95% of turns. The trace line carries the first-text time. The stream shows text as it is written.
  - Not met, with the reason: *acknowledge fast through an inbox table* and *steering*. The web request is the queue, and the page disables Send while a turn runs, so no second message arrives in a running turn. One run per chat is held by a Postgres advisory lock on the chat id; a second message gets `409 CONFLICT` "The assistant is still answering." Needs the owner's OK (Planner choice 4).
- **Tool design.** The tools are the app's MCP tools, which FORGE-MCP-1 builds to these rules. The assistant shows at most 15 tools. If an app has more, the turn passes the 15 whose features the person can use, ordered by the person's last use, and the plan for that client says so.
- **Output and side effects.**
  - Identity comes from the signed-in session (`@CurrentAccount()`), never from the model.
  - Code owns facts: a block shows the tool's own values; the model's text never repeats a figure that a block holds, and the prompt says so.
  - Writes run once with a confirm: `interrupt()` before the write, a retry key on the write, and the 15-minute expiry. The limit check is the service's own, in its transaction.
  - One reply path: the message endpoint takes `Idempotency-Key` through the agent-ready helper (`RetryKeys.once`, Python `create_once`), action name `assistant_message`. A resent message with the same key gives back no second turn.
  - Limits never break a feature: a refusal for budget, or a model stop reason, gives the `limit` line and a log line `limit_hit`.
- **Safety and privacy.**
  - Delete means every copy: the clean-up removes the chat row and the checkpoints. Nothing else holds chat text: the history keeps the action and not the words, the trace line holds no message text, and no tool or admin screen reads a chat.
  - Never take secrets: the prompt tells the assistant to refuse a password or a card number and to point to the screen. A test sends one.
  - Not met, with the reason: *a way to a human* and *consent before personal questions*. The app has no human inbox, and the assistant asks no personal question; it works only on the app's own data. The assistant's help line says "Ask an admin of your organisation for anything the assistant cannot do." Needs the owner's OK (Planner choice 4).
- **Cost and tracing.** Every model call goes through the one Mainline client. Each turn writes one `usage` row for the person. Each turn writes one JSON log line with `promptVersion`, a hashed account id, the tools called, the timings and the `limit_hit` flag. There is no tracing provider, so there is nothing to erase there.
- **Testing and prompt changes.** Bug first and one job per layer, as the skill says. The tests use a stub of Mainline's model service that is a test file only; production code has no test setting. The prompt has a byte budget test. Not met, with the reason: *a calibrated judge*. No quality judge exists yet, and the cases use answer keys. Needs the owner's OK (Planner choice 4).

### Done-when details

1. Text and blocks.
   - TypeScript app cases, in `apps/api/test/assistant.e2e-spec.ts`, with the module turned on by the test's own app module and the Mainline stub answering with a fixed tool call and a fixed text:
     - `a question about projects streams text and a table block of the person's own projects`
     - `a report question streams a chart block and stat tiles from the report service`
     - `a tool with no display entry streams its summary text only`
     - `the stream never carries markup that the model wrote` (the stub returns `<script>`; the text event holds it as plain text and no block holds it)
     - `a message over 4000 characters gets 400 VALIDATION_ERROR`
   - Python app cases, in `tests/test_assistant.py`, with the same names in snake case.
   - Web unit cases, in `libs/assistant/web/src/**/*.test.tsx`: `each block kind renders from its props with the design system's components`; `an unknown block kind renders nothing`; `Send is disabled while a turn runs`.
   - Test `tests/test_assistant.py::test_1_a_person_asks_and_reads_text_and_blocks`, parameters `typescript` and `python`. Live: the reports hold the API cases and, for `typescript`, the web unit cases.
2. Confirm before every write.
   - API cases: `a write stops at a confirm card and changes nothing`; `confirm makes the change once`; `confirm sent twice makes one change`; `a message sent again with the same Idempotency-Key runs one turn`; `cancel changes nothing and tells the model`; `a confirm after 15 minutes runs nothing`; `a second message while a turn runs gets 409`.
   - Test `tests/test_assistant.py::test_2_every_write_waits_for_a_confirm`, parameters `typescript` and `python`.
3. The person's identity.
   - API cases: `the assistant lists only what the person's role allows`; `a person without the permission gets the tool's plain refusal`; `a change made through the assistant is in the history as the person, via the assistant`; `the model cannot choose another user` (the stub asks for another account id as a tool argument; the tool schema has no such field and the call fails validation).
   - Test `tests/test_assistant.py::test_3_the_assistant_acts_as_the_person`, parameters `typescript` and `python`.
4. Chats kept 30 days.
   - API cases: `a person lists only their own chats`; `another person and an admin get 404 for a chat`; `a chat 31 days after its last message is deleted with its checkpoints`; `a chat 29 days after its last message stays`; `a new message moves the 30 days`. The clean-up case calls the module's exported `deleteExpired(now)` (Python `delete_expired(now)`) with a given time, so no test waits.
   - Test `tests/test_assistant.py::test_4_chats_are_private_and_kept_30_days`, parameters `typescript` and `python`.
5. Mainline.
   - API cases: `the module reads MAINLINE_AI_KEY and no other file does` (a source check inside the app's own tests); `a model not on the Can use list stops the module's start with a plain message`; `a budget refusal streams the limit line and the app's other routes still work`; `each turn writes one usage row for the person`; `each turn logs one line with the prompt version and a hashed account id and no message text`; `the prompt stays under 12 KB`.
   - Test `tests/test_assistant.py::test_5_the_model_comes_from_mainline`, parameters `typescript` and `python`.
6. Off by default, nothing for existing apps.
   - Test `tests/test_assistant.py::test_6_the_module_is_off_until_turned_on`, parameters `new typescript`, `new python` and `earlier adopted`.
     - New apps: `app.module.ts` (Python `main.py`) has no assistant import, `app-shell.tsx` has no Assistant entry, and the app's own run with no `MAINLINE_AI_KEY` starts and passes its existing cases. `libs/assistant/README.md` (Python `app/assistant/README.md`) lists the turn-on steps.
     - `earlier adopted`: after upgrade and `forge sync`, the files under `apps/` and `libs/` are unchanged and the repo has no `libs/assistant` and no `app/assistant`.

### New and existing repos

- **New repos** (`forge init --starter`, `forge init --starter python`): the module in the tree, off, with its libraries, tables and README. Plain `forge init` and a newly adopted app get none of it.
- **Existing repos** (on upgrade, after `forge sync`): the guide text from GUIDE only. They get no app file, no library and no migration. Adding the assistant to an existing app is a separate choice, made by a story for that app.

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing | Developer |
|---|---|---|---|---|---|---|---|---|
| ASSIST | The assistant in the TypeScript starter | The `assistant` module in the TypeScript starter: contracts with the five blocks, the Mainline client, the agent over the app's tools, the confirm step, the chat tables and clean-up, the display map and the off-by-default README. | 3, 4, 5 | `src/forge/templates/starter/libs/assistant/contracts/` (new), `starter/libs/assistant/server/` (new), `starter/libs/assistant/README.md` (new), `starter/apps/api/prisma/schema/assistant.prisma` (new), `starter/apps/api/prisma/migrations/<UTC yyyyMMddHHmmss>_assistant/` (new), `starter/apps/api/test/assistant.e2e-spec.ts` (new), `starter/package.json`, `starter/pnpm-lock.yaml`, `starter/tsconfig.base.json`, `starter/apps/api/src/app.module.ts` (a comment line only) | `tests/test_assistant.py` (`test_3`, `test_4`, `test_5`, new) | | no | |
| ASSISTPY | The assistant in the Python starter | The same module in the Python starter: `app/assistant/` with models, routes, agent, display map, Mainline client, clean-up, README and its Alembic revision, and the TypeScript types in `libs/assistant/contracts`. | 3, 4, 5 | `src/forge/templates/starter-python/apps/api/app/assistant/` (new), `starter-python/apps/api/migrations/versions/<next>_assistant.py` (new), `starter-python/apps/api/tests/test_assistant.py` (new), `starter-python/apps/api/pyproject.toml`, `starter-python/apps/api/uv.lock`, `starter-python/libs/assistant/contracts/` (new), `starter-python/libs/shared/api-types/` (regenerated) | `tests/test_assistant.py` (the `python` cases) | ASSIST | no | |
| WEB | The Assistant page and the five blocks | The page, its hooks, the stream reader, the five block components and the shadcn chart component, off until turned on. | 1, 2 | `src/forge/templates/starter/libs/assistant/web/` (new), `starter/libs/shared/ui/src/components/ui/chart.tsx` (new), `starter/libs/shared/ui/package.json`, `starter/apps/web/vitest.config.ts` (only if the glob misses the new folder), `starter/package.json`, `starter/pnpm-lock.yaml` | `tests/test_assistant.py` (`test_1`, `test_2`, new) | ASSIST | yes | |
| GUIDE | The guides name the optional assistant | The optional-module line in the coordinator's guide, the worker brief sentence, the guide paragraph, the synced copies and the existing-repo case. | 6 | `src/forge/templates/skill.md`, `src/forge/templates/brief.md`, `docs/guide.md`, `.claude/skills/forge/SKILL.md`, `.codex/skills/forge/SKILL.md` | `tests/test_assistant.py` (`test_6`, new) | | no | |

ASSIST pins the contract, the endpoints, the block shapes and the table names. ASSISTPY and WEB use them, so they wait for it. WEB's page is shared by both starters. GUIDE shares no file with the others and can start now; the starters' files wait for the two stories named above. ASSISTPY and WEB share `tests/test_assistant.py` and `starter-smoke.yml` lines with ASSIST, so those edits go in ASSIST's commit as stubs that the later parts fill in.

New moving parts: the LangGraph libraries and `langchain` in each starter (items 1 to 3); the Postgres checkpointer's tables (item 4); a one-hour clean-up timer in each API (item 4); the Mainline model client (item 5).

## Notes

- **Scores (F x H >= 2 x C).**
  - The module as a switch, in each starter: F 1 (only a client that asks), H 2 (wrong answers or a bad write), C 3 (a new module, tables and a timer). 2 < 6. It fails the score. It stays because the owner decided it on 28 Oct 2026 and said it is built when the first client asks. The plan keeps the cost down: no custom graph, no new command, no new job runner.
  - Retry key on the write: 2 x 2 = 4 >= 2 x 1. Kept; it reuses the agent-ready helper.
  - A chart component: F 2, H 1, C 2. 2 < 4. Cut as a separate item; the chart block is the owner's decision and is the one place the component is used.
  - A user "delete my chat" button: not asked. Cut.
  - A tracing provider: cut. One JSON log line stands in.
  - A quality judge, a classifier, memory notes, speech: cut for now (see How the build meets the agents skill).
- **Owner decisions (28 Oct 2026, settled).** Optional module in both starters, turned on only when a client asks, planned now. The loop runs in each app's API with LangGraph's prebuilt tool-calling agent only. It works over the app's MCP tools with the person's identity. Generative UI is the fixed five-part set from typed tool results. Reads run at once, writes use a confirm card through `interrupt` and a retry key. Analytics come from report services. Model, key, allowed models and budget come from Mainline. Chats kept 30 days in Postgres through the checkpointer, then deleted, private. The build follows the agents skill, web chat only. Design: none.
- **Planner choices the owner did not make.**
  1. The module ships in every new app, off, with its libraries, and a README holds the turn-on steps. The alternative is a copy-in command, which is a new command.
  2. The 30 days count from the last message. The clean-up is an hourly timer in the API, because the starters have no job runner.
  3. A trace is one JSON log line with the prompt version and a hashed account id, because no tracing provider is set up.
  4. **Three rules of the agents skill are not met, with reasons, and need your OK:** acknowledge through an inbox table and steering (the web page disables Send while a turn runs, and an advisory lock holds one run per chat); a way to a human and consent before personal questions (the app has no human inbox, and the assistant asks no personal question); a calibrated judge (none exists yet).
  5. The Mainline client is built for an OpenAI-compatible model service, with `MAINLINE_AI_URL` and `ASSISTANT_MODEL` as settings. Nothing in this repo describes Mainline's model service, so the first client's build checks its real shape and changes only `mainline.ts` (`mainline.py`).
  6. Write tools are the ones whose annotations say they do not only read. A confirm card expires after 15 minutes, which is the skill's default.
  7. The retry key for a write is the chat id and the tool call id, so a re-run after a confirm makes one change.
  8. The assistant shows at most 15 tools, as the skill's default says.
  9. A new `assistant.use` permission, held by every role that signs in.
  10. A person's message is capped at 4,000 characters.
  11. Four parts: ASSIST (TypeScript API), ASSISTPY (Python API), WEB, GUIDE.
  12. The chart uses the shadcn chart component, which adds one component to the design system. It is the only new component.
- No client repo is named in this story's code, tests, texts or commits.
