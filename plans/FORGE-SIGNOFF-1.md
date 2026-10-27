# Clients settle every open decision from one ranked list before sign-off

2 parts · Risks: none one-way · New moving parts: none

## What changes for you

- Each client repo has one list of open decisions. Forge collects it from one fixed form of
  question that the agent writes in decision records (under "To confirm"), specs, plans and
  cold-read notes. The agent copies a review note that needs the client into the same form.
- Each item on the list says, in plain words: the question, why we ask it (what the answer
  changes, and the screen or rule it touches), the default we picked and why we picked it, what
  happens if the default stands, a due date, and Gain, Work and Harm scores. The list is ranked
  with the same bar as reviews, so the client sees what matters most first.
- `forge decision open` prints the ranked list. The agent goes through it with the client in one
  sitting, not one question per round.
- `forge decision answer` records all the client's answers from one file as one decision record.
  The record keeps each question's reason beside its answer. Forge marks each question answered
  where it was asked, so it leaves the list.
- When a due date passes with no answer, the default applies. `forge next` names each such
  decision and its default, and tells the agent to record it as "decided by default" and to tell
  the client. The client can change it later with a new decision.
- The canvas in Play mode is the default clickable prototype. A coded working prototype stays
  optional. Forge asks for a demo address only when a working prototype exists. Today it asks
  every new client repo, because each one starts with a Dockerfile.
- The canvas shows the whole product: every screen, state and flow, later ones too. Each screen
  in the screen list is marked "Build now" or "Later". Only "Build now" screens become the first
  stories. "Later" screens stay on the signed canvas as the source for later stories.
- Sign-off waits while an open decision touches a "Build now" screen. The refusal lists each such
  decision with why we ask it, why its default was picked and what happens if the default stands,
  and then names the next step. A decision that touches only a "Later" screen does not block.
- A new client repo gets all of this at init. An existing client repo gets the commands and the
  guide with `forge sync`. Its older to-confirm lists do not count until the agent rewrites them
  in the new form once, and its next sign-off asks for the Build now or Later mark on each screen.

Design: none (no screens; it adds two decision commands, two sign-off checks and guide text)

## Why

A client repo about two months old had 46 decision records, and 29 of them amend or replace an
earlier one. Six still carry "to confirm" lists, and specs hold more open questions. Nothing
collects them, so the owner answers in fragments across many rounds and items. The questions
have no due date, so their defaults get built on and then reopened. The team built a one-page
list of about 60 questions by hand, ranked with Forge's Gain, Work and Harm bar and with defaults
picked, to stop the back-and-forth (client issue 1145). Also, Forge asks a canvas-only prototype
for a demo address that it cannot have, and nothing says which screens the first stories build.
An FDE or client who is stopped must see why, so each item and each refusal carries its reasons.

## Done when

1. **`forge decision open` prints one ranked list of every open decision written in the fixed form in the checkout's decision records, specs, plans and cold-read notes; each item shows its question, why it is asked with the screen or rule it touches, its default and why that default was picked, what happens if the default stands, its due date and its Gain, Work and Harm, ranked by the review bar; an item with a missing field is listed with what it needs; the agent's guide, the worker brief and the cold-read prompt tell agents to write such questions in that form.**
2. **`forge decision answer --from <file> --by "<name>"` records every answer in the file as one accepted decision record, never a sign-off record, that keeps each question's reason beside its answer, and marks each question answered where it was asked, so the list no longer shows it; a question that is not open, or one with no answer, is refused by name with the next step.**
3. **When an open decision's due date has passed, `forge next` names it with its default and tells the agent to record it and tell the client; `forge decision answer --defaults` records each such default as decided by default in one decision record and marks it where it was asked.**
4. **`forge next` asks a prototype for a demo address only after app code is on the default branch; a client sign-off accepted from this release on needs each screen in the screen list marked `Build: now` or `Build: later`; the guide says the canvas in Play mode is the default clickable prototype and only Build now screens become the first stories.**
5. **Client sign-off is refused while an open decision touches a screen marked `Build: now`; the refusal lists, for each such decision, why it is asked, its default and why that default was picked, and what happens if the default stands, then names the next step; a decision that touches only a Later screen, or one already answered or decided by default, does not block.**

