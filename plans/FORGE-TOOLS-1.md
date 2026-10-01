# Run Forge all in Claude, all in Codex, or both

2 parts · Risks: none · New moving parts: none

## What changes for you

- One setting says which tools run Forge's work: Claude Code only, Codex only, or both. Both is the
  default and behaves exactly as today.
- With one tool, building, plan reads, questions about the code and reviews all run on that tool,
  each with that tool's model for the kind of work.
- If the chosen tool isn't installed, Forge stops and says so in one plain line. It never quietly
  uses the other tool.
- New repos start with Forge's recommended model for each kind of work on both tools. Your
  existing settings file is never rewritten; your agent changes it only when you ask.
- You can tell your agent "run everything in Claude", "run everything in Codex", "use both",
  "Claude plans, Codex builds" or "Codex plans, Claude builds", and it knows the exact change.
- `forge doctor` points out a chosen tool that isn't installed, and any kind of work with no model
  for a tool you use.

## Why

Developers use Claude Code, Codex or both, mixed. Today Forge decides for them: reviews run on
Codex whenever it is installed, and plan reads run on the tool that isn't coordinating whenever it
is installed. A team that wants to stay on one tool can't, and a team with both installed can't
choose. New repos also get a model for only one tool for most kinds of work, so the other tool
runs on its own default.

## Done when

1. **A repo can choose Claude Code only, Codex only, or both, and both is the default and works exactly as today.**
2. **With one tool chosen, building, plan reads, questions about the code and reviews all run on that tool, each with that tool's model for the work.**
3. **When the chosen tool isn't installed, Forge stops with a plain message and never quietly uses the other tool.**
4. **New repos start with Forge's recommended model for each kind of work on each tool, and existing repos' settings are never rewritten.**
5. **The coordinator explains the settings and Forge's recommended models, and makes the right change when asked to run all in Claude, all in Codex, both, or one tool planning while the other builds.**
6. **Doctor reports a chosen tool that isn't installed, and a kind of work with no model for a tool in use.**

## Risks

Risks: none

## For the builders

### Done-when details

1. `forge.toml` gets a `tools` key: `repo.KEYS["tools"] = str`, `repo.DEFAULTS["tools"] = "both"`,
   `repo.CHOICES["tools"] = ("both", "claude", "codex")`. RUN pins one helper that every later
   caller uses:

   ```python
   def worker_tool(cfg: dict[str, Any]) -> str:
       """The tool workers run on: tools when it names one, else workers."""
       return cfg["workers"] if cfg["tools"] == "both" else cfg["tools"]
   ```

   With `tools = "both"` or no `tools` key, every choice is today's: workers follow `workers`;
   design work tries Claude and falls back to Codex; the cold reader is the other app when it is
   installed, else a separate conversation of this one; reviews use Codex when `codex` is on PATH,
   else Claude. `workers` keeps its meaning and its default.

   Tests:
   - a `forge.toml` without `tools` reads as `"both"`;
   - `tools = "gemini"` is refused as `tools must be one of both, claude, codex`;
   - the existing worker, cold-read and review tests pass unchanged, which proves "both" is today's.
