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
import uuid
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
    clone = client.parent / f"lander-{uuid.uuid4().hex[:8]}"
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
    shutil.rmtree(clone)
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

    # A second run starts nothing and commits nothing: the fix is current.
    fix_head = repo.git("rev-parse", "fix/forge-files", cwd=client)
    again = repo.forge("doctor", "--fix", cwd=client)
    assert fix_row in again.stdout and "- Fixed: wrote" not in again.stdout, again.stdout
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


def _a_fix_already_named_forge_files_gets_a_suffix(repo, gh, tmp_path, monkeypatch, _):
    client = _client(repo, gh, tmp_path, monkeypatch)
    _old_hosts(repo, client)
    started = repo.forge("fix", "start", "Something else", "--done", "x", "--slug", "forge-files",
                         cwd=client)
    assert started.returncode == 0, started.stderr
    done = repo.forge("doctor", "--fix", cwd=client)
    assert "- Fixed: wrote 2 of Forge's files in fix forge-files-2.\n" in done.stdout, done.stdout
    assert _in(repo, client, "fix/forge-files") == [STATE.format("forge-files")]  # left alone
    assert _in(repo, client, "fix/forge-files-2") == sorted([HOOKS, SETTINGS,
                                                             STATE.format("forge-files-2")])


def _a_file_sync_wants_empty_is_removed(repo, gh, tmp_path, monkeypatch, _):
    client = _client(repo, gh, tmp_path, monkeypatch)
    # A CLAUDE.md holding only what AGENTS.md has: forge sync deletes it.
    _land(repo, client, "Upgrade Forge", lambda folder: _set(folder, "CLAUDE.md", "@AGENTS.md\n"),
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


def _a_stale_doctor_fix_is_left_alone_and_a_new_one_starts(repo, gh, tmp_path, monkeypatch,
                                                           change):
    client = _client(repo, gh, tmp_path, monkeypatch)
    _old_hosts(repo, client)
    assert "fix forge-files." in repo.forge("doctor", "--fix", cwd=client).stdout
    old = _folder_of(repo, client, "fix/forge-files")
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
    assert _row("Doctor's fix forge-files is behind main, so doctor started a new one.",
                f"close its pull request if it has one, then git worktree remove --force {old} "
                "and git branch -D fix/forge-files") in done.stdout, done.stdout
    assert _status(repo, old) == before  # nothing changed there
    assert "- Fixed: wrote " in done.stdout and "in fix forge-files-2.\n" in done.stdout
    assert "Doctor's fix forge-files-2 holds Forge's files" in done.stdout
    if change != "its forge.toml was edited":
        assert 'run: "make check"' in repo.git("show", "fix/forge-files-2:.github/workflows/forge.yml",
                                                cwd=client)


def _nothing_differing_leaves_no_fix_behind(repo, gh, tmp_path, monkeypatch, _):
    client = _client(repo, gh, tmp_path, monkeypatch)
    folders = repo.git("worktree", "list", cwd=client)
    done = repo.forge("doctor", "--fix", cwd=client)
    assert "Forge's files" not in done.stdout and "- Fixed: wrote" not in done.stdout, done.stdout
    assert _fixes(repo, client) == [] and repo.git("worktree", "list", cwd=client) == folders

    # Behind the default branch, whose files are already sync's: a fix starts, finds nothing,
    # and goes.
    _land(repo, client, "A note", lambda folder: _set(folder, "NOTES.txt", "a note\n"))
    repo.git("reset", "-q", "--hard", "HEAD~1", cwd=client)
    done = repo.forge("doctor", "--fix", cwd=client)
    assert "Forge's files" not in done.stdout and "- Fixed: wrote" not in done.stdout, done.stdout
    assert _fixes(repo, client) == [] and repo.git("worktree", "list", cwd=client) == folders


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


def _refusing_hook(client: Path, lock: bool) -> Path:
    """The team's own pre-commit check, which Forge's hook runs first: it refuses a commit that
    changes the Claude settings, and may lock the folder it runs in first."""
    hook = Path(subprocess.run(["git", "rev-parse", "--path-format=absolute", "--git-path",
                                "hooks/pre-commit.pre-forge"], cwd=client, capture_output=True,
                               text=True, check=True).stdout.strip())
    _executable(hook, "#!/bin/sh\n"
                      f"git diff --cached --name-only | grep -qx '{SETTINGS}' || exit 0\n"
                      + ('git worktree lock "$(git rev-parse --show-toplevel)"\n' if lock else "")
                      + "echo 'our check refuses changes to the Claude settings' >&2\nexit 1\n")
    return hook


def _a_commit_a_git_hook_refuses_leaves_no_fix(repo, gh, tmp_path, monkeypatch, locked):
    client = _client(repo, gh, tmp_path, monkeypatch)
    _old_hosts(repo, client)
    if locked:  # an earlier doctor repair already merged must not make the failed one current
        _land(repo, client, f"{WHY} (#7)", lambda folder: _set(folder, "NOTES.txt", "x\n"))
    hook = _refusing_hook(client, locked)
    folder = client.parent / f"{client.name}-fix-forge-files"

    done = repo.forge("doctor", "--fix", cwd=client)
    problem = ("Doctor couldn't bring Forge's files up to date in fix forge-files: our check "
               "refuses changes to the Claude settings")
    if locked:
        assert _row(f"{problem} Its folder {folder} is still there.") in done.stdout, done.stdout
        assert folder.exists() and _fixes(repo, client) == ["fix/forge-files"]
    else:
        assert _row(problem) in done.stdout, done.stdout
        assert not folder.exists() and _fixes(repo, client) == []
    assert "Doctor's fix forge-files holds" not in done.stdout and done.returncode == 1

    hook.unlink()
    again = repo.forge("doctor", "--fix", cwd=client)
    name = "forge-files-2" if locked else "forge-files"
    assert f"- Fixed: wrote 2 of Forge's files in fix {name}.\n" in again.stdout, again.stdout
    if locked:
        assert (f"- Doctor's fix forge-files is behind main, so doctor started a new one.\n"
                in again.stdout)
    assert _in(repo, client, f"fix/{name}") == sorted([HOOKS, SETTINGS, STATE.format(name)])


def _a_file_the_system_wont_write(repo, gh, tmp_path, monkeypatch, _):
    client = _client(repo, gh, tmp_path, monkeypatch)
    wanted = _wanted(repo, client, tmp_path)
    # In a new fix: a folder stands where sync writes the Codex hooks file.
    _land(repo, client, "Upgrade Forge", lambda folder: (
        _set(folder, SETTINGS, OLD), _set(folder, HOOKS, None),
        _set(folder, f"{HOOKS}/inside", "x\n")), forge=True)
    done = repo.forge("doctor", "--fix", cwd=client)
    assert ("- Doctor couldn't bring Forge's files up to date in fix forge-files: [Errno 21] Is a "
            f"directory: '{client.parent / (client.name + '-fix-forge-files') / HOOKS}'\n"
            "  Fix: forge doctor --fix\n") in done.stdout, done.stdout
    assert _fixes(repo, client) == []

    # In place: the settings are written, the read-only hooks file isn't, and stays a row.
    _land(repo, client, "Upgrade Forge", lambda folder: (
        shutil.rmtree(folder / HOOKS), _set(folder, HOOKS, OLD)), forge=True)
    folder = _start_fix(repo, client)
    (folder / HOOKS).chmod(0o444)
    done = repo.forge("doctor", "--fix", cwd=folder)
    assert f"- Fixed: wrote {SETTINGS}.\n" in done.stdout, done.stdout
    assert (f"- doctor couldn't write {HOOKS}: [Errno 13] Permission denied: "
            f"'{folder / HOOKS}'\n  Fix: forge doctor --fix\n") in done.stdout
    assert (folder / SETTINGS).read_text(encoding="utf-8") == wanted[SETTINGS]
    (folder / HOOKS).chmod(0o644)
    again = repo.forge("doctor", "--fix", cwd=folder)
    assert f"- Fixed: wrote {HOOKS}.\n" in again.stdout and SETTINGS not in again.stdout
    assert (folder / HOOKS).read_text(encoding="utf-8") == wanted[HOOKS]


def _a_link_that_leads_outside_the_repo(repo, gh, tmp_path, monkeypatch, _):
    client = _client(repo, gh, tmp_path, monkeypatch)
    outside = tmp_path / "outside.md"
    outside.write_text("not the repo's\n", encoding="utf-8")

    def link(folder: Path) -> None:
        (folder / SKILL).unlink()
        (folder / SKILL).symlink_to(outside)
    _land(repo, client, "Upgrade Forge", link, forge=True)
    folder = _start_fix(repo, client)
    done = repo.forge("doctor", "--fix", cwd=folder)
    assert _row(f"doctor couldn't write {SKILL}: {SKILL} leads outside this repo, so Forge won't "
                "write through it; remove that link.") in done.stdout, done.stdout
    assert outside.read_text(encoding="utf-8") == "not the repo's\n"


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
    assert _row(f"main now pins Forge v99.0.0, not the installed {version}, so doctor started no "
                "fix for Forge's files.", "git pull --ff-only, then forge doctor --fix") in done.stdout, (
        done.stdout)
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

    # Staged by hand, with the working copy back to sync's: still held, and the index kept.
    _old_hosts(repo, client)  # so the fix has something else to hold
    _land(repo, client, "Upgrade Forge", lambda folder: _set(folder, SKILL, "Older skill\n"),
          forge=True)
    (client / SKILL).write_text("Our skill\n", encoding="utf-8")
    repo.git("add", SKILL, cwd=client)
    (client / SKILL).write_text(wanted[SKILL], encoding="utf-8")
    index = repo.git("diff", "--cached", cwd=client)
    done = repo.forge("doctor", "--fix", cwd=client)
    assert row in done.stdout, done.stdout
    assert repo.git("diff", "--cached", cwd=client) == index
    assert SKILL not in _in(repo, client, "fix/forge-files")
    # A second run finds the fix current, and the staged edit still keeps its row.
    again = repo.forge("doctor", "--fix", cwd=client)
    assert "Doctor's fix forge-files holds Forge's files" in again.stdout, again.stdout
    assert row in again.stdout and repo.git("diff", "--cached", cwd=client) == index


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


def _ui_client(repo, gh, tmp_path, monkeypatch) -> Path:
    client = _client(repo, gh, tmp_path, monkeypatch)
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


def _the_ui_skills_check_covers_each_installed_host(repo, gh, tmp_path, monkeypatch, codex):
    client = _ui_client(repo, gh, tmp_path, monkeypatch)
    if codex:
        _executable(repo.bin / "codex", "#!/bin/sh\n")
    done = repo.forge("doctor", cwd=client)
    for name in ("impeccable", "emil-design-eng"):
        assert (f"- {name} is required for UI work but isn't installed where the codex worker "
                "reads skills.\n" in done.stdout) == codex, done.stdout
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


SHELL = pytest.mark.skipif(os.name == "nt", reason="shell scripts, file modes and links")


def _cases(*cases) -> list:
    """Each case, once per value it takes, named after the case and the value."""
    return [pytest.param(case, value, marks=marks, id=case.__name__.strip("_") + (
                f"[{value}]" if value is not None else "")) for case, values, marks in cases
            for value in values]


@pytest.mark.parametrize("case, value", _cases(
    (_on_the_default_branch_one_fix_holds_both_hosts_files, [None], ()),
    (_codex_workers_under_claude_code_repair_both_hosts, [None], ()),
    (_on_a_fix_branch_the_files_are_written_in_place, [None], ()),
    (_a_failed_pin_install_writes_nothing, [None], SHELL),
    (_a_fix_already_named_forge_files_gets_a_suffix, [None], ()),
    (_a_file_sync_wants_empty_is_removed, [None], ()),
    (_a_stale_doctor_fix_is_left_alone_and_a_new_one_starts,
     ["the default branch changed the test command", "its forge.toml was edited"], ()),
    (_nothing_differing_leaves_no_fix_behind, [None], ()),
    (_a_fix_holds_the_repaired_file_and_the_held_one_keeps_its_row, [None], ()),
    (_a_commit_a_git_hook_refuses_leaves_no_fix, [False, True], SHELL),
    (_a_file_the_system_wont_write, [None], SHELL),
    (_a_link_that_leads_outside_the_repo, [None], SHELL),
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
    (_in_forges_own_repo_history_holds_nothing_back, [None], ()),
    (_the_ui_skills_check_covers_each_installed_host, [True, False], SHELL),
    (_signing_in_to_github_stays_a_plain_step, [None], ()),
    (_exit_codes, [None], SHELL)))
def test_5_doctor_never_overwrites_a_change_made_by_hand(repo, gh, tmp_path, monkeypatch, case,
                                                        value):
    case(repo, gh, tmp_path, monkeypatch, value)
