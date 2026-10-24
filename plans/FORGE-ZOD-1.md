# One zod schema checks every client app input

2 parts · Risks: none one-way · New moving parts: none

## What changes for you

- A new client app checks each request body and each list query with one zod schema in the shared library. The web form uses the same schema.
- A new client app does not include class-validator or class-transformer.
- A wrong value in the projects list query gets the same error reply as a wrong value in a request body.
- The API documentation of the projects list query and of each request body comes from the same zod schema, so the documentation and the checks cannot be different.
- The API and backend convention pages tell agents to write a zod schema for request input, not class-validator rules.
- In an app that uses zod, the review flags a new request body or query that no zod schema checks.
- An existing client app keeps its current validation. The review does not flag its current code, and an app without zod keeps its own validation for new code too.

Design: none (no screen changes; the change is in the API, its documentation and the rules)

## Why

The starter checks input two ways: class-validator on the projects list query and zod on request bodies. The API convention page tells agents to write class-validator rules, so new code follows the older rule and the starter ships two validators. The API documentation of each field is also written by hand, apart from the checks. On 24 October 2026 the owner chose zod for all input in TypeScript client apps, with the API documentation made from the same schema, and chose that existing apps keep their validation.

## Done when

1. **A new client app's dependencies have no class-validator or class-transformer.**
2. **A bad projects list query gets the same validation error reply as a bad request body.**
3. **The documented fields of the projects list query and of each request body come from the zod schemas in the shared library.**
4. **The API and backend convention pages name zod for request input.**
5. **In an app that uses zod, the review flags a new request body or query that no zod schema checks.**
6. **An existing client app keeps its current validation after upgrading.**

## Risks

<!-- Each one-way step: deleting data, a destructive migration, a new vendor. -->

Risks: none one-way. Each part reverts with its pull request. A client app owns its copy of the
starter after set-up, so no existing app changes.

Trade-off: an app made from an earlier starter has both zod and class-validator. Its new input
uses zod, and its current list query keeps class-validator until a change moves it.

## For the builders

<!-- Everything from here down is for the agents. The owner doesn't see it when approving, and
tightening it needs no new approval. -->

Each new test file starts with `STORY = "FORGE-ZOD-1"`. Each test runs the forge command or, for
the starter's own behaviour, reads the starter's files or runs its own commands, and never imports
forge. One test per Done-when item, named `test_<n>_...`. The API behaviour (items 2 and 3) is
proven by named API cases in the starter's `apps/api/test/api.e2e-spec.ts`, which `starter-smoke`
runs live through `tests/test_starter_tree.py` (`FORGE_STARTER_LIVE=1`). Forge-command tests run
on a new repo and on `tests/fixtures/adopted-v1.2.2` moved to this release, through
`_client_repo as setup_client` from `tests/test_score_notes.py`, with the stubs that
`tests/test_shadcn_only.py` uses (`env`, `finding`, `blocked`, `CLEAN` from `tests/test_close.py`;
`install_claude` and `calls` from `tests/test_worker.py`; its `_fix` helper).

**Plan against FORGE-REACTDEFAULTS-1's starter.** STARTER starts after
FORGE-REACTDEFAULTS-1/STARTER merges. That part changes the starter's `package.json`,
`pnpm-lock.yaml`, the web app and `BROWSER_FLOWS` in `tests/test_starter_tree.py`. Read the merged
starter before you start; where a line below differs from the merged tree, follow the merged tree.

**Words this story pins.** Each part owns its own words; no part needs the other part's code.

- The list query schema (STARTER), in `libs/shared/src/index.ts`, with its output type
  `ProjectListQuery = z.output<typeof projectListQuerySchema>`:

  ```ts
  export const projectListQuerySchema = z.object({
    page: z.coerce.number().int().min(1).default(1).meta({ description: 'The one-based page number.', example: 1 }),
    limit: z.coerce.number().int().min(1).max(100).default(20).meta({ description: 'The number of projects per page, up to 100.', example: 20 }),
    sortBy: z.enum(['name', 'status', 'createdAtUtc', 'updatedAtUtc']).default('createdAtUtc').meta({ description: 'The project field used to sort the list.' }),
    sortOrder: z.enum(['asc', 'desc']).default('desc').meta({ description: 'The sort direction.' }),
  }).strict();
  ```

