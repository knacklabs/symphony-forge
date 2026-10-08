"""forge.doctor preserves hand changes with a fixed number of real git processes.

The logger delegates every command to git; only external tools use the existing fakes.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import _install
from test_doctor_fix_files import (SKILL, _client, _folder_of, _land, _old_hosts, _pin,
                                   _set, _start_fix)
from test_setup import _autoreview, _version

STORY = "fix-forge-doctor-fix-checks-every-forge-file"


def _git_log(repo, tmp_path, monkeypatch):
    real_git = shutil.which("git")
    assert real_git
    log = tmp_path / "git-calls.jsonl"
    folder = tmp_path / "counted-git"
    folder.mkdir()
    _install(folder, "git", f"""#!{sys.executable}
import json, subprocess, sys
with open({json.dumps(str(log))}, "a", encoding="utf-8") as calls:
    calls.write(json.dumps(sys.argv[1:]) + "\\n")
sys.exit(subprocess.call([{json.dumps(real_git)}, *sys.argv[1:]]))
""")
    monkeypatch.setenv("PATH", f"{folder}{os.pathsep}{os.environ['PATH']}")
    return log


def _adopted_client(repo, gh, tmp_path, monkeypatch, adoption):
    if adoption == "new init":
        client = _client(repo, gh, tmp_path, monkeypatch)
    else:
        client = repo.path
        shutil.copytree(Path(__file__).parent / "fixtures/doctor-v1.2.2", client,
                        dirs_exist_ok=True)
        repo.git("add", "-A")
        repo.git("commit", "-qm", "Adopt Forge")
        repo.git("push", "-q", "origin", "main")
        _land(repo, client, "Upgrade Forge", lambda folder: _set(
            folder, "forge.toml", _pin((folder / "forge.toml").read_text(encoding="utf-8"),
                                     _version(repo))))
        gh.respond("auth", "status")
        gh.respond("api", stdout="{}")
        _autoreview(tmp_path, monkeypatch)
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
        monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex-home"))
        _install(repo.bin, "uv", f"#!{sys.executable}\nimport sys\nsys.exit(1)\n")
    return client


@pytest.mark.parametrize("adoption", ["new init", "previous release"])
def test_1_doctor_fix_batches_git_checks_without_overwriting_hand_changes(
        repo, gh, tmp_path, monkeypatch, adoption):
    # Independent contract: process cost stays fixed as drift grows, while git still
    # determines which committed, staged and unstaged edits doctor must leave alone.
    client = _adopted_client(repo, gh, tmp_path, monkeypatch, adoption)
    folder = _start_fix(repo, client)
    synced = repo.forge("sync", cwd=folder)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    repo.git("add", "-A", cwd=folder)
    repo.git("commit", "--allow-empty", "-qm", "Bring generated files up to date", cwd=folder)
    generated = sorted(path.relative_to(folder).as_posix()
                       for path in (folder / ".codex" / "skills").rglob("*.md"))
    assert len(generated) > 5
    log = _git_log(repo, tmp_path, monkeypatch)
    counts = []
    for paths in ([SKILL], [SKILL, *generated]):
        for rel in paths:
            _set(folder, rel, "Our instructions.\n")
        repo.git("add", "--", *paths, cwd=folder)
        repo.git("commit", "-qm", "Keep our instructions", cwd=folder)
        unstaged, staged = ".claude/skills/forge/standards.md", ".claude/skills/forge/fde.md"
        _set(folder, unstaged, "Our uncommitted standards.\n")
        _set(folder, staged, "Our staged guidance.\n")
        repo.git("add", "--", staged, cwd=folder)
        log.write_text("", encoding="utf-8")
        done = repo.forge("doctor", "--fix", cwd=folder)
        calls = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
        assert "was changed by hand (Keep our instructions), so doctor won't overwrite it" in done.stdout, done.stdout + done.stderr
        for rel in paths:
            assert (folder / rel).read_text(encoding="utf-8") == "Our instructions.\n"
        for rel, text in ((unstaged, "Our uncommitted standards.\n"),
                          (staged, "Our staged guidance.\n")):
            assert f"{rel} has changes not committed yet, so doctor won't overwrite it" in done.stdout
            assert (folder / rel).read_text(encoding="utf-8") == text
        counts.append(calls)
        repo.git("restore", "--staged", "--worktree", "--", unstaged, staged, cwd=folder)
    for calls in counts:
        assert sum(args[0] == "status" and "--" in args for args in calls) == 1
        assert sum(args[0] == "log" and "--" in args for args in calls) == 1
    assert len(counts[0]) == len(counts[1]), [len(calls) for calls in counts]


def test_2_doctor_fix_reuses_git_checks_when_creating_its_repair_checkout(
        repo, gh, tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_NOW", "2026-10-04T09:00:00+00:00")
    client = _client(repo, gh, tmp_path, monkeypatch)
    _old_hosts(repo, client)
    before = repo.git("rev-parse", "HEAD", cwd=client)
    log = _git_log(repo, tmp_path, monkeypatch)

    done = repo.forge("doctor", "--fix", cwd=client)

    calls = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert "- Fixed: wrote 2 of Forge's files in fix forge-files-20261004-0900." in done.stdout, done.stdout + done.stderr
    assert repo.git("rev-parse", "HEAD", cwd=client) == before
    folder = _folder_of(repo, client, "fix/forge-files-20261004-0900")
    for rel in (".claude/settings.json", ".codex/hooks.json"):
        assert (client / rel).read_text(encoding="utf-8") == '{"hooks": {}}\n'
        assert json.loads((folder / rel).read_text(encoding="utf-8"))["hooks"]
    assert sum(args[0] == "status" and "--" in args for args in calls) == 1
    assert sum(args[0] == "log" and "--" in args for args in calls) == 1


@pytest.mark.parametrize("adoption", ["new init", "previous release"])
@pytest.mark.parametrize("branch", ["default", "fix"])
def test_4_doctor_fix_batches_separately_landed_hand_edits(
        repo, gh, tmp_path, monkeypatch, adoption, branch):
    # Land each hand edit independently: each last-change commit needs its own pin
    # classification, unlike the earlier test's single unlanded commit.
    client = _adopted_client(repo, gh, tmp_path, monkeypatch, adoption)
    synced = _start_fix(repo, client, "Prepare current generated files")
    done = repo.forge("sync", cwd=synced)
    assert done.returncode == 0, done.stdout + done.stderr
    generated = sorted(path.relative_to(synced).as_posix()
                       for path in (synced / ".codex" / "skills").rglob("*.md"))
    assert len(generated) > 5
    current = {path.relative_to(synced).as_posix(): path.read_text(encoding="utf-8")
               for directory in (".codex", ".claude", ".github", ".forge")
               for path in (synced / directory).rglob("*") if path.is_file()}
    for name in ("AGENTS.md", "CLAUDE.md", ".gitattributes"):
        if (synced / name).exists():
            current[name] = (synced / name).read_text(encoding="utf-8")
    current["forge.toml"] = (synced / "forge.toml").read_text(encoding="utf-8") + "\n# Client guidance: café\n"
    _land(repo, client, "Keep our first instructions", lambda folder: (
        [_set(folder, rel, text) for rel, text in current.items()],
        _set(folder, generated[0], "Our instructions.\n")))
    folder = client if branch == "default" else _start_fix(repo, client)
    log = _git_log(repo, tmp_path, monkeypatch)
    counts = []
    for paths in (generated[:1], generated):
        for rel in paths[1:]:
            _land(repo, client, f"Keep our instructions in {rel}",
                  lambda clone, rel=rel: _set(clone, rel, "Our instructions.\n"))
        if branch == "fix":
            repo.git("merge", "-q", "--no-edit", "origin/main", cwd=folder)
        log.write_text("", encoding="utf-8")
        done = repo.forge("doctor", "--fix", cwd=folder)
        calls = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
        for rel in paths:
            subject = ("Keep our first instructions" if rel == generated[0]
                       else f"Keep our instructions in {rel}")
            assert f"{rel} was changed by hand ({subject}), so doctor won't overwrite it" in done.stdout, done.stdout + done.stderr
            assert (folder / rel).read_text(encoding="utf-8") == "Our instructions.\n"
        counts.append(calls)
    for calls in counts:
        assert sum(args[0] == "status" and "--" in args for args in calls) == 1
        assert sum(args[0] == "log" and "--" in args for args in calls) == 1
    assert len(counts[0]) == len(counts[1]), [len(calls) for calls in counts]


@pytest.mark.parametrize("resolution", ["keep main", "new value"])
def test_3_doctor_fix_preserves_each_files_last_hand_change_through_a_merge(
        repo, gh, tmp_path, monkeypatch, resolution):
    client = _client(repo, gh, tmp_path, monkeypatch)
    other_skill = ".codex/skills/forge/SKILL.md"

    def merged_hand_changes(folder):
        def date(day):
            for name in ("GIT_AUTHOR_DATE", "GIT_COMMITTER_DATE"):
                monkeypatch.setenv(name, f"2026-10-{day:02d}T09:00:00+00:00")
        repo.git("checkout", "-qb", "fix/side-instructions", cwd=folder)
        _set(folder, SKILL, "Side instructions.\n")
        _set(folder, other_skill, "Side instructions.\n")
        date(3)
        repo.git("commit", "-qam", "Keep side instructions", cwd=folder)
        repo.git("checkout", "-q", "main", cwd=folder)
        _set(folder, SKILL, "Main instructions.\n")
        date(2)
        repo.git("commit", "-qam", "Keep main instructions", cwd=folder)
        merged = subprocess.run(["git", "merge", "--no-commit", "fix/side-instructions"],
                                cwd=folder, capture_output=True, text=True, encoding="utf-8")
        assert merged.returncode == 1 and "CONFLICT" in merged.stdout, merged.stdout + merged.stderr
        _set(folder, SKILL, "Main instructions.\n" if resolution == "keep main" else "Merged instructions.\n")
        date(4)

    _land(repo, client, "Resolve instructions", merged_hand_changes)
    folder = _start_fix(repo, client)
    expected = {SKILL: ("Keep main instructions", "Main instructions.\n")
                if resolution == "keep main" else ("Resolve instructions", "Merged instructions.\n"),
                other_skill: ("Keep side instructions", "Side instructions.\n")}
    # Independent oracle: the prior command selected the most recent commit separately
    # for each path; a bulk history must retain that same merge-parent selection.
    for rel, (subject, _) in expected.items():
        assert repo.git("log", "-1", "--format=%s", "HEAD", "--", rel, cwd=folder) == subject
    log = _git_log(repo, tmp_path, monkeypatch)

    done = repo.forge("doctor", "--fix", cwd=folder)

    calls = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    for rel, (subject, text) in expected.items():
        assert f"{rel} was changed by hand ({subject}), so doctor won't overwrite it" in done.stdout, done.stdout + done.stderr
        assert (folder / rel).read_text(encoding="utf-8") == text
    assert sum(args[0] == "log" and "--" in args for args in calls) == 1
