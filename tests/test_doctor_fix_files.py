"""forge doctor --fix brings the files forge sync writes up to date: in doctor's own fix on the
default branch, in place on any other branch, and never over a change made by hand.

Each test is named test_<n>_<rule> after the Done-when item of STORY it proves. Fakes stand only
for the third parties at their edge: gh, uv and, for the exit codes, the forge the host hooks run.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from conftest import _install
from test_setup import _autoreview, _executable, _fresh_client, _stub_forge, _version

STORY = "FORGE-DOCTORFIX-1"
WHY = "Bring the files Forge writes for Claude Code and Codex up to date"
SETTINGS, HOOKS, SKILL = ".claude/settings.json", ".codex/hooks.json", ".claude/skills/forge/SKILL.md"
OLD = '{"hooks": {}}\n'
HAND_FIX = "move your change out of this file, since forge sync rewrites it, then forge doctor --fix"
STATE = ".factory/fixes/{}.json"


def _row(problem: str, fix: str = "forge doctor --fix") -> str:
    return f"- {problem}\n  Fix: {fix}\n"


def _drift(rel: str, version: str) -> str:
    return _row(f"{rel} differs from what forge sync writes for the installed Forge {version}.")


def _held(rel: str, why: str) -> str:
    return _row(f"{rel} {why}, so doctor won't overwrite it.", HAND_FIX)


def _set(folder: Path, rel: str, text: str | None) -> None:
    path = folder / rel
    if text is None:
        path.unlink()
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _pin(text: str, version: str) -> str:
    return re.sub(r'^version = ".*"$', f'version = "{version}"', text, count=1, flags=re.M)


def _land(repo, client: Path, message: str, edit, forge: bool = False) -> str:
    """Push a commit to the default branch from a clone without Forge's hooks, then pull it into
    the client. forge=True makes it look like Forge's own: the same commit moves the pin, and a
    second commit moves it back."""
    # TemporaryDirectory also removes Git's read-only objects on Windows.
    with tempfile.TemporaryDirectory(prefix="lander-", dir=client.parent) as directory:
        clone = Path(directory)
        repo.git("clone", "-q", repo.git("remote", "get-url", "origin", cwd=client), str(clone))
        edit(clone)
        toml = clone / "forge.toml"
        pinned = toml.read_text(encoding="utf-8")
        if forge:
            toml.write_text(_pin(pinned, "v0.0.1"), encoding="utf-8")
        repo.git("add", "-A", cwd=clone)
        repo.git("commit", "-q", "-m", message, cwd=clone)
        if forge:
            toml.write_text(pinned, encoding="utf-8")
            repo.git("commit", "-q", "-am", "Pin the installed Forge again", cwd=clone)
        repo.git("push", "-q", "origin", "HEAD:main", cwd=clone)
    repo.git("pull", "-q", "--ff-only", "origin", "main", cwd=client)
    return repo.git("rev-parse", "HEAD", cwd=client)


def _client(repo, gh, tmp_path, monkeypatch, workers: str = "claude") -> Path:
    """A client made by forge init, with its workers set on the default branch."""
    client, init = _fresh_client(repo, gh, tmp_path)
    assert init.returncode == 0, init.stderr
    gh.respond("auth", "status")
    _autoreview(tmp_path, monkeypatch)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))  # never the real Codex SDK
    # Without the pinned Forge's uv, nothing installs the Codex SDK for real.
    _install(repo.bin, "uv", "#!/bin/sh\necho 'uv: offline in this test' >&2\nexit 1\n")
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex-home"))  # never the user's Codex
    if f'workers = "{workers}"' not in (client / "forge.toml").read_text(encoding="utf-8"):
        _land(repo, client, f"Use {workers} workers", lambda folder: _set(
            folder, "forge.toml", re.sub(r'workers = "\w+"', f'workers = "{workers}"',
                                         (folder / "forge.toml").read_text(encoding="utf-8"))))
    return client


def _old_hosts(repo, client: Path) -> str:
    """Both hosts' hook files as an older Forge wrote them, on the default branch."""
    return _land(repo, client, "Upgrade Forge", lambda folder: (
        _set(folder, SETTINGS, OLD), _set(folder, HOOKS, OLD)), forge=True)


def _wanted(repo, client: Path, tmp_path) -> dict[str, str]:
    """What forge sync writes for this client: run it in a throwaway fix and read the result."""
    started = repo.forge("fix", "start", "See what sync writes", "--done", "read", cwd=client)
    assert started.returncode == 0, started.stdout + started.stderr
    folder = Path(started.stdout.split(" in ", 1)[1].splitlines()[0])
    assert repo.forge("sync", cwd=folder).returncode == 0
    found = {rel: (folder / rel).read_text(encoding="utf-8")
             for rel in (SETTINGS, HOOKS, SKILL, ".github/workflows/forge.yml")}
    repo.git("worktree", "remove", "--force", str(folder), cwd=client)
    repo.git("branch", "-D", started.stdout.split(" on ", 1)[1].split()[0], cwd=client)
    return found


def _fixes(repo, client: Path) -> list[str]:
    return repo.git("for-each-ref", "--format=%(refname:short)", "refs/heads/fix/",
                    cwd=client).splitlines()


def _in(repo, client: Path, branch: str) -> list[str]:
    """The files a fix's own commits change, beyond the default branch."""
    return sorted(repo.git("diff", "--name-only", f"origin/main...{branch}", cwd=client).split())


def _folder_of(repo, client: Path, branch: str) -> Path:
    listed = repo.git("worktree", "list", "--porcelain", cwd=client).split("\n\n")
    return Path(next(entry.splitlines()[0].removeprefix("worktree ") for entry in listed
                     if f"branch refs/heads/{branch}" in entry.splitlines()))


def _start_fix(repo, client: Path, why: str = "Try doctor on a fix branch") -> Path:
    started = repo.forge("fix", "start", why, "--done", "it works", cwd=client)
    assert started.returncode == 0, started.stdout + started.stderr
    return Path(started.stdout.split(" in ", 1)[1].splitlines()[0])