## Risks

<!-- Each one-way step: deleting data, a destructive migration, a new vendor. -->

Risks: none one-way. Each part reverts with its pull request. The answer command edits only the
lines that ask a question, and git keeps the old text.

Trade-off: Forge collects only questions in the fixed form. A free-form "to confirm" line does not
count until the agent rewrites it. A guess from free text would put noise on the list or miss a
question.

Trade-off: the list reads the checkout where the command runs. A question written on a branch that
has not merged shows only in that branch's checkout.

Trade-off: the blocking rule looks only at screens. A question about a rule blocks only when its
"Touches" line names a Build now screen. Stories after sign-off keep the cold read's "Decide
first" rule.

Trade-off: the scores and the due date are the agent's judgement, as in reviews.

## For the builders

<!-- Everything from here down is for the agents. The owner doesn't see it when approving, and
tightening it needs no new approval. -->

Each new test file starts with `STORY = "FORGE-SIGNOFF-1"`. Tests run the forge command and never
import forge. One test per Done-when item, named `test_<n>_...`. Each test has a new-repo case and
an existing-repo case. The new client is `_client(repo, tmp_path, monkeypatch, working_build=False)`
from `tests/test_proto_signoff.py`; the existing client is `_adopted_client(...)` from the same
file (the `tests/fixtures/adopted-v1.2.2/client` repo moved to this release). Both return a fix
worktree, so the decision commands can run in it. Use `FORGE_NOW` for dates.

`src/forge/nextstep.py` has 1,101 lines and `src/forge/records.py` has 750; the module ceiling is
1,200. So the list lives in a new module, `src/forge/open_decisions.py`, and nextstep.py and
records.py only call it. The two commands are subcommands of the `decision` group, so the
top-level command count in `tests/test_rules.py::test_5_forge_stays_small` does not change.

### Words this story pins (OPENLIST pins them; SIGNOFF uses them)

**The open-question form.** A line that starts, after optional indentation, with
`- Open question: ` followed by the question, and then the indented field lines below it. The
fields end at the first line that is not a field line. Every field is required:

```
- Open question: Can staff delete a client?
  Touches: Client list
  Why we ask: it decides if staff see a Delete button on the Client list.
  Default: no, only admins delete clients
  Why this default: deletes stay rare, and an admin can restore a client.
  If the default stands: staff see no Delete button, and admins delete clients.
  Due: 2026-11-03
  Gain 3, Work 2, Harm 4
```

- In a cold-read note, the block has no score line of its own. The reader puts it just before
  the note's own score line, so that one line is both the note's score (`score.parse` finds the
  first score line) and the question's score. The note keeps its scores, and no consumer of
  cold-read notes changes.
- `Touches:` names a screen section of `docs/design/prototype/SCREENS.md` (its `## ` title) or a
  rule ID. `Due:` is a real `YYYY-MM-DD` date. The score line is `score.LINE`'s format; read it
  with `score.parse`.
- Field line regex: `^[ \t]+(Touches|Why we ask|Default|Why this default|If the default stands|Due):[ \t]*(.*?)[ \t]*$`.
- Marker regex: `^([ \t]*)- Open question:[ \t]*(\S.*?)[ \t]*$`. It works inside a numbered
  cold-read note when the block is indented under the note.
- Lines inside a ``` or ~~~ fence are skipped, so a doc that shows the form (this plan, a README)
  adds no item. Mark this with a `ponytail:` comment: no other Markdown parsing.
- Answered forms (no longer open; the field lines stay as they are):
  `- Answered in NNNN-<slug>: <question>` and `- Decided by default in NNNN-<slug>: <question>`.
- Questions match by their text with runs of whitespace made one space, case kept.

**Where Forge looks.** Every `*.md` file under `docs/` and `plans/` in the checkout's working tree
(`rglob`, sorted paths). This covers decision records (`## To confirm`), specs, plans (Notes),
`plans/*.read.md` and `docs/specs/*.read.md`. No git process: reading files keeps
`tests/test_git_process_ceiling.py` unchanged.

