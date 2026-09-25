# Security

How the standards page's security basics look in NestJS. Read it when your task touches start-up,
sign-in, permissions, uploads or secrets. None of this is ever cut to make a change simpler.

## Start-up

```ts
app.use(helmet());
app.enableCors({ origin: config.corsOrigins, credentials: true });  // a named list, never '*'
```

- The global `ValidationPipe` from api.md strips and rejects unknown fields.
- `@nestjs/throttler` limits sign-in, password reset and other sensitive routes (for example 10
  requests a minute); `/health` skips it.
- Production serves HTTPS only.

## Who may do what

- Once a story adds sign-in, a global guard rejects every request without a valid token; a public
  route opts out with a `@Public()` decorator, so forgetting a guard fails closed.
- Every service method that reads or changes data takes the caller's account and scopes its query
  to what that account may see. A role check alone is not enough: an order id from someone else's
  account must still come back as 404.
- Tokens carry ids and roles only, never personal data.
- If the app ever stores its own API keys, keep only a hash and show the key once.

## Secrets and personal data

- Secrets come from environment variables: `.env` locally (never committed), and the hosting
  platform's or GitHub's secret store elsewhere.
- Logs, events and error responses never hold passwords, tokens, one-time codes or personal data.

## Uploads

Set a size limit per endpoint, accept only a named list of file types, and check the type from the
file's content, not its name or header. Store uploads outside the web root under generated names.