2. With `tools` naming one tool:
   - **Workers.** `worker.py` sets `on_codex = repo.worker_tool(config) == "codex" and not design`,
     so `tools` overrides `workers`. Design work (a User-facing task or a prototype fix) runs on the
     named tool directly: on `"codex"` it skips the Claude attempt and takes today's Codex path with
     `design_models(config, "codex")`; on `"claude"` it runs on Claude and has no Codex fallback.
     A Claude worker reads one entry every round, as today: build for a task, lite for a fix. Its
     later rounds continue the same session, so the `fix` kind is read on Codex only.
   - **Cold reads.** In `story.read`, the reader is the named tool. When that tool is the app
     coordinating, the read is a separate conversation of it, as today. The `wrong_app` refusal
     doesn't apply, since the reader is fixed by the setting. The record says why:
     `codex (gpt-6.1-sol), a separate Codex conversation because forge.toml's tools is codex`.
     When the recorded reader of an earlier round is the other tool (the setting changed), the
     round starts fresh with the named tool, with the reason `forge.toml's tools is now <tool>`
     through the existing `why` path.
   - **Reviews.** In `review.run`, the engine is the named tool. The model is
     `repo.models(cfg, "review", engine)`, then on Claude today's fallback to the Claude cold-read
     entry. The light prototype review on Codex stays pinned to Sol at medium; on Claude it uses
     the Claude review entry's model at `medium` effort.
   - **Sign-off.** It follows `tools` like other reviews. It stays pinned per tool and still
     confirms the model and effort it asked for: on Codex `gpt-6.1-sol` at `high`, on Claude
     `claude-opus-5-5` at `high`. With `"both"`, sign-off is today's.
   - **Questions.** `forge ask` follows `tools`. With `"claude"` it asks Claude read-only:
     `claude -p --model <m> --effort <e> --permission-mode plan --no-session-persistence` through
     `repo.run` with the question on stdin, the same route as the Claude cold read
     (`story._claude_read`). It uses the Claude lite entry; `--model` and `--effort` each override
     their half of it, as they do on Codex, and with no entry and no option the flag is left out.
     The same snapshot check refuses when a file changed. Its refusals name the tool that answered
     (`A file changed while Claude answered`, `Claude did not complete the answer.`), and an empty
     or failed answer prints nothing. With `"codex"` or `"both"` it asks Codex as today. Its help
     and command listing say "a read-only question" instead of naming Codex.
   - Each kind uses that tool's entry through `repo.models(cfg, kind, tool)`. A kind with no entry
     for the tool runs on the tool's own default, as today, with today's two exceptions: a review
     on Claude with no Claude review entry uses the Claude grill entry, and design work uses
     `repo.design_models`, which supplies Forge's pinned design models. Item 6 reports the rest.

   Tests use the stub app-server and stub `claude` already in the suite, with both installed:
   - `tools = "claude"` with `workers = "codex"`: `forge work` runs on Claude with the Claude
     build entry;
   - `tools = "codex"` with `workers = "claude"`: it runs on Codex with the Codex build entry;
   - design work under `tools = "codex"` never calls `claude`; under `tools = "claude"` a failing
     Claude run refuses and never starts Codex;
   - a Claude worker with different Claude build, fix and lite entries runs a task's first and
     second rounds on the build entry and a fix's on the lite entry;
   - `forge read` under Claude Code with `tools = "claude"` reads with a separate Claude
     conversation and the Claude grill entry; under Codex with `tools = "codex"` the same on
     Codex;
   - `forge read` under Codex with `tools = "claude"` reads with Claude and the Claude grill entry;
     under Claude Code with `tools = "codex"` it reads with Codex and the Codex grill entry;
   - a second round after `tools` changed starts fresh with the named tool;
   - `forge close` with `tools = "claude"` and `codex` on PATH passes `--engine claude` and the
     Claude review entry; with `tools = "codex"` it passes `--engine codex` and the Codex entry;
   - a light review on Claude passes the Claude review model at `medium`;
   - sign-off with `tools = "claude"` passes `claude-opus-5-5` at `high` and refuses when Autoreview reports
     another model; with `tools = "codex"` it passes `gpt-6.1-sol` at `high`;
   - `forge ask` with `tools = "claude"` calls the stub `claude` in plan mode with
     `--no-session-persistence` and the Claude lite entry, and never starts Codex; `--model` alone
     overrides only the model and `--effort` alone only the effort; with no Claude lite entry it
     passes neither flag; a file changed during the answer, a failed run and an empty answer each
     refuse with the Claude wording and print no answer; with `"both"` it asks Codex as today.
