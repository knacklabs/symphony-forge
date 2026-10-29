# Python (FastAPI)

The same backend, API, data, security, test and deploy rules in Python terms. The other pages'
rules still apply; their NestJS and Prisma code does not. Keep an existing app's stack and layout.

## Layout

```text
apps/api/
  pyproject.toml, uv.lock     uv project, Python checks and import contracts
  alembic.ini, migrations/   one Alembic history, with versions/0001_initial.py
  app/main.py                middleware, handlers, routers, /health and the web build at /
  app/openapi.py             writes OpenAPI without a database connection
  app/core/                  config, Base, session dependency, errors, envelope, logs, security
  app/auth/                  sign-in: __init__.py, models.py, schema.py, routes.py, service.py, mail.py
  app/projects/              example records: __init__.py, models.py, schema.py, routes.py, service.py
  tests/                     pytest HTTP tests against the running API
apps/web/                    route table, app shell, theme CSS and Playwright flows
libs/<module>/contracts/     zod schemas and types, exported as @app/<module>-contracts
libs/<module>/web/           module screens and hooks, exported as @app/<module>-web
libs/core/web/               API client, query client and route error page
libs/shared/ui/              shadcn/ui components and shared screen parts
libs/shared/api-types/       openapi.json and src/api-types.ts, exported as @app/shared-api-types
libs/shared/util/            general helpers copied from the TypeScript starter
pnpm-workspace.yaml          apps/web and libs/*/*; Python dependencies stay in uv
compose.test.yml             Postgres and test API instances
scripts/test.mjs             installs, builds and tests both sides
Dockerfile, .env.example     one image; dummy values for every variable
```

An app made before this layout keeps its own folders and schema; follow the folders it has.

The Python API stays in `apps/api`. Its React app uses the same module web libraries, shared UI
and core web libraries as the TypeScript starter. OpenAPI types stay in `libs/shared/api-types`.

## Modules

Each module owns its tables in its own `models.py`; auth owns account, session and
password_reset_token, and projects owns project. Its public entry is `__init__.py`.
Import another module only through that entry's public service and types, never its internal
files or tables. Links to core name the foreign key as a schema-qualified string, with no model import.
A link between business modules stores an indexed id without a foreign key and uses the other
module's public service to check it. Links within a module and links to core keep their foreign key.
A service queries its own data; move shared queries or raw SQL into a repository file.

```python
# app/projects/service.py
from typing import Annotated
from fastapi import Depends
from sqlalchemy.orm import Session
from app.core import get_session

class ProjectService:
    def __init__(self, session: Annotated[Session, Depends(get_session)]) -> None:
        self.session = session
```

Routes receive services through `Depends(ProjectService)`; services never build each other.
Export `ProjectService` and the router from `app.projects`. Auth exports its router,
`current_account` and `AccountPrincipal`; core exports what the modules use.
Call another module's public service when this action needs its answer; send an in-process
event only when the story names it and the action needs no answer, as backend.md says.
Add an interface only for an external service or a real second implementation.

The `pyproject.toml` import-linter check has `root_package = "app"` and a `protected`
contract per module. Add a contract for each new module; run `lint-imports` in the root test script:

```toml
[[tool.importlinter.contracts]]
name = "projects internals"
type = "protected"
protected_modules = ["app.projects.*"]
allowed_importers = ["app.projects"]
broken_contract_guidance = "A module uses another module only through its public service in its __init__.py, never through its internal files."
```

## Ready for agents

- Routes check their permission with `require_permission`, and agents reach the same services
  through `call_tool`, which checks the same permission. A later in-app agent calls `call_tool`
  with the person's principal and `via_agent` set, never a service directly.
- In an app with `app/core/retry_keys.py`, a create or a send, pay or notify action reads the
  `Idempotency-Key` header and runs through `create_once`, as the projects create does.
  The MCP tools use the same helper.