**The answers file.** The same marker line with the question, and one indented `Answer: <text>`
line under it. Other lines are ignored.

**Build marks.** Each `## ` screen section in `docs/design/prototype/SCREENS.md` has one line
`Build: now` or `Build: later`. An open item, complete or not, blocks sign-off when its
`Touches:` value, compared without case and with whitespace made one space, equals the title of a
section with `Build: now`. Only the sign-off path asks `blocking`; `decision open` shows its
`Blocks sign-off` line only while `repo.is_prototype(top)` is true.

**Ranking.** Sort complete items by `(list(score.WORDS).index(score.bar(s)), -harm, -gain, work,
due, path, line)`, the same order as `score.table`.

### Done-when details

1. The ranked list (OPENLIST).
   - `src/forge/open_decisions.py` (new, about 150 lines): `items(top)` returns each open
     question with path, line, fields, scores and the fields it lacks; `blocking(top)` returns the
     complete and incomplete open items that touch a Build now screen; `decision_open(args)`;
     `decision_answer(args)`; `due_lines(top)`. Its `COMMANDS` holds `decision open` (position
     224, `changes_state: False`, no arguments) and `decision answer` (position 226,
     `changes_state: True`; no positional argument, `--from` with `dest="answers"` and metavar `FILE`, `--by`
     with metavar `NAME`, `--defaults` with `action="store_true"`), each with its `listing` row.
   - `src/forge/cli.py` `ROUTES`: `"decision open": "open_decisions"`,
     `"decision answer": "open_decisions"`. `src/forge/records.py` `GROUP_HELP["decision"]`:
     "Write, accept, list and answer decisions". `docs/commands.md` is regenerated as close does.
   - `decision open` runs on any branch and changes nothing. Output, exactly:

     ```
     <n> open decisions, highest first:

     1. <question>
        Asked in <path>, line <line>. Due <date>. Gain <g>, Work <w>, Harm <h>.
        Touches: <touches>
        Why we ask: <text>
        Default: <text>
        Why this default: <text>
        If the default stands: <text>
        Blocks sign-off: <touches> is marked Build: now in docs/design/prototype/SCREENS.md.

     These open questions need every field before they count:
     - <path>, line <line>: <question> needs <missing fields, joined with ", ">.

     Next: go through the list with the client, then forge decision answer --from <answers file> --by "<name>"
     ```

     The `Blocks sign-off` line shows only for a blocking item. A past due date reads
     `Due <date> (passed; the default applies)`. The incomplete section shows only when one
     exists. With no open question at all: `No open decisions.` and exit 0.
   - Guide text (OPENLIST): in `src/forge/templates/skill.md`, two rows in the command table after
     "The decision is accepted": `| "What does the client still need to decide?" | `forge decision open` |`
     and `| "Record the client's answers" | In a fix: `forge decision answer --from <file> --by "<name>"` |`.
     And a new `**Open decisions.**` paragraph in `## Prototype`, before `**Sign-off.**`. It says:
     write each question only the client can answer in the form above (shown in a fence), in the
     decision record under `## To confirm`, the spec or the plan's Notes it belongs to; pick the
     default, the due date and the scores with the review bar before you ask; copy a cold-read or
     review note that needs the client into that form; `forge decision open` prints the ranked
     list; go through the whole list with the client in one sitting; record their answers with
     `forge decision answer`; when `forge next` says a due date passed, record the defaults with
     `--defaults` and tell the client each default and that a new decision can change it; after an
     upgrade, rewrite each existing to-confirm list and open question in this form in one
     mechanical fix. In `**Sign-off.**`, the read-back call also goes through every item from
     `forge decision open`.
   - `src/forge/templates/brief.md`, after `These checks belong to the production story, not canvas sign-off.`:
     "When your work needs a choice only the client can make, do not guess and do not stop. Build
     with a sensible default, and name it in your handback as an open question: what it touches,
     why it is asked, the default, why you picked it and what happens if it stands. The coordinator
     adds it to the open-decisions list."
   - `src/forge/templates/cold-read.md`, after the `Decide first` paragraph: "When a note needs a
     choice only the client can make, put this block inside the note, indented under it, just
     before the note's score line. The block has no score line of its own: the note's score line
     scores the question too." Then the form in a fence with no score line, with
     `Due: <one week after today>`.
   - `src/forge/templates/skeleton/docs/decisions/README.md`: one line: "Questions still open go
     under `## To confirm` in the open-question form from the Forge guide. `forge decision open`
     lists them; `forge decision answer` records the answers." (new repos only; sync does not
     rewrite this file).
   - `forge sync` rewrites `.claude/skills/forge/SKILL.md` and `.codex/skills/forge/SKILL.md`.
   - Test: `tests/test_open_decisions.py::test_1_decision_open_ranks_every_open_question`,
     parametrised `new-client` and `adopted-v1.2.2`. In the fix: a decision record with
     `## To confirm` and one complete item (Gain 4, Work 2, Harm 3, `Touches: Order list`), a spec
     with one complete item (Gain 2, Work 1, Harm 1), a `docs/specs/orders.read.md` note with an
     indented complete item (Gain 5, Work 3, Harm 2), one item with no `Due:` and no
     `Why this default:`, and a fenced example in a README. `forge decision open` exits 0 and
     prints the three complete items in the order read note, decision record, spec, each with
     every field line; the incomplete one under the needs section with
     `needs Why this default, Due`; nothing from the fence. New client only: with
     `Build: now` under `## Order list` in SCREENS.md, the decision-record item has its
     `Blocks sign-off` line. Then the synced skill copies hold `forge decision open`,
     `forge decision answer` and `Why this default:`; the worker brief from `forge work` holds the
     handback sentence (as `tests/test_services_guide.py::test_3` reads it); the cold-read prompt
     from `forge read` holds the form (as `tests/test_proto_topics.py` reads it).