def _status(repo, folder: Path) -> tuple[str, str, str]:
    """The checkout's commit, its index and its working files, as git lists them."""
    return (repo.git("rev-parse", "HEAD", cwd=folder), repo.git("diff", "--cached", cwd=folder),
            repo.git("status", "--porcelain", cwd=folder))


# --- item 4: Forge's files through a fix, never on the default branch ---------------------------


def _on_the_default_branch_one_fix_holds_both_hosts_files(repo, gh, tmp_path, monkeypatch, _):
    client = _client(repo, gh, tmp_path, monkeypatch, workers="claude")  # run under Codex
    assert os.environ["CODEX_THREAD_ID"] and "CLAUDECODE" not in os.environ
    wanted = _wanted(repo, client, tmp_path)
    head = _old_hosts(repo, client)
    version = "v" + _version(repo).removeprefix("v")

    listed = repo.forge("doctor", cwd=client)
    assert _drift(SETTINGS, version) in listed.stdout and _drift(HOOKS, version) in listed.stdout
    assert _fixes(repo, client) == []  # without --fix, nothing starts

    done = repo.forge("doctor", "--fix", cwd=client)
    fix_row = _row("Doctor's fix forge-files holds Forge's files and isn't merged yet.",
                   "forge close forge-files")
    assert "- Fixed: wrote 2 of Forge's files in fix forge-files.\n" in done.stdout, done.stdout
    assert fix_row in done.stdout and done.returncode == 1
    assert _drift(SETTINGS, version) not in done.stdout
    # The default branch has no new commit and its files stay; the fix holds both hosts' files.
    assert repo.git("rev-parse", "HEAD", "origin/main", cwd=client).split() == [head, head]
    assert (client / SETTINGS).read_text(encoding="utf-8") == OLD
    assert _fixes(repo, client) == ["fix/forge-files"]
    assert _in(repo, client, "fix/forge-files") == sorted([HOOKS, SETTINGS, STATE.format("forge-files")])
    for rel in (SETTINGS, HOOKS):
        assert repo.git("show", f"fix/forge-files:{rel}", cwd=client) == wanted[rel].strip()
    subjects = repo.git("log", "--format=%s", "origin/main..fix/forge-files", cwd=client)
    assert subjects.splitlines() == [WHY, f"Start the fix: {WHY}"]
    record = json.loads(repo.git("show", f"fix/forge-files:{STATE.format('forge-files')}",
                                 cwd=client))
    assert record["why"] == WHY and record["kind"] == "fix"
    assert record["done_when"] == "The files match what forge sync writes for the pinned Forge"
    assert record["allow_large"] == ("Doctor brings every file forge sync writes up to date in one "
                                     "change; Forge Test allowed it by running forge doctor --fix.")

    # A second run starts nothing and commits nothing, and gives the fix's one step.
    fix_head = repo.git("rev-parse", "fix/forge-files", cwd=client)
    again = repo.forge("doctor", "--fix", cwd=client)
    assert (_left_over("forge-files", _folder_of(repo, client, "fix/forge-files")) in again.stdout
            and "- Fixed: wrote" not in again.stdout), again.stdout
    assert _fixes(repo, client) == ["fix/forge-files"]
    assert repo.git("rev-parse", "fix/forge-files", "HEAD", cwd=client).split() == [fix_head, head]


def _codex_workers_under_claude_code_repair_both_hosts(repo, gh, tmp_path, monkeypatch, _):
    client = _client(repo, gh, tmp_path, monkeypatch, workers="codex")
    _old_hosts(repo, client)
    monkeypatch.delenv("CODEX_THREAD_ID")
    monkeypatch.setenv("CLAUDECODE", "1")
    done = repo.forge("doctor", "--fix", cwd=client)
    assert "- Fixed: wrote 2 of Forge's files in fix forge-files.\n" in done.stdout, done.stdout
    assert _in(repo, client, "fix/forge-files") == sorted([HOOKS, SETTINGS, STATE.format("forge-files")])


def _a_finished_doctor_fix_is_left_in_place(repo, gh, tmp_path, monkeypatch, state):
    client = _client(repo, gh, tmp_path, monkeypatch)
    _old_hosts(repo, client)
    started = repo.forge("doctor", "--fix", cwd=client)
    assert "- Fixed: wrote 2 of Forge's files in fix forge-files.\n" in started.stdout
    folder = _folder_of(repo, client, "fix/forge-files")
    # A lockfile alone would qualify other finished worktrees for cleanup.
    _set(folder, "uv.lock", "version = 2\n")
    before = _status(repo, folder)
    contents = {path.relative_to(folder): path.read_bytes()
                for path in folder.rglob("*") if path.is_file()}
    main = _status(repo, client)
    trees = repo.git("worktree", "list", "--porcelain", cwd=client)
    gh.respond("pr", "list", "--head", "fix/forge-files", stdout=json.dumps(
        [{"headRefOid": before[0], "state": state}]))

    done = repo.forge("doctor", "--fix", cwd=client)

    assert folder.is_dir(), done.stdout + done.stderr
    assert _fixes(repo, client) == ["fix/forge-files"]
    assert _status(repo, folder) == before and _status(repo, client) == main
    assert repo.git("worktree", "list", "--porcelain", cwd=client) == trees
    assert {path.relative_to(folder): path.read_bytes()
            for path in folder.rglob("*") if path.is_file()} == contents
    assert _left_over("forge-files", folder) in done.stdout and done.returncode == 1, done.stdout
    assert "- Fixed: removed" not in done.stdout and "- Fixed: wrote" not in done.stdout


