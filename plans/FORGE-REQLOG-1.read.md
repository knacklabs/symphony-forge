---
reader: codex (gpt-6.1-sol)
read_at: 2026-10-28T12:25:14.214266+00:00
seconds: 353.075
read_hash: 0f7164779547543623f57562c759a227d6c49c10
round: 1
passed: no
doc_seen: 0f7164779547543623f57562c759a227d6c49c10
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
answers_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
conversation: 01a18273-6185-7941-beda-d85d2a3806d8
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

1. Blocking: Not done: TypeScript preflight requests bypass the proposed request logger.
   Raise: Functional.
   Case: normal use - a browser sends `OPTIONS /api/v1/projects` before a cross-origin request.
   `plans/FORGE-REQLOG-1.md:66` installs logging after correlation middleware. In `src/forge/templates/starter/apps/api/src/main.ts:17-23`, CORS runs before both. The pinned CORS implementation ends preflight responses without calling the next middleware, so these API requests produce no request line. The planned cases at `plans/FORGE-REQLOG-1.md:81-87` cannot detect this.
   Gain 3, Work 2, Harm 3
   Disposition: cut - `main.ts` now registers the correlation and request-log middleware right after helmet and before `enableCors`, and both app cases add a preflight step whose line has method OPTIONS, route null and status 204.

2. Blocking: Trap: Python’s web fallback contradicts the required unmatched-route result.
   Raise: Plan gap.
   Case: normal use - the planned `GET /api/v1/missing-<word>` receives 404.
   `plans/FORGE-REQLOG-1.md:75` reads the matched route’s `path`, while lines 84-87 require `route: null`. However, `src/forge/templates/starter-python/apps/api/app/main.py:85-111` matches that request to `/{path:path}` before raising 404. The prescribed implementation therefore logs `/{path:path}` and fails its prescribed acceptance case. Pin how this fallback becomes `null`.
   Gain 4, Work 1, Harm 2
   Disposition: cut - the Python route rule now maps the web fallback's `/{path:path}` to `None`, and the Python case asserts `route: null` for the missing route, not `/{path:path}`.

3. Blocking: Unproven: item 1 never requires a successful API request to produce a log line.
   Raise: Test.
   Case: normal use - a signed-in person successfully lists projects.
   The logging assertions at `plans/FORGE-REQLOG-1.md:81-87` require rejected and missing requests, but no successful response. Existing successful HTTP coverage, such as `src/forge/templates/starter/apps/api/test/api.e2e-spec.ts:16-35` and `src/forge/templates/starter-python/apps/api/tests/test_api.py:55-81`, checks responses without checking request logs. Logging only failures could pass this proof while leaving the story’s main problem unchanged. Require a successful request in the logging case.
   Gain 3, Work 2, Harm 3
   Disposition: cut - both app cases now sign up and send a successful `GET /api/v1/auth/me?search=<word>`, whose line must have route `/api/v1/auth/me` and status 200, and the log must hold none of the query words.

4. Blocking: Not done: the delivered guides claim logging guarantees that upgraded apps do not receive.
   Raise: Not done.
   Case: normal use - an existing Python app upgrades, syncs, and follows the new `LOG_LEVEL` guidance.
   `plans/FORGE-REQLOG-1.md:109-117` unconditionally says the logger filters levels, removes secrets, and already supplies request logging; the worker brief also forbids adding those facilities. Line 129 explicitly preserves the existing logger. Today’s Python logger at `src/forge/templates/starter-python/apps/api/app/core/logging.py:29-40` writes every level and copies context unchanged. Qualify the delivered instructions by whether the app has adopted the new logger, preserving the decision to leave existing app code unchanged.
   Gain 4, Work 2, Harm 2
   Disposition: cut - the standards, Python, deploy and brief text now applies the logger rules only in an app with `request-log.middleware.ts` or `set_log_level`; the constitution's Built in line moves to its own paragraph with that condition, out of the outlines that every app with libs/organisations copies.

5. Advisory: the shared test file unnecessarily makes Python wait for TypeScript.
   Raise: Plan gap.
   `plans/FORGE-REQLOG-1.md:136-140` assigns both tasks parameter cases in `tests/test_request_log.py` and makes that shared ownership a dependency. The shared names are already pinned at lines 58-76; neither implementation consumes the other’s code. Split the language-specific Forge tests into separately owned files so this dependency is unnecessary.
   Gain 2, Work 2, Harm 1
   Disposition: keep - below the bar (live with)
