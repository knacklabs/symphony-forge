---
status: accepted
confirmed_by: "Ravi Kiran Vemula"
date: 2026-09-25
stories: []
supersedes: 0088-simple-upgrade
---

# Forge is rebuilt lean in the same repo, then switched over

## Context

Forge has grown to about 47,000 lines of scripts and a similar amount of tests. Most of that is
bookkeeping that checks other bookkeeping: proof receipts, review generations, grill byte bindings,
Lite manifests, a session write lock with a shell parser, per-role model routing and vendored copies
of all of it in every client. On 2026-09-25 four finished tasks could not close because of Forge's
own machinery, and 11 of the last 25 merged pull requests fixed Forge rather than the product. The
in-place cut (decision 0092 and its story) would remove about 15,000 lines but keeps the shape
that produced them.

On 2026-09-25 the owner went through the options one question at a time and chose to rebuild Forge
from scratch in this repo, run it beside the old one, switch over, then delete the old tree. The
rule for closing a task that 0092 set (green CI plus a clean review) carries into the new Forge
unchanged. The owner's own words set two limits: "Only PR is very late" (rules must bite before
the pull request, not only there) and "think about old clients too" (clients that copied Forge in
must have a way to move over).

## Decision

Build a lean Forge v1 and switch to it. Seventeen owner decisions define it:

1. **Both coordinators stay equal.** Claude Code and Codex can each drive the whole flow and get
   the same result.
2. **Where rules are enforced.** Forge commands enforce the order of steps. The repo's git hooks
   enforce the rules for commits and pushes. The pull request's checks are the backstop. Host hooks
   do only three things: block destructive commands, capture the human's approval, and load
   context.
3. **One story doc.** Each story has one document (what changes, why, done when, tasks). It gets
   one cold read and one human approval. There are no task plans and no task grills.
4. **One way to ship.** Every change, big or small, is a pull request that closes by the same rule.
   A fix needs only a pull request and a one-line reason. A fix that touches more than 5 code files,
   or changes an interface or a decision, is promoted to a story.
5. **`.factory/` holds current state only.** History lives in git, and reviews and test results
   live in the pull request.
6. **The board is for non-technical readers.** It tells the whole history and the current state of
   each story in plain English. The timeline is built from each merged pull request's plain-English
   title and summary plus the dates in the current state, so Forge keeps no history of its own.
7. **Forge is a pinned tool, not a copy.** Clients pin a Forge version and get generated adapter
   files; `forge sync` regenerates them, and upgrading means bumping the pin.
8. **Workers are a setting:** `claude` or `codex`. Claude workers ship first; Codex workers follow
   through the Codex SDK. The Codex plugin path is removed.
9. **Behaviour tests, one per rule.** The whole suite runs in CI in under five minutes.
10. **Build fresh in this repo, switch, then delete the old tree.**
11. **In-flight stories.** The full-access story and the simple-upgrade story are superseded. Code
    already built for the FDE story and the SDK setup task is carried into the new Forge. The FDE,
    warm-threads and sign-off stories continue after the switch, and a new story moves the remaining
    vendored clients.
12. **Version 1 is the core flow on both hosts,** and nothing else.
13. **How the rebuild ships.** Rebuild pull requests are Forge development pull requests with a
    `Ticket:` line, which today's checks already accept. Each still needs the approved plan, the
    Autoreview loop until clean and green CI. Claude Opus subagents write the code in Forge's
    degraded window, so each pull request touches at most five code files, and the coordinator
    drives. The owner first asked for a temporary label-based lane; it turned out not to be
    needed.
14. **Switch checks.** Before the switch, one real story (the FDE story) runs end to end on the new
    Forge, and a fresh client closes a fix on it.
15. **Old clients.** Clients that copied Forge in (the myclaw family, copied on 12 September, with
    about five active plans) are frozen until the switch. After it, each moves over in one
    `forge migrate` pull request. Migrating myclaw is itself a switch check.
16. **Docs.** One standards page of about 300 lines replaces the constitution. Only the guide, the
    specs and the decisions stay live. Only three workflows remain: test CI, ticket and roadmap.
    Lessons and deferrals are dropped.
17. **Releases** are git tags on the public repo, installed with `uv` from the tag.