def _on_a_fix_branch_the_files_are_written_in_place(repo, gh, tmp_path, monkeypatch, _):
    client = _client(repo, gh, tmp_path, monkeypatch)
    wanted = _wanted(repo, client, tmp_path)
    _old_hosts(repo, client)
    folder = _start_fix(repo, client)
    head = repo.git("rev-parse", "HEAD", cwd=folder)
    done = repo.forge("doctor", "--fix", cwd=folder)
    assert f"- Fixed: wrote {SETTINGS}.\n- Fixed: wrote {HOOKS}.\n" in done.stdout, done.stdout
    assert "differs from what forge sync writes" not in done.stdout
    for rel in (SETTINGS, HOOKS):
        assert (folder / rel).read_text(encoding="utf-8") == wanted[rel]
    # Not committed, as forge sync leaves them; no other fix started.
    assert repo.git("rev-parse", "HEAD", cwd=folder) == head
    assert sorted(line.split() for line in repo.git("status", "--porcelain", cwd=folder).splitlines()) == [
        ["M", SETTINGS], ["M", HOOKS]]
    assert len(_fixes(repo, client)) == 1
    # A second run: doctor's own unstaged repairs are nothing to do, never a hand edit.
    again = repo.forge("doctor", "--fix", cwd=folder)
    assert "- Fixed:" not in again.stdout and "won't overwrite" not in again.stdout, again.stdout
    assert SETTINGS not in again.stdout and HOOKS not in again.stdout


def _a_stale_tests_workflow_is_repaired_in_place(repo, gh, tmp_path, monkeypatch, _):
    client = _client(repo, gh, tmp_path, monkeypatch)
    folder = _start_fix(repo, client)
    toml = folder / "forge.toml"
    toml.write_text(re.sub(r"^test = .*$", 'test = "make check"', toml.read_text(encoding="utf-8"),
                           count=1, flags=re.M), encoding="utf-8")
    repo.git("commit", "-qam", "Run the tests with make", cwd=folder)
    workflow = ".github/workflows/forge.yml"
    listed = repo.forge("doctor", cwd=folder).stdout
    assert f"{workflow} differs from what forge sync writes" in listed, listed
    assert f"The tests check in {workflow} doesn't run forge.toml's test command." in listed
    head = repo.git("rev-parse", "HEAD", cwd=folder)

    done = repo.forge("doctor", "--fix", cwd=folder)
    assert f"- Fixed: wrote {workflow}.\n" in done.stdout, done.stdout
    assert 'run: "make check"' in (folder / workflow).read_text(encoding="utf-8")
    assert workflow not in done.stdout.replace(f"- Fixed: wrote {workflow}.\n", "")
    assert "The tests check" not in done.stdout
    assert repo.git("rev-parse", "HEAD", cwd=folder) == head


def _a_failed_pin_install_writes_nothing(repo, gh, tmp_path, monkeypatch, _):
    client = _client(repo, gh, tmp_path, monkeypatch)
    _old_hosts(repo, client)
    toml = client / "forge.toml"
    toml.write_text(_pin(toml.read_text(encoding="utf-8"), "v99.0.0"), encoding="utf-8")
    _install(repo.bin, "uv", "#!/bin/sh\necho 'error: the network is down' >&2\nexit 2\n")
    version = "v" + _version(repo).removeprefix("v")
    done = repo.forge("doctor", "--fix", cwd=client)
    assert "Installing it failed: error: the network is down" in done.stdout, done.stdout
    assert _drift(SETTINGS, version) in done.stdout and _drift(HOOKS, version) in done.stdout
    assert _fixes(repo, client) == [] and (client / SETTINGS).read_text(encoding="utf-8") == OLD


def _a_fix_already_named_forge_files_is_left_alone(repo, gh, tmp_path, monkeypatch, _):
    # The fixed branch name now identifies doctor's fix, regardless of its record or why.
    client = _client(repo, gh, tmp_path, monkeypatch)
    _old_hosts(repo, client)
    started = repo.forge("fix", "start", "Something else", "--done", "x", "--slug", "forge-files",
                         cwd=client)
    assert started.returncode == 0, started.stderr
    folder = _folder_of(repo, client, "fix/forge-files")
    before = _status(repo, folder)
    done = repo.forge("doctor", "--fix", cwd=client)
    assert _left_over("forge-files", folder) in done.stdout, done.stdout
    assert "- Fixed: wrote" not in done.stdout and _fixes(repo, client) == ["fix/forge-files"]
    assert _status(repo, folder) == before
    assert _in(repo, client, "fix/forge-files") == [STATE.format("forge-files")]  # left alone


def _a_file_sync_wants_empty_is_removed(repo, gh, tmp_path, monkeypatch, claude):
    client = _client(repo, gh, tmp_path, monkeypatch)
    # A CLAUDE.md holding only what AGENTS.md has, or nothing at all: forge sync deletes it.
    _land(repo, client, "Upgrade Forge", lambda folder: _set(folder, "CLAUDE.md", claude),
          forge=True)
    done = repo.forge("doctor", "--fix", cwd=client)
    assert "- Fixed: wrote 1 of Forge's files in fix forge-files.\n" in done.stdout, done.stdout
    assert repo.git("diff", "--name-status", "origin/main...fix/forge-files", "--", "CLAUDE.md",
                    cwd=client) == "D\tCLAUDE.md"
    assert (client / "CLAUDE.md").is_file()  # the default branch keeps it until the fix merges

    folder = _start_fix(repo, client)
    done = repo.forge("doctor", "--fix", cwd=folder)
    assert "- Fixed: removed CLAUDE.md.\n" in done.stdout, done.stdout
    assert not (folder / "CLAUDE.md").exists()
    assert repo.git("status", "--porcelain", "--", "CLAUDE.md", cwd=folder) == "D CLAUDE.md"
    again = repo.forge("doctor", "--fix", cwd=folder)  # its own repair is nothing to do
    assert "- Fixed:" not in again.stdout and "CLAUDE.md" not in again.stdout, again.stdout


