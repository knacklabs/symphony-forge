---
reader: codex (gpt-6.1-sol)
read_at: 2026-10-28T13:27:07.989763+00:00
seconds: 173.257
read_hash: 087ebc16830029e3ac5ad9fa53bfdc6d7d1062e1
round: 2
passed: yes
doc_seen: 087ebc16830029e3ac5ad9fa53bfdc6d7d1062e1
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: d1a5d3b4fd7bd22ebeaeb435bcf20bf04db96e78
answers_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
conversation: 01a18273-6249-7501-ac6b-8fc103df2240
session:
loop_choice:
loop_reason:
---
# Cold read notes

Written by `forge read`. Under every blocking finding, write one disposition line, amend the
doc, then run `forge read <doc>` again until a round has no blocking notes. Notes marked
`Advisory:` are recorded without requiring a disposition or another round:

- `Disposition: cut` when the doc was edited to remove it;
- `Disposition: defer` when the item moved to the spec's Out of scope;
- `Disposition: keep <one-line reason>` otherwise.

A finding inside What counts is cut or deferred. Keep one only when it falls outside that boundary
or is factually wrong or not worth the change, and give as the reason the Leave out line, the
missing Raise line, the cited fact that disproves it, why it is not worth the change, or the
human's `Decided:` line.

Only a genuine trade-off goes to the human, as a question with options.

## Round 1