- The documentation decorators (STARTER code, RULES page snippet), in
  `libs/core/src/common/api-zod.decorator.ts`, exported from `@app/core`:
  `ApiZodBody(schema: z.ZodType): MethodDecorator` (one `ApiBody({ schema })`) and
  `ApiZodQuery(schema: z.ZodObject): MethodDecorator` (one `ApiQuery({ name, required, schema })`
  per property, `required` from the JSON Schema's `required` list). Both turn the schema into JSON
  Schema with `z.toJSONSchema(schema, { io: 'input', target: 'openapi-3.0' })`. Checked on zod
  4.1.12 (the starter's pin): this gives `type`, `minimum`/`maximum`, `minLength`/`maxLength`,
  `enum`, `default`, and copies `.meta()`'s `description` and `example`; with `io: 'input'` a
  field with a default is not in `required`. No new library.
- API case names (STARTER), exact, in `apps/api/test/api.e2e-spec.ts` and in a new tuple
  `API_ZOD_CASES` in `tests/test_starter_tree.py`:
  - `rejects a bad list query with the same field errors as a bad body`
  - `documents the list query and request bodies from the shared zod schemas`
- The review finding title (RULES): `Zod: <the endpoint>`. No score floor: `src/forge/score.py`
  does not change.

### Done-when details

1. No class-validator or class-transformer (STARTER).
   - `package.json`: remove `class-transformer` and `class-validator`. Run `corepack pnpm install`
     so `pnpm-lock.yaml` drops them; `tests/test_starter_tree.py::test_1` still finds the lock's
     root importer equal to `package.json`. The `@nestjs/*` packages list both only as optional
     peers, so nothing else needs them. Their peer declaration lines (`class-validator: '>=0.13.2'`)
     stay in the lock; no resolved `class-validator@` entry stays.
   - `apps/api/src/main.ts`: remove the global `ValidationPipe` and its `exceptionFactory`. Nest's
     `ValidationPipe` loads class-validator when it is made, so the API cannot start with it.
     `ZodValidationPipe` on each `@Body` and `@Query` does the work. `BadRequestException` and
     `ValidationPipe` leave the import.
   - `libs/projects/src/projects.dto.ts`: remove `ProjectListQueryDto` and `ProjectInputDto`.
     `ProjectsService.list` takes `ProjectListQuery` from `@app/shared`.
   - `libs/auth/src/auth.dto.ts`: remove the request classes `CredentialsDto`,
     `ForgotPasswordDto` and `ResetPasswordDto`. The response classes stay.
   - README "How it works": one sentence that zod schemas in `libs/shared` check every request
     body and query, and that the API documentation comes from the same schemas.
   - Test (new repo): `tests/test_zod_starter.py::test_1_a_new_app_has_no_class_validator` reads
     the starter tree: no dependency group of `package.json` names either package; no line of
     `pnpm-lock.yaml` matches `class-(?:validator|transformer)@`; no other starter file names
     either package; `apps/api/src/main.ts` has no `ValidationPipe(`. No platform marker: it only
     reads files. The `starter-smoke` run builds and starts the API without them, and the current
     API case `rejects invalid input with field errors in the API envelope` shows body checks
     still work.
   - Existing repo: the starter is written only by `forge init --starter`;
     `tests/test_starter_app.py::test_3` (adopted case) already shows that upgrade and sync write
     no starter file. Item 6's test covers the existing app.
2. A bad list query gets the body's error reply (STARTER).
   - `libs/projects/src/projects.controller.ts`, `list`:
     `@Query(new ZodValidationPipe(projectListQuerySchema)) query: ProjectListQuery`.
     `ZodValidationPipe` (`libs/core/src/common/zod-validation.pipe.ts`) does not change: it
     already gives `VALIDATION_ERROR`, `Check the fields and try again.` and
     `details.fieldErrors`, with `Remove this field.` for an unknown field.
   - Query values arrive as strings; `z.coerce.number()` reads them. A repeated parameter
     (`?page=1&page=2`) arrives as an array and fails the number check; an empty one
     (`?page=`) becomes 0 and fails `min(1)`. Both are 400s, as they should be.
   - API case `rejects a bad list query with the same field errors as a bad body`: sign up. Send
     `GET /api/v1/projects?page=0&limit=500&sortBy=password&unexpected=true` and
     `POST /api/v1/projects` with `{ name: '', status: 'gone', unexpected: true }` (with the CSRF
     token). Both answer 400, and both bodies match `{ success: false, data: null, error: { code:
     'VALIDATION_ERROR', message: 'Check the fields and try again.' } }`. The query's
     `fieldErrors` hold `page`, `limit`, `sortBy` and `{ field: 'unexpected', reason: 'Remove this
     field.' }`; the body's hold `name`, `status` and the same `unexpected` entry. Then
     `GET /api/v1/projects?page=2&limit=5` answers 200 with `pagination.page` 2 and
     `pagination.limit` 5, so string values still coerce.
3. The documentation comes from the zod schemas (STARTER).
   - `list`: `@ApiZodQuery(projectListQuerySchema)`. `create` and `update`:
     `@ApiZodBody(projectSchema)` in place of `@ApiBody({ type: ProjectInputDto })`. The four auth
     body routes: `@ApiZodBody(<their schema>)` in place of `@ApiBody({ type: ... })`.
   - The descriptions and examples that the removed request classes held move to `.meta({
     description, example })` on the fields of `projectSchema`, `signUpSchema`,
     `forgotPasswordSchema` and `resetPasswordSchema` in `libs/shared/src/index.ts`. The web forms
     keep using these schemas; `.meta()` does not change a check.
   - The shared schemas use no `.transform()`: `z.toJSONSchema` throws on one. `.trim()` and
     `.toLowerCase()` are fine (checked on 4.1.12).
   - Test (new repo):
     `tests/test_zod_starter.py::test_3_the_request_docs_come_from_the_shared_zod_schemas` reads
     the starter tree: no `.ts` file under `libs/` or `apps/api/src`, except
     `libs/core/src/common/api-zod.decorator.ts` (which calls `ApiQuery` and `ApiBody` from the
     schema), has `ApiQuery(`,
     `ApiPropertyOptional` or `ApiBody({ type`; `libs/shared/src/index.ts` defines
     `projectListQuerySchema`; `libs/core/src/common/api-zod.decorator.ts` calls
     `z.toJSONSchema`.
   - API case `documents the list query and request bodies from the shared zod schemas`: get
     `/api/docs-json` (Nest's default JSON path for `SwaggerModule.setup('api/docs', ...)`; the
     web fallback skips `/api/`). `paths['/api/v1/projects'].get.parameters` are `page`, `limit`,
     `sortBy` and `sortOrder`, each `in: 'query'` and `required: false`; `limit`'s schema has
     `maximum: 100` and `default: 20`; `sortBy`'s `enum` is the four fields; `page`'s description
     is `The one-based page number.`. `paths['/api/v1/projects'].post.requestBody` JSON schema has
     `name` with `maxLength: 120` and `status` with `enum: ['active', 'archived']`, and
     `/api/v1/auth/sign-up`'s has `password` with `minLength: 12`.
   - `tests/test_starter_tree.py`: add `API_ZOD_CASES` (the two names) and require them with
     `API_SECURITY_TESTS` in `test_1`'s live branch. Nothing else in that file changes.
4. The convention pages name zod (RULES).
   - `conventions/api.md`:
     - Start-up snippet: remove the `ValidationPipe` line.
     - Replace the bullet "Request DTOs carry class-validator rules ..." with this text (the test
       checks it, whitespace joined): `Request input is a zod schema in `@app/shared`: one for
       each body and one for each list query, and the web form uses the same schema. Check it
       with `@Body(new ZodValidationPipe(schema))` or `@Query(new ZodValidationPipe(schema))`, and
       document it with `@ApiZodBody(schema)` or `@ApiZodQuery(schema)`. Each schema is
       `.strict()`, gives every string a maximum length, and gives every field `.meta({
       description, example })`. A request schema has no `.transform()`, because the
       documentation cannot show one.`
     - `## Lists`: the `ListQueryDto` class becomes a zod `listQuerySchema` in the shape pinned
       above, with `z.coerce.number()` for `page` and `limit`.
     - `## Swagger`: a snippet of `api-zod.decorator.ts` with the two signatures and the
       `z.toJSONSchema` options pinned above, so an app without it can copy it. "every DTO field
       has a description and an example" becomes "every request schema field and response DTO
       field has a description and an example". Keep "path and query param" (pinned in
       `tests/test_standards.py`).
     - A last section `## In an app set up before this release`, this text (the test checks it):
       `An app's current request DTOs and its global ValidationPipe stay as they are, and the
       review does not flag them. In an app with zod, new request input follows this page. An app
       without zod keeps its own validation for new code too.`
   - `conventions/backend.md`: the layout's `main.ts` line drops "validation"; the `shared/src/`
     line becomes "zod schemas for request input, and shared types". Replace "Name DTOs
     `CreateXDto`, `UpdateXDto` and `XResponseDto`." with: `Name request schemas `createXSchema`
     and `updateXSchema` (one `xSchema` when both are the same) and list queries
     `xListQuerySchema`, in `@app/shared`; name response DTOs `XResponseDto`.` Add to
     `## Modules` (the test checks it): `Request input is checked by zod schemas from
     `@app/shared`, as api.md says; the app has no global ValidationPipe.`
   - `conventions/security.md` line 13 ("The global `ValidationPipe` from api.md strips and
     rejects unknown fields.") becomes `Each request schema is `.strict()`, so `ZodValidationPipe`
     from api.md rejects unknown fields.`
   - `tests/test_standards.py` `CARRIED_OVER_RULES["backend.md"]`: `"CreateXDto"` becomes
     `"createXSchema"`. Nothing else in that file changes.
   - Test: `tests/test_zod_rules.py::test_4_the_api_and_backend_pages_name_zod_for_request_input`,
     with `adopted` in `[False, True]` (ids `new-client`, `adopted-v1.2.2`), through
     `setup_client`. A fix's `forge work` gives a brief; its conventions folder (`is in \`...\`` in
     the brief, as `tests/test_starter_app.py::test_3` reads it) has `api.md` with the request
     input text and without `class-validator rules` or `new ValidationPipe(`, and `backend.md`
     with the `## Modules` sentence.