def _left_over(name: str, path: Path | None) -> str:
    """The one step for a doctor fix that already exists, current, stale or locked."""
    remove = f'git worktree remove --force --force "{path}" and ' if path else ""
    return _row(f"Doctor's fix {name} isn't merged yet, so doctor started no new one.", f"finish it with forge close {name}, or remove it with {remove}git branch -D "
                f"fix/{name}, then forge doctor --fix")


# Was: a stale doctor fix got a row and a new fix, forge-files-2, beside it. Now doctor keeps at
# most one fix of its own: a stale one gets one plain step and nothing new starts.
def _a_stale_doctor_fix_gets_one_step_and_nothing_new_starts(repo, gh, tmp_path, monkeypatch,
                                                           change):
    client = _client(repo, gh, tmp_path, monkeypatch)
    _old_hosts(repo, client)
    assert "fix forge-files." in repo.forge("doctor", "--fix", cwd=client).stdout
    old = _folder_of(repo, client, "fix/forge-files")
    spaced = old.with_name(old.name + " with spaces")
    repo.git("worktree", "move", str(old), str(spaced), cwd=client)
    old = spaced
    if change == "its forge.toml was edited":
        toml = old / "forge.toml"
        toml.write_text(re.sub(r"^test = .*$", 'test = "make it"', toml.read_text(encoding="utf-8"),
                               count=1, flags=re.M), encoding="utf-8")
    else:
        _land(repo, client, "Run the tests with make", lambda folder: _set(
            folder, "forge.toml", re.sub(r"^test = .*$", 'test = "make check"',
                                         (folder / "forge.toml").read_text(encoding="utf-8"),
                                         count=1, flags=re.M)))
    before = _status(repo, old)

    done = repo.forge("doctor", "--fix", cwd=client)
    assert _left_over("forge-files", old) in done.stdout, done.stdout
    assert _status(repo, old) == before  # nothing changed there
    assert "- Fixed: wrote" not in done.stdout and _fixes(repo, client) == ["fix/forge-files"]


def _nothing_differing_leaves_no_fix_behind(repo, gh, tmp_path, monkeypatch, _):
    client = _client(repo, gh, tmp_path, monkeypatch)
    folders = repo.git("worktree", "list", cwd=client)
    done = repo.forge("doctor", "--fix", cwd=client)
    assert "Forge's files" not in done.stdout and "- Fixed: wrote" not in done.stdout, done.stdout
    assert _fixes(repo, client) == [] and repo.git("worktree", "list", cwd=client) == folders


def _clean_checkout_step() -> str:
    return _row("Doctor needs a clean checkout at origin/main before it makes a fix for Forge's files.",
                "commit or discard your changes first, bring this checkout to origin/main, "
                "then forge doctor --fix")


def _doctor_starts_its_fix_only_from_a_clean_checkout_at_origin(repo, gh, tmp_path, monkeypatch,
                                                               change):
    client = _client(repo, gh, tmp_path, monkeypatch)
    # Previously an uncommitted test command could cause a permanently empty doctor fix.
    if change in ("unstaged config", "staged config"):
        toml = client / "forge.toml"
        original = toml.read_text(encoding="utf-8")
        _set(client, "forge.toml", re.sub(r'^test = .*$', 'test = "make check"', original, flags=re.M))
        if change == "staged config":
            repo.git("add", "forge.toml", cwd=client)
            toml.write_text(original, encoding="utf-8")  # an index change still blocks creation
    elif change == "untracked file":
        _set(client, "notes.txt", "Our work.\n")
    else:
        _land(repo, client, "A note", lambda folder: _set(folder, "NOTES.txt", "a note\n"))
        repo.git("reset", "-q", "--hard", "HEAD~1", cwd=client)
    before = _status(repo, client)
    folders = repo.git("worktree", "list", cwd=client)

    done = repo.forge("doctor", "--fix", cwd=client)

    assert _clean_checkout_step() in done.stdout and done.returncode == 1, done.stdout
    assert "- Fixed: wrote" not in done.stdout and _fixes(repo, client) == []
    assert repo.git("worktree", "list", cwd=client) == folders
    assert _status(repo, client) == before


def _a_fix_holds_the_repaired_file_and_the_held_one_keeps_its_row(repo, gh, tmp_path,
                                                                   monkeypatch, _):
    client = _client(repo, gh, tmp_path, monkeypatch)
    _old_hosts(repo, client)
    _land(repo, client, "Tweak the skill", lambda folder: _set(folder, SKILL, "Our skill\n"))
    done = repo.forge("doctor", "--fix", cwd=client)
    assert "- Fixed: wrote 2 of Forge's files in fix forge-files.\n" in done.stdout, done.stdout
    assert "Doctor's fix forge-files holds Forge's files and isn't merged yet." in done.stdout
    assert _held(SKILL, "was changed by hand (Tweak the skill)") in done.stdout
    assert SKILL not in _in(repo, client, "fix/forge-files")


def _refusing_hook(client: Path, commit: str) -> Path:
    """The team's check refuses either the record commit or the later files commit."""
    hook = Path(subprocess.run(["git", "rev-parse", "--path-format=absolute", "--git-path",
                                "hooks/pre-commit.pre-forge"], cwd=client, capture_output=True,
                               text=True, check=True).stdout.strip())
    _executable(hook, "#!/bin/sh\n"
                      f"git diff --cached --name-only | grep -qx "
                      f"'{STATE.format('forge-files') if commit == 'record' else SETTINGS}' || exit 0\n"
                      "echo 'Work still in progress.' > notes.txt\n"
                      "echo 'our check refuses this commit' >&2\nexit 1\n")
    return hook


