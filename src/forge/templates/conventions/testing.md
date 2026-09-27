# Testing

How the standards page's test rules look on this stack. Read it when your task adds tests or
changes how they run.

## The one test command

The root `package.json` runs everything CI needs:

```json
{ "scripts": { "test": "npm run lint --workspaces --if-present && npm run typecheck --workspaces --if-present && npm run test --workspaces --if-present" } }
```

Once the app has a database, set forge.toml's `test` so CI starts Postgres first, then run
`forge sync` to write it into the `tests` check:

```toml
test = "docker compose up -d --wait db && npm ci && npm test"
```

## End-to-end tests

Every Done-when item needs an end-to-end test through the real entry point: Forge's own command;
for client apps, the running API with a real database and user flows in a browser through
Playwright. Fake only third-party services at their edge. Unit tests are only for pure logic with
many cases, never an item's only proof. Review reports an item proven only by unit tests as a P1
`Not done` and never asks for unit tests of helpers.

Each Done-when item an endpoint serves gets a Supertest test through HTTP, against the running API
at `baseUrl` and a real database (see database.md):

```ts
it('cancels an order that has not shipped', async () => {
  const order = await makeOrder(db);
  const res = await request(baseUrl)
    .post(`/api/v1/orders/${order.id}/cancel`).set(signedInAs(order.userId)).expect(200);
  expect(res.body.data.cancelledAtUtc).not.toBeNull();
});
```

Cover the refusals the story cares about the same way: another account's order gets 404, so its
existence doesn't leak (see security.md), and bad input gets 400.

## UI tests

Use Playwright in a browser against the running app and API. Find elements by role and label:

```tsx
await page.getByRole('button', { name: 'Cancel order' }).click();
await expect(page.getByText('Order cancelled')).toBeVisible();
```

Each event handler gets an idempotency test (the same event twice runs once) and a failure test.

## Test data

- Factories are plain functions (`makeOrder(db, overrides)`) that fill in sensible values and
  return the saved record. Each test makes the rows it needs.
- Unit tests for pure logic with many cases (a price rule, a date calculation) need no database.
- No sleeps: wait for the thing itself (`findBy...`, an awaited promise).