5. The review flags new input that zod does not check (RULES).
   - `review.md`, `<!-- rules -->` block, a new paragraph right after the `Module tables:`
     paragraph (before the motion paragraph, so it does not touch the lines
     FORGE-REACTDEFAULTS-1/RULES adds after the motion paragraph), this text (the test checks it,
     whitespace joined): `In a TypeScript app with `zod` in a `package.json`, report a request
     body or query that this change adds and that no zod schema checks as a P1 finding titled
     `Zod: <the endpoint>`. Request input has one zod schema in the app's shared package, which
     the web form and the API both use, and the API documentation comes from that schema. A
     class-validator rule or an `@ApiProperty` on request input that this change adds is a
     finding. Input the default branch already has is not a finding, and neither is a path
     parameter that a Nest parse pipe checks.`
   - `brief.md`, `## Build simple`, a new paragraph right after the module paragraph (the one
     that ends "a new query on another module's tables."), this text (the test checks it): `In a
     TypeScript app with zod in a package.json, check each request body and query that you add
     with a zod schema in the shared package, through ZodValidationPipe, and document it from the
     same schema, as the API convention says. Do not add class-validator rules or @ApiProperty to
     request input. Review flags new request input that no zod schema checks.`
   - Test: `tests/test_zod_rules.py::test_5_review_flags_new_request_input_that_zod_does_not_check`,
     same `adopted` parameter. Commit on main a `package.json` with `zod` in `dependencies`. A fix
     (`_fix`) adds `libs/orders/src/orders.dto.ts` with a class-validator `CreateOrderDto`.
     `forge work` gives a brief with the brief paragraph (`install_claude`,
     `calls(log)[-1]["brief"]`). Autoreview returns a P1 finding titled
     `Zod: POST /api/v1/orders` with `Gain 4, Work 1, Harm 1`. Close exits 1 with "The review left
     serious findings open" and the title, and close's review prompt (`env.prompt()`) has the
     review paragraph.