def _a_commit_a_git_hook_refuses_leaves_the_fix(repo, gh, tmp_path, monkeypatch, commit):
    # Old contract: doctor removed a failed fix. The revised story leaves it intact, with
    # the rejection reason and a finish-or-remove step, even if its record commit failed.
    client = _client(repo, gh, tmp_path, monkeypatch)
    head = _old_hosts(repo, client)
    _refusing_hook(client, commit)
    folder = client.parent / f"{client.name}-fix-forge-files"

    done = repo.forge("doctor", "--fix", cwd=client)
    problem = ("Doctor couldn't bring Forge's files up to date in fix forge-files: our check "
               "refuses this commit")
    step = _left_over("forge-files", folder).split("\n  Fix: ", 1)[1].strip()
    assert _row(problem, step) in done.stdout, done.stdout
    assert folder.exists() and _fixes(repo, client) == ["fix/forge-files"]
    assert (folder / "notes.txt").read_text(encoding="utf-8") == "Work still in progress.\n"
    assert repo.git("rev-parse", "HEAD", "origin/main", cwd=client).splitlines() == [head, head]
    assert "Doctor's fix forge-files holds" not in done.stdout and done.returncode == 1
    # Even the failed record commit must be recognized on the next run, without a second fix.
    before = _status(repo, folder)
    folders = repo.git("worktree", "list", cwd=client)
    again = repo.forge("doctor", "--fix", cwd=client)
    assert _left_over("forge-files", folder) in again.stdout, again.stdout
    assert "- Fixed: wrote" not in again.stdout and _fixes(repo, client) == ["fix/forge-files"]
    assert _status(repo, folder) == before
    assert repo.git("worktree", "list", cwd=client) == folders
    assert (folder / "notes.txt").read_text(encoding="utf-8") == "Work still in progress.\n"


def _a_file_the_system_wont_write(repo, gh, tmp_path, monkeypatch, _):
    client = _client(repo, gh, tmp_path, monkeypatch)
    wanted = _wanted(repo, client, tmp_path)
    # In a new fix: a folder stands where sync writes the Codex hooks file.
    _land(repo, client, "Upgrade Forge", lambda folder: (
        _set(folder, SETTINGS, OLD), _set(folder, HOOKS, None),
        _set(folder, f"{HOOKS}/inside", "x\n")), forge=True)
    done = repo.forge("doctor", "--fix", cwd=client)
    failed_folder = client.parent / (client.name + "-fix-forge-files")
    step = _left_over("forge-files", failed_folder).split("\n  Fix: ", 1)[1].strip()
    assert _row("Doctor couldn't bring Forge's files up to date in fix forge-files: [Errno 21] "
                f"Is a directory: '{failed_folder / HOOKS}'", step) in done.stdout, done.stdout
    assert failed_folder.is_dir() and _fixes(repo, client) == ["fix/forge-files"]

    # In place: the settings are written, the read-only hooks file isn't, and stays a row.
    _land(repo, client, "Upgrade Forge", lambda folder: (
        shutil.rmtree(folder / HOOKS), _set(folder, HOOKS, OLD)), forge=True)
    folder = _start_fix(repo, client)
    (folder / HOOKS).chmod(0o444)
    done = repo.forge("doctor", "--fix", cwd=folder)
    assert f"- Fixed: wrote {SETTINGS}.\n" in done.stdout, done.stdout
    assert (f"- doctor couldn't write Forge's files: [Errno 13] Permission denied: "
            f"'{folder / HOOKS}'\n  Fix: forge doctor --fix\n") in done.stdout
    assert (folder / SETTINGS).read_text(encoding="utf-8") == wanted[SETTINGS]
    (folder / HOOKS).chmod(0o644)
    again = repo.forge("doctor", "--fix", cwd=folder)
    assert f"- Fixed: wrote {HOOKS}.\n" in again.stdout and SETTINGS not in again.stdout
    assert (folder / HOOKS).read_text(encoding="utf-8") == wanted[HOOKS]


def _an_ignored_synced_file_written_by_hand_is_held_back(repo, gh, tmp_path, monkeypatch, _):
    client = _client(repo, gh, tmp_path, monkeypatch)
    _land(repo, client, "Upgrade Forge", lambda folder: (
        _set(folder, SKILL, None), _set(folder, ".gitignore", f"{SKILL}\n")), forge=True)
    folder = _start_fix(repo, client)
    (folder / SKILL).write_text("Our own skill\n", encoding="utf-8")
    done = repo.forge("doctor", "--fix", cwd=folder)
    assert _held(SKILL, "has changes not committed yet") in done.stdout, done.stdout
    assert (folder / SKILL).read_text(encoding="utf-8") == "Our own skill\n"


def _a_link_stops_every_repair(repo, gh, tmp_path, monkeypatch, link):
    """Any file forge sync writes or reads, or a folder above it, that is a link: doctor repairs
    none of Forge's files, writes and copies nothing, and gives one plain step."""
    client = _client(repo, gh, tmp_path, monkeypatch)
    _old_hosts(repo, client)
    outside = tmp_path / "private.md"
    outside.write_text("Private notes\n", encoding="utf-8")
    folder = _start_fix(repo, client)
    if link == "CLAUDE.md to a file outside the repo":
        (folder / "CLAUDE.md").symlink_to(outside)
        rel = "CLAUDE.md"
    else:  # the skill's folder leads to notes in the repo, edited by hand
        skills = folder / ".claude/skills/forge"
        shutil.copytree(skills, folder / "notes")
        (folder / "notes/SKILL.md").write_text("Our notes\n", encoding="utf-8")
        shutil.rmtree(skills)
        skills.symlink_to("../../notes")
        rel = SKILL
    before = {path: path.read_bytes() for path in folder.rglob("*") if path.is_file()
              and ".git" not in path.parts}
    done = repo.forge("doctor", "--fix", cwd=folder)
    assert _row(f"{rel} is a link, so doctor repaired none of Forge's files.",
                "replace the link with a regular file, then forge doctor --fix") in done.stdout, (
        done.stdout)
    assert "- Fixed: wrote" not in done.stdout and "- Fixed: removed" not in done.stdout
    assert {path: path.read_bytes() for path in folder.rglob("*") if path.is_file()
            and ".git" not in path.parts} == before
    assert outside.read_text(encoding="utf-8") == "Private notes\n"
    assert "Private notes" not in (folder / "AGENTS.md").read_text(encoding="utf-8")