The owner also adopted 13 first principles for the rebuild. The spec for the new Forge lists them,
and the standards page opens with them.

## Consequences

- Once the switch lands, the old `factory/` tree, the `forge` launcher script, `harness.yaml`,
  `constitution/`, the old prompts, schemas and workflows, and every doc other than the guide, the
  specs, the decisions and the standards page are deleted. They stay in git history under a final
  tag.
- Until the new Forge is adopted here, the old Forge keeps running this repo. Nothing else starts
  until the switch.
- Clients stay on their copied Forge until their migrate pull request. Clients from before the
  `factory/` layout move in the later "move vendored clients" story.
- The close rule of decision 0092 is the v1 close rule. Its parts about the old tree (lens files,
  Lite windows, module splits) stop mattering once that tree is deleted.
- **Superseded in whole:**
  - The old pipeline: 0001 (schema-validated recorders), 0005 (findings escalation), 0006
    (lessons ledger), 0007 (stage commit loop) and 0008 (loop audit).
  - Copying Forge into clients: 0009 (frozen vendored gates), 0016 (the `factory/` folder) and
    0034 (vendored docs).
  - The old planning and delegation rules: 0013 (the always-on planning lock), 0015 (the plan
    contradiction gate), 0018 (delegation gates), 0023 (stage delta), 0025 (evidence lifetime),
    0031 (Lite mode), 0032 (task plans made just in time), 0033 (work-record declaration), 0035
    (the commit belt) and 0036 (client gates arming on the roadmap).
  - Launch, bootstrap and proof machinery: 0042 (the process model), 0044 (the accountable
    engineering loop), 0048 (grill provenance), 0057 (coordinator operation), 0058 and 0063
    (native bootstrap), 0060 (signal masks), 0064 (lean delivery and durable history), 0065 and
    0072 (platform proof) and 0066 (closeout binding).
  - Model routing: 0083 and 0084 (role routing) and 0085 (executor modes), replaced by the workers
    setting.
  - 0088 (simple upgrade), replaced by bumping the pin and `forge migrate`.
  - 0011 (the coordinator runs Autoreview): `forge close` runs it.
  - 0067, 0069, 0073, 0077, 0078 and 0079 were already superseded by 0092.
- **Superseded in part:**
  - 0053 (either coordinator on the shared contract): equal coordinators stay; the contract they
    share is now this one.
  - 0012 (project memory): project facts go in specs, decisions or the guide, not a separate memory
    folder.
  - 0017 (the repo as system of record): still true, but history is git and the pull request, not
    Forge record files.
  - 0022 and 0045 (conflict-free ledgers and story state): kept only as "each task writes its own
    state file".
  - 0029 and 0050 (plan approval and plan authoring): approval stays native to each host; the old
    digests and eligibility rules go.
  - 0054 (native questions and task proof): the questions part stays, the task proof goes.
  - 0059 (task workspaces): one worktree per task and starting dependency-ready tasks stay; the
    rest goes.
  - 0076 (review reads the tree it judges): the review still runs read-only in the task's
    worktree; the lens wording goes.
  - 0081 and 0087 (full access): no write lock stays; the close checks are 0092's.
  - 0086 (the SDK route): it becomes the future Codex worker; hybrid mode goes.
- **Still in force:**
  - The same close and review rules: 0047 (a worktree and pull request per task), 0052 (from
    approval to pull request the run is the agent's), 0075 (host triage of findings) and 0092
    (the close rule).
  - Safety and platform rules: 0028 (path boundary), 0030 (Forge is a product in its own repo),
    0038 (hooks fail loudly), 0040 (Windows user scope), 0061 (host-native questions), 0068
    (workers may use the network) and 0082 (Codex hook trust boundary).
  - The FDE and approval rules: 0089 (FDE discovery) and 0090 (one approval per story).
  - Client sign-off, 0010 and 0014: still binding. In client repos, v1 refuses story approval
    until the client sign-off is recorded; the Forge repo itself is exempt, as today. The sign-off
    story adds the fuller checks after the switch.
- Any other decision that depends on machinery this rebuild removes (stages, recorders, schemas,
  the write lock, vendoring, lessons, deferrals, audits) is superseded to that extent.
- The `supersedes:` field holds one slug (0088, simple upgrade, replaced outright by the pinned tool and `forge migrate`). The full list above is the record.