2. Recording answers (OPENLIST).
   - `decision answer` takes no slug. Forge names the record itself: `client-answers` with
     `--from`, `decided-by-default` with `--defaults`. So it never writes a `client-signoff`,
     `prototype-design`, `prototype-build` or `app-constitution` record, and sign-off keeps all
     its checks. It runs only on a fix or story branch: call `records._start(args, <that slug>)`.
     With `--from`, `--by` is required, checked with `records._name`. Exactly one of `--from` and
     `--defaults`, or refuse `("Use --from <file> with --by \"<name>\", or --defaults.", "forge decision open")`.
   - Every question in the file must match an open item, and each needs an `Answer:` line. Refuse
     with the first problem:
     `("{file} answers a question that is not open: {question}.", "copy the question from forge decision open, then forge decision answer --from {file} --by \"{by}\"")`
     and `("{file} has no Answer: line for: {question}.", "add its answer, then forge decision answer --from {file} --by \"{by}\"")`.
     Pass the question and file through `repo.refuse`'s values, never inside the format string, so
     braces in a question cannot break the message.
   - Write `docs/decisions/NNNN-<slug>.md` with that slug (several such records share it; each is
     named by its number), number `max(records._decision_numbers(top), default=0) + 1`:

     ```
     ---
     status: accepted
     confirmed_by: "<by>"
     date: <today>
     stories: []
     supersedes: ""
     ---

     # Client answers   (or: Decided by default)

     ## Context
     <n> open decisions were answered by <by> on <today>.

     ## Decision
     - <question>
       Answer: <answer>
       Asked in: <path>
       Touches: <touches>
       Why we ask: <text>
       Default was: <default>
       Why this default: <text>
       If the default stands: <text>

     ## Consequences
     Each question is marked answered where it was asked. A new decision that supersedes this one
     changes an answer.
     ```

     The Decision section has one block per answer, in the file's order. An incomplete item keeps
     only the fields it has.
   - On each source line of an answered question, change `- Open question:` to
     `- Answered in NNNN-client-answers:`. Mark every place that asks the same question.
   - `repo.commit_state(f"Record {n} answers from the client", rel, *sources, top=top)` and print
     `Recorded <n> answers in <rel> and marked each where it was asked.`
   - Test: `tests/test_open_decisions.py::test_2_decision_answer_records_one_decision`,
     parametrised `new-client` and `adopted-v1.2.2`. Two open items in two files, an answers file
     in `tmp_path` answering both: exit 0; one new accepted record with both blocks and their
     `Why we ask:`, `Why this default:` and `If the default stands:` lines; each source line now
     reads `- Answered in NNNN-client-answers:` with its field lines kept; `forge decision open` prints `No open decisions.`; the last commit holds the
     record and both sources. New client only: an answers file with an unknown question exits 1
     and names it, and one with no `Answer:` line exits 1 and names it; neither writes a record.