6. An existing app keeps its validation (RULES).
   - The rule applies only where `zod` is in a `package.json`, and only to input a change adds,
     so an existing app is never told to move its current input, and an app without zod is never
     told to add it.
   - Test: `tests/test_zod_rules.py::test_6_an_existing_app_keeps_its_current_validation`, adopted
     case only (the item is about existing apps). Before `setup_client(..., True)`, write a
     `package.json` with `class-validator`, `class-transformer` and `zod`,
     `apps/api/src/main.ts` with a global `ValidationPipe`, and
     `libs/projects/src/projects.dto.ts` with a class-validator `ProjectListQueryDto`, so the
     fixture's adoption commit holds them. After upgrade and sync, the three files on main are
     byte for byte the same. A fix changes another file; Autoreview returns `CLEAN`; close
     succeeds; `env.prompt()` has the review paragraph with its sentence "Input the default
     branch already has is not a finding"; and the brief's conventions folder has `api.md` with
     the `## In an app set up before this release` text.

### New and existing repos

- **New repos** (`forge init --starter`): the starter has no class-validator or
  class-transformer, the list query and the bodies are checked and documented from the shared
  zod schemas, and `starter-smoke` runs the two new API cases. The review rule, the brief
  paragraph and the convention pages arrive with setup. Plain `forge init` gets the rule and the
  pages, and no starter.
- **Existing repos** (on upgrade to this release, after `forge sync`): no app file changes. The
  review rule, the brief paragraph and the convention pages arrive with the release, and the rule
  applies only to input a change adds, in an app with zod. Tested on the adopted earlier-release
  fixture moved to this release (items 4, 5 and 6).