- Put each report in `app/<module>/reports.py`, one method per report, with Pydantic result
  models. Give agents a report with `define_tool` in the feature's tools file.

## Config

Only `app/core/config.py` reads environment variables. Validate `DATABASE_URL`, `APP_ENV`,
`APP_ORIGIN` and `PORT` once in FastAPI's lifespan; a missing or malformed value stops start-up
with a clear message. Secrets have no defaults. Keep `.env` out of git and list dummy values in
`.env.example`. Importing `app.main` reads no variables and opens no connection, so OpenAPI
generation works without Postgres. For example, inside the config loader:

```python
database_url = os.environ.get("DATABASE_URL")
if not database_url:
    raise RuntimeError("DATABASE_URL is required.")
```

## Logs

Log with `log_event(request, level, message, module, context)` from `app.core` (`app/core/logging.py`), not print and not the stdlib `logging` module. It writes one JSON line to stdout with the backend.md fields at the top level: `timestampUtc`, `level`, `message`, `context`, `environment` (from `APP_ENV`), `serviceName`, `module` and `correlationId`. Code without a request passes `None` with `environment` and `correlation_id`. The security middleware in `app/core/security.py` takes `x-correlation-id` or makes a UUID, keeps it on `request.state.correlation_id`, and returns it in the response; `log_event` adds it to each line, and outgoing calls send it. An app made before this starter keeps its own logger; follow the one it has.

Use fixed messages and ids only in context: `log_event(request, "info", "Project created", "app.projects", {"projectId": str(project.id)})`. Never log whole objects, passwords, tokens, one-time codes,
secrets or personal data. Levels are debug, info, warn, error and fatal. Log 4xx at debug and failed operations at error.

In an app whose `app/core/logging.py` has `set_log_level`, `log_event` removes secret values and writes nothing below `LOG_LEVEL`, which the lifespan sets at start with `set_log_level`. The security middleware writes the request line. Add no other request logging, redaction or error-tracking code.

## Errors

Register one set of handlers in `app/main.py`: `ApiError`, request validation and unexpected
exceptions. Keep UPPER_SNAKE_CASE codes in one list in core; messages are fixed, actionable text.
For example, a service raises:

```python
raise ApiError(404, "PROJECT_NOT_FOUND", "The project was not found.", None)
```

Handlers return `{"success": false, "data": null, "error": {"code", "message", "details",
"errorId"}}` with a new errorId, and log it with correlationId. Validation is 400 with
`details.fieldErrors: [{field, reason}]`, never FastAPI's default 422. A 500 uses a fixed
message; the stack goes to the log only. Never expose SQL, library errors or secrets.
A provider wraps its vendor's errors with our codes and types, sets timeouts, and retries only
failures that can succeed on retry; it holds no business logic. Never swallow unexpected errors.

## API

Routers live under `/api/v1`, with plural kebab-case nouns and POST for actions.
Each module's `schema.py` owns typed Pydantic request and response models. Pick response fields
explicitly, never return ORM objects. Web forms keep zod. For example:

```python
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

class CreateProject(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True,
                              alias_generator=to_camel, populate_by_name=True)
    name: str = Field(min_length=1, max_length=200, description="Project name",
                      examples=["Renovation"])
```

Use these settings on input models, including query models, and a maximum length on every string.
JSON names stay camelCase. Type successful responses with `Envelope[T]` from core, with
`success: true`, `data: T` and `error: null`. For example, on a projects router:

```python
@router.post("", status_code=201, response_model=Envelope[ProjectResponse],
             summary="Create a project.", tags=["Projects"],
             responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}})
```