3. Defaults on the due date (OPENLIST).
   - `due_lines(top)`: the complete open items whose `Due` is before today (`repo.now()[:10]`).
     `nextstep._report` calls it inside its `if (top / "forge.toml").is_file():` block, only when
     `cfg["repo"] == "client"`, and adds:

     ```
     <n> open decisions passed their due date, so their defaults apply:
     - <question>: <default> (due <date>, <path>)
     Next: forge fix start "Record the defaults of past-due decisions" --done "One decision record holds each default" --kind mechanical
     Next: forge decision answer --defaults, then tell the client each default and that a new decision can change it
     ```

   - `decision answer --defaults` records the same record as item 2 with
     `confirmed_by: "decided by default"`, Context `<n> open decisions passed their due date with no answer, so their defaults apply.`,
     and `Answer: <default> (decided by default; due <date>)`. Source lines become
     `- Decided by default in NNNN-decided-by-default:`. It prints the record path, then one line per default
     for the agent to tell the client. With no past-due item it prints
     `No open decision has passed its due date.` and exits 0.
   - Test: `tests/test_open_decisions.py::test_3_a_passed_due_date_applies_the_default`,
     parametrised `new-client` and `adopted-v1.2.2`. One item due 2026-11-03 committed on main,
     `FORGE_NOW=2026-11-04T09:00:00+00:00`: `forge next` in the main checkout prints the lines
     above; with `FORGE_NOW=2026-11-03T09:00:00+00:00` it prints none. In the fix:
     `forge decision answer --defaults` exits 0, writes the record with
     `confirmed_by: "decided by default"`, and marks the source line; `forge next` in the fix
     prints no due lines.
4. Canvas first and the Build marks (SIGNOFF).
   - `src/forge/nextstep.py` `_needs_demo_address`: return true only when it does today and
     `design.has_app_code(top, ref)` is true: app code on the default branch's history. Do not use
     `design.working_build`; it is also true for an accepted build request before any code
     exists. Check it last, after the brief's demo address, so a repo with an address starts no
     extra git process. Keep `tests/test_git_process_ceiling.py`
     green.
   - `src/forge/records.py` `_signoff_design` gets a `marks: bool` argument. `decision_accept`
     passes `status == "proposed"`, so a record already accepted (the `design_checked` recheck
     path) is never held for marks. With `marks`, the screens loop adds
     `SCREENS.md: <screen> needs Build: now or Build: later` to `gaps` when the section has no
     line matching `^Build: (?:now|later)[ \t]*$`. The existing refusal lists it with the others.
   - `tests/test_proto_signoff.py` `_design_records`: add `Build: now\n` after the `Image:` line,
     so the existing sign-off tests keep passing.
   - Guide text (SIGNOFF), `src/forge/templates/skill.md` `## Prototype`: replace
     "The customer can sign off on the canvas alone." with "The canvas in Play mode is the default
     clickable prototype: the customer clicks through it, and can sign off on it alone." After
     "Copy that address into the sign-off decision." add "A canvas-only prototype needs no demo
     address." In **Canvas and app design**, after the `Fields:` sentences: "Add `Build: now` or
     `Build: later` to each screen. Put the whole product on the canvas, every screen, state and
     flow, later ones too, and mark `Build: now` only what the first stories build." In the
     after-sign-off paragraph: "Plan the first stories only from screens marked `Build: now`. A
     `Build: later` screen stays on the signed canvas as the source for a later story."
   - `src/forge/templates/brief.md`, after OPENLIST's sentence: "Build the screens marked
     `Build: now` in SCREENS.md. Build a `Build: later` screen only when the plan names it."
   - Test: `tests/test_signoff_scope.py::test_4_canvas_first_and_build_marks`. New client: commit
     a `Dockerfile` on main; `forge next` prints no `connect the repo on our deploy platform` line;
     an accepted `prototype-build` request with no app code still prints none; then
     `_client(..., working_build=True)` (app code on main) with `stage = "prototype"` added to its
     forge.toml and a `Dockerfile` prints it.
     Canvas sign-off with a SCREENS.md section that has no `Build:` line exits 1 with
     `SCREENS.md: Order list needs Build: now or Build: later`. Adopted client: the same sign-off
     refusal for its SCREENS.md written before this release; and an accepted sign-off record with
     `design_checked` set, rerun with `forge decision accept client-signoff`, reports no Build
     gap. The synced skill copies hold
     `Play mode`, `Build: now` and `Build: later`; the worker brief holds the Build sentence.