3. RUN pins one refusal in `repo.REFUSALS`:

   ```python
   "tool_missing": ("forge.toml's tools is {tool}, so this runs on {name}, which isn't installed. "
                    "Forge won't use the other tool instead.", "forge doctor"),
   ```

   It is raised wherever the named tool would otherwise be swapped for the other:
   - the cold read, when the named tool isn't installed (Claude: `claude` on PATH; Codex:
     `codex.installed()`, as today's reader check);
   - the review, when the named tool's program isn't on PATH (`CODEX_BIN` or `codex`, or
     `claude`);
   - design work under `tools = "claude"` when `claude` is missing, instead of the fallback;
   - `forge ask` under `tools = "claude"` when `claude` is missing.

   A Claude worker without `claude` keeps today's `missing_tool` refusal, and a Codex worker
   without the SDK keeps today's SDK refusal: neither falls back today. Every refusal comes before
   any state commit. Today a Claude worker finds `claude` missing only in `_run`, after the status
   commit, so `worker.ready` takes that check: every Claude worker, and design work under
   `tools = "claude"`, refuses there when `claude` isn't on PATH. Design work under
   `tools = "codex"` runs `ready(top, config, kind, True, design=True)` before the commit like
   other Codex work. Design work under `"both"` keeps today's fallback.

   Tests: each of the four cases refuses with the message and starts nothing on the other tool;
   an ordinary Claude worker without `claude` and a Codex design worker without the SDK each
   refuse; every case leaves HEAD and the item's state as they were.
4. `init.MODELS` gives every kind one entry per tool, with Forge's recommended defaults, and
   `_settings` writes `tools = "both"` after `workers`:

   | Kind | Codex | Claude |
   |---|---|---|
   | build | gpt-6.1-sol, medium | claude-opus-5-5, medium |
   | fix | gpt-6.1-sol, medium | none: Claude workers read build and lite only (item 2) |
   | lite | gpt-6.1-sol, medium, subagents gpt-6-luna at max | claude-sonnet-5-5, medium |
   | grill | gpt-6.1-sol, high | claude-opus-5-5, high |
   | design | gpt-6.1-sol, high | claude-opus-5-5, high |
   | review | gpt-6.1-sol, high | claude-opus-5-5, high |

   The light review (Sol at medium on Codex, the Claude review model at medium) and sign-off (high)
   are pinned in code, not in this table. Claude entries set no subagents, since Claude workers
   refuse them. Autoreview's Claude engine takes any `claude --model` name and the efforts low,
   medium, high, xhigh and max, so `claude-opus-5-5` at `high` is accepted.

   Subagent roles read each kind's entry through `repo.models(cfg, kind, family)`, so a
   per-tool table reaches both hosts' roles. Before, only `design` was read per tool. A kind with
   no entry for a host now leaves out both the model and the effort there, where the roles fix kept
   the other tool's effort. Forge's own `.claude/agents/` and `.codex/agents/` are written again
   with `forge sync`, and the existing role assertions in `tests/test_subagent_roles.py` that read
   a single entry's effort on the other host change with them.

   No code rewrites an existing `forge.toml`: `forge sync`, `forge upgrade` and doctor leave
   `[models]` and `tools` as they are.

   Tests:
   - `forge init` writes a `forge.toml` that `repo.config` accepts, with `tools = "both"` and every
     cell of the table above;
   - `forge work` on a new repo runs with the Codex build entry under `workers = "codex"` and with
     the Claude build entry under `workers = "claude"`;
   - the synced `.claude/agents/coder.md` names `claude-opus-5-5` at `medium` and
     `.codex/agents/coder.toml` names `gpt-6.1-sol` at `medium`;
   - `forge sync` on a repo with a single-entry `[models.build]` leaves `forge.toml` byte for byte;
   - a single gpt `[models.build]` writes no model and no effort into `.claude/agents/coder.md`;
   - Forge's own synced role files match `forge sync`'s output (the existing roles test).
