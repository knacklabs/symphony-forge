# Python assistant storage

This optional package stores private chats in Postgres. A chat expires 30 days
after its last accepted message. Clean-up runs at API start and once each hour.
It deletes the chat and all its LangGraph checkpoints, blobs and pending writes.
The package ships no page, route or agent tool.

## Copy into an app

From the app root, copy these paths from
`.codex/skills/agents/assistant-module/python/` (or `.claude/skills/`):

- `apps/api/app/assistant/` to `apps/api/app/assistant/`.
- `apps/api/migrations/versions/20261106_assistant.py` to the same app path.
- `apps/api/tests/test_assistant_chats.py` to the same app path.
- `apps/api/tests/test_assistant_model.py` to the same app path.
- `apps/api/migrations/versions/20261106_assistant_usage.py` to the same app path.

In the copied app's `apps/api/tests/test_module_schemas.py`, add these entries at
the start of `EXPECTED_TABLE_SCHEMAS`, before the existing `core.*` entries:

```text
    "assistant.chat",
    "assistant.checkpoint_blobs",
    "assistant.checkpoint_migrations",
    "assistant.checkpoint_writes",
    "assistant.checkpoints",
    "assistant.usage",
```

Keep every existing entry and the exact inventory assertion. The check still
rejects missing tables, extra tables and tables in the wrong schema. Change only
the copied app's test; the starter has no assistant tables.

The migration follows `20261105_notifications`. For an app with a different
Alembic head, set the copied revision's `down_revision` to that head. Keep one
Alembic history. Add `langgraph-checkpoint-postgres==3.2.0` to the dependencies in
`apps/api/pyproject.toml`. Also add `langchain-openai==1.7.4` for the model client.
Then run `uv --directory apps/api lock` and
`uv --directory apps/api sync --frozen`. Commit the updated lock file.
If the host sets `UV_FROZEN=1`, set it to `0` for the lock command only. That
command must update the lock file for the added dependency. Restore the host's
value after the lock command; keep `--frozen` on the sync command.

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

## Model settings and spend cap

The optional module reads its provider settings only in `app/assistant/model.py`.
Its lifespan checks them before it opens the checkpointer connection. An app
without this module needs none of these settings. Keep the core settings loader
unchanged. The approved app-owned provider replaces the agents skill's
Mainline-only model rule until Mainline supplies that service.

Set these values in host settings or an uncommitted `.env`. Add dummy entries to
the copied app's `.env.example`:

```dotenv
ASSISTANT_AI_KEY=replace-with-provider-key
ASSISTANT_MODEL=replace-with-model-name
ASSISTANT_SPEND_CAP_USD=10
ASSISTANT_PRICE_INPUT_USD_PER_MTOK=1
ASSISTANT_PRICE_OUTPUT_USD_PER_MTOK=3
# Optional OpenAI-compatible endpoint:
ASSISTANT_AI_URL=https://provider.example/v1
```

For tests, edit `compose.test.yml`. Add these dummy settings under `environment`
in each service: `api`, `one-company-api` and `production-api`:

```yaml
ASSISTANT_AI_KEY: test-model-key
ASSISTANT_MODEL: test-model
ASSISTANT_SPEND_CAP_USD: "10"
ASSISTANT_PRICE_INPUT_USD_PER_MTOK: "0.15"
ASSISTANT_PRICE_OUTPUT_USD_PER_MTOK: "0.60"
```

Keep every existing setting. Host settings and `.env` values do not enter a
container unless Compose passes them. Use these dummy values only in the test
containers. The deployed app needs the real provider key, model and prices.

The prices are USD per million tokens for the chosen model. Set the actual
provider prices. There is no price guess or secret default. The cap accepts at
most six decimal places. Zero disables new answers. A missing or invalid required
value stops module startup with a plain message. The usage migration follows the
storage migration. Import `app.assistant` to register both models for Alembic.

Use `load_settings()` and `create_model(settings)` from `app.assistant.model`.
The client uses the configured model, key and optional URL, a 20-second timeout
and one retry. It requests token usage in streams. Do not make a second client or
read the key elsewhere. The turn part supplies the prebuilt agent.

Before an answer, call `UsageService(db).can_start(settings, datetime.now(UTC))`.
It sums `assistant.usage.cost_micros` for the whole app in the current UTC calendar
month. It returns false at the cap. Last month's rows stay available for cost
reports but do not count. A turn that starts below the cap can finish above it.
Use `LIMIT_MESSAGE` from `app.assistant.usage` for the stop line.

After the turn, calculate its cost with
`settings.cost_micros(input_tokens, output_tokens)`. Then call
`UsageService(db).record(principal, cost_micros)`. The service stores integer
micro-dollars, rounded up, with the person's account, organisation and UTC time.
These append-only cost rows contain no chat text and do not expire with chats.
The turn part owns the one-row-per-turn rule and the streamed limit line.

Use `SYSTEM_PROMPT` and `PROMPT_VERSION` from `app.assistant.prompt`. Keep the
static prompt under 12 KB. It treats tool output as data, leaves display parts to
code and requires confirmation before changes. Before accepting a message or
saving a checkpoint, call `contains_secret(text)` from `app.assistant.guard`.
If true, return `SECRET_MESSAGE` without saving or sending the text to the model.
The check finds labelled passwords, keys and one-time codes, and card numbers
with a valid checksum. It cannot identify a bare password without a label.

The model test copies this package into a new Python app and checks the monthly
sum against real Postgres. New starter apps have no assistant code or tables.
An upgrade changes no existing app code. Both receive the optional module through
the agents skill. Copying the template is an explicit app change. The turn and
page remain outside this part.
