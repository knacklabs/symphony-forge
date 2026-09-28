# Screens and flows are built by Opus 5.5

4 parts · Risks: none · New moving parts: none

## What changes for you

- Any story task that changes what people see, and every prototype fix before sign-off, is built by
  Claude on Opus 5.5 at high effort, using impeccable, Emil's design engineering and the app
  baseline. Backend and Forge's own work stays on Codex, as today.
- If Claude can't run on the machine, the same work goes to Codex on Sol at high effort instead,
  and the work log says so and why.
- Both choices sit in the repo's `forge.toml`, next to the other models, so they can be changed in
  one place.

## Why

The owner wants every screen to be flawless and judges Opus 5.5 the best designer, with Sol at
high effort as the last resort. Today every worker in a Codex repo is a Codex worker, whatever the
work is.

## Done when

1. **The choice is recorded.** A decision says design work runs on Claude with Opus 5.5 at high
   effort and falls back to Codex with Sol at high effort, and why.
2. **Design work has its own models.** `forge.toml` accepts `[models.design.claude]` and
   `[models.design.codex]`; `forge init` writes them as Opus 5.5 (`claude-opus-5-5`) high and
   `gpt-6-sol` high; a repo without them uses those same values; this repo's `forge.toml` has them.
3. **Design work goes to Opus 5.5.** `forge work` on a story task whose row is user-facing, or on a
   fix whose allowance is "Prototype before sign-off", runs a Claude worker with
   `[models.design.claude]`, whatever `workers` says; every other item runs as today.
4. **Sol high is the fallback.** When the `claude` command is missing, or the Claude run fails
   before it changes the checkout, `forge work` runs the same brief on Codex with
   `[models.design.codex]` and prints and logs that it fell back and why; a Claude run that changed
   the checkout and then failed is reported as a failure, not retried on Codex.
5. **The guide says so.** The guide's models section explains the design models and the fallback.

## Risks

Risks: none

## For the builders

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing |
|---|---|---|---|---|---|---|---|
| SPEC | The decision | The decision record for design work on Opus 5.5 | 1 | `docs/decisions/` | | none | no |
| MODELS | Design models | The design kind with its two family entries, the defaults, init's forge.toml and this repo's forge.toml | 2 | `src/forge/repo.py`, `src/forge/init.py`, `forge.toml` | `tests/test_design_models.py` | none | no |
| ROUTE | Route design work | Choosing the Claude worker for design items and the Codex fallback | 3, 4 | `src/forge/worker.py` | `tests/test_design_route.py` | MODELS | no |
| DOCS | Say so | The guide's models section | 5 | `docs/guide.md` | `tests/test_design_docs.py` | none | no |

New moving parts: none

## Notes

- MODELS adds `design` to the kinds with one entry per family, like `grill`, and a
  `repo.design_models(cfg, family)` that returns the table's entry or the default when the table
  has none: claude `{"model": "claude-opus-5-5", "effort": "high"}`, codex
  `{"model": "gpt-6-sol", "effort": "high"}`. ROUTE uses it.
- ROUTE reads the prototype allowance exactly as FORGE-PROTO-1's GATE records it: the fix state's
  `allow_large` equals "Prototype before sign-off". A task is user-facing when its row's
  User-facing cell says yes, as the brief already reads it.
- A Claude worker round starts fresh each time, so it always gets the full brief; the Codex
  fallback continues the item's Codex conversation when it has one, as any Codex round does.
- "Changed the checkout" means HEAD moved or `git status --porcelain` is not empty after the run.
- Each test file starts with `STORY = "FORGE-DESIGN-1"`, and its `test_<n>_` names cite the
  Done-when items its task covers.