5. Sign-off waits for blocking decisions (SIGNOFF).
   - `records.decision_accept`, in the `signed` path, right after the `open_topics` refusal:
     `found = open_decisions.blocking(top)`; when there is one, refuse with:

     ```
     Sign-off waits for <n> open decisions on Build now screens:
     - <question> (<path>, line <line>)
       Why we ask: <text>
       Default: <text>
       Why this default: <text>
       If the default stands: <text>
     Next: record the client's answers with forge decision answer --from <file> --by "<name>", or the passed defaults with --defaults, then forge decision accept client-signoff --by "<by>"
     ```

     A missing field prints as `<field>: not written yet`. Pass the item text through values, as in
     item 2. The check comes before the design check and the reviews, so a blocked sign-off costs
     no model call.
   - Test: `tests/test_signoff_scope.py::test_5_signoff_waits_for_blocking_decisions`,
     parametrised `new-client` and `adopted-v1.2.2`. A decision record with one open item that
     touches `Order list` (Build now): `forge decision accept client-signoff --by Ravi` exits 1
     with the lines above and no review call. New client only: an item that touches
     `Order list` and has no `Why this default:` and no `Due:` also blocks, and its refusal block
     shows `Why this default: not written yet`. Add a second screen
     `## Order archive` with `Build: later`, an image and its fields, and change `Touches:` to
     `Order archive`: sign-off passes this check (it reaches
     `The canvas completeness check passed`). Then set `Touches:` back to `Order list`, answer it
     with `forge decision answer`, and sign-off passes the check again.

### New and existing repos

- **New repos** (init or adoption): both commands, the due-date lines in `forge next`, the demo
  address only after a working build, the Build marks and the blocking check at sign-off, the
  guide, brief and cold-read text, and the decisions README line. Tested on the new client in
  every item.
