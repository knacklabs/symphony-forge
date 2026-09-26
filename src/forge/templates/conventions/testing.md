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

## API tests

Each Done-when item an endpoint serves gets a Supertest test through HTTP, against the real app
module and a real database (see database.md):

```ts
it('cancels an order that has not shipped', async () => {
  const order = await makeOrder(db);
  const res = await request(app.getHttpServer())
    .post(`/api/v1/orders/${order.id}/cancel`).set(signedInAs(order.userId)).expect(200);
  expect(res.body.data.cancelledAtUtc).not.toBeNull();
});
```

Cover the refusals the story cares about the same way: another account's order gets 404, so its
existence doesn't leak (see security.md), and bad input gets 400.

## UI tests

Vitest with Testing Library and jsdom. Find elements the way a user would, by role and label:

```tsx
await user.click(screen.getByRole('button', { name: 'Cancel order' }));
expect(await screen.findByText('Order cancelled')).toBeInTheDocument();
```

Answer the app's API calls with a small fake `fetch` per test, not a mocked hook.

## Test data

- Factories are plain functions (`makeOrder(db, overrides)`) that fill in sensible values and
  return the saved record. Each test makes the rows it needs.
- Unit tests are for logic with real branches (a price rule, a date calculation) and need no
  database. Fake only what sits at the edge: a provider or the clock.
- No sleeps: wait for the thing itself (`findBy...`, an awaited promise).
