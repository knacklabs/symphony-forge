# Log every API request safely in client apps

3 parts · Risks: none one-way · New moving parts: none

## What changes for you

- Each API request in a client app writes one log line. The line names the method, the route pattern (such as `/api/v1/projects/:id`), the status, the time the request took and the request id. It never holds the query string, the request body or the real path, so a search word or an id in the address does not reach the logs. Health checks and web pages write no line. (Source: your decision, 28 Oct 2026)
- A new setting, `LOG_LEVEL`, picks the lowest level that the app writes: `debug`, `info`, `warn` or `error`. It is `info` when it is not set. An unknown value stops the app at start with a clear message. (Source: your decision, 28 Oct 2026)
- The logger removes the values of password, token, secret, key and authorization fields from every log line's details, at any depth, before it writes the line. A mistake in a later feature then cannot put a password or a key in the logs. (Source: your decision, 28 Oct 2026)
- Error alerts come from Mainline. Mainline reads the error lines that the app already writes, and each error line carries its error id. The app gets no error-tracking service. The guides state this, so no story adds one. (Source: your decision, 28 Oct 2026)
- The standards page, the backend and Python guides, the deploy guide, the agent's guide and the worker brief state these rules. The constitution lists them as built in, so nobody asks the FDE about them. (Source: your decision, 28 Oct 2026)
- A new client repo gets all of this at `forge init`. An existing client repo gets the guide text with `forge sync` and keeps its app code. (Source: your decision, 28 Oct 2026)

## Why

Today a client app writes a log line only for an error, a rejected request at debug, and a local mail link. A successful request leaves no trace, so nobody can see which routes are slow or busy, or what a person did before a failure. The app writes every level, with no setting to turn detail down. The guides say "never log passwords or tokens", but nothing in the logger removes them, so one careless log call leaks a secret. Nothing says how errors reach a person, so a story could add an error-tracking vendor that Mainline makes unneeded.

## Done when

1. **In a new app from either starter, each API request writes one log line with its method, route pattern, status, time taken and request id, and never its query string. Health checks and web pages write no line. An existing app's code does not change.**
2. **In a new app from either starter, the log level setting picks the lowest level written. It is info when not set, and an unknown value stops the app at start with a clear message.**
3. **In a new app from either starter, password, token, secret, key and authorization values are removed from every log line's details.**
4. **The standards page, the backend, Python and deploy guides, the agent's guide and the worker brief state the request line, the log level, the removed values and that Mainline sends error alerts from the error lines, with no error-tracking service in the app. A new repo gets this text at init. An existing repo gets it with forge sync, and its app code does not change.**

## Risks

Risks: none one-way. Each part reverts with its pull request. No migration and no new dependency.

Trade-off: the default level is `info`, so the existing debug line "API request rejected" no longer shows by default. The new request line shows the same method and status at info.

Trade-off: the key rule removes any field whose name holds `key`, such as a `keyboardLayout`. Removing too much is safe; removing too little leaks.

Trade-off: until Mainline reads the error lines, nobody gets an alert, as today.

## For the builders

<!-- Everything from here down is for the agents. The owner doesn't see it when approving, and
tightening it needs no new approval. -->

Each new Forge test file starts with `STORY = "FORGE-REQLOG-1"`. Tests run the forge command and never import forge. For app behaviour, they name the cases that the app's own run reports, through `live_run` and `live_python_run` from `tests/test_starter_tree.py`, with `_require_cases`, `_junit_cases` and `require_feature_cases`, as `tests/test_mcp_resources.py::test_1` does. Live tests carry `@pytest.mark.platform` and `@pytest.mark.timeout(1800)`. `.github/workflows/starter-smoke.yml` lists and runs `tests/test_request_log.py` in both jobs, as it does `tests/test_mcp_resources.py`. The `earlier adopted` case uses `_adopted_files_after_sync` from `tests/test_mcp.py`.

### What exists (evidence)