def _the_default_branch_cant_be_fetched(repo, gh, tmp_path, monkeypatch, _):
    client = _client(repo, gh, tmp_path, monkeypatch)
    _old_hosts(repo, client)
    repo.git("remote", "set-url", "origin", str(tmp_path / "gone.git"), cwd=client)
    version = "v" + _version(repo).removeprefix("v")
    done = repo.forge("doctor", "--fix", cwd=client)
    assert ("- doctor couldn't fetch main from origin, so it started no fix for Forge's files: "
            in done.stdout), done.stdout
    assert "  Fix: check your network and GitHub access, then forge doctor --fix\n" in done.stdout
    assert _drift(SETTINGS, version) in done.stdout and _drift(HOOKS, version) in done.stdout
    assert _fixes(repo, client) == []


def _the_default_branch_moved_to_another_pin(repo, gh, tmp_path, monkeypatch, _):
    client = _client(repo, gh, tmp_path, monkeypatch)
    head = _old_hosts(repo, client)
    _land(repo, client, "Upgrade Forge to v99.0.0", lambda folder: _set(
        folder, "forge.toml", _pin((folder / "forge.toml").read_text(encoding="utf-8"), "v99.0.0")))
    repo.git("reset", "-q", "--hard", head, cwd=client)  # this checkout still pins the installed one
    version = "v" + _version(repo).removeprefix("v")
    done = repo.forge("doctor", "--fix", cwd=client)
    assert _clean_checkout_step() in done.stdout, done.stdout
    assert _drift(SETTINGS, version) in done.stdout and _fixes(repo, client) == []


def _a_detached_head_changes_nothing(repo, gh, tmp_path, monkeypatch, _):
    client = _client(repo, gh, tmp_path, monkeypatch)
    _old_hosts(repo, client)
    repo.git("checkout", "-q", "--detach", cwd=client)
    before = _status(repo, client)
    version = "v" + _version(repo).removeprefix("v")
    done = repo.forge("doctor", "--fix", cwd=client)
    assert _row("Forge changes nothing on a detached HEAD; work happens on a story, task or fix "
                "branch.", 'forge fix start "<why>" --done "<done when>"') in done.stdout, done.stdout
    assert _drift(SETTINGS, version) in done.stdout and _drift(HOOKS, version) in done.stdout
    assert _status(repo, client) == before and _fixes(repo, client) == []


# --- item 5: never over a change made by hand ---------------------------------------------------


def _skill_commit(repo, client: Path, case: str) -> None:
    """The skill changed on the default branch, together with what case names."""
    def edit(folder: Path) -> None:
        _set(folder, SKILL, "Our skill\n")
        toml = folder / "forge.toml"
        text = toml.read_text(encoding="utf-8")
        if case == "a version line edit that keeps the pin":
            text = re.sub(r'^(version = ".*")$', r"\1  # the same pin", text, count=1, flags=re.M)
        elif case == "another forge.toml line":
            text = re.sub(r"^test = .*$", 'test = "make check"', text, count=1, flags=re.M)
        toml.write_text(text, encoding="utf-8")
    subject = f"{WHY} (#12)" if case == "doctor's fix, squashed" else "Tweak the skill"
    _land(repo, client, subject, edit, forge=case == "the pin")


HELD = {"nothing else": True, "the pin": False, "a version line edit that keeps the pin": True,
        "another forge.toml line": True, "doctor's fix, squashed": False}


def _a_skill_changed_on_the_default_branch_is_held_back_unless_forge_changed_it(
        repo, gh, tmp_path, monkeypatch, case):
    held = HELD[case]
    client = _client(repo, gh, tmp_path, monkeypatch)
    _skill_commit(repo, client, case)
    subject = f"{WHY} (#12)" if case == "doctor's fix, squashed" else "Tweak the skill"
    row = _held(SKILL, f"was changed by hand ({subject})")
    assert (row in repo.forge("doctor", cwd=client).stdout) == held
    done = repo.forge("doctor", "--fix", cwd=client)
    if held:  # another forge.toml line may make other files differ, which a fix holds
        assert row in done.stdout, done.stdout
        assert not _fixes(repo, client) or SKILL not in _in(repo, client, "fix/forge-files")
    else:
        assert "- Fixed: wrote 1 of Forge's files in fix forge-files.\n" in done.stdout, done.stdout
        assert "changed by hand" not in done.stdout
        assert SKILL in _in(repo, client, "fix/forge-files")


def _a_local_commit_that_moves_the_pin_on_a_fix_branch_is_held_back(repo, gh, tmp_path,
                                                                    monkeypatch, _):
    client = _client(repo, gh, tmp_path, monkeypatch)
    folder = _start_fix(repo, client)
    toml = folder / "forge.toml"
    pinned = toml.read_text(encoding="utf-8")
    _set(folder, SKILL, "Our skill\n")
    toml.write_text(_pin(pinned, "v0.0.1"), encoding="utf-8")
    repo.git("commit", "-q", "-am", "Move the pin and the skill", cwd=folder)
    toml.write_text(pinned, encoding="utf-8")
    repo.git("commit", "-q", "-am", "Pin back", cwd=folder)
    done = repo.forge("doctor", "--fix", cwd=folder)
    assert _held(SKILL, "was changed by hand (Move the pin and the skill)") in done.stdout, done.stdout
    assert (folder / SKILL).read_text(encoding="utf-8") == "Our skill\n"


