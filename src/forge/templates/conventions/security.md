# Security

How the standards page's security basics look in NestJS. Read it when your task touches start-up,
sign-in, permissions, uploads or secrets. None of this is ever cut to make a change simpler.

## Start-up

```ts
app.use(helmet());
app.enableCors({ origin: config.corsOrigins, credentials: true });  // a named list, never '*'
```

- Each request schema is `.strict()`, so `ZodValidationPipe` from api.md rejects unknown fields.
- `@nestjs/throttler` limits sign-in, password reset and other sensitive routes (for example 10
  requests a minute); `/health` skips it.
- Production serves HTTPS only.

## Who may do what

- Once a story adds sign-in, a global guard rejects every request without a valid token; a public
  route opts out with a `@Public()` decorator, so forgetting a guard fails closed.
- Every service method that reads or changes data takes the caller's account and scopes its query
  to what that account may see. A role check alone is not enough: an order id from someone else's
  account must still come back as 404.
- In an app that has `libs/organisations`, scope every query to `organisationId` on the caller's
  principal. Guard each admin action with `@AdminOnly()`; it still needs the organisation scope.
- Tokens carry ids and roles only, never personal data.
- If the app ever stores its own API keys, keep only a hash and show the key once.

## Secrets and personal data

- Secrets come from environment variables: `.env` locally (never committed), and the hosting
  platform's or GitHub's secret store elsewhere.
- Logs, events and error responses never hold passwords, tokens, one-time codes or personal data.

## Uploads

Set a size limit per endpoint, accept only a named list of file types, and check the type from the
file's content, not its name or header. Store uploads in a private S3-compatible bucket configured
with `S3_ENDPOINT`, `S3_REGION`, `S3_BUCKET`, `S3_ACCESS_KEY_ID` and `S3_SECRET_ACCESS_KEY`; Mainline
will supply these settings later. Use a generated key, store the key in the database, never a URL,
and give downloads signed links that expire in 5 minutes or less. Use `@aws-sdk/client-s3` with
`@aws-sdk/s3-request-presigner` in TypeScript, or `boto3` in Python. The story that first needs
uploads adds the bucket and these libraries; do not add them to the starters in advance.