- TypeScript logger. `JsonLogger` in `starter/libs/core/server/src/common/json-logger.ts` writes every level to stdout as JSON with `timestampUtc`, `level`, `message`, `context`, `environment`, `serviceName`, `module` and `correlationId` (from `correlationStorage`). It has no level filter and copies `context` as it is. `main.ts` builds it with `new JsonLogger()` before Nest reads config.
- TypeScript request id. `correlationMiddleware` in `common/correlation.middleware.ts` takes `x-correlation-id` (up to 128 characters) or makes a UUID, sets it on the response and runs the rest of the request in `correlationStorage`. `main.ts` registers it after `app.enableCors(...)` and before `express.static` and the web fallback. Nothing logs a finished request.
- TypeScript config. `validateEnvironment` in `libs/core/server/src/config/environment.ts` checks each setting and keeps module-level values that code without injection reads (`activeEnvironment` through `getAppEnvironment`, `activeRateLimits` through `getRateLimits`). Cases live in `apps/api/test/environment.e2e-spec.ts`.
- TypeScript log calls today: `AllExceptionsFilter` (5xx through `ErrorReporter.report` at error with `errorId`; 4xx at debug as "API request rejected"), `ErrorReporter` (`common/error-report.ts`, strips the query from `path`), and `LogMailProvider` (`mail/mail.provider.ts`, `resetUrl` and `inviteUrl` in development and test only).
- Python logger. `log_event(request, level, message, module, context, *, environment, correlation_id)` in `starter-python/apps/api/app/core/logging.py` writes the same fields. It has no level filter and copies `context`. Callers: `app/core/error_report.py`, `app/core/errors.py` (4xx at debug), `app/core/mail.py` (`resetUrl`, `inviteUrl`).
- Python request id. `install_security_middleware` in `app/core/security.py` sets `request.state.correlation_id`. It answers `OPTIONS`, the origin check (403) and the rate limit (429) itself, and calls `call_next` for the rest. It is the outermost middleware (`app/main.py` installs it last). The Dockerfile runs uvicorn with `--no-access-log`, which stays.
- Python config. `Settings` and `load_settings` in `app/core/config.py`. The lifespan in `app/main.py` stores the settings on `app.state.settings`. Cases live in `apps/api/tests/test_config.py`.
- Tests read info lines: `logEvents` in `apps/api/test/helpers.ts` and `compose_logs` in `apps/api/tests/test_api.py` find `resetUrl` and `inviteUrl` in the `api` and `one-company-api` services. `compose.test.yml` sets no `LOG_LEVEL`, so the default `info` keeps them. `production forgot-password does not log a reset link` asserts that the `production-api` log has no 43-character token; the request line holds none.
- Rules today. `src/forge/standards.md` "Errors and logs" lists the fields, the levels and "Never log passwords, tokens, one-time codes, secrets or personal data". `src/forge/templates/conventions/backend.md` "Logs" and `conventions/python.md` "Logs" describe the logger. `conventions/deploy.md` says to check the platform logs when a migration fails. `src/forge/templates/skill.md` has "- Built in: each UI or API crash writes one error report to the logs." in the TypeScript outline only.

### Words this story pins

REQTS pins each name. REQPY follows it.

- **The request line.**
  - `level`: `info` for every status. The 5xx error report stays the one `error` line, with its `errorId`, so Mainline alerts once per failure.
  - `message`: `API request`. `module`: `RequestLog` in TypeScript, `app.core.security` in Python.
  - `context`: exactly `{ method, route, status, durationMs }`. `method` is the HTTP method. `route` is the matched route pattern with the global prefix, or `null` when no route matched. TypeScript patterns use `:id` and Python patterns use `{project_id}`, as each framework writes them. `status` is the response status as a number. `durationMs` is a whole number of milliseconds.
  - The request id is the existing top-level `correlationId`. The line adds no `requestId` field.
  - Which requests: a path that starts with `/api/`, or is `/mcp` or starts with `/mcp/`. `/health`, static files and web pages write no line.
  - Never in the line: the query string, the real path, headers, the body, the client address.
