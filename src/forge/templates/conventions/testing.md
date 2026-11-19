# Testing

How the standards page's test rules look on this stack. Read it when your task adds tests or
changes how they run.

Tests check behaviour at the boundary the user touches, never internal record formats or private
calls. A behaviour-preserving refactor must not break a test; use the owning boundary instead.

## The one test command

The root `package.json` runs the lint, type-check, API, hook and browser tests:

```json
{ "scripts": { "test": "corepack pnpm run lint && corepack pnpm run typecheck && corepack pnpm run test:api && corepack pnpm run test:hooks && corepack pnpm run test:browser" } }
```

Nx builds and type-checks `apps/web` and `apps/api`. The API tests use a real Postgres database.
The browser tests use Playwright against the running web app.

Run `COREPACK_ENABLE_DOWNLOAD_PROMPT=0 corepack pnpm test` for lint, type checks and the API, hook
and browser tests. Set forge.toml's `test` to `node scripts/test.mjs`. This script installs
dependencies and builds the apps. It runs
`COREPACK_ENABLE_DOWNLOAD_PROMPT=0 corepack pnpm exec playwright install --with-deps chromium`.
It starts a fresh test database and app, then runs the root test script. Run `forge sync` to write
this into the one `tests` check. Set a separate change command that excludes browser steps:

```toml
test = "node scripts/test.mjs"
fast_test = "node scripts/test.mjs {base}"
```

The script's base-argument mode must omit browser tests and their installation, even when shared
settings select all other tests. Its no-base mode must run the full browser suite nightly.
For an existing app, ask the owner before this script or settings change.

## End-to-end tests

Every Done-when item needs an end-to-end test through the real entry point when it changes runtime
behaviour: Forge's own command; for client apps, the running API with a real database and user
flows in a browser through Playwright. Settings, docs, deletions and test-only items are proven by
the check the item names. Fake only third-party services at their edge. Unit tests are only for pure logic with
many cases, never an item's only proof. Review reports an item proven only by unit tests as a P1
`Not done` and never asks for unit tests of helpers.

An item with no UI gets a Supertest test through HTTP when it changes runtime behaviour, against
the running API at `baseUrl` and a real database (see database.md): one per Done-when item, not one
per function. Settings, docs, deletions and test-only items get none; they are proven by the check
the item names. Create its data through the running app's API:

```ts
it('cancels an order that has not shipped', async () => {
  const order = await request(baseUrl).post('/api/v1/orders')
    .set(signedInAs(userId)).send({ /* valid order fields */ }).expect(201);
  const res = await request(baseUrl)
    .post(`/api/v1/orders/${order.body.data.id}/cancel`).set(signedInAs(userId)).expect(200);
  expect(res.body.data.cancelledAtUtc).not.toBeNull();
});
```

Cover the refusals the story cares about the same way: another account's order gets 404, so its
existence doesn't leak (see security.md), and bad input gets 400.

## Browser tests

Every user-facing Done-when item gets one Playwright test when it changes runtime behaviour, walking
the flow in a browser against the running app and API. Find elements by role and label:

```tsx
await page.getByRole('button', { name: 'Cancel order' }).click();
await expect(page.getByText('Order cancelled')).toBeVisible();
```

Each screen of the app gets one rendered check in the same browser tests. Import `checkScreen` from
`.forge/design/render-check.mjs` and call it once for each listed screen:

```ts
import { checkScreen } from '../../../.forge/design/render-check.mjs';

test('renders orders', async ({ page }) => { await checkScreen(page, { name: 'orders', path: '/orders' }); });
```

It opens the screen in its loaded state, in light and dark, at 1440 pixels. Add `phone: true` only for an
app that needs a phone view; it then also checks at 375 pixels. `path` is the address the screen ends on.
A hash counts as part of it only when `path` has one. Overflow, cut text and low contrast fail the test.
To set one kind aside for one screen, add `waive: { 'cut-text': '<the reason>' }`.
Close runs this check only when its test command runs the browser tests.