1. Blocking: Python’s SMTP recipe does not verify the server’s identity.
   Raise: Security. [Plan:74](plans/FORGE-MAIL-1.md:74) specifies `SMTP_SSL` and `starttls()` without a verifying context. Python 3.14 uses an unverified context for both, accepting an untrusted certificate and exposing SMTP credentials and account-access links to interception. [SMTP source](https://github.com/python/cpython/blob/v3.14.0/Lib/smtplib.py), [SSL source](https://github.com/python/cpython/blob/v3.14.0/Lib/ssl.py).
   Case: normal use - a deployed Python app sends account emails over TLS.
   Pin `ssl.create_default_context()` for both TLS paths and test rejection of an untrusted certificate.
   Adds work: verify SMTP server certificates; F 3 x H 3 = 9; 2 x C = 2.
   Gain 5, Work 2, Harm 4
   Disposition: cut - the Python sender makes `ssl.create_default_context()` and passes it to `SMTP_SSL` and `starttls`; a new Python case sends to Mailpit services with a self-signed certificate on both paths and expects `ssl.SSLCertVerificationError`.

2. Blocking: Python checks for STARTTLS before discovering server capabilities.
   Raise: Functional. [Plan:74](plans/FORGE-MAIL-1.md:74) checks `has_extn("starttls")` before login or sending, without first issuing EHLO. `SMTP` construction does not populate those capabilities; EHLO does. The prescribed sequence therefore skips TLS, and providers requiring TLS refuse authentication. Plain Mailpit delivery passes despite this defect. [Python SMTP documentation](https://docs.python.org/3.14/library/smtplib.html#smtplib.SMTP.ehlo).
   Case: normal use - the client configures an authenticated SMTP provider on port 587.
   Pin EHLO before the capability check and cover that negotiation.
   Gain 4, Work 2, Harm 3
   Disposition: cut - the `smtp:` path now calls `ehlo()` before `has_extn("starttls")` and again after `starttls`; the certificate case's STARTTLS server requires the upgrade, so code that skips it gets an SMTP refusal and fails the case.

3. Blocking: The TypeScript recipe puts transport timeouts in message defaults.
   Raise: Functional. [Plan:73](plans/FORGE-MAIL-1.md:73) passes the timeout settings as `createTransport`’s second argument. That argument supplies message defaults; transport settings belong in the first argument. The pinned call does not establish the promised ten-second limits. [Nodemailer documentation](https://nodemailer.com/smtp).
   Case: normal use - an SMTP provider stalls during a password-reset request.
   Put the URL and timeout settings together in the transport options.
   Gain 3, Work 1, Harm 3
   Disposition: cut - the call is now `nodemailer.createTransport({ url: SMTP_URL, connectionTimeout, greetingTimeout, socketTimeout })`, all in the transport options.

4. Blocking: The sign-in page hides the verification instructions.
   Raise: Functional. [Plan:98](plans/FORGE-MAIL-1.md:98) says the existing sign-in page displays the API message. In fact, `src/forge/templates/starter/libs/auth/web/src/pages/sign-in-page.tsx:28-30` replaces non-field errors with “Could not sign in. Check your email and password…”. `form-errors.ts:5` returns false for the proposed error’s null details. VERIFY excludes the sign-in page from Scope.
   Case: normal use - an unverified person signs in correctly and receives another email, while the screen tells them their credentials failed.
   Include the page change and a browser assertion for the resend message.
   Gain 3, Work 2, Harm 3
   Disposition: cut - VERIFYON changes the sign-in page to show the API message for `EMAIL_NOT_VERIFIED`, with `sign-in-page.tsx` in its Scope, and the new browser case `a person who signs up opens the emailed link to get in` asserts the new-link alert.

5. Blocking: Removing a member does not make their next in-app navigation ask for sign-in.
   Raise: Functional. [Plan:11](plans/FORGE-MAIL-1.md:11) promises that behavior, but `apps/web/src/app.tsx:17-38` redirects only when the account query returns null. `libs/auth/web/src/hooks/auth-hooks.ts:15-28` does not refresh that query on navigation, and `libs/core/web/src/api-client.ts:36-38` only throws on a protected request’s 401. The planned test at line 133 reloads the browser, bypassing this case.
   Case: normal use - a removed member follows a sidebar link in their already-open app.
   Include handling and browser proof for that navigation.
   Gain 3, Work 2, Harm 3
   Disposition: cut - `ProtectedLayout` refetches the account on each page change, so `/auth/me` answers 401 and the layout sends the person to sign-in; the browser case now has the removed member follow a sidebar link with no reload.

6. Blocking: The verification helpers cannot establish the production admin used by the SMTP tests.
   Raise: Plan gap. [Plan:99](plans/FORGE-MAIL-1.md:99) makes the helpers obtain verification links from logs, while line 83 gives `production-api` an SMTP provider. The existing production invite cases create their admin through production sign-up (`starter/apps/api/test/invites.e2e-spec.ts:214-220` and `starter-python/apps/api/tests/test_invites.py:337`). After VERIFY, those calls receive no session, and their verification links exist only in Mailpit.
   Case: normal use - the starter’s required production SMTP invite test runs after VERIFY.
   Pin a Mailpit verification path for production session setup.
   Gain 4, Work 2, Harm 3
   Disposition: cut - the sign-up helpers take a service; for `production-api` they read the verify link from Mailpit by the account's email, and the production invite cases pass that service.

7. Blocking: The browser helper can verify another worker’s account.
   Raise: Test. [Plan:99](plans/FORGE-MAIL-1.md:99) selects the newest shared `verifyUrl`. `starter/apps/web/playwright.config.ts:6-9` runs fully parallel tests with two workers. The existing helper explicitly accounts for shared-log concurrency at `apps/web/e2e/helpers.ts:52-58`; a verification token alone provides no email-mismatch protection.
   Case: normal use - two browser workers sign up concurrently and one selects the other account’s newest link.
   Correlate each verification link with the signup that created it.
   Gain 3, Work 2, Harm 3
   Disposition: cut - every helper now takes the link whose log line has the `correlationId` of its own sign-up or sign-in response (`x-correlation-id`), never the newest link.

8. Blocking: P1 — `Design: none` covers a new screen and a changed signup flow.
   Raise: Gate. [Plan:16](plans/FORGE-MAIL-1.md:16) claims the small-existing-screen exception, but line 98 adds `/verify-email` and replaces immediate signup navigation with an email-confirmation flow. The current route table at `starter/apps/web/src/app.tsx:66-81` has no verification screen. The cold-read rule explicitly requires design for this scope.
   Case: normal use - every new public signup follows the new screen and flow.
   Gain 4, Work 2, Harm 3
   Disposition: keep - owner decision 28 Oct 2026: starter screens take each client app's design; no Forge design

9. Blocking: Split: VERIFY → verification support; coordinated activation.
   Raise: Plan gap. [Plan:170](plans/FORGE-MAIL-1.md:170) puts both APIs’ token and session changes, two migrations, mail changes, a new page, shared auth hooks, dozens of test-call changes and feature-generation compatibility into one task. Its Scope plainly exceeds the approximately 400-line task limit. Shared web requires coordinated activation, but does not require dormant token support and migrations to ship in that same task.
   Case: normal use - the builder must implement and verify this entire cross-language change as one part.
   Gain 4, Work 2, Harm 4
   Disposition: cut - VERIFY is now VERIFYTS and VERIFYPY (each API's dormant support with its migration, route and expiry case) and VERIFYON (the switch in both APIs, the web, the helpers and the call sites); the plan has 9 parts.

10. Blocking: Unproven: item 5’s 24-hour verification expiry.
    Raise: Test. [Plan:95](plans/FORGE-MAIL-1.md:95) promises expired links are refused, but lines 136-145 test only a replaced token and successful verification. An implementation that ignores `expiresAtUtc` passes every named verification case. The existing reset implementation checks expiry independently at `starter/libs/auth/server/src/auth.service.ts:171-180`; exercising reset does not prove the new endpoint.
    Case: normal use - a person opens their signup email more than a day later.
    Include expiry refusal in VERIFY’s API cases for both starters.
    Gain 3, Work 2, Harm 3
    Disposition: cut - VERIFYTS and VERIFYPY each add an expiry case: the token's expiry set to the past with psql gets 400 `VERIFY_TOKEN_INVALID`, and a new token expires within 24 hours.

11. Advisory: Give shared test wiring one owner instead of serializing unrelated work.
    Raise: Plan gap. [Plan:165-170](plans/FORGE-MAIL-1.md:165) assigns all five implementation parts the same `tests/test_mail.py`; MAILPY and REMOVE can become eligible together but overlap there. `src/forge/task.py:355-360` refuses overlapping active scopes. VERIFY also waits for REMOVEWEB solely through this shared test file, and GUIDE’s external dependency exists only for unrelated guide edits.
    Split implementation-owned cases into separate files, with shared workflow/list wiring owned once.
    Gain 3, Work 2, Harm 2
   Disposition: keep - below the bar (follow-up)

12. Advisory: Consolidate the repeated earlier-adopted sync checks.
    Raise: Test. [Plan:106-147](plans/FORGE-MAIL-1.md:106) repeats unchanged-app assertions across items 1–5; item 3’s absent compose file repeats item 1, and item 4 repeats its `libs/` and `apps/` comparison. `tests/test_mcp.py:46-74` already supplies one whole-app before/after snapshot. These use the same sync path, so the repository’s review rules identify them as deletion candidates.
    Keep one adopted-repo sync case covering the protected files and absent additions.
    Gain 2, Work 1, Harm 1
   Disposition: keep - below the bar (live with)

## Round 2

No findings.
