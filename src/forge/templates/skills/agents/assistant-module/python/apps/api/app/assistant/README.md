# Python assistant storage

This optional package stores private chats in Postgres. A chat expires 30 days
after its last accepted message. Clean-up runs at API start and once each hour.
It deletes the chat and all its LangGraph checkpoints, blobs and pending writes.
The package ships private chat API routes, but no page or agent tool.

## Copy into an app

From the app root, copy these paths from
`.codex/skills/agents/assistant-module/python/` (or `.claude/skills/`):

- `apps/api/app/assistant/` to `apps/api/app/assistant/`.
- `apps/api/migrations/versions/20261106_assistant.py` to the same app path.
- `apps/api/tests/test_assistant_chats.py` to the same app path.
- `apps/api/tests/test_assistant_api.py` to the same app path.
- `libs/assistant/contracts/` to the same app path.

Run `pnpm install --no-frozen-lockfile` after the copy. Commit the workspace lock
file. The contracts use the app's existing Zod library.
Add `libs/assistant/contracts/tsconfig.json` to the `tsc --build` arguments in
the root `package.json` typecheck script.

In the copied app's `apps/api/tests/test_module_schemas.py`, add these entries at
the start of `EXPECTED_TABLE_SCHEMAS`, before the existing `core.*` entries:

```python
    "assistant.chat",
    "assistant.checkpoint_blobs",
    "assistant.checkpoint_migrations",
    "assistant.checkpoint_writes",
    "assistant.checkpoints",
```

Keep every existing entry and the exact inventory assertion. The check still
rejects missing tables, extra tables and tables in the wrong schema. Change only
the copied app's test; the starter has no assistant tables.

The migration follows `20261105_notifications`. For an app with a different
Alembic head, set the copied revision's `down_revision` to that head. Keep one
Alembic history. Add `langgraph-checkpoint-postgres==3.2.0` and
`langgraph==1.2.20` to the dependencies in
`apps/api/pyproject.toml`, then run `uv --directory apps/api lock` and
`uv --directory apps/api sync --frozen`. Commit the updated lock file.

Import `app.assistant` in `apps/api/migrations/env.py` to register the model.
LangGraph owns its four tables; Alembic must leave them unchanged. Add this
callback to both `context.configure` calls with `include_name=include_name`:

```python
from alembic.runtime.environment import NameFilterParentNames, NameFilterType


def include_name(
    name: str | None, type_: NameFilterType, parent_names: NameFilterParentNames
) -> bool:
    return not (
        type_ == "table"
        and parent_names.get("schema_name") == "assistant"
        and name
        in {
            "checkpoints",
            "checkpoint_blobs",
            "checkpoint_writes",
            "checkpoint_migrations",
        }
    )
```

Add an import-linter protected contract in `apps/api/pyproject.toml`:

```toml
[[tool.importlinter.contracts]]
name = "assistant internals"
type = "protected"
protected_modules = ["app.assistant.*"]
allowed_importers = ["app.assistant"]
broken_contract_guidance = "Use the assistant public service."
```

## Start and stop with the API

In `apps/api/app/main.py`, import `assistant_lifespan` from `app.assistant`.
Also import `router as assistant_router` and call
`app.include_router(assistant_router)` beside the other router registrations.
Inside the existing lifespan's `try`, wrap the MCP manager's context as follows:

```python
async with assistant_lifespan(
    session_factory, settings.database_url, settings.app_env
) as checkpoints:
    application.state.assistant_checkpoints = checkpoints
    async with manager.run():
        yield
```

Keep the existing engine disposal in `finally`. Run `alembic upgrade head` before
starting the API, as the starter's Dockerfile already does. The assistant context
creates LangGraph's tables with `setup()` before serving requests, runs clean-up
at start, and waits for its timer to stop before closing the connection. A failed
startup stops the app. A later clean-up failure writes a fixed error line and
tries again at the next hour. No chat text is logged.

The checkpointer connection uses `search_path=assistant,public`; it must use the
same database as the app. Its connection closes at shutdown. Run `alembic check`
after startup to check the copied model and migration.

## Use storage

Use `ChatService(db).create(principal)` to make a chat. Use its UUID, converted
to a string, as LangGraph's `thread_id`. Before every checkpoint read, message,
model call or confirmation, call `ChatService(db).own_chat(principal, chat_id)`.
It checks both the account and organisation; another account gets 404, including
an admin. Do not export checkpoints through MCP or admin tools.

After checking a new message for secrets, call `touch(principal, chat_id)` when
accepting it. This moves the expiry date. Never checkpoint refused text.
`Cleanup(session_factory, checkpoints).delete_expired(now)` accepts a UTC time
and returns the number of chats removed. It removes checkpoints before committing
the chat deletion; a failed checkpoint deletion keeps the chat available for a
later clean-up attempt. The approved hourly timer replaces a separate job runner.

## Settings and remaining assistant parts

Storage uses the existing `DATABASE_URL` and no model key. The model part adds
validation in `app/core/config.py` for `ASSISTANT_AI_KEY`, `ASSISTANT_MODEL`,
`ASSISTANT_SPEND_CAP_USD`, `ASSISTANT_PRICE_INPUT_USD_PER_MTOK` and
`ASSISTANT_PRICE_OUTPUT_USD_PER_MTOK`. `ASSISTANT_AI_URL` is optional for an
OpenAI-compatible service with a custom address. Keep secrets in host settings
or an uncommitted `.env`; list dummy values in `.env.example`. An app that does
not import the module needs none of these settings.

The model and turn handling arrive in later parts. Build the
Assistant page in the client's design by the agents skill's assistant page rules.
The storage test copies this package into a new Python app and calls the public
clean-up service against real Postgres. The chat API part owns the full copy-in
and API proof. New starter apps have no assistant code or tables; upgrading an
existing app changes no app code. Copying this template is an explicit app change.

## Chat API and contracts

`POST /api/v1/assistant/chats` takes an empty object and returns the new chat id.
It requires the session's CSRF token. Supply `Idempotency-Key` to reuse the same
chat after a retry. The chat and retry record commit in one transaction.
`GET /api/v1/assistant/chats` lists only the signed-in person's chats, newest
message first. Use `limit` (20 by default, at most 100), and either `after` or
`before` from the returned paging object. Totals stop at 10,000.
`GET /api/v1/assistant/chats/{id}` returns the chat's text messages and pending
confirm card. Another person's chat returns 404, even for an admin.

`schema.py` defines the five block types and the six stream event types. The
browser contracts in `libs/assistant/contracts` use the same camelCase names.
Serialize events with `model_dump_json(by_alias=True, exclude_none=True)` so
optional block properties are absent when unset. The chat read response keeps
`confirm: null` when there is no pending card. These routes make no model call.