Keep browser tests and each screen's rendered check in the full test command and nightly full
run, not in `fast_test` or pull request CI, even when shared settings select all other tests.
A broken screen can merge; the nightly run finds it the next morning. Playwright runs in
parallel workers with zero retries: an intermittent failure fails the check. Fix its cause by
waiting for real app state, never by adding a fixed sleep. A minimal config is:

```ts
import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  retries: 0,
  use: { baseURL: 'http://localhost:5173' },
});
```

The test command above starts the app with Compose. If the app starts outside Compose, configure
Playwright's `webServer` instead. A Node client's generated `tests` job has a 60-minute cap; split a
suite that outgrows it into groups within the same check.

For an existing app, add a browser test for each new or changed flow. An untouched old flow gets
its test when a story first changes it; do not backfill untouched flows.

Each event handler gets an idempotency test (the same event twice runs once) and a failure test.

## Test data

Each test file owns its data so files can run at the same time. Before a shared reset in
`beforeEach`, await all outstanding jobs, `waitUntil` work, alarms and Durable Objects still
running after a timeout. Reset only that file's data. If a global reset forces serial files,
repair it first and measure again. Never hide leftover work with `INSERT OR IGNORE`, upserts,
random keys, blind retries or a serial suite.

- Each test creates what it needs through the running app's API on a fresh database per run.
  Do not use a shared seed or insert rows directly into the database.
- Shared seed data stays out of tests, the demo loader's too: demo data is allowed on the demo
  host only (see demo-data.md).
- Unit tests for pure logic with many cases (a price rule, a date calculation) need no database.
- No sleeps: wait for the thing itself (`findBy...`, an awaited promise).

## Selection and parallel files

Shared setup and helpers must not import the app entry or the whole app: one dependency change
can then select almost every test. Fix those imports, not the list of changed source files.
Selection follows the real import graph. Never drop changed files from `vitest related` or
replace them with area names: that loses integration tests importing an API through its index.

Keep a table of slow tests (harness, build and bundle checks) and each test's input paths. Run
them on a pull request only when an input changes, and always nightly. A test that starts scripts
has no import to follow: list its inputs and explicitly select it when they change. Excludes use
`**/<file>` because each Vitest project collects from its own root. Feed the gate's excludes into
the Vitest config's `exclude`, not `--exclude`, which related and per-project runs can ignore.

Select each test file once per CI job. Do not run a whole project's files again as related tests;
still select other projects' related files. Selection tests run the whole chain, from the CI
wrapper's document-only decision to the inner picker, including executable documents and
contract inputs. Tests starting a picker or script that reads `FORGE_GROUP` and `FORGE_GROUPS`
set both themselves, so the CI job's group cannot silently narrow their proof.

Before adding a process-per-runtime launcher, check the runner's own file isolation. Vitest's
default `isolate: true` and Cloudflare's pool give each file its own worker, Miniflare and
temporary storage. Try file parallelism and a bounded `maxWorkers` first. In CI, start with one
worker per runner-slot core; cap total workers across processes by cores and measured peak
memory, including memory-backed temporary storage. A timing assertion's bound sits between the
good and bad cases, with room for a loaded machine. A worker-count change needs one parallel
run of timing tests as proof.

For time-based Vitest groups in an existing app, ask the owner and make a fix. Copy the
TypeScript starter's `scripts/test-groups.mjs`, `scripts/timed-sequencer.mjs` and the `--group`
handling in `scripts/test.mjs`. Register `sequence: { sequencer }` in each grouped Vitest config.
Count files before passing `--shard`: use no more groups than files.
When the job's group exceeds that count, skip only this Vitest invocation.
Continue with the job's other test runs. Fail clearly for zero files and leave no group in use
empty. Each group gets its own setup.
Through the settings fix, put `{group}` and `{groups}` in `test` and `fast_test`. Add a refresh
command that writes `test-timings.json` from Vitest's JSON report and commit it through a fix.
No CI job refreshes times or opens a pull request. Python pytest groups keep their existing split.
