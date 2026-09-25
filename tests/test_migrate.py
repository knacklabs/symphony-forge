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
                 "\n- setup\n", "\n- .claude/CLAUDE.md\n",
                 "Deletes 12 old Forge records under .factory/; git history keeps them.",
                 "Deletes 4 old ledger records under plans/",
                 "Sets aside 2 files that differ from the copied-in Forge, in .forge-migrate/kept/",
                 "\n- factory/skills/our-skill/SKILL.md\n",
                 "Shoppers can save a basket (SHIP-1): its approval on main carries over; 1 of 3 "
                 "parts done.", "  | T2 | Show a saved basket |",
                 "Needs you in plans/SHIP-1.md: T3: no Scope and covers no Done-when item.",
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
                 f"forge.toml pinned to Forge {version}",
                 "forge close migrate-v1 turns on branch protection for main"):
        assert line in dry.stdout, dry.stdout

    # A run stopped part way (here the client's own pre-commit hook fails once) is run again: it
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
    done = repo.forge("migrate")
    assert done.returncode == 0, done.stderr
    assert done.stdout.startswith(dry.stdout.split("\n\n", 1)[1].rstrip()), done.stdout
    assert "Next: forge doctor and your tests" in done.stdout
    tree = repo.git("rev-parse", "forge/migrate-v1^{tree}")
    again = repo.forge("migrate")
    assert again.returncode == 0, again.stderr
    assert repo.git("rev-parse", "forge/migrate-v1^{tree}") == tree
    assert repo.git("rev-list", "--count", "main..forge/migrate-v1") == "1"
    assert repo.git("rev-parse", "main") == main  # the default branch never changes
    assert ("The fix migrate-v1 moves this repo to the new Forge.\nNext: forge close migrate-v1"
            in repo.forge("next").stdout)

    # One branch: exactly the listed Forge paths and old records go, the client's own files stay.
    changed = dict(line.split("\t")[::-1] for line in repo.git(
        "diff", "--name-status", "--no-renames", "main", "forge/migrate-v1").splitlines())
    records = {path for path in _files(FIXTURE / "client")
               if path.startswith((".factory/", "plans/quickfixes/", "plans/lessons", "plans/deferrals"))}
    sync_rewrites = {".codex/skills/forge/SKILL.md", ".claude/skills/forge/SKILL.md"}
    assert {path for path, status in changed.items() if status == "D"} == (
        (_files(FIXTURE / "source") - sync_rewrites - SHARED) | set(KEPT) | records
        | {"constitution/VENDORED_FROM", SHIP, DRAFT, TIDY, SEARCH, SIGNIN})
    added = {path for path, status in changed.items() if status != "D"}
    written = {*(f".forge-migrate/kept/{path}" for path in KEPT), "plans/SHIP-1.md", "plans/TIDY-UP.md",
               "plans/SEARCH-1.md", "plans/SIGNIN-1.md", ".forge-migrate/replan/DRAFT-1.md",
               "forge.toml", *LISTED}
    assert written <= added and all(path.startswith(".factory/") for path in added - written)
    assert not set(OWN) & set(changed)
    for path in KEPT:
        assert repo.git("show", f"forge/migrate-v1:.forge-migrate/kept/{path}") == (
            FIXTURE / "client" / path).read_text("utf-8").strip()
    assert f'version = "{version}"' in repo.git("show", "forge/migrate-v1:forge.toml")
    # AGENTS.md was the old Forge's word for word, so only the Forge block is left; CLAUDE.md
    # keeps its own lines but no longer imports the deleted old Claude adapter.
    agents = repo.git("show", "forge/migrate-v1:AGENTS.md")
    assert agents.startswith("<!-- forge:begin -->") and "The old Forge contract" not in agents
    claude = repo.git("show", "forge/migrate-v1:CLAUDE.md")
    assert "@.claude/CLAUDE.md" not in claude and "@AGENTS.md\n" in claude
    assert "<!-- forge:begin -->" in claude

    # The approved plan is a story doc: its sections word for word, the old tasks as rows.
    doc = repo.git("show", "forge/migrate-v1:plans/SHIP-1.md")
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

    # Work migrate didn't make (close's committed review) is never reset.
    head = repo.git("rev-parse", "forge/migrate-v1")
    refused = repo.forge("migrate")
    assert refused.returncode == 1 and "holds work that forge migrate didn't make" in refused.stderr
    assert "\nNext: " in refused.stderr and repo.git("rev-parse", "forge/migrate-v1") == head

    # Once a human merged it, close turns branch protection on and says so.
    gh.respond("pr", "list", stdout=json.dumps([{"number": 7, "state": "MERGED", "body": ""}]))
    gh.respond("api", "--method", "PUT", stdout="{}")
    merged = repo.forge("close", "migrate-v1")
    assert merged.returncode == 0, merged.stderr
    assert "Branch protection is on for main" in merged.stdout
    [put] = [call for call in gh.calls() if call[:3] == ["api", "--method", "PUT"]]
    assert put[3] == "repos/{owner}/{repo}/branches/main/protection"

    # On the default branch the carried-over approval and the merged task hold for v1's commands.
    repo.git("merge", "-q", "--no-ff", "-m", "Move to Forge v1 (#7)", "forge/migrate-v1")
    repo.git("push", "-q", "--no-verify", "origin", "main")
    for item in ("SHIP-1/T2", "TIDY-UP/T2"):
        started = repo.forge("task", "start", item)
        assert started.returncode == 0, started.stderr
    finished = repo.forge("task", "start", "SHIP-1/T1")
    assert finished.returncode == 1 and "is already started" in finished.stderr
    # Stories shipped before the move are finished: forge next asks no bookkeeping about them.
    after = repo.forge("next").stdout
    assert "story done" not in after and "search the shop" not in after
    assert "stay signed in" not in after


