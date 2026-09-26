"""forge migrate: a client that copied Forge in moves to v1 in one pull request.

The fixture (tests/fixtures/copied-client/) is shaped like myclaw. `source/` is the old Forge as it
was copied in; the test commits it as the Forge source repo that constitution/VENDORED_FROM names.
`client/` is laid over it: the client's product, its own changes to Forge files (harness.yaml, and a
skill added under factory/), old plans in myclaw's format, and old ledgers and records.

Each test is named test_<criterion>_<rule> after the spec's acceptance criterion it proves.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

import pytest

import conftest
from test_close import CLEAN, CODEX_STUB, PIN, body, run
from test_setup import LISTED

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "copied-client"
SHIP = "plans/active/SHIP-1-shoppers-can-save-a-basket.md"
DRAFT = "plans/active/DRAFT-1-shoppers-can-share-a-basket.md"
# A lower-case story key, like myclaw's cache-bug: it becomes TIDY-UP.
TIDY = "plans/active/tidy-up-the-shop-code-is-easy-to-change.md"
# Fully shipped before the move: one whole (with its outcome), one task by task (with none).
SEARCH = "plans/active/SEARCH-1-shoppers-can-search-the-shop.md"
SIGNIN = "plans/active/SIGNIN-1-shoppers-stay-signed-in.md"
# Files the old Forge source has that are the client's once copied in; migrate edits, never deletes.
SHARED = {"AGENTS.md", "CLAUDE.md"}
# The client's own files, which forge migrate never touches.
OWN = ["README.md", "src/app.js", "docs/product/BRIEF.md", "docs/decisions/0001-client-signoff.md",
       ".github/workflows/ci.yml", "plans/roadmap.json"]
# Forge files the client changed or added: set aside, not deleted.
KEPT = ["factory/skills/our-skill/SKILL.md", "harness.yaml"]
# The client's old verify commands in .envrc, outside the harness-only block, in order; a phase
# with its own && or || is grouped, so it fails as one step.
TEST = ("(npm run format:check && npm run check:architecture && npm run lint:changed) && "
        "(npm run typecheck || npm run typecheck:legacy) && npm test")
# gstack's store in the repo: the office-hours design doc moves, the rest goes.
DESIGN = "main-design-20260901-120000.md"
GSTACK = ("Keeps 1 office-hours design doc in docs/context/; deletes the rest of gstack's store "
          "(.gstack/, 2 files); git history keeps them.")


def _files(folder: Path) -> set[str]:
    return {path.relative_to(folder).as_posix() for path in folder.rglob("*") if path.is_file()}


def _land(repo, message: str) -> None:
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", message)
    repo.git("push", "-q", "origin", "main")


def _copied_client(repo, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "forge-source"
    shutil.copytree(FIXTURE / "source", source)
    for args in (("init", "-q", "-b", "main"), ("add", "-A"), ("commit", "-q", "-m", "Old Forge")):
        repo.git(*args, cwd=source)
    monkeypatch.setenv("FORGE_SOURCE_URL", str(source))
    shutil.copytree(FIXTURE / "source", repo.path, dirs_exist_ok=True)
    shutil.copytree(FIXTURE / "client", repo.path, dirs_exist_ok=True)
    repo.write("constitution/VENDORED_FROM",
               f"symphony-forge @ {repo.git('rev-parse', 'HEAD', cwd=source)}\n")
    _land(repo, "Copy Forge in")


def _snapshot(repo) -> list[str]:
    hooks = Path(repo.git("rev-parse", "--path-format=absolute", "--git-path", "hooks"))
    return [repo.git("rev-parse", "HEAD"), repo.git("status", "--porcelain", "--ignored", "-uall"),
            repo.git("for-each-ref"), repo.git("worktree", "list", "--porcelain"),
            " ".join(sorted(os.listdir(hooks)))]


def _review_and_checks(repo, gh, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A clean stub Autoreview, and only the tests check green (forge-pr-check can't run yet)."""
    skill = tmp_path / "autoreview"
    (skill / "scripts").mkdir(parents=True)
    shutil.copy(ROOT / "tests" / "stubs" / "autoreview", skill / "scripts" / "autoreview")
    (skill / ".upstream-sha").write_text(PIN + "\n", "utf-8")
    monkeypatch.setenv("AUTOREVIEW", str(skill / "scripts" / "autoreview"))
    monkeypatch.setenv("AUTOREVIEW_STUB", str(tmp_path / "reviews.json"))
    monkeypatch.setenv("FORGE_CHECKS_WAIT", "0")
    monkeypatch.delenv("CODEX_BIN", raising=False)
    conftest._install(repo.bin, "codex", CODEX_STUB.format(python=sys.executable))
    (tmp_path / "reviews.json").write_text(json.dumps([CLEAN]), "utf-8")
    gh.respond("pr", "list", stdout="[]")
    gh.respond("pr", "create", stdout="https://github.com/acme/shop/pull/7\n")
    gh.respond("api", "--paginate", "--jq", ".check_runs[]", stdout=json.dumps(run("tests")) + "\n")
    gh.respond("api", "--paginate", "--jq", ".statuses[]", stdout="")