Document every endpoint's summary, a short description, field examples, path and query parameters,
auth and error responses in OpenAPI at `/api/docs`. Use one PascalCase tag per module.
Status codes: 200 read, update, action or delete (delete has an envelope with null data, never
204); 201 create; 400 invalid input; 401 not signed in; 403 not allowed; 404 missing or another
account's record; 409 conflict; 429 rate limit; 500 our fault. GET never changes data.
PUT replaces a resource; PATCH changes part. Use plain query filters and `?search=`.
Lists take limit (20 by default, at most 100), one cursor (after or before), sortBy from an allowed column list, and sortOrder asc or desc. Return `data.items` and `data.paging` with limit, nextCursor, previousCursor, total and totalCapped, as `app/projects/service.py` does. Follow the standards page's versioning and Idempotency-Key rules.

After an API change, run `pnpm run api-types`. Commit both `libs/shared/api-types/openapi.json` and
`libs/shared/api-types/src/api-types.ts`; module contract libraries import these generated types
through `@app/shared-api-types`.

## Database

The database skill (`.codex/skills/database/SKILL.md`) has the rules for new tables, columns,
constraints, indexes and queries. This section has the SQLAlchemy and Alembic how-to. Existing
tables keep their current rules unless a story asks to change them. If the app's constitution
differs, follow it.

Use SQLAlchemy 2 typed models and synchronous sessions over psycopg on Postgres. Table and column
names are snake_case, tables singular. A model in its owning module's `models.py` looks like:

```python
class Project(Base):
    __tablename__ = "project"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, server_default=text("uuidv7()"))
    total: Mapped[Decimal] = mapped_column(Numeric(19, 4))
    total_currency: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="draft")
    is_archived: Mapped[bool] = mapped_column(default=False)
    created_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                   default=lambda: datetime.now(UTC))
    updated_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                   default=lambda: datetime.now(UTC))
    deleted_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint("status IN ('draft', 'active')", name="project_status_allowed"),
        {"schema": "projects"},
    )
```

Use a named CHECK constraint for the allowed status values. For money and other field types,
follow the database skill: an exact decimal with its own `*_currency` column.

Each module keeps its tables in its own Postgres schema. Organisation, account and sign-in
tables live in `core`; projects live in `projects`, and change history lives in `history`.
Set `__table_args__ = {"schema": "<schema>"}` on each model, or put that dictionary last in
the tuple when the model has constraints or indexes. Schema-qualify foreign keys, for example
`ForeignKey("core.account.id")`. Give an existing Postgres enum its owning `schema=` too.
New status fields use the named CHECK rule above.

Booleans have defaults.
Every domain table has id, created_at_utc and updated_at_utc; once there are accounts, add
created_by_account_id, modified_by_account_id and deleted_by_account_id. Updates set the time
and account; the shared `set_updated_at()` trigger sets updated_at_utc, and automated jobs use a
system account. Store `*_at_utc` in UTC. Follow the database skill for search and its indexes.
Soft delete sets deleted_at_utc; filter it in the query itself, together with the caller's scope:

```python
statement = select(Project).where(Project.id == project_id,
                                  Project.created_by_account_id == account.id,
                                  Project.deleted_at_utc.is_(None))
```

Hard delete is only for logs, temporary tables and data the client asked to erase.
Raw SQL belongs in a repository file and uses only `text()` with bound values, for example
`session.execute(text("SELECT id FROM projects.project WHERE id = :id"), {"id": project_id})`.
Index foreign keys, frequent filter columns and unique fields; name indexes
`idx_<table>_<column>`, for example `idx_project_created_by_account_id`.

## Migrations

Keep one Alembic history in `apps/api/migrations/`; env.py imports the modules' public entries
and uses Base.metadata from core. Generate a revision, then read and commit it:

```sh
uv --directory apps/api run alembic revision --autogenerate -m "<what>"
```