- **TypeScript.**
  - New file `libs/core/server/src/common/request-log.middleware.ts` exports `requestLogMiddleware(logger: JsonLogger)`, which returns an Express middleware. `@app/core-server` exports it. In `main.ts`, move `app.use(correlationMiddleware)` up to right after `app.use(helmet())`, then register `app.use(requestLogMiddleware(logger))` after it, both before `app.enableCors(...)`. Nest adds each middleware in call order, and the CORS middleware answers a preflight `OPTIONS` itself and calls no later middleware, so a request log registered after it writes no line for a preflight.
  - The middleware reads `correlationStorage.getStore()` and `performance.now()` when the request comes in. On `response.on('finish')` it runs `correlationStorage.run(correlationId, () => logger.log('API request', 'RequestLog', context))`, because an event listener does not keep the async store. `route` is `` `${request.baseUrl}${request.route.path}` `` when `request.route` is set, else `null`. A preflight never reaches a route, so its `route` is `null`. Add a `ponytail:` comment that a request whose client leaves before the reply writes no line.
  - `LOG_LEVEL`: `Environment` gets `LOG_LEVEL: LogLevel`, with `export type LogLevel = 'debug' | 'info' | 'warn' | 'error'`. `validateEnvironment` reads it, defaults to `info`, and throws `LOG_LEVEL must be debug, info, warn or error.` for another value. It keeps the value in `activeLogLevel`, read through `getLogLevel()`, as `getAppEnvironment` does. Lines written before config runs use `info`.
  - `JsonLogger.write` returns without writing when the level ranks below `getLogLevel()`. The order is `debug`, `info`, `warn`, `error`, `fatal`; `fatal` always writes.
  - Removal: `JsonLogger.write` writes `context: removeSecrets(context)`. `removeSecrets` is a function in `json-logger.ts`, not exported. It walks objects and arrays at any depth. For each key, it lowercases the key and drops `_` and `-`. When the result contains `password`, `token`, `secret`, `key` or `authorization`, the value becomes the string `[removed]`. Other values stay as they are.
- **Python.**
  - `Settings` gets `log_level: str = "info"` as its last field. `load_settings` reads `LOG_LEVEL`, defaults to `info`, and raises `RuntimeError("LOG_LEVEL must be debug, info, warn or error.")` for another value.
  - `app/core/logging.py` gets `set_log_level(level: str) -> None` and a module value `_minimum_level = "info"`. The lifespan in `app/main.py` calls `set_log_level(settings.log_level)` after `load_settings()`. `log_event` returns without writing below the minimum, with the same order as TypeScript. `app.core` exports `set_log_level`.
  - Removal: `log_event` writes `"context": _remove_secrets(context)`, with the same rule and the same `[removed]` text.
  - The request line: `security_middleware` reads `time.perf_counter()` first. Before it returns, when the path matches, it calls `log_event(request, "info", "API request", "app.core.security", {...})`. `route` is `getattr(request.scope.get("route"), "path", None)`, except that the path `/{path:path}` becomes `None`. That path is `web_app` in `app/main.py`, the web fallback, which matches every unknown GET, including `/api/v1/missing-<word>`, and answers it with 404. The `OPTIONS` branch, which the middleware answers itself, has no route, so its `route` is `None`. In the rate-limit branch, `route` is `request.url.path`, because those paths are fixed text from `_RATE_LIMITED_PATHS`. For a streamed reply (MCP), `durationMs` is the time until the reply starts; say so in a `ponytail:` comment.
  - `.env.example` in both starters: add `# The lowest log level written: debug, info, warn or error.` and `LOG_LEVEL=info`.

### Done-when details

