# Testing

How the standards page's test rules look on this stack. Read it when your task adds tests or
changes how they run.

## The one test command

The root `package.json` runs everything CI needs:

```json
{ "scripts": { "test": "npm run lint --workspaces --if-present && npm run typecheck --workspaces --if-present && npm run test --workspaces --if-present && playwright test" } }
```

Once the app has a database, use a test-only Compose project that starts a fresh database and
the running API and web app. Set forge.toml's `test` to install dependencies and Playwright's
browser, start the app, and run the whole root test script. Then run `forge sync` to write this
into the one `tests` check:

```toml
test = "npm ci && npx playwright install --with-deps chromium && docker compose -p forge-tests -f compose.test.yml down --volumes && docker compose -p forge-tests -f compose.test.yml up -d --build --wait && npm test"
```

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

Keep browser tests in the root test command alongside unit and API tests. Playwright runs in
parallel workers with zero retries: an intermittent failure fails the check. Fix its cause by
waiting for real app state, never by adding a fixed sleep. A minimal config is:

```ts
import { defineConfig } from '@playwright/test';

export default defineConfig({
  fullyParallel: true,
  retries: 0,
  use: { baseURL: 'http://localhost:5173' },
});
```

The test command above starts the app with Compose. If the app starts outside Compose, configure
Playwright's `webServer` instead. A client's generated `tests` job has a 10-minute cap; split a
suite that outgrows it into groups within the same check.

For an existing app, add a browser test for each new or changed flow. An untouched old flow gets
its test when a story first changes it; do not backfill untouched flows.

Each event handler gets an idempotency test (the same event twice runs once) and a failure test.

## Test data

- Each test creates what it needs through the running app's API on a fresh database per run.
  Do not use a shared seed or insert rows directly into the database.
- Shared seed data stays out of tests, the demo loader's too: demo data is allowed on the demo
  host only (see demo-data.md).
- Unit tests for pure logic with many cases (a price rule, a date calculation) need no database.
- No sleeps: wait for the thing itself (`findBy...`, an awaited promise).