def _uncommitted_changes_are_held_back(repo, gh, tmp_path, monkeypatch, _):
    client = _client(repo, gh, tmp_path, monkeypatch)
    wanted = _wanted(repo, client, tmp_path)
    folder = _start_fix(repo, client)
    (folder / SKILL).write_text("Our skill\n", encoding="utf-8")
    row = _held(SKILL, "has changes not committed yet")
    done = repo.forge("doctor", "--fix", cwd=folder)
    assert row in done.stdout and "- Fixed:" not in done.stdout, done.stdout
    assert (folder / SKILL).read_text(encoding="utf-8") == "Our skill\n"
    # On the fix branch: staged by hand, then the working copy put back to sync's text.
    repo.git("add", SKILL, cwd=folder)
    (folder / SKILL).write_text(wanted[SKILL], encoding="utf-8")
    staged = repo.git("diff", "--cached", cwd=folder)
    done = repo.forge("doctor", "--fix", cwd=folder)
    assert row in done.stdout and "- Fixed:" not in done.stdout, done.stdout
    assert repo.git("diff", "--cached", cwd=folder) == staged
    repo.git("reset", "-q", "--", SKILL, cwd=folder)

    # Staged by hand, with the working copy back to sync's: still held, and the index kept.
    _old_hosts(repo, client)  # other files need repair, but a staged edit blocks the new fix
    _land(repo, client, "Upgrade Forge", lambda folder: _set(folder, SKILL, "Older skill\n"),
          forge=True)
    (client / SKILL).write_text("Our skill\n", encoding="utf-8")
    repo.git("add", SKILL, cwd=client)
    (client / SKILL).write_text(wanted[SKILL], encoding="utf-8")
    index = repo.git("diff", "--cached", cwd=client)
    branches = _fixes(repo, client)  # the earlier in-place test already made a user's fix
    done = repo.forge("doctor", "--fix", cwd=client)
    assert row in done.stdout, done.stdout
    assert repo.git("diff", "--cached", cwd=client) == index
    assert _clean_checkout_step() in done.stdout and _fixes(repo, client) == branches
    # The next run also refuses creation, leaves the hand-edit row and keeps the index.
    again = repo.forge("doctor", "--fix", cwd=client)
    assert _clean_checkout_step() in again.stdout and row in again.stdout, again.stdout
    assert _fixes(repo, client) == branches
    assert repo.git("diff", "--cached", cwd=client) == index


def _in_forges_own_repo_history_holds_nothing_back(repo, gh, tmp_path, monkeypatch, _):
    client = _client(repo, gh, tmp_path, monkeypatch)
    _land(repo, client, "Forge's own repo", lambda folder: _set(
        folder, "forge.toml", (folder / "forge.toml").read_text(encoding="utf-8").replace(
            'repo = "client"', 'repo = "forge-source"', 1)))
    _land(repo, client, "Tweak the skill", lambda folder: _set(folder, SKILL, "Our skill\n"))
    done = repo.forge("doctor", "--fix", cwd=client)
    assert "changed by hand" not in done.stdout, done.stdout
    assert "Forge's files in fix forge-files.\n" in done.stdout
    assert SKILL in _in(repo, client, "fix/forge-files")


def _ui_client(repo, gh, tmp_path, monkeypatch, workers="claude") -> Path:
    client = _client(repo, gh, tmp_path, monkeypatch, workers=workers)
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex-home"))
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    for name in ("impeccable", "emil-design-eng"):  # where the Claude worker reads skills only
        _set(home / ".claude", f"skills/{name}/SKILL.md", f"{name}\n")
    _set(client, "web/package.json", '{"name": "web"}\n')
    # No Codex program on PATH, whatever this machine has.
    monkeypatch.setenv("PATH", os.pathsep.join(
        folder for folder in os.environ["PATH"].split(os.pathsep)
        if not shutil.which("codex", path=folder)))
    return client


def _the_ui_skills_check_covers_each_installed_host(repo, gh, tmp_path, monkeypatch, case):
    workers, codex = case
    client = _ui_client(repo, gh, tmp_path, monkeypatch, workers=workers)
    if codex:
        _executable(repo.bin / "codex", "#!/bin/sh\n")
    done = repo.forge("doctor", cwd=client)
    for name in ("impeccable", "emil-design-eng"):
        assert (f"- {name} is required for UI work but isn't installed where the codex worker "
                "reads skills.\n" in done.stdout) == (codex or workers in ("split", "codex")), done.stdout
        assert "where the claude worker reads skills" not in done.stdout


def _signing_in_to_github_stays_a_plain_step(repo, gh, tmp_path, monkeypatch, _):
    client = _client(repo, gh, tmp_path, monkeypatch)
    gh.respond("auth", "status", exit=1)
    done = repo.forge("doctor", "--fix", cwd=client)
    assert _row("gh is not signed in to GitHub.", "gh auth login") in done.stdout
    assert done.returncode == 1


def _exit_codes(repo, gh, tmp_path, monkeypatch, _):
    client = _client(repo, gh, tmp_path, monkeypatch)
    _old_hosts(repo, client)
    folder = _start_fix(repo, client)
    # Everything else checks out: GitHub, Claude, Codex's trust, and the host hooks' forge.
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    codex_home = tmp_path / "codex"
    _set(codex_home, "config.toml", f'[projects.{json.dumps(str(folder))}]\ntrust_level = "trusted"\n')
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    _executable(repo.bin / "claude", "#!/bin/sh\n")
    _stub_forge(tmp_path, monkeypatch)

    listed = repo.forge("doctor", cwd=folder)
    assert listed.returncode == 1 and "forge doctor found 2 problem(s)" in listed.stderr, (
        listed.stdout + listed.stderr)
    done = repo.forge("doctor", "--fix", cwd=folder)
    assert done.returncode == 0, done.stdout + done.stderr
    assert done.stdout.startswith(f"- Fixed: wrote {SETTINGS}.\n- Fixed: wrote {HOOKS}.\n")
    assert "Everything checks out" in done.stdout