def _moves(repo, gh, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    version = repo.forge("--version").stdout.split()[-1]
    main = repo.git("rev-parse", "main")

    # --dry-run prints the whole plan and changes nothing: no files, branches or GitHub calls.
    before = _snapshot(repo)
    dry = repo.forge("migrate", "--dry-run")
    assert dry.returncode == 0, dry.stderr
    assert _snapshot(repo) == before and gh.calls() == []
    for line in ("\n- factory/ (2 files)\n", "\n- forge\n", "\n- forge.cmd\n", "\n- harness.yaml\n",
                 "\n- constitution/ (2 files)\n", "\n- .github/workflows/pr-ticket-check.yml\n",
                 "\n- setup\n", "\n- .claude/CLAUDE.md\n", "\n- .envrc\n",
                 "Deletes 12 old Forge records under .factory/; git history keeps them.",
                 "Deletes 4 old ledger records under plans/", GSTACK,
                 "\nNeeds you in .gitignore: these gstack lines are yours, so they stay; take them "
                 "out once nothing uses them: .gstack/slug-cache/\n",
                 "Sets aside 2 files that differ from the copied-in Forge, in .forge-migrate/kept/",
                 "\n- factory/skills/our-skill/SKILL.md\n",
                 # A task with no Scope makes a malformed story doc: it isn't approved.
                 "Shoppers can save a basket (SHIP-1): not carried over, because the story doc it "
                 "becomes is malformed: Tasks row T3: Scope is empty. Its draft is "
                 ".forge-migrate/replan/SHIP-1.md; re-plan it with forge story new SHIP-1.",
                 "  | T2 | Show a saved basket |",
                 "Needs you in .forge-migrate/replan/SHIP-1.md: T3: no Scope and covers no "
                 "Done-when item.",
                 'Shoppers can share a basket (DRAFT-1): not carried over, because its plan on main '
                 'says "awaiting-approval", not "approved". Its draft is '
                 ".forge-migrate/replan/DRAFT-1.md; re-plan it with forge story new DRAFT-1.",
                 "Converts 5 active plans into story docs:",
                 "The shop code is easy to change (TIDY-UP): its approval on main carries over; "
                 "1 of 2 parts done.",
                 "Shoppers can search the shop (SEARCH-1): its approval on main carries over, and "
                 "it is finished: every part was done before the move. Outcome: Shoppers now find "
                 "any product by name from every page.",
                 "Shoppers stay signed in (SIGNIN-1): its approval on main carries over, and it is "
                 "finished: every part was done before the move. Outcome: Finished before the move "
                 "to the new Forge.",
                 "Replaces AGENTS.md, which is the old Forge's word for word, with the Forge block.",
                 "Drops CLAUDE.md's import of .claude/CLAUDE.md, the old Claude adapter.",
                 f"Moves the old verify commands from .envrc into forge.toml's test: {TEST}\n",
                 "Pins your sign-off record, docs/decisions/0001-client-signoff.md, in forge.toml's "
                 "signoff, as harness.yaml did",
                 f"forge.toml pinned to Forge {version}",
                 "forge close migrate-v1 turns on branch protection for main"):
        assert line in dry.stdout, dry.stdout

    # A run stopped part way (here the client's own pre-commit hook fails once) leaves changes in
    # its folder, so the next run refuses and wipes nothing; once a human removed the folder it
    # starts its own branch over, and one more run gives the same branch.
    hooks = Path(repo.git("rev-parse", "--path-format=absolute", "--git-path", "hooks"))
    flag = tmp_path / "stop-commits"
    flag.write_text("", "utf-8")
    (hooks / "pre-commit").write_text(f'#!/bin/sh\n[ ! -e "{flag.as_posix()}" ]\n', "utf-8")
    (hooks / "pre-commit").chmod(0o755)
    stopped = repo.forge("migrate")
    assert stopped.returncode == 1 and "git commit failed" in stopped.stderr, stopped.stderr
    worktree = tmp_path / "repo-forge-migrate-v1"
    (worktree / "left-behind.txt").write_text("from the stopped run\n", "utf-8")
    flag.unlink()
    unsaved = repo.forge("migrate")
    assert unsaved.returncode == 1 and (", the folder of forge/migrate-v1, has changes that aren't "
                                        "committed, so forge migrate won't start that branch "
                                        "again.") in unsaved.stderr
    assert str(worktree) in unsaved.stderr and "\nNext: look at them in " in unsaved.stderr
    assert (worktree / "left-behind.txt").is_file()
    repo.git("worktree", "remove", "--force", str(worktree))
    done = repo.forge("migrate")
    assert done.returncode == 0, done.stderr
    assert done.stdout.startswith(dry.stdout.split("\n\n", 1)[1].rstrip()), done.stdout
    assert "Next: forge doctor and your tests" in done.stdout
    # An ignored file in its folder is someone's too: the rerun refuses and leaves it.
    (worktree / ".env").write_text("SECRET=ours\n", "utf-8")
    ignored = repo.forge("migrate")
    assert ignored.returncode == 1 and "has changes that aren't committed" in ignored.stderr
    assert (worktree / ".env").is_file()
    (worktree / ".env").unlink()
    tree = repo.git("rev-parse", "forge/migrate-v1^{tree}")
    again = repo.forge("migrate")
    assert again.returncode == 0, again.stderr
    assert repo.git("rev-parse", "forge/migrate-v1^{tree}") == tree
    assert repo.git("rev-list", "--count", "main..forge/migrate-v1") == "1"
    assert repo.git("rev-parse", "main") == main  # the default branch never changes
    # Only the commit migrate recorded making is its own: an amended one, even under its subject,
    # is a human's and is never reset.
    made = repo.git("rev-parse", "forge/migrate-v1")
    (worktree / "ours.txt").write_text("a human's change\n", "utf-8")
    repo.git("add", "ours.txt", cwd=worktree)
    repo.git("commit", "-q", "--amend", "--no-edit", "--no-verify", cwd=worktree)
    amended = repo.git("rev-parse", "forge/migrate-v1")
    kept_amend = repo.forge("migrate")
    assert kept_amend.returncode == 1, kept_amend.stdout
    assert ("forge/migrate-v1 holds work that forge migrate didn't make, so it won't start the "
            "branch again.") in kept_amend.stderr
    assert repo.git("rev-parse", "forge/migrate-v1") == amended
    repo.git("reset", "-q", "--hard", made, cwd=worktree)
    assert ("The fix migrate-v1 moves this repo to the new Forge.\nNext: forge close migrate-v1"
            in repo.forge("next").stdout)

    # One branch: exactly the listed Forge paths and old records go, the client's own files stay.
    changed = dict(line.split("\t")[::-1] for line in repo.git(
        "diff", "--name-status", "--no-renames", "main", "forge/migrate-v1").splitlines())
    records = {path for path in _files(FIXTURE / "client")
               if path.startswith((".factory/", ".gstack/", "plans/quickfixes/", "plans/lessons",
                                   "plans/deferrals"))}
    sync_rewrites = {".codex/skills/forge/SKILL.md", ".claude/skills/forge/SKILL.md"}
    assert {path for path, status in changed.items() if status == "D"} == (
        (_files(FIXTURE / "source") - sync_rewrites - SHARED) | set(KEPT) | records
        | {"constitution/VENDORED_FROM", ".envrc", SHIP, DRAFT, TIDY, SEARCH, SIGNIN})
    added = {path for path, status in changed.items() if status != "D"}
    written = {*(f".forge-migrate/kept/{path}" for path in KEPT), ".forge-migrate/replan/SHIP-1.md",
               "plans/TIDY-UP.md", "plans/SEARCH-1.md", "plans/SIGNIN-1.md",
               ".forge-migrate/replan/DRAFT-1.md", f"docs/context/{DESIGN}", ".gitignore",
               ".gitattributes", "forge.toml", *LISTED}
    assert written <= added and all(path.startswith(".factory/") for path in added - written)
    assert not set(OWN) & set(changed)
    for path in KEPT:
        assert repo.git("show", f"forge/migrate-v1:.forge-migrate/kept/{path}") == (
            FIXTURE / "client" / path).read_text("utf-8").strip()
    assert repo.git("show", f"forge/migrate-v1:docs/context/{DESIGN}") == (
        FIXTURE / "client" / ".gstack/projects/x" / DESIGN).read_text("utf-8").strip()
    # Only the old Forge's gstack lines go; the client's own stay.
    assert repo.git("show", "forge/migrate-v1:.gitignore") == (
        "node_modules/\n.env\n.gstack/slug-cache/")
    assert repo.git("show", "forge/migrate-v1:.gitattributes") == "*.png binary"
    toml = repo.git("show", "forge/migrate-v1:forge.toml")
    assert f'version = "{version}"' in toml and f"\ntest = {json.dumps(TEST)}\n" in toml
    # The client's sign-off record, pinned in harness.yaml, is pinned in forge.toml.
    assert '\nsignoff = "docs/decisions/0001-client-signoff.md"\n' in toml
    # AGENTS.md was the old Forge's word for word, so only the Forge block is left; CLAUDE.md
    # keeps its own lines but no longer imports the deleted old Claude adapter.
    agents = repo.git("show", "forge/migrate-v1:AGENTS.md")
    assert agents.startswith("<!-- forge:begin -->") and "The old Forge contract" not in agents
    claude = repo.git("show", "forge/migrate-v1:CLAUDE.md")
    assert "@.claude/CLAUDE.md" not in claude and "@AGENTS.md\n" in claude
    assert "<!-- forge:begin -->" in claude

    # A converted plan keeps its sections word for word and the old tasks as rows.
    doc = repo.git("show", "forge/migrate-v1:.forge-migrate/replan/SHIP-1.md")
    assert doc.startswith("# Shoppers can save a basket\n\n## What changes for you\n\n"
                          "- A shopper can save a basket and see it again after signing in.")
    assert "## Done when\n\n1. AC1: a shopper can save a basket with one click.\n2. AC2:" in doc
    assert ("| T1 | Save a basket | Shoppers can save their basket with one click. | 1 | "
            "`src/basket.js` | `test/basket.test.js` | none | yes |") in doc
    assert "| T2 | Show a saved basket |" in doc and "| 2 | `src/signin.js`, `src/basket-view.js` |" in doc
    assert "## Notes" in doc and "### Technical Approach\n\nKeep the basket in the session table." in doc
    assert "# Shoppers can share a basket" in repo.git(
        "show", "forge/migrate-v1:.forge-migrate/replan/DRAFT-1.md")

    # It closes like any fix: its pull request lists what was set aside and why; it waits only for
    # the tests check, since forge-pr-check runs from a default branch that has no Forge yet.
    _review_and_checks(repo, gh, tmp_path, monkeypatch)
    closed = repo.forge("close", "migrate-v1")
    assert closed.returncode == 0, closed.stdout + closed.stderr
    [create] = [call for call in gh.calls() if call[:2] == ["pr", "create"]]
    text = body(create)
    assert text.startswith("Forge v1 runs this repo:") and "\n- harness.yaml\n" in text
    assert "Needs you in .forge-migrate/replan/SHIP-1.md: T3: no Scope" in text
    assert "\n- .envrc\n" in text and f"from .envrc into forge.toml's test: {TEST}\n" in text
    assert GSTACK in text

    # Work migrate didn't make (close's committed review) is never reset.
    head = repo.git("rev-parse", "forge/migrate-v1")
    refused = repo.forge("migrate")
    assert refused.returncode == 1 and "holds work that forge migrate didn't make" in refused.stderr
    assert "\nNext: " in refused.stderr and repo.git("rev-parse", "forge/migrate-v1") == head

    # Once a human merged it, close turns branch protection on and says so. It never weakens the
    # client's rule: a protection it can't read stops it before it writes anything...
    gh.respond("pr", "list", stdout=json.dumps([{"number": 7, "state": "MERGED", "body": ""}]))
    gh.respond("api", "--method", "PUT", stdout="{}")
    endpoint = "repos/{owner}/{repo}/branches/main/protection"
    gh.respond("api", endpoint, stdout='{"message":"Must have admin rights"}', exit=1)
    unread = repo.forge("close", "migrate-v1")
    assert unread.returncode == 1 and unread.stderr == (
        "Branch protection on main was not set: gh exited with code 1.\n"
        f"Next: gh api '{endpoint}'\n"), unread.stderr
    assert not [call for call in gh.calls() if call[:3] == ["api", "--method", "PUT"]]
    # ... and the rule it reads keeps everything it had, with Forge's pull request, checks and
    # admins added.
    gh.respond("api", endpoint, stdout=json.dumps({
        "required_status_checks": {"strict": True, "contexts": ["lint", "tests"],
                                   "checks": [{"context": "lint", "app_id": 15368},
                                              {"context": "tests", "app_id": None}]},
        "enforce_admins": {"enabled": False},
        "required_pull_request_reviews": {
            "required_approving_review_count": 2, "dismiss_stale_reviews": True,
            "require_code_owner_reviews": True, "require_last_push_approval": False,
            "dismissal_restrictions": {"users": [{"login": "lead"}], "teams": [], "apps": []}},
        "restrictions": {"users": [{"login": "release-bot"}], "teams": [{"slug": "core"}],
                         "apps": []},
        "required_linear_history": {"enabled": True}, "allow_force_pushes": {"enabled": False},
        "required_conversation_resolution": {"enabled": True}}))
    merged = repo.forge("close", "migrate-v1")
    assert merged.returncode == 0, merged.stderr
    assert "Branch protection is on for main" in merged.stdout
    assert "Its other rules stay as they were." in merged.stdout
    [put] = [call for call in gh.calls() if call[:3] == ["api", "--method", "PUT"]]
    assert put[3] == endpoint
    assert json.loads(Path(put[put.index("--input") + 1]).read_text("utf-8")) == {
        "required_status_checks": {"strict": True, "checks": [
            {"context": "lint", "app_id": 15368}, {"context": "tests"},
            {"context": "forge-pr-check"}]},
        "enforce_admins": True,
        "required_pull_request_reviews": {
            "required_approving_review_count": 2, "dismiss_stale_reviews": True,
            "require_code_owner_reviews": True, "require_last_push_approval": False,
            "dismissal_restrictions": {"users": ["lead"], "teams": [], "apps": []}},
        "restrictions": {"users": ["release-bot"], "teams": ["core"], "apps": []},
        "required_linear_history": True, "allow_force_pushes": False,
        "required_conversation_resolution": True}

    # On the default branch the carried-over approval and the merged task hold for v1's commands.
    repo.git("merge", "-q", "--no-ff", "-m", "Move to Forge v1 (#7)", "forge/migrate-v1")
    repo.git("push", "-q", "--no-verify", "origin", "main")
    started = repo.forge("task", "start", "TIDY-UP/T2")
    assert started.returncode == 0, started.stderr
    finished = repo.forge("task", "start", "TIDY-UP/T1")
    assert finished.returncode == 1 and "is already started" in finished.stderr
    # Stories shipped before the move are finished: forge next asks no bookkeeping about them, and
    # no story doc it reads is malformed.
    after = repo.forge("next").stdout
    assert "story done" not in after and "search the shop" not in after and "malformed" not in after
    assert "stay signed in" not in after


# Forge's own repo: its plans have no frontmatter; the old plan metadata names and approves them.
NEXT_PLAN = """# Forge v1: a lean rebuild

## What and why

Forge is heavier than the work it manages.

## What changes for you

- Forge becomes one small tool.

## Done when

1. A fix is merged the new way.
2. The old Forge is deleted.

## Risks

- The old Forge runs this repo until the switch.

## Technical approach

Code goes in `src/forge/`.

## Task decomposition

| Label / exact task ID | What it delivers | Covers | Scope | Tests | Depends on | user_facing |
|---|---|---|---|---|---|---|
| Core / CORE | The package | 1 | `src/forge/cli.py` | `tests/test_rules.py` | none | false |
| Switch / SWITCH | The old tree deleted | 2 | `factory/` | the full suite | CORE | false |

New moving parts:
- the v1 package (Done when 1);
- git hooks (1).
"""
# Already a story doc: it carries over word for word.
WARM_DOC = """# Codex builds your tasks

## What changes for you

Codex builds each task.

## Why

Every hand-off started cold.

## Done when

1. `forge work` builds a task with Codex.

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing |
|---|---|---|---|---|---|---|---|
| SDK | Codex SDK set up | The pinned SDK | 1 | `src/forge/codex.py` | `tests/test_sdk.py` | — | no |
| BUILD | Codex builds a task | Codex builds it | 1 | `src/forge/worker.py` | `tests/test_work.py` | SDK | no |

New moving parts: the pinned Codex SDK (1).

## Risks

Risks: none
"""
FDE_PLAN = """# The agent works as a forward deployed engineer

## What and why

Customers often don't know what to build.

## What changes for you

- The agent interviews you one question at a time.

## Done when

- A vague ask turns into discovery, one question at a time.

## Risks

- Cost figures end up in client repos.

## Task decomposition

| Label / exact task ID | What it delivers | Depends on | user_facing |
|---|---|---|---|
| Skill / FDE | The FDE skill section | none | false |
"""
SOURCE_TEST = "uv run --python 3.11 --with pytest --with pytest-xdist python -m pytest tests -q -n auto"


def _forge_source(repo, gh, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    version = repo.forge("--version").stdout.split()[-1]
    repo.write("src/forge/cli.py", "print('forge')\n")  # it holds Forge's own source
    for key, name, text in (("FORGE-NEXT-1", "lean-rebuild", NEXT_PLAN),
                            ("FORGE-WARM-1", "warm-threads", WARM_DOC),
                            ("FORGE-FDE-1", "fde", FDE_PLAN)):
        rel = f"plans/active/{key}-{name}.md"
        repo.write(rel, text)
        repo.write(f".factory/stories/{key}/plan-meta.json", json.dumps(
            {"story": key, "status": "approved", "saved": "2026-09-24T09:00:00+00:00",
             "plan_file": rel}))
        repo.write(f".factory/stories/{key}/plan-approval.json",
                   json.dumps({"approved_at": "2026-09-26T01:29:20+00:00"}))
    _land(repo, "Forge's own repo")
    # Its tasks were closed by pull request: without gh, Forge can't tell which are done.
    gh.respond("pr", "list", "--state", "merged", exit=1)
    blind = repo.forge("migrate", "--dry-run")
    assert blind.returncode == 1 and blind.stderr == (
        "Forge can't list the merged pull requests (gh exited with code 1), so it can't tell which "
        "tasks are done.\nNext: gh auth status, then forge migrate --dry-run\n")
    # A task is done when a pull request from exactly feat/<KEY>-<TASK> merged; near misses aren't.
    gh.respond("pr", "list", "--state", "merged", stdout=json.dumps([
        {"headRefName": "feat/FORGE-NEXT-1-CORE", "mergedAt": "2026-09-25T10:00:00Z"},
        {"headRefName": "feat/FORGE-WARM-1-SDK", "mergedAt": "2026-09-26T08:00:00Z"},
        {"headRefName": "feat/FORGE-NEXT-1-SWITCH-docs", "mergedAt": "2026-09-26T09:00:00Z"},
        {"headRefName": "FORGE-NEXT-1-SWITCH", "mergedAt": "2026-09-26T09:00:00Z"},
        {"headRefName": "feat/FORGE-WARM-1-BUILD", "mergedAt": None}]))

    hooks = Path(repo.git("rev-parse", "--path-format=absolute", "--git-path", "hooks"))
    before = sorted(os.listdir(hooks)) if hooks.is_dir() else []
    done = repo.forge("migrate")
    assert done.returncode == 0, done.stderr
    # Every worktree shares the hooks folder, and the old Forge's branches may still be in
    # flight, so no git hook goes in.
    assert (sorted(os.listdir(hooks)) if hooks.is_dir() else []) == before
    assert "No git hooks were installed" in done.stdout
    # Nothing is deleted: the old tree, its records and every old plan stay as they are, and only
    # the adapters change.
    assert "so nothing is deleted" in done.stdout
    changed = dict(line.split("\t")[::-1] for line in repo.git(
        "diff", "--name-status", "--no-renames", "main", "forge/migrate-v1").splitlines())
    assert {path for path, status in changed.items() if status != "A"} <= LISTED, changed
    # Only the three plans the switch carries are converted; the others wait for the switch.
    for line in ("Converts 3 active plans into story docs:",
                 "- Forge v1: a lean rebuild (FORGE-NEXT-1): its approval on main carries over; "
                 "1 of 2 parts done.",
                 "- Codex builds your tasks (FORGE-WARM-1): its approval on main carries over; "
                 "1 of 2 parts done.",
                 "- The agent works as a forward deployed engineer (FORGE-FDE-1): not carried over, "
                 "because the new Forge re-plans it with one fresh approval. Its draft is "
                 ".forge-migrate/replan/FORGE-FDE-1.md; re-plan it with forge story new FORGE-FDE-1.",
                 "Leaves 5 other active plans as they are, superseded at the switch:",
                 f"\n- {SHIP}\n", f"\n- {TIDY}\n",
                 "Replaces AGENTS.md and CLAUDE.md wholly with the Forge block."):
        assert line in done.stdout, done.stdout
    listing = repo.git("ls-tree", "-r", "--name-only", "forge/migrate-v1").splitlines()
    assert {"plans/FORGE-NEXT-1.md", "plans/FORGE-WARM-1.md", ".forge-migrate/replan/FORGE-FDE-1.md",
            *LISTED} <= set(listing)
    assert "plans/SHIP-1.md" not in listing
    assert repo.git("show", "forge/migrate-v1:plans/FORGE-WARM-1.md") == WARM_DOC.strip()
    assert ("\nNew moving parts: the v1 package (Done when 1); git hooks (1).\n"
            in repo.git("show", "forge/migrate-v1:plans/FORGE-NEXT-1.md"))
    # AGENTS.md and CLAUDE.md hold only the Forge block now.
    for name in ("AGENTS.md", "CLAUDE.md"):
        text = repo.git("show", f"forge/migrate-v1:{name}")
        assert text.startswith("<!-- forge:begin -->") and text.endswith("<!-- forge:end -->"), text
    toml = repo.git("show", "forge/migrate-v1:forge.toml")
    for setting in (f'version = "{version}"', 'repo = "forge-source"',
                    f"test = {json.dumps(SOURCE_TEST)}", 'checks = ["tests", "forge-pr-check"]',
                    '"**/routes/**"', "\n[models.build]\n", "\n[models.grill.claude]\n",
                    "\n[models.review]\n"):  # forge init's defaults
        assert setting in toml, toml

    assert "2026-09-25T10:00:00Z" in repo.git(
        "show", "forge/migrate-v1:.factory/stories/FORGE-NEXT-1/tasks/CORE.json")

    # Merged, the carried-over approvals hold: the open tasks of both stories start, after the
    # tasks merged by pull request; those are done, and the draft's tasks don't start.
    repo.git("merge", "-q", "--no-ff", "-m", "Move to Forge v1 (#8)", "forge/migrate-v1")
    repo.git("push", "-q", "--no-verify", "origin", "main")
    for item in ("FORGE-NEXT-1/SWITCH", "FORGE-WARM-1/BUILD"):
        started = repo.forge("task", "start", item)
        assert started.returncode == 0, started.stderr
    for item in ("FORGE-NEXT-1/CORE", "FORGE-WARM-1/SDK"):
        assert "is already started" in repo.forge("task", "start", item).stderr
    refused = repo.forge("task", "start", "FORGE-FDE-1/FDE")
    assert refused.stderr.startswith("Story FORGE-FDE-1 has no story doc on main"), refused.stderr


def _changed_agents(repo, gh, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo.write("AGENTS.md", "# Shop agents\n\nOur own rules, and the old Forge contract.\n")
    # A line of the client's own in .envrc, a comment or an export: it is set aside, and still
    # seeds test.
    for line in ("# Our npm commands, not the harness gate tests.\n",
                 'export DATABASE_URL="postgres://localhost/shop"\n'):
        repo.write(".envrc", (FIXTURE / "client" / ".envrc").read_text("utf-8") + line)
        _land(repo, "Our own AGENTS.md and .envrc line")
        dry = repo.forge("migrate", "--dry-run")
        assert dry.returncode == 0, dry.stderr
        kept = dry.stdout.split("Sets aside 3 files that differ from the copied-in Forge", 1)[1]
        assert kept.split("\nConverts ", 1)[0].endswith(
            "\n- .envrc\n- factory/skills/our-skill/SKILL.md\n- harness.yaml\n.envrc has lines of "
            "your own besides the old Forge's, so it is set aside, not deleted."), dry.stdout
        assert f"forge.toml's test: {TEST}\n" in dry.stdout
    assert ("Needs you in AGENTS.md: it differs from the old Forge's, so its text stays above the "
            "Forge block; take the old Forge instructions out of it.") in dry.stdout
    assert "Replaces AGENTS.md" not in dry.stdout
    # A phase with a comment could hide the phases after it, so test isn't seeded; .envrc, only
    # the old Forge's lines, still goes.
    repo.write(".envrc", (FIXTURE / "client" / ".envrc").read_text("utf-8")
               + 'export FACTORY_STRUCTURAL_CMD="npm run lint # structural checks"\n')
    _land(repo, "A verify phase with a comment")
    dry = repo.forge("migrate", "--dry-run")
    assert dry.returncode == 0, dry.stderr
    assert ("Couldn't carry your old verify commands into forge.toml's test automatically: "
            '"npm run lint # structural checks", "npm run typecheck || npm run typecheck:legacy", '
            '"npm test". Ask your agent to set test.') in dry.stdout
    assert "forge.toml's test:" not in dry.stdout and "\n- .envrc\n" in dry.stdout


def _refusal(problem: str, next_step: str, setup):
    def case(repo, gh, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        setup(repo, tmp_path)
        main = repo.git("rev-parse", "main")
        for args in (("migrate", "--dry-run"), ("migrate",)):
            done = repo.forge(*args)
            assert done.returncode == 1, done.stdout
            assert problem in done.stderr and f"\nNext: {next_step}" in done.stderr, done.stderr
        assert repo.git("branch", "--list", "forge/migrate-v1") == ""
        assert repo.git("rev-parse", "main") == main
    return case


def _in_flight(repo, tmp_path: Path) -> None:
    repo.write(".factory/stages.json", json.dumps({"stages": [{"id": "SHIP-1-T2", "status": "active"}]}))
    _land(repo, "A stage is active")


def _linked_folder(repo, tmp_path: Path) -> None:
    os.symlink("docs", repo.path / ".forge-migrate")  # a folder inside the repo
    _land(repo, "A linked .forge-migrate")


def _linked_adapter(repo, tmp_path: Path) -> None:
    (repo.path / ".claude/settings.json").unlink()
    os.symlink(tmp_path / "elsewhere.json", repo.path / ".claude/settings.json")
    _land(repo, "An adapter file linked out of the repo")


def _agents_era(repo, tmp_path: Path) -> None:
    repo.git("rm", "-r", "-q", "factory")
    repo.write(".agents/README.md", "# The older layout\n")
    _land(repo, "The .agents/ layout")


def _behind(repo, tmp_path: Path) -> None:
    repo.write("src/app.js", "console.log('newer');\n")
    _land(repo, "A newer commit")
    repo.git("reset", "-q", "--hard", "HEAD~1")


def _same_design(repo, tmp_path: Path) -> None:
    repo.write(f".gstack/projects/y/{DESIGN.capitalize()}", "# Another project's office hours\n")
    _land(repo, "Another project's design doc, its name differing only in capitals")


def _kept_taken(repo, tmp_path: Path) -> None:
    repo.write(".forge-migrate/kept/harness.yaml/notes.md", "a folder where a file goes\n")
    _land(repo, "A folder at a set-aside path")


def _draft_taken(repo, tmp_path: Path) -> None:
    repo.write(".forge-migrate/replan/SHIP-1.md", "# An older draft\n")
    _land(repo, "An older draft")


def _pin(repo, pin: str) -> None:
    repo.write("harness.yaml", f'project: shop\nsignoff_record: "{pin}"\n')
    _land(repo, "Pin another sign-off record")


def _legacy_signoff(repo, gh, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A name the old Forge accepted, with no hyphen before client-signoff, carries over."""
    pin = "docs/decisions/0001-acmeclient-signoff.md"
    _pin(repo, pin)
    dry = repo.forge("migrate", "--dry-run")
    assert dry.returncode == 0, dry.stderr
    assert f"Pins your sign-off record, {pin}, in forge.toml's signoff" in dry.stdout, dry.stdout


def _no_source(repo, tmp_path: Path) -> None:
    repo.write("constitution/VENDORED_FROM", "symphony-forge @ an unknown commit\n")
    _land(repo, "Lost the vendored commit")


CASES = {
    "moves in one branch": _moves,
    "forge's own repo": _forge_source,
    "a changed AGENTS.md": _changed_agents,
    "uncommitted changes": _refusal(
        "The working tree has changes that aren't committed: src/app.js.",
        "commit or drop them, then forge migrate --dry-run",
        lambda repo, tmp_path: repo.write("src/app.js", "console.log('changed');\n")),
    "a checkout behind origin": _refusal(
        "This checkout isn't at origin/main, which forge migrate moves, so it can't check that "
        "tree here.",
        "git switch main && git pull, then forge migrate", _behind),
    "a folder already at a set-aside path": _refusal(
        ".forge-migrate/kept/harness.yaml is already there, so forge migrate won't write over it.",
        "move .forge-migrate/ aside, then forge migrate", _kept_taken),
    "a draft already there": _refusal(
        ".forge-migrate/replan/SHIP-1.md is already there",
        "move .forge-migrate/replan/SHIP-1.md aside, then forge migrate", _draft_taken),
    "two design docs whose names differ only in capitals": _refusal(
        f"docs/context/{DESIGN.capitalize()} (from .gstack/projects/x/{DESIGN}) is already there",
        f"move .gstack/projects/y/{DESIGN.capitalize()} aside, then forge migrate", _same_design),
    "work in flight": _refusal(
        "Work is still in flight in the copied-in Forge: the stage SHIP-1-T2 in ",
        "finish or drop each one with the copied-in ./forge", _in_flight),
    # Never through a link, even to a folder inside the repo: the run works in another folder.
    "a linked .forge-migrate": _refusal(
        ".forge-migrate is a link, and forge migrate never follows one.",
        "remove that link, then forge migrate --dry-run", _linked_folder),
    # sync writes the adapters only after the move began, so they are checked before any change.
    "an adapter file linked out of the repo": _refusal(
        ".claude/settings.json is a link, and forge migrate never follows one.",
        "remove that link, then forge migrate --dry-run", _linked_adapter),
    "an .agents/-era layout": _refusal(
        "origin/main has no copied-in factory/ layout to move; a client from before it (the "
        '.agents/ layout) moves with the "move vendored clients" story.', "forge next", _agents_era),
    "a legacy sign-off name": _legacy_signoff,
    # Dropping the pin would let any accepted sign-off record approve a story.
    "a sign-off pin forge.toml can't hold": _refusal(
        "harness.yaml pins docs/signoff.md as the client's sign-off record, which forge.toml "
        "can't pin: it isn't a docs/decisions/NNNN-client-signoff.md record.",
        "pin the accepted client-signoff record in harness.yaml's signoff_record, "
        "then forge migrate --dry-run", lambda repo, tmp_path: _pin(repo, "docs/signoff.md")),
    "no copied-in commit": _refusal(
        "Forge can't read the copied-in version (constitution/VENDORED_FROM names no copied-in "
        "commit), so it can't tell your changes from its own.",
        "check the network and constitution/VENDORED_FROM", _no_source),
}


@pytest.mark.parametrize("case", [
    pytest.param(name, marks=pytest.mark.skipif(
        name in ("a linked .forge-migrate", "an adapter file linked out of the repo")
        and os.name == "nt",
        reason="making a symlink needs extra rights on Windows")) for name in CASES])
def test_30_migrate(repo, gh, tmp_path, monkeypatch, case):
    monkeypatch.setenv("FORGE_NOW", "2026-09-25T12:00:00+00:00")
    _copied_client(repo, tmp_path, monkeypatch)
    CASES[case](repo, gh, tmp_path, monkeypatch)