Never edit a merged migration. Put a data change in its own migration. Expand, then contract:
add a new table or column before code uses it, keep the old table or column for two releases, and
remove it only when no live release uses it. Mainline rollback restores the previous release's
code and keeps the database, so each migration must work with that code still running. Apply with
`alembic upgrade head`.
Close checks only migrations added by the change, and skips the check in a prototype repo with no
live release. A migration that drops or renames a table or column, or changes a column's type,
needs a `# Contract: ...` comment explaining why the live release no longer reads it. Close allows
the migration when the line is present; review reads the explanation.
Pass `include_schemas=True` to Alembic's `context.configure` in both online and offline modes.
Move tables and existing enums with `ALTER TABLE ... SET SCHEMA` and `ALTER TYPE ... SET SCHEMA`.
Indexes, foreign keys and triggers move with the table; shared trigger functions stay in `public`.
Run `alembic check` after migrations to check that autogenerate finds no model changes.

## Security

Use HTTPS in production and the core headers middleware with the React starter's helmet defaults.
CORS allows only APP_ORIGIN with credentials, never a wildcard. Reject unknown input fields.
Limit sign-up, sign-in, forgot and reset password to 30 requests per minute per client address;
the limit is per running instance. Health skips it. Protected routers require
`Depends(current_account)`; explicitly public auth routes opt out.
Every service scopes each query to the caller's account, including updates and deletes; another
account's id returns 404, never its data. A role check alone does not grant access.

Store a random, opaque session token's hash. The starter_session cookie is HttpOnly;
starter_csrf is readable by the web app. Both use SameSite=Lax, Path=/, an expiry and Secure
outside development and test. Mutating requests must send `x-csrf-token` matching the session's
CSRF token and pass the origin check. For example, setting the session cookie:

```python
response.set_cookie("starter_session", session_token, httponly=True, samesite="lax",
                    secure=config.app_env not in ("development", "test"), path="/",
                    expires=expires_at_utc)
```

Hash passwords with `hashlib.scrypt`, a random salt and constant-time comparison on verification.
Password reset answers never reveal whether an account exists; tokens expire and work once.
A deployed app never logs reset links or tokens. Keep secrets in environment variables, and
apply security.md's upload size, content-type and storage rules when uploads exist.

## Tests

Use pytest and httpx against the running API on a fresh real Postgres database per run, migrated
before tests and removed afterwards. Create data through the API, never direct inserts or a shared
seed. One end-to-end test per Done-when item that changes runtime behaviour, including its refusals;
settings, docs, deletions and test-only items use the check the item names. For example, with
an authenticated httpx client whose cookies and CSRF header came from sign-up through the API:

```python
def test_project_can_be_deleted(api: httpx.Client) -> None:
    created = api.post("/api/v1/projects", json={"name": "Renovation"})
    assert created.status_code == 201
    project_id = created.json()["data"]["id"]
    assert api.delete(f"/api/v1/projects/{project_id}").status_code == 200
    assert api.get(f"/api/v1/projects/{project_id}").status_code == 404
```

Cover invalid input, missing sign-in, CSRF and another account's records through HTTP.
Playwright walks new and changed UI flows as testing.md says, with zero retries and no sleeps.
Fake only third-party services at their edge. Unit tests are only for pure logic with many cases.

The root test script runs api-types before typecheck, lint (ESLint, `ruff check` and
`ruff format --check`), `mypy` with `strict = true`, `lint-imports`, pytest, hooks and
Playwright. Run `node scripts/test.mjs` to install, build and run the whole check, as forge.toml's
test command does.

## Deploy

One image holds the API and the web build: Node 24 builds the web app, Python 3.14 with uv runs
the API. Postgres comes from DATABASE_URL; config converts `postgresql://` to
`postgresql+psycopg://`. Run migrations before serving traffic and stop if they fail:

```sh
uv run --no-sync alembic upgrade head &&
exec uv run --no-sync uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-3000}" --no-access-log
```

Run this from apps/api. The image exposes port 3000, serves the web app at / and answers
`GET /health` with 200 after migrations succeed. Disable access logs: request URLs can hold
reset tokens. A GET accepting HTML outside /api and /health falls back to the web index.html.

The demo loader in `apps/api/app/demo/` is app code, not a module, and may read every table.