def _forge_source(repo, gh, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    version = repo.forge("--version").stdout.split()[-1]
    repo.write("forge.toml", f'version = "{version}"\nrepo = "forge-source"\n'
                             'checks = ["tests", "forge-pr-check"]\n')
    _land(repo, "Forge's own repo")
    done = repo.forge("migrate")
    assert done.returncode == 0, done.stderr
    assert "nothing is deleted" in done.stdout
    assert repo.git("diff", "--name-only", "--diff-filter=D", "main", "forge/migrate-v1") == ""
    listing = repo.git("ls-tree", "-r", "--name-only", "forge/migrate-v1").splitlines()
    assert {"factory/scripts/forge.py", SHIP, "plans/SHIP-1.md", *LISTED} <= set(listing)
    # The old records stay here, and tidy-up's folder would clash with TIDY-UP's on a disk that
    # ignores capitals, so that plan stays as it is.
    assert (f"- {TIDY} stays as it is: .factory/stories/TIDY-UP is taken by a name that differs "
            "only in capitals") in done.stdout
    assert "plans/TIDY-UP.md" not in listing
    assert "<!-- forge:begin -->" in repo.git("show", "forge/migrate-v1:AGENTS.md")


def _changed_agents(repo, gh, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo.write("AGENTS.md", "# Shop agents\n\nOur own rules, and the old Forge contract.\n")
    _land(repo, "Our own AGENTS.md")
    dry = repo.forge("migrate", "--dry-run")
    assert dry.returncode == 0, dry.stderr
    assert ("Needs you in AGENTS.md: it differs from the old Forge's, so its text stays above the "
            "Forge block; take the old Forge instructions out of it.") in dry.stdout
    assert "Replaces AGENTS.md" not in dry.stdout


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


def _outside(repo, tmp_path: Path) -> None:
    (tmp_path / "elsewhere").mkdir()
    os.symlink(tmp_path / "elsewhere", repo.path / ".forge-migrate")
    _land(repo, "A link out of the repo")


def _agents_era(repo, tmp_path: Path) -> None:
    repo.git("rm", "-r", "-q", "factory")
    repo.write(".agents/README.md", "# The older layout\n")
    _land(repo, "The .agents/ layout")


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
    "work in flight": _refusal(
        "Work is still in flight in the copied-in Forge: the stage SHIP-1-T2 in ",
        "finish or drop each one with the copied-in ./forge", _in_flight),
    "a path outside the repo": _refusal(
        "leads outside this repo, so Forge won't change anything through it.",
        "remove that link, then forge migrate --dry-run", _outside),
    "an .agents/-era layout": _refusal(
        "origin/main has no copied-in factory/ layout to move", "forge next", _agents_era),
    "no copied-in commit": _refusal(
        "Forge can't read the copied-in version (constitution/VENDORED_FROM names no copied-in "
        "commit)", "check the network and constitution/VENDORED_FROM", _no_source),
}


@pytest.mark.parametrize("case", [
    pytest.param(name, marks=pytest.mark.skipif(
        name == "a path outside the repo" and os.name == "nt",
        reason="making a symlink needs extra rights on Windows")) for name in CASES])
def test_30_migrate(repo, gh, tmp_path, monkeypatch, case):
    monkeypatch.setenv("FORGE_NOW", "2026-09-25T12:00:00+00:00")
    _copied_client(repo, tmp_path, monkeypatch)
    CASES[case](repo, gh, tmp_path, monkeypatch)
