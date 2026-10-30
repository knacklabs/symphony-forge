# Client specs state each rule once

1 part · Risks: none one-way · New moving parts: none

## What changes for you

- In a client repo's specs, each rule is one line with an ID, for example `R-13: Only the owner
  sets the limits.` Validation (VAL), UAT and acceptance (AC) lines name the rule that they check
  by its ID, for example `VAL-11 checks R-13`, and do not say the rule again.
- When you accept a decision that changes a rule and names its ID, `forge decision accept` lists
  every spec line that names that ID. The agent updates those lines in the same change, before
  review. It does not refuse anything.
- A new repo gets the spec format in `docs/specs/README.md` at init. An existing repo gets the
  list at accept and the guide text when it upgrades with `forge sync`.
- The first sync on this release lists the old spec lines that seem to repeat a rule: each VAL,
  UAT or AC line that names no `R-` ID. The agent shows you the list and asks when to rewrite
  those specs. Later syncs do not list them again.
- Forge does not rewrite old specs. Spec save and confirm accept a spec in the old format, as
  today.

Design: none (no screens; it changes one template, guide text, one command's output and sync's
output)

## Why

A client repo restates each rule in up to five lines: a rule line (R or BR), a validation line, a
UAT line and an acceptance line (client issue 1145). When a decision changes the rule, the agent
updates the rule line and the copies keep the old meaning. A cold read, QA or review finds the
contradiction one round later, and `forge next` then says the spec "keeps breaking". Both open
problems in the issue are this case, and the specs got 27 commits in one month, many only to
bring copies back into line. Forge's spec template, `docs/specs/README.md`, gives no rule IDs and
no rule for how check lines refer to rules.

## Done when

1. **A new repo from `forge init` has a `docs/specs/README.md` that shows each rule on one `R-<n>:` line and an acceptance line that names the rule by its ID. The agent's guide and the worker brief say to state each rule once and to name it by ID in VAL, UAT and AC lines. An existing repo gets the guide and brief text on upgrade with `forge sync`, and sync does not change its `docs/specs/README.md`.**
2. **`forge decision accept` on a decision that names rule IDs such as `R-13` prints every line in the repo's specs that names one of those IDs, with its file and line number. It does not print a line that names only `R-130` or `BR-13`, a cold-read notes line, or a README line. A decision that names no rule ID prints as today.**
3. **In an existing repo, the first `forge sync` on this release prints each spec line that seems to repeat a rule (a VAL, UAT or AC line that names no `R-` ID), with its file and line number, and a next step. The next `forge sync` does not print them. A repo set up on this release gets no such list from sync.**

## Risks

<!-- Each one-way step: deleting data, a destructive migration, a new vendor. -->

Risks: none one-way. The part reverts with its pull request.

Trade-off: the list at accept is advice, not a gate. Forge cannot tell if a line that names
`R-13` still fits the changed rule. When check lines only name the rule, most of them stay true
when the rule changes.

Trade-off: rule IDs can repeat across specs, so accept also lists `R-13` lines from other specs.
The agent ignores the ones that do not apply.

Trade-off: the sync list finds only numbered VAL, UAT and AC lines. It does not find an
unnumbered check that repeats a rule, or a BR line that repeats an R line.

## For the builders

<!-- Everything from here down is for the agents. The owner doesn't see it when approving, and
tightening it needs no new approval. -->

The new test file starts with `STORY = "FORGE-SPECRULES-1"`. Tests run the forge command and never
import forge.

### Why the check is at accept

`forge decision accept` is the one step where a decision becomes the rule. It already runs on the
fix or story branch (`records._start`), before close's review, and it already reads the
decision's body. A pre-commit check would run on every commit and would have to parse diffs.
`decision new` writes an empty template, so it has no IDs to read. Accept costs one read of
`docs/specs/*.md`.

### The format (pinned)

- A rule ID is `R-` and a number. One regex, `RULE_ID = re.compile(r"\bR-\d+\b")`, in
  `src/forge/records.py`. The `\b` keeps `BR-13` and `R-130` out of a search for `R-13`.
- The spec files are `docs/specs/*.md` in the checkout, except `README.md` and `*.read.md`
  (cold-read notes). One helper, `_spec_lines(top)`, yields `(rel, number, line)` for them in
  path and line order, and both checks use it.
- A printed line is `f"{rel}:{number}: {line.strip()}"`.
- The guide marker that sync looks for is the 8 characters `` `R-<n>:` `` (with the backticks)
  on one line of `skill.md`.

### Done-when details

1. The template and the guides say it (SPECRULES).
   - `src/forge/templates/skeleton/docs/specs/README.md`: keep every line that is there (the
     cold-read lines are pinned by `tests/test_readloop_cut.py`). After
     `A field may wrap onto indented lines.` add:

     ````markdown
     State each rule once, on one line with an ID, under `## Behaviour`. Validation (VAL), UAT and
     acceptance (AC) lines name the rule that they check by its ID and say how it is checked. They
     do not say the rule again:

     ```markdown
     ## Behaviour

     - R-1: An invoice goes out by email when it is issued.

     ## Acceptance criteria

     - AC-1 checks R-1: issue a test invoice; the client's inbox has it within a minute.
     ```

     A decision that changes a rule names its ID. `forge decision accept` then lists every spec
     line that names that ID, so you update them in the same change.
     ````

     The required sections do not change (`records.SPEC_SECTIONS`), so spec save needs no code
     change, and a spec in the old format still saves.
   - `src/forge/templates/skill.md`, `## Save decisions and ideas`: a new bullet after the bullet
     that starts `Save a standing rule or direction`:
     "- In `docs/specs/`, state each rule once, on an `R-<n>:` line under `## Behaviour`.
     Validation (VAL), UAT and acceptance (AC) lines name the rule that they check by its ID, for
     example `VAL-11 checks R-13`, and do not say the rule again. A decision that changes a rule
     names its ID. `forge decision accept` then lists every spec line that names that ID: in the
     same change, before close, update each line that no longer fits. On upgrade, the first
     `forge sync` lists the old spec lines that seem to repeat a rule, with a fix to start. Show
     the list to the owner and ask with options: rewrite those specs now in that fix, or later."
     Keep `` `R-<n>:` `` on one line: sync looks for it (item 3).
   - `src/forge/templates/brief.md`: a new paragraph after the `services.toml` paragraph, before
     `## When you finish`:
     "In `docs/specs/`, state each rule once, on an `R-<n>:` line. Validation (VAL), UAT and
     acceptance (AC) lines name the rule that they check by its ID, for example
     `VAL-11 checks R-13`, and do not say the rule again. When a change edits a rule, update the
     lines that name its ID in the same change."
   - `forge sync` rewrites `.claude/skills/forge/SKILL.md` and `.codex/skills/forge/SKILL.md` in
     this repo.
   - Test: `tests/test_spec_rules.py::test_1_specs_state_each_rule_once`, parametrised `new` and
     `previous-release adoption`, as
     `tests/test_deployment_requires_an_explicit_request.py::test_1` does: `_fresh_client`, or
     the `tests/fixtures/forge-v1.2.2` release run as `old-forge init`; the pin moved with
     `_version(repo)` and, for the previous release, `forge sync`; `install_claude` and
     `calls(log)[-1]["brief"]` after `forge work`. Compare text with its whitespace joined
     (`" ".join(text.split())`).
     - Both cases: both synced `SKILL.md` copies have "state each rule once, on an" followed by
       the marker, and "`forge decision accept` then lists every spec line that names that ID";
       the worker brief has "When a change edits a rule, update the lines that name its ID in the
       same change."
     - New: `docs/specs/README.md` has "- R-1: An invoice goes out by email" and
       "- AC-1 checks R-1:".
     - Previous release: `docs/specs/README.md`, or its absence, is the same before and after
       `forge sync`.
2. Accept lists the lines that name the decision's rule IDs (SPECRULES).
   - `src/forge/records.py`, `decision_accept`: after its last line,
     `print(f"Accepted {rel}, confirmed by {by}{also}.")`, take the IDs from the decision's body
     with HTML comments removed (the same `re.sub(r"<!--.*?-->", "", ..., flags=re.S)` that the
     `unfilled` check uses), as a set sorted by number. When there are IDs and `_spec_lines`
     finds lines that name one of them (`re.search(rf"\b{re.escape(rule)}\b", line)`), print
     `These spec lines name {the IDs joined with ", "}; in this change, update each one that no longer fits the decision:`
     and then each line. Print nothing more when there are no IDs or no lines. The early returns
     (already accepted, the sign-off review step) do not change.
   - A `ponytail:` comment: IDs can repeat across specs, so other specs' lines are listed too;
     read only the specs that the decision names if that gets noisy.
   - `records.COMMANDS`, the `decision accept` listing: add `, and lists the spec lines that name
     a rule ID it names` to its text. `forge sync` rewrites `docs/commands.md`, which
     `tests/test_split_page.py` pins.
   - Test: `tests/test_spec_rules.py::test_2_accept_lists_the_spec_lines_that_name_its_rules`,
     parametrised `new` (`_fresh_client`, then `forge fix start ... --kind mechanical` and its
     folder) and `previous-release adoption` (the `old-forge init` adoption fix folder, after the
     pin move and `forge sync`). In the fix folder, write:
     - `docs/specs/admin.md` with, on known lines, `- R-13: Only the owner sets the limits.`,
       `- VAL-11 checks R-13: the top admin's settings page has no limits field.`,
       `- AC-11 checks R-2 and R-13: ...`, `- R-130: ...` and `- BR-13: ...`;
     - `docs/specs/admin.read.md` with a line that names `R-13`;
     - a decision from `forge decision new limits-move` with its three sections filled and its
       Decision section naming `R-13`, and a second one from `forge decision new plain-choice`
       that names no ID. Commit them.

     `forge decision accept limits-move --by Ravi` prints the header that names `R-13` and then
     exactly three lines, `docs/specs/admin.md:<n>: ...` for the R-13, VAL-11 and AC-11 lines,
     in file order. `forge decision accept plain-choice --by Ravi` prints exactly
     `Accepted docs/decisions/<NNNN>-plain-choice.md, confirmed by Ravi.\n`.
3. The first sync on this release flags old spec lines (SPECRULES).
   - `src/forge/records.py`: `old_spec_lines(top) -> list[str]`, the printed lines from
     `_spec_lines(top)` whose text matches
     `re.match(r"[\s>*|-]*(?:\d+\.\s*)?\**(?:VAL|UAT|AC)-\d+\b", line)` and has no `RULE_ID`
     match. A `ponytail:` comment: it misses unnumbered checks and BR lines that repeat an R
     line; widen the pattern when a client shows the need.
   - `src/forge/sync.py`, `sync`: before `changed = write(top, cfg)`, read
     `read(top / ".claude/skills/forge/SKILL.md")` and set `first` when the marker is not in it.
     After the `Wrote ...` lines, when `first` is set and `records.old_spec_lines(top)` is not
     empty (import `records` in the function), print
     `These spec lines seem to repeat a rule instead of naming its R- ID:`, then each line, then
     `Next: forge fix start "Specs state each rule once" --done "Each VAL, UAT and AC line in docs/specs names the R- rule it checks" --kind mechanical`.
     The old skill copy lacks the marker only until this sync writes the new one, so the list
     prints once. Init does not call `sync.sync`, and a repo set up on this release has the
     marker from its first commit.
   - Test: `tests/test_spec_rules.py::test_3_the_first_sync_flags_old_spec_lines_once`,
     parametrised `new` and `previous-release adoption`. In each, write `docs/specs/admin.md`
     with `- VAL-11: The top admin cannot set the limits.`,
     `| UAT-16 | The top admin sees no settings page |`, `1. **AC-11**: The limits stay as set.`,
     `- VAL-12 checks R-23: ...` and `- BR-24: ...`, and `docs/specs/admin.read.md` with a
     `- VAL-9: ...` line.
     - Previous release: after the pin move, `forge sync` prints the header, exactly the VAL-11,
       UAT-16 and AC-11 lines as `docs/specs/admin.md:<n>: ...`, and the Next line. A second
       `forge sync` prints none of them.
     - New: after `_fresh_client`, write the spec in a fix folder; `forge sync` there prints no
       "seem to repeat a rule" line.

### New and existing repos

- **New repos** (`forge init` and `forge init --starter`, and a repo adopted with `forge init` on
  this release): `docs/specs/README.md` with the rule-ID format (adoption writes no skeleton, as
  today), the skill bullet, the brief paragraph and the list at accept. Sync never flags their
  specs, because their skill copy has the marker from the first commit. Tested in each item's
  `new` case.
- **Existing repos** (on upgrade to this release with `forge upgrade` or `forge sync`): the skill
  bullet through sync, the brief paragraph and the accept list with the release, and one list of
  old spec lines on the first sync. Their `docs/specs/README.md` and specs do not change. Tested
  in each item's `previous-release adoption` case.

## Tasks

<!-- One row per task. Covers: the Done-when numbers it delivers, at most three. Scope: the paths
it may change. Tests: the tests it adds or changes. After: the tasks it waits for. When two tasks
share a function, field, file format or command, the first task pins it: it commits the shared
names and stubs plus one test that crosses both sides, and the tasks that use it list it under
After. Split tasks so each owns its files; shared lines (command table, guide list, registry) go
to one task or a small last wiring task; After only when a task needs another task's code. The
Developer column is optional: the lead fills or changes a GitHub username here, below For the
builders, without another approval. Leave it blank for an unassigned part. Forge next uses
the caller's GitHub login; another developer may start it with a warning. Existing tables
without Developer still work. The moving-parts line stays last: "none", or each new dependency, service, datastore,
queue, background job or abstraction layer, with the Done-when item that needs it. -->

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing | Developer |
|---|---|---|---|---|---|---|---|---|
| SPECRULES | Specs state each rule once | The rule-ID spec template, the guide and brief text, the list at decision accept, and the one-time sync list of old spec lines, on new and existing repos | 1, 2, 3 | `src/forge/templates/skeleton/docs/specs/README.md`, `src/forge/templates/skill.md`, `src/forge/templates/brief.md`, `src/forge/records.py` (`RULE_ID`, `_spec_lines`, `old_spec_lines`, `decision_accept`, the `decision accept` listing), `src/forge/sync.py` (`sync`), `.claude/skills/forge/SKILL.md`, `.codex/skills/forge/SKILL.md` and `docs/commands.md` (rewritten by `forge sync`), `tests/test_spec_rules.py` (new) | `tests/test_spec_rules.py` (`test_1`, `test_2`, `test_3`) | | no | |

One part: the sync check needs the skill text, and the skill text describes the accept list, so
a split makes one part wait for the other.

New moving parts: none

## Notes

- Owner decision (27 Oct 2026, settled): client specs state each rule once. The spec template
  gives each rule one line with an ID (`R-13: ...`). VAL, UAT and AC lines refer to rules by ID
  (`VAL-11 checks R-13`). When a decision record changes a rule and names its ID, Forge lists
  every spec line that names that ID, in the same change and before review. New repos get the
  template at init. Existing repos get the check and the guide text on upgrade with `forge sync`,
  and their old specs are flagged once with the lines that seem to repeat a rule.
- Not in this story: the issue's second problem, one ranked list of every open decision across
  specs and decision records (`forge decisions open` and `settle` in the issue). The owner
  decision does not cover it.
- Planner choices the owner did not make: (1) the check runs at `forge decision accept`, and it
  lists lines but refuses nothing; (2) a rule ID is `R-<n>` only, rule lines go under the
  required `## Behaviour` section, and spec save and confirm do not check the format; (3) IDs are
  matched in every spec, not only the spec the decision is about; (4) the flag is a numbered VAL,
  UAT or AC line that names no `R-` ID, and "once" means the first sync whose old guide copy does
  not have the new text; (5) sync does not change an existing repo's `docs/specs/README.md`, and
  adoption on this release writes no skeleton, as today.