def _an_existing_app_adopted_on_v1_2_2_is_repaired(repo, gh, tmp_path, monkeypatch, _):
    # Unlike fresh-init coverage, this app has history before its previous-release adoption.
    client = repo.path
    application = (client / "README.md").read_text(encoding="utf-8")
    shutil.copytree(Path(__file__).parent / "fixtures/doctor-v1.2.2", client,
                    dirs_exist_ok=True)
    assert 'version = "v1.2.2"' in (client / "forge.toml").read_text(encoding="utf-8")
    repo.git("add", "-A")
    repo.git("commit", "-qm", "Adopt Forge")
    repo.git("push", "-q", "origin", "main")
    _land(repo, client, "Upgrade Forge", lambda folder: _set(
        folder, "forge.toml", _pin((folder / "forge.toml").read_text(encoding="utf-8"),
                                 "v" + _version(repo).removeprefix("v"))))
    _land(repo, client, "Keep our skill instructions", lambda folder: _set(folder, SKILL, "Ours.\n"))
    gh.respond("auth", "status")
    gh.respond("api", stdout="{}")
    _autoreview(tmp_path, monkeypatch)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex-home"))
    _install(repo.bin, "uv", f"#!{sys.executable}\nimport sys\nsys.exit(1)\n")
    head = repo.git("rev-parse", "HEAD")
    before = repo.forge("doctor", cwd=client)
    assert "differs from what forge sync writes" in before.stdout, before.stdout
    done = repo.forge("doctor", "--fix", cwd=client)
    assert "- Fixed: wrote " in done.stdout and "in fix forge-files." in done.stdout, done.stdout
    assert _row("Doctor's fix forge-files holds Forge's files and isn't merged yet.",
                "forge close forge-files") in done.stdout, done.stdout
    assert _held(SKILL, "was changed by hand (Keep our skill instructions)") in done.stdout
    assert repo.git("rev-parse", "HEAD", "origin/main").splitlines() == [head, head]
    folder = _folder_of(repo, client, "fix/forge-files")
    for checkout in (client, folder):
        assert (checkout / SKILL).read_text(encoding="utf-8") == "Ours.\n"
        assert (checkout / "README.md").read_text(encoding="utf-8") == application
        assert "Keep our application." in (checkout / "AGENTS.md").read_text(encoding="utf-8")
    assert SKILL not in _in(repo, client, "fix/forge-files")
    # Compare at the user's real sync boundary: only the protected hand edit still differs.
    checked = repo.forge("doctor", cwd=folder)
    assert "differs from what forge sync writes" not in checked.stdout, checked.stdout
    assert _held(SKILL, "was changed by hand (Keep our skill instructions)") in checked.stdout
    assert repo.git("status", "--porcelain", cwd=folder) == ""


SHELL = pytest.mark.skipif(os.name == "nt", reason="shell scripts, file modes and links")


def _cases(*cases) -> list:
    """Each case, once per value it takes, named after the case and the value."""
    return [pytest.param(case, value, marks=marks, id=case.__name__.strip("_") + (
                f"[{value}]" if value is not None else "")) for case, values, marks in cases
            for value in values]


@pytest.mark.parametrize("case, value", _cases(
    (_an_existing_app_adopted_on_v1_2_2_is_repaired, [None], ()),
    (_on_the_default_branch_one_fix_holds_both_hosts_files, [None], ()),
    (_codex_workers_under_claude_code_repair_both_hosts, [None], ()),
    (_a_finished_doctor_fix_is_left_in_place, ["CLOSED", "MERGED"], ()),
    (_on_a_fix_branch_the_files_are_written_in_place, [None], ()),
    (_a_stale_tests_workflow_is_repaired_in_place, [None], ()),
    (_a_failed_pin_install_writes_nothing, [None], SHELL),
    (_a_fix_already_named_forge_files_is_left_alone, [None], ()),
    (_a_file_sync_wants_empty_is_removed, ["@AGENTS.md\n", ""], ()),
    (_a_stale_doctor_fix_gets_one_step_and_nothing_new_starts,
     ["the default branch changed the test command", "its forge.toml was edited"], ()),
    (_nothing_differing_leaves_no_fix_behind, [None], ()),
    (_doctor_starts_its_fix_only_from_a_clean_checkout_at_origin,
     ["unstaged config", "staged config", "untracked file", "behind origin"], ()),
    (_a_fix_holds_the_repaired_file_and_the_held_one_keeps_its_row, [None], ()),
    (_a_commit_a_git_hook_refuses_leaves_the_fix, ["record", "files"], SHELL),
    (_a_file_the_system_wont_write, [None], SHELL),
    (_a_link_stops_every_repair, ["CLAUDE.md to a file outside the repo",
                                  "the skill's folder to notes in the repo"], SHELL),
    (_the_default_branch_cant_be_fetched, [None], ()),
    (_the_default_branch_moved_to_another_pin, [None], ()),
    (_a_detached_head_changes_nothing, [None], ())))
def test_4_doctor_brings_forges_files_up_to_date_through_a_fix(repo, gh, tmp_path, monkeypatch,
                                                              case, value):
    case(repo, gh, tmp_path, monkeypatch, value)


@pytest.mark.parametrize("case, value", _cases(
    (_a_skill_changed_on_the_default_branch_is_held_back_unless_forge_changed_it, list(HELD), ()),
    (_a_local_commit_that_moves_the_pin_on_a_fix_branch_is_held_back, [None], ()),
    (_uncommitted_changes_are_held_back, [None], ()),
    (_an_ignored_synced_file_written_by_hand_is_held_back, [None], ()),
    (_in_forges_own_repo_history_holds_nothing_back, [None], ()),
    (_the_ui_skills_check_covers_each_installed_host,
     [("claude", True), ("claude", False), ("split", False), ("codex", False)], SHELL),
    (_signing_in_to_github_stays_a_plain_step, [None], ()),
    (_exit_codes, [None], SHELL)))
def test_5_doctor_never_overwrites_a_change_made_by_hand(repo, gh, tmp_path, monkeypatch, case,
                                                        value):
    case(repo, gh, tmp_path, monkeypatch, value)