## Tasks

<!-- One row per task. Covers: the Done-when numbers it delivers, at most three. Scope: the paths
it may change. Tests: the tests it adds or changes. After: the tasks it waits for. When two tasks
share a function, field, file format or command, the first task pins it: it commits the shared
names and stubs plus one test that crosses both sides, and the tasks that use it list it under
After. Split tasks so each owns its files; shared lines (command table, guide list, registry) go
to one task or a small last wiring task; After only when a task needs another task's code. The
Developer column is optional: the lead fills or changes a GitHub username here, below For the
builders, without another approval. Leave it blank for an unassigned part. Forge next uses
the caller's GitHub login; another developer may start it with a warning. Existing tables
without Developer still work. The moving-parts line stays last: "none", or each new dependency, service, datastore,
queue, background job or abstraction layer, with the Done-when item that needs it. -->

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing | Developer |
|---|---|---|---|---|---|---|---|---|
| STARTER | Zod for all input in the starter | The starter without class-validator or class-transformer, the list query checked by a shared zod schema with the body's error reply, the request documentation made from the zod schemas, and the two live API cases, in the starter that `forge init --starter` writes. | 1, 2, 3 | `src/forge/templates/starter/**`, `tests/test_starter_tree.py` (`API_ZOD_CASES` and its use in `test_1` only) | `tests/test_zod_starter.py` (`test_1`, `test_3`, new); API cases `rejects a bad list query with the same field errors as a bad body` and `documents the list query and request bodies from the shared zod schemas` in `apps/api/test/api.e2e-spec.ts`, required live by `tests/test_starter_tree.py::test_1` | FORGE-REACTDEFAULTS-1/STARTER | no | |
| RULES | Zod rules for agents and reviews | The API, backend and security convention pages on zod, the review rule and the worker brief paragraph, and the existing-app section, on new and existing repos. | 4, 5, 6 | `src/forge/templates/conventions/api.md`, `src/forge/templates/conventions/backend.md`, `src/forge/templates/conventions/security.md`, `src/forge/templates/review.md`, `src/forge/templates/brief.md`, `tests/test_standards.py` (`CARRIED_OVER_RULES["backend.md"]` only) | `tests/test_zod_rules.py` (`test_4`, `test_5`, `test_6`, new) | | no | |

New moving parts: none

## Notes

- **Order.** STARTER waits for FORGE-REACTDEFAULTS-1/STARTER, because both change the starter's
  `package.json` and `pnpm-lock.yaml`. RULES waits for nothing and runs in parallel: it shares no
  file with STARTER, and its `review.md` and `brief.md` paragraphs sit next to the module lines,
  away from the lines FORGE-REACTDEFAULTS-1/RULES adds. Both parts ship in one release.
- **Size.** STARTER is about 330 changed lines, about 90 of them in the lockfile, so it needs no
  size allowance. If the merged lockfile pushes it over 400 lines, the lockfile lines are
  generated and count as the allowance.
- **Choice made for the owner to confirm.** The intake named only the list query's documentation;
  this plan also documents each request body from its schema (item 3), because the owner's
  decision is that the documentation comes from the same schema, and hand-written body classes
  would repeat each limit. Dropping the body half removes about 40 lines from STARTER.
- **Choice made for the owner to confirm.** The review rule applies only in an app with zod in a
  `package.json`. An existing app without zod keeps its own validation for new code too, so the
  review never asks it to add a library. An app made from an earlier starter has zod, so its new
  input uses zod.
- **The web list page does not change.** `readListQuery` in `projects-page.tsx` falls back to a
  default for each wrong value in the web address, which the API schema does not do, and
  FORGE-REACTDEFAULTS-1/STARTER owns that file. The web hooks keep their own `ProjectListQuery`
  type; a follow-up can import it from `@app/shared`.
- **No score floor.** `Zod:` findings keep the reviewer's scores, as the owner's lean-review rule
  asks.
- **The light review does not change.** A prototype fix's light review and a docs-only review do
  not check the rule.
- **Changes no flow.** No command, option, `forge.toml` setting or stored state. `skill.md` does
  not change; the brief paragraph carries the worker side.
- **Not in this story.** Moving an existing app to zod; response DTOs (they stay classes with
  `@ApiProperty`, since they are not input); path parameters (Nest's parse pipes stay); a lint
  rule that forbids class-validator (the review flags it); `src/forge/standards.md`, whose
  typed-boundary and Swagger lines already fit zod.
- No client repo is named anywhere in this story's code, tests, texts or commits.