5. `src/forge/templates/skill.md` gets a short `## Models` section, at most about 30 lines:
   - **Who does what.** The orchestrator is whichever app the developer opens, Claude Code or
     Codex; Forge doesn't choose it. `tools` says which tools run Forge's work. With `"both"`,
     `workers` picks the implementer, plan reads use the tool that isn't orchestrating, and reviews
     use Codex when it is installed. With one tool, workers, plan reads and reviews all run on that
     tool and `workers` is ignored.
   - **The shape.** `[models.<kind>.codex]` and `[models.<kind>.claude]` for build, fix, lite,
     grill, design and review; a single `[models.<kind>]` counts for its model's tool.
   - **Forge's recommended models**, the table in item 4. DEFAULTS adds this table with item 4's
     defaults; RUN writes the rest of this item in the same change as the setting, as the review
     rules require.
   - **Upgrade first.** When `forge.toml` pins a Forge older than the release that adds `tools`,
     follow Upgrade Forge before adding the key, because an older Forge refuses keys it doesn't
     know.

   The intent table replaces the row `"Switch to Codex workers" or "Change the test command"` with
   `"Change the test command"`, renames `"Ask Codex about this code"` to `"Ask about this code"`,
   and adds:

   | The human says | Run |
   |---|---|
   | "Run everything in Claude" | Ask, then in a fix: `tools = "claude"`, `workers = "claude"`, add any missing `[models.<kind>.claude]` with Forge's recommended models, `forge close <fix>` |
   | "Run everything in Codex" | Ask, then in a fix: `tools = "codex"`, `workers = "codex"`, add any missing `[models.<kind>.codex]`, `forge close <fix>` |
   | "Use both" | Ask, then in a fix: `tools = "both"`, add any missing entries for either tool, `forge close <fix>` |
   | "Claude plans, Codex builds" | Ask, then in a fix: `tools = "both"`, `workers = "codex"`, `forge close <fix>`; the developer opens Claude Code |
   | "Codex plans, Claude builds" | Ask, then in a fix: `tools = "both"`, `workers = "claude"`, `forge close <fix>`; the developer opens Codex |

   `docs/guide.md`'s settings section says the same in a paragraph: `tools`, its default, and the
   mixed-use pairs. The synced copies in `.claude/skills/forge/` and `.codex/skills/forge/` are
   written again with `forge sync`.

   Tests:
   - RUN: the skill holds each of the five intent rows and the `## Models` section, and
     `forge ask`'s listing names no tool;
   - DEFAULTS: every model and effort in the skill's recommended table matches `init.MODELS`, so
     the two can't drift;
   - both: the synced copies match the template (the existing sync test).
6. Doctor, using `repo.worker_tool(cfg)` and `cfg["tools"]`:
   - **Programs.** The missing-program rows check git, gh and uv, plus `claude` when the worker
     tool is Claude or `tools = "claude"`, plus Codex when `tools = "codex"`, since reviews then
     need it. That row looks the program up exactly as the review does,
     `shutil.which(os.environ.get("CODEX_BIN") or "codex")`. `INSTALL["codex"] = "npm install -g @openai/codex"`. With `"both"` the
     rows are today's: `claude` for Claude workers, and the SDK row for Codex workers. This is the
     report when `workers` names a tool that isn't installed.
   - **Codex SDK.** It is needed when the worker tool is Codex or `tools = "codex"`; never with
     `tools = "claude"`; with `"both"`, today's rule. `--fix` installs it as today.
   - **UI skills.** The skills check reads the worker tool, not `workers`.
   - **Missing entries.** For each tool in use (both with `"both"`, else the named one), one note
     line lists the kinds with no entry for it through `repo.models`:
     `- Note: forge.toml has no Claude model for build and lite, so that work runs on Claude
     Code's own default.` The kinds checked are the ones that fall to the tool's own default
     (item 2): build, fix, lite, grill and review on Codex; build, lite and grill on Claude, plus
     review when there is no Claude grill entry either. Design never appears, since
     `repo.design_models` supplies Forge's pinned models. A note isn't a problem row and doesn't change the exit code, so an
     existing client with single entries isn't failed for a setting it never chose.

   Tests:
   - `tools = "claude"` without `claude` on PATH: the row;
   - `tools = "codex"` without `codex` on PATH: the row and the SDK check;
   - `tools = "codex"` with `CODEX_BIN` naming an installed program and no `codex` on PATH: no
     row; with `CODEX_BIN` naming a missing program and `codex` on PATH: the row;
   - `tools = "claude"` with Codex installed under Claude Code: no SDK row and `--fix` never
     installs it;
   - `"both"` with `workers = "claude"` and no `claude`: today's row;
   - a single gpt `[models.build]` under `"both"`: the Claude note names build, and the exit code
     is 0 when nothing else is wrong;
   - a new repo's `forge.toml`: no notes, though it has no Claude fix entry;
   - a Claude grill entry and no Claude review entry: the Claude note doesn't name review.

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing |
|---|---|---|---|---|---|---|---|
| RUN | Tools setting | The `tools` key, `repo.worker_tool`, the `tool_missing` refusal, and workers, design work, cold reads, `forge ask`, reviews and sign-off following it, with the coordinator's guide for them | 1, 2, 3, 5 | `src/forge/repo.py`, `src/forge/worker.py`, `src/forge/story.py`, `src/forge/review.py`, `src/forge/ask.py`, `docs/commands.md`, `src/forge/templates/skill.md`, `.claude/skills/forge/`, `.codex/skills/forge/`, `docs/guide.md` | `tests/test_tools_setting.py` | none | no |
| DEFAULTS | Defaults and doctor | New repos' per-tool models and `tools = "both"`, roles reading per-tool entries, doctor's program, SDK, skills and missing-entry checks, and the skill's recommended-models table | 4, 5, 6 | `src/forge/init.py`, `src/forge/roles.py`, `src/forge/doctor.py`, `src/forge/templates/skill.md`, `.claude/skills/forge/`, `.codex/skills/forge/`, `.claude/agents/`, `.codex/agents/`, `tests/test_subagent_roles.py` | `tests/test_tools_defaults.py`, `tests/test_tools_doctor.py`, `tests/test_subagent_roles.py` | RUN | no |