- **Existing repos** (on upgrade to this release, after `forge sync`): the same commands, checks
  and guide. Their decisions README stays as it was. Their free-form to-confirm lists do not count
  until the agent rewrites them in the form, as the guide says, in one mechanical fix. An unsigned
  prototype's next sign-off refuses screens with no Build mark and names each one. A repo that
  already has its sign-off needs no Build marks and is never blocked. An adopted repo whose stage
  is live gets no demo-address line, as today. Tested on the adopted earlier-release fixture in
  every item.

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
| OPENLIST | One ranked list of open decisions | The open-question form, `forge decision open`, `forge decision answer` with `--from` and `--defaults`, the due-date lines in `forge next`, and their guide, brief, cold-read and README text, on new and existing repos | 1, 2, 3 | `src/forge/open_decisions.py` (new), `src/forge/cli.py` (`ROUTES`), `src/forge/records.py` (`GROUP_HELP` only), `src/forge/nextstep.py` (`_report` only), `src/forge/templates/skill.md`, `src/forge/templates/brief.md`, `src/forge/templates/cold-read.md`, `src/forge/templates/skeleton/docs/decisions/README.md`, `docs/commands.md` (generated), `.claude/skills/forge/SKILL.md` and `.codex/skills/forge/SKILL.md` (rewritten by `forge sync`), `tests/test_open_decisions.py` (new) | `tests/test_open_decisions.py` (`test_1`, `test_2`, `test_3`) | | no | |
| SIGNOFF | Canvas first, Build marks and blocked sign-off | The demo address only after a working build, the Build mark check, the blocking-decision refusal at sign-off, and their guide and brief text, on new and existing repos | 4, 5 | `src/forge/records.py` (`_signoff_design`, `decision_accept`), `src/forge/nextstep.py` (`_needs_demo_address`), `src/forge/templates/skill.md`, `src/forge/templates/brief.md`, `.claude/skills/forge/SKILL.md` and `.codex/skills/forge/SKILL.md` (rewritten by `forge sync`), `tests/test_proto_signoff.py` (`_design_records`), `tests/test_signoff_scope.py` (new) | `tests/test_signoff_scope.py` (`test_4`, `test_5`); the changed `_design_records` | OPENLIST | no | |

SIGNOFF calls `open_decisions.blocking` from OPENLIST and edits the same guide, brief, records.py
and nextstep.py files, so it starts after OPENLIST merges.

New moving parts: none

## Notes

- Owner decisions (27 Oct 2026, settled; build the core only): one open-decisions list per client
  repo, from fixed markers only, in decision records, specs and cold-read or review notes marked
  as needing the client; each item has its question, a pre-picked default, a due date and Gain,
  Work and Harm scores, ranked; one command prints the list and one records answers from a file
  as one decision record and marks each question answered where it was asked; a passed due date
  applies the default, recorded as decided by default in the same flow, and forge next tells the
  agent to tell the client; the canvas in Play mode is the default clickable prototype and a
  demo address is needed only for a coded working prototype; the canvas shows the whole product
  and each screen is marked Build now or Later; sign-off is refused while a blocking open
  decision exists, and the refusal names the next step.
- Owner addition (27 Oct 2026): FDEs and clients must not feel blocked for no reason. Every item
  on the list, every sign-off refusal for a blocking decision and the answers record carry why the
  question is asked (with the screen or rule it touches), why the default was picked and what
  happens if the default stands.
- Planner choices the owner did not make: (1) the commands are `forge decision open` and
  `forge decision answer --from <file> --by "<name>"` or `--defaults`, inside the decision
  group, with no slug, so it can never write a sign-off record, so the top-level command count stays the same; (2) one form for every source, a
  `- Open question:` line with seven field lines, and the agent copies review notes into it,
  because review notes live in pull requests and item state, not in files; (3) the blocking rule
  is "its Touches line names a Build now screen", with no rule for stories, because no story
  exists before sign-off and later stories keep "Decide first"; a passed due date still blocks
  until `--defaults` records it; (4) the list reads the checkout's files, not the default branch,
  so forge next starts no new git process; (5) `forge next` today asks every new client prototype
  for a demo address because init writes a Dockerfile, so the ask now waits for a working build;
  (6) the twelve topics on the brief's Answers page stay where they are and are not on the list;
  (7) the draft's five guided steps with a check-in after each were not in the core list, so this
  story does not build them, and the title changed to match.
- Follow-ups, not built here (owner's later list): a sign-off readiness line in forge next and on
  the board (such as "Decisions 3 open (1 blocks)"); automatic asks for open decisions at the end
  of each step and at least weekly; turning canvas comments into open decisions. Also from the
  draft: the five guided steps with check-ins. From the same client issue, not built: a spec
  format that states each rule once, or a check that lists every line that repeats a changed
  rule's ID.