1. The request line. REQTS does TypeScript, REQPY does Python.
   - TypeScript app case, in `apps/api/test/api.e2e-spec.ts`: `each API request writes one log line without its query string`.
     - `GET /api/v1/projects?search=<word>` with no session and `x-correlation-id: <id>` (two fresh UUIDs) answers 401. The `api` log has one line with `message` `API request` and that `correlationId`. Its `level` is `info` and its `context` equals `{ method: 'GET', route: '/api/v1/projects', status: 401, durationMs }`, with `durationMs` a whole number of 0 or more.
     - `GET /api/v1/projects/<uuid>` gives a line whose `route` is `/api/v1/projects/:id`.
     - `GET /api/v1/missing-<word>` gives a line with `route: null` and status 404.
     - A successful request: a `request.agent(apiBaseUrl)` client signs up with `credentials()`, then sends `GET /api/v1/auth/me?search=<third word>` with its own correlation id. It answers 200, and its line has `route: '/api/v1/auth/me'` and `status: 200`.
     - A preflight: `OPTIONS /api/v1/projects` with `Origin: new URL(apiBaseUrl).origin` (the test run's `APP_ORIGIN`), `Access-Control-Request-Method: POST` and its own correlation id answers 204, and its line has `method: 'OPTIONS'`, `route: null` and `status: 204`.
     - `GET /health` with its own correlation id gives no line.
     - The whole `api` log holds none of the three words.
   - Python app case, in `apps/api/tests/test_api.py`: `test_each_api_request_writes_one_log_line_without_its_query_string`, with the same steps through `compose_logs("api")`. It signs up with the file's `sign_up(client)` helper, and its preflight uses `client.options` with `Origin: str(client.base_url).rstrip("/")`. The project route is `/api/v1/projects/{project_id}`, and the missing route's line has `route: null`, not `/{path:path}`. One more step: a POST with a foreign `Origin` header, refused before routing, gives a line with status 403 and `route: null`.
   - Test `tests/test_request_log.py::test_1_each_api_request_writes_one_log_line`, parameters `typescript` (REQTS), `python` (REQPY) and `earlier adopted` (REQTS).
     - New app: `forge init --starter react` has `libs/core/server/src/common/request-log.middleware.ts`; `forge init --starter python` has `"API request"` in `apps/api/app/core/security.py`.
     - Live: the API reports hold the app case.
     - `earlier adopted`: after upgrade and sync, the files under `libs/` and `apps/` are unchanged, and the repo has no `request-log.middleware.ts`.
2. The log level.
   - TypeScript config cases, in `apps/api/test/environment.e2e-spec.ts` under `describe('LOG_LEVEL configuration')`: `LOG_LEVEL defaults to info and accepts debug, info, warn or error` and `LOG_LEVEL refuses an unsupported value`.
   - TypeScript unit case, in `libs/core/server/src/common/json-logger.test.ts` (new; `apps/web/vitest.config.ts` runs `libs/*/*/src/**/*.test.ts` into `test-results/formats.xml`): `the logger writes nothing below LOG_LEVEL`. It calls `validateEnvironment` with `LOG_LEVEL: 'warn'` and spies on `process.stdout.write`. `debug` and `log` write nothing; `warn`, `error` and `fatal` write one line each. Reset the level to `info` after the case.
   - Python cases, in `apps/api/tests/test_config.py`: `test_log_level_defaults_to_info_and_accepts_debug_info_warn_or_error` and `test_log_level_refuses_an_unsupported_value`. In `apps/api/tests/test_logging.py` (new): `test_the_logger_writes_nothing_below_the_log_level`, with `set_log_level("warn")`, `log_event(None, ...)` and `capsys`. Reset to `info` in `finally`.
   - Test `tests/test_request_log.py::test_2_the_log_level_picks_the_lowest_level_written`, parameters `typescript`, `python` and `earlier adopted`.
     - New app: `.env.example` has `LOG_LEVEL=info`.
     - Live: the API reports hold the config cases. For `typescript`, `formats.xml` holds the unit case; for `python`, the API report holds `test_logging`'s case.
     - `earlier adopted`: after upgrade and sync, `.env.example` and the files under `libs/` and `apps/` are unchanged.
3. The removed values.
   - TypeScript unit case, in `json-logger.test.ts`: `the logger removes password, token, secret, key and authorization values`. A `log` call with the context `{ password: 'p', resetToken: 't', client_secret: 's', apiKey: 'k', Authorization: 'a', nested: [{ newPassword: 'n' }], projectId: 'x' }` writes a line whose `context` has `[removed]` for each of the six values and keeps `projectId: 'x'`. The written line holds none of the six values.
   - Python unit case, in `test_logging.py`: `test_the_logger_removes_password_token_secret_key_and_authorization_values`, with the same context.
   - The local mail lines keep `resetUrl` and `inviteUrl`, because the tests read them and their keys do not match. Those lines are written only in development and test.
   - Test `tests/test_request_log.py::test_3_secret_values_never_reach_the_logs`, parameters `typescript`, `python` and `earlier adopted`.
     - Live: `formats.xml` (TypeScript) or the API report (Python) holds the unit case.
     - `earlier adopted`: after upgrade and sync, `json-logger.ts` and `logging.py`, where present, are unchanged.
4. The guides (GUIDE). The text is pinned below. Compare with whitespace collapsed.
   - `src/forge/standards.md`, "Errors and logs", after the "Never log passwords" bullet:
     - "- An app with `libs/core/server/src/common/request-log.middleware.ts` (TypeScript) or `set_log_level` in `apps/api/app/core/logging.py` (Python) has the next three rules built into its logger. Another app keeps its own logger: it may write every level and keep secret values, so never log a secret there, and add these parts only in a story that copies the starter's logger."
     - "- The logger removes the value of any context field whose name holds `password`, `token`, `secret`, `key` or `authorization`, at any depth, and writes `[removed]`. Still log only the ids you need."
     - "- Each API request writes one `info` line, `API request`, with `method`, the matched `route` pattern, `status` and `durationMs` in its context and the request's `correlationId`. It never holds the query string, the real path, headers or the body. Health checks and web pages write no line."
     - "- `LOG_LEVEL` (`debug`, `info`, `warn` or `error`; `info` when unset) picks the lowest level written."
     - "- Mainline sends error alerts from the `error` lines, each with its `errorId`. Add no error-tracking service to the app."
   - `src/forge/templates/conventions/backend.md`, "Logs", after the correlation paragraph: "In an app with `libs/core/server/src/common/request-log.middleware.ts`, `requestLogMiddleware` writes the request line and `JsonLogger` removes secret values and reads `LOG_LEVEL` through `getLogLevel()`. Add no other request logging, redaction or error-tracking code."
   - `src/forge/templates/conventions/python.md`, "Logs", after the levels paragraph: "In an app whose `app/core/logging.py` has `set_log_level`, `log_event` removes secret values and writes nothing below `LOG_LEVEL`, which the lifespan sets at start with `set_log_level`. The security middleware writes the request line. Add no other request logging, redaction or error-tracking code."
   - `src/forge/templates/conventions/deploy.md`, after the migration-failure paragraph: "Mainline sends error alerts from the app's `error` log lines. Each carries an `errorId`, which the person sees on the error screen, so search the platform logs for it. In an app whose `.env.example` names `LOG_LEVEL`, set it in the platform's settings to change how much the app writes."
   - `src/forge/templates/skill.md`, after "In an app that has libs/organisations or apps/api/app/organisations, also copy the built-in lines into ## Fixed rules, and ask nothing about the defaults they answer.", a new paragraph, so an older app with `libs/organisations` does not copy a line its logger does not keep: "In an app with libs/core/server/src/common/request-log.middleware.ts or set_log_level in apps/api/app/core/logging.py, also copy this line into ## Fixed rules: "- Built in: each API request writes one log line with its method, route, status, time taken and request id, never the query string; LOG_LEVEL picks the lowest level written; password, token, secret, key and authorization values are removed from log details; Mainline sends error alerts from the error lines, so the app has no error-tracking service."" No outline gets the line, because the outlines' built-in lines are copied for every app with `libs/organisations`.
   - `src/forge/templates/brief.md`, after "...and let crashes reach the one error report.": "Add no error-tracking service; Mainline sends alerts from the error lines. In an app with `request-log.middleware.ts` or `set_log_level` in `app/core/logging.py`, the logger writes each API request's line and removes password, token, secret, key and authorization values from its context, so add no request logging or redaction there."
   - `src/forge/templates/conventions/backend.md`, "Logs", the logger example: `environment: process.env.NODE_ENV` becomes `environment: process.env.APP_ENV`, because the starter's `JsonLogger` reads `APP_ENV` through `getAppEnvironment()`. In `tests/test_standards.py::_logger_example_writes_the_documented_fields`, the run's environment sets `APP_ENV` instead of `NODE_ENV`, so the example still writes a non-empty `environment`.
   - `src/forge/templates/conventions/python.md`, "Logs": replace the section's text before the levels paragraph (the stdlib `logging` formatter and its example, and the `ContextVar` middleware and its example) with: "Log with `log_event(request, level, message, module, context)` from `app.core` (`app/core/logging.py`), not print and not the stdlib `logging` module. It writes one JSON line to stdout with the backend.md fields at the top level: `timestampUtc`, `level`, `message`, `context`, `environment` (from `APP_ENV`), `serviceName`, `module` and `correlationId`. Code without a request passes `None` with `environment` and `correlation_id`. The security middleware in `app/core/security.py` takes `x-correlation-id` or makes a UUID, keeps it on `request.state.correlation_id`, and returns it in the response; `log_event` adds it to each line, and outgoing calls send it. An app made before this starter keeps its own logger; follow the one it has." The levels paragraph's example becomes `log_event(request, "info", "Project created", "app.projects", {"projectId": str(project.id)})`, and "(logging WARNING and CRITICAL map to warn and fatal)" goes. The terms that `tests/test_python_guide.py` pins (such as `x-correlation-id` and `errorId`) stay on the page.
   - Test `tests/test_request_log_guide.py::test_4` also checks that the conventions folder's `backend.md` has `process.env.APP_ENV` and no `NODE_ENV`, and that `python.md`'s Logs section has `log_event(` and no `JSON formatter`.
   - `forge sync` rewrites `.claude/skills/forge/SKILL.md`, `.codex/skills/forge/SKILL.md`, `.claude/skills/forge/standards.md` and `.codex/skills/forge/standards.md`.
   - Test `tests/test_request_log_guide.py::test_4_the_guides_state_the_log_rules`, parameters `new init` and `previous release`, with the setup of `tests/test_mcp_resources_guide.py::test_3`.
     - Both synced skill copies have the new conditional paragraph with its Built in line once.
     - Both synced standards copies have the five bullets, the first naming `request-log.middleware.ts` and `set_log_level`.
     - The brief from `forge work` has the brief sentence.
     - The conventions folder that the brief names has the new lines in `backend.md`, `python.md` and `deploy.md`.
     - `previous release`: after `forge sync`, `git status --porcelain` lists only `LISTED` files.

### New and existing repos

- **New repos** (`forge init --starter react`, `forge init --starter python`): the request line, `LOG_LEVEL`, the removed values and the guide text. Plain `forge init` and a newly adopted app get the guide text only.
- **Existing repos** (on upgrade, after `forge sync`): the standards, skill, brief and convention text. They get no app file. Their logger stays as it is until a story copies the starter's logger. Items 1 to 3 each have a test on the adopted earlier-release fixture; item 4 has the `previous release` case.
- The feature command copies no logger file, so it needs no change, and an app made before this release builds features as today.

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing | Developer |
|---|---|---|---|---|---|---|---|---|
| REQTS | Request line, log level and removed values in the TypeScript starter | `requestLogMiddleware`, `LOG_LEVEL` in the environment and the logger, `removeSecrets` in the logger, `.env.example`, the app's cases, and the Forge test file with its TypeScript and earlier-adopted cases. | 1, 2, 3 | `src/forge/templates/starter/libs/core/server/src/common/request-log.middleware.ts` (new), `starter/libs/core/server/src/common/json-logger.ts`, `starter/libs/core/server/src/common/json-logger.test.ts` (new), `starter/libs/core/server/src/config/environment.ts`, `starter/libs/core/server/src/index.ts`, `starter/apps/api/src/main.ts`, `starter/.env.example`, `starter/apps/api/test/api.e2e-spec.ts` (the request case), `starter/apps/api/test/environment.e2e-spec.ts` (the level cases), `.github/workflows/starter-smoke.yml`, `tests/test_request_log.py` (new) | `tests/test_request_log.py` (`test_1`, `test_2`, `test_3`: `typescript`, `earlier adopted`) | FORGE-AGENTREADY-1/RETRY | no | |
| REQPY | Request line, log level and removed values in the Python starter | The same in the Python starter: the request line in the security middleware, `log_level` in the settings, `set_log_level` and `_remove_secrets` in the logger, the lifespan call, `.env.example`, and the app's cases. | 1, 2, 3 | `src/forge/templates/starter-python/apps/api/app/core/security.py`, `starter-python/apps/api/app/core/logging.py`, `starter-python/apps/api/app/core/config.py`, `starter-python/apps/api/app/core/__init__.py`, `starter-python/apps/api/app/main.py` (the lifespan call), `starter-python/.env.example`, `starter-python/apps/api/tests/test_api.py` (the request case), `starter-python/apps/api/tests/test_config.py` (the level cases), `starter-python/apps/api/tests/test_logging.py` (new), `tests/test_request_log.py` (the `python` cases) | `tests/test_request_log.py` (`test_1`, `test_2`, `test_3`: `python`) | REQTS, FORGE-AGENTREADY-1/RETRYPY | no | |
| GUIDE | The guides state the log rules | The standards bullets, the backend, Python and deploy guide lines, the conditional Built in paragraph for the constitution, the corrected Logs sections, the brief sentence and the synced copies, on new and existing repos. | 4 | `src/forge/standards.md`, `src/forge/templates/conventions/backend.md`, `src/forge/templates/conventions/python.md`, `src/forge/templates/conventions/deploy.md`, `src/forge/templates/skill.md`, `src/forge/templates/brief.md`, `.claude/skills/forge/SKILL.md`, `.codex/skills/forge/SKILL.md`, `.claude/skills/forge/standards.md`, `.codex/skills/forge/standards.md` (rewritten by `forge sync`), `tests/test_standards.py` (the logger example's environment), `tests/test_request_log_guide.py` (new) | `tests/test_request_log_guide.py::test_4` (new), `tests/test_standards.py` (the logger example) | FORGE-AGENTREADY-1/GUIDE | no | |

REQPY waits for REQTS because they share `tests/test_request_log.py` and REQTS pins the names. GUIDE needs no code from the other two parts.

New moving parts: none. The request line uses the existing logger and middleware (item 1). The level and the removal live in the existing logger (items 2 and 3).

## Notes

- **Order with other work.**
  - FORGE-AGENTREADY-1/RETRY changes `starter/apps/api/src/main.ts` (the CORS header) and `.github/workflows/starter-smoke.yml`, so REQTS waits for it.
  - FORGE-AGENTREADY-1/RETRYPY changes `starter-python/apps/api/app/core/security.py` (the CORS header) and `app/core/__init__.py`, so REQPY waits for it.
  - FORGE-AGENTREADY-1/GUIDE changes `standards.md`, `backend.md`, `python.md`, `skill.md` (Built in lines in the same outlines) and `brief.md`, so GUIDE waits for it.
  - FORGE-MAIL-1 adds `SMTP_URL` to `environment.ts`, `config.py`, both `.env.example` files and their config cases, and changes the mail module that writes `resetUrl` and `inviteUrl`. That is a merge on other lines, not a code dependency. If MAIL-1 removes the logged mail links, the removal rule does not change.
  - FORGE-GUIDES-1 changes `standards.md` (the environment-name line in "Errors and logs", next to these bullets), `backend.md`, `python.md`, the FDE defaults (its "error tracking" default text) and both READMEs. That is a merge, not a code dependency. This story does not touch the FDE defaults or the READMEs.
- **The acting agent.** Once FORGE-AGENTREADY-1 lands, a later story can add the acting agent to the request line as one context field from the principal's `viaAgent`. This story does not depend on it.
- **Scores (F x H >= 2 x C).**
  - Request line, in each starter: 3 x 2 = 6 >= 2. Kept.
  - `LOG_LEVEL`: 2 x 2 = 4 >= 2. Kept.
  - Removed values: 1 x 3 = 3 >= 2. Kept. No code logs a secret today, but a leak is a security finding.
  - Error alerts from Mainline, as guide text: 2 x 2 = 4 >= 2. Kept. No code is needed.
  - `accountId` in the request line: 2 x 1 = 2 < 4 in Python, where the account is known only inside each route's dependency and needs a new value on the request. Cut. A later story can add it with the acting agent.
  - A line for `/health`: 1 x 1 = 1 < 2. Cut; compose checks it every second.
  - A README line on `LOG_LEVEL`: 1 x 1 = 1 < 2. Cut; `.env.example` names it.
  - An end-to-end case that a sign-in password is not in the logs: cut. The unit case proves the rule, and the request line logs no body.
- **Logs sections.** `conventions/python.md` "Logs" described stdlib `logging` with a formatter while the Python starter uses `log_event`, and `backend.md`'s logger example read `NODE_ENV` while the code reads `APP_ENV`. GUIDE fixes both, because this story owns the Logs sections (FORGE-GUIDES-1 leaves them here).
- **Planner choices the owner did not make.**
  1. The request id is the existing `correlationId`; the line adds no `requestId` field.
  2. The line leaves out `accountId` (scored and cut above).
  3. The line is `info` for every status; the 5xx error report stays the one error line, so an alert fires once.
  4. Only `/api/` and `/mcp` paths write a line; `/health` and web pages do not.
  5. An unmatched route writes `route: null`, never the real path; so do a preflight and the Python web fallback (`/{path:path}`). The Python rate-limit refusal writes its fixed path.
  6. The default level is `info`, and the existing debug lines stop showing by default.
  7. `fatal` always writes; `LOG_LEVEL` accepts `debug`, `info`, `warn` and `error`.
  8. The key rule is "the name, lowercased with `_` and `-` dropped, contains one of the five words"; the value becomes `[removed]`; it walks nested objects and arrays.
  9. The local mail lines keep their links, because their keys do not match and they are written only in development and test.
  10. TypeScript writes the line when the reply finishes, so an abandoned request writes none. Python measures a streamed reply until it starts.
  11. The alert rule lives in the standards page and the deploy guide, with no code.
- No client repo is named in this story's code, tests, texts or commits.