New moving parts: none

## Notes

- Starts after two fixes in flight merge: the one giving each kind a Codex and a Claude entry
  (`repo.models(cfg, kind, family)`, which this story uses everywhere) and the one writing the
  subagent roles for both hosts (`src/forge/roles.py`, which DEFAULTS changes). It also starts after the fix
  moving reviews, the light review and sign-off to gpt-6.1-sol, which the owner chose today.
- RUN pins `repo.worker_tool`, `cfg["tools"]` and the `tool_missing` refusal; DEFAULTS uses the
  first two in doctor. Each task updates the coordinator's guide for what it changes, as the
  repo's review rules require: RUN the setting, the intent rows and `forge ask`; DEFAULTS the
  recommended-models table, whose test reads `init.MODELS`.
- Decided: Claude workers keep reading build for a task and lite for a fix on every round, since
  their later rounds continue the same session; `fix` stays a Codex kind and new repos get no
  Claude fix entry (owner, 2026-10-01).
- Decided: sign-off follows `tools` and stays pinned per tool: Codex `gpt-6.1-sol` at high, Claude
  `claude-opus-5-5` at high (owner, 2026-09-30).
- Decided: with one tool, `tools` wins and `workers` is ignored; the skill's rows set both keys so
  the file never reads as a contradiction (owner, 2026-09-30).
- Decided: `forge ask` follows `tools`: `"claude"` asks Claude read-only, `"codex"` and `"both"`
  ask Codex as today (owner, 2026-09-30).
- Not changed: the coordinator app, which the developer chooses by opening it.
- Existing clients keep their `forge.toml`; their agent adds `tools` and entries only when asked,
  through the skill's rows.
- No client repo is named anywhere in this story's code, tests, texts or commits.
- Each new test file starts with `STORY = "<this story's key>"`, and its `test_<n>_` names cite the
  Done-when items its task covers.
- Claude defaults follow Anthropic's guidance (owner, 2026-09-30): pinned IDs, not aliases, because
  `opus` and `sonnet` resolve to different models on different providers. Work at `claude-opus-5-5`
  medium; plan reads, design, reviews and sign-off at `claude-opus-5-5` high; quick asks and the
  explorer role at `claude-sonnet-5-5` medium; Fable 5.1 never by default. A Claude benchmark on the
  same review and cold-read cases may change the review and read efforts before this story ships.
