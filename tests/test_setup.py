"""Setup: forge init, forge sync and forge doctor, and the host hooks they generate.

Each test is named test_<criterion>_<rule> after the spec's acceptance criterion it proves.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

# The adapter files the spec lists for both hosts, plus the generated workflow.
LISTED = {"AGENTS.md", "CLAUDE.md", ".claude/settings.json", ".claude/skills/forge/SKILL.md",
          ".codex/hooks.json", ".codex/config.toml", ".codex/skills/forge/SKILL.md",
          ".github/workflows/forge.yml"}
SCAFFOLD = {"forge.toml", "docs/product/BRIEF.md", "docs/product/DISCOVERY.md",
            "docs/specs/README.md", "docs/decisions/README.md", "plans/roadmap.json"}
OLD_FORGE_HOOK = "sh -c '\"$(git rev-parse --show-toplevel)/forge\" hook stop_continue || exit 2' || exit 2"


def _executable(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)


def _version(repo) -> str:
    return repo.forge("--version").stdout.split()[-1]


def _on_a_branch_with_forge_toml(repo) -> None:
    repo.git("checkout", "-q", "-b", "fix/adapters")
    repo.write("forge.toml", f'version = "{_version(repo)}"\ntest = "make check"\n'
                             'checks = ["tests", "forge-pr-check"]\n')


def _hook_commands(top: Path) -> list[tuple[str, str, str]]:
    """(host file, event, command) for every command in the generated host hook files."""
    found = []
    for rel in (".claude/settings.json", ".codex/hooks.json"):
        hooks = json.loads((top / rel).read_text(encoding="utf-8"))["hooks"]
        found += [(rel, event, hook["command"]) for event, groups in hooks.items()
                  for group in groups for hook in group["hooks"]]
    return found


def _hooks_folder(top: Path) -> Path:
    return Path(subprocess.run(["git", "rev-parse", "--path-format=absolute", "--git-path", "hooks"],
                               cwd=top, capture_output=True, text=True, check=True).stdout.strip())


def test_28_sync(repo):
    _on_a_branch_with_forge_toml(repo)
    repo.write("AGENTS.md", "# Our agents\n\nOur own rules.\n")
    repo.write(".claude/settings.json", json.dumps({
        "permissions": {"allow": ["Bash(ls)"]},
        "hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command",
                                                                  "command": "our-guard"}]}],
                  "Stop": [{"hooks": [{"type": "command", "command": OLD_FORGE_HOOK}]}]}}))
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "Our own files")

    first = repo.forge("sync")
    assert first.returncode == 0, first.stderr
    # Exactly the listed adapter files, for both hosts, and nothing else.
    changed = {line.split(None, 1)[1] for line in
               repo.git("status", "--porcelain", "-uall").splitlines()}
    assert changed == LISTED
    for rel in LISTED:
        assert f"Wrote {rel}" in first.stdout
    hooks = _hooks_folder(repo.path)
    for shim in ("pre-commit", "pre-push"):
        assert f"exec forge hook {shim}" in (hooks / shim).read_text(encoding="utf-8")

    # The workflow runs the test command as tests, plus forge-pr-check from the base branch.
    workflow = (repo.path / ".github/workflows/forge.yml").read_text(encoding="utf-8")
    tests_job, check_job = workflow.split("\n  tests:\n")[1].split("\n  forge-pr-check:\n")
    assert '- run: "make check"' in tests_job
    assert "forge hook pr-check" in check_job
    assert "pull_request_target" in workflow
    assert "ref: ${{ github.event.pull_request.base.sha }}" in check_job

    # A second run changes nothing.
    before = {rel: (repo.path / rel).read_bytes() for rel in LISTED}
    shims = {shim: (hooks / shim).read_bytes() for shim in ("pre-commit", "pre-push")}
    second = repo.forge("sync")
    assert second.returncode == 0, second.stderr
    assert second.stdout.startswith("Nothing to change")
    assert before == {rel: (repo.path / rel).read_bytes() for rel in LISTED}
    assert shims == {shim: (hooks / shim).read_bytes() for shim in ("pre-commit", "pre-push")}

    # Text outside the AGENTS.md block and settings keys that aren't Forge's are kept.
    agents = (repo.path / "AGENTS.md").read_text(encoding="utf-8")
    assert agents.startswith("# Our agents\n\nOur own rules.\n")
    assert agents.count("<!-- forge:begin -->") == agents.count("<!-- forge:end -->") == 1
    settings = json.loads((repo.path / ".claude/settings.json").read_text(encoding="utf-8"))
    assert settings["permissions"] == {"allow": ["Bash(ls)"]}
    commands = [hook["command"] for groups in settings["hooks"].values() for group in groups
                for hook in group["hooks"]]
    assert "our-guard" in commands
    assert OLD_FORGE_HOOK not in commands and "Stop" not in settings["hooks"]


def _fresh_client(repo, gh, tmp_path: Path) -> tuple[Path, subprocess.CompletedProcess[str]]:
    """A repo with no commits and an empty origin, set up with forge init."""
    client, remote = tmp_path / "client", tmp_path / "client.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(client)], check=True)
    repo.git("remote", "add", "origin", str(remote), cwd=client)
    gh.respond("api", stdout="{}")
    return client, repo.forge("init", cwd=client)


def _host_hook_forge(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failing: str = "") -> Path:
    """A forge that the host hook commands find first on PATH. It logs each call and its payload,
    and fails the call named by failing. Doctor itself still runs the real forge."""
    folder, log = tmp_path / "hook-forge", tmp_path / "hook-calls.log"
    folder.mkdir()
    _executable(folder / "forge", f'#!/bin/sh\n{{ echo "$*"; cat; echo; }} >> "{log.as_posix()}"\n'
                                  f'[ "$*" != "{failing}" ]\n')
    monkeypatch.setenv("PATH", f"{folder}{os.pathsep}{os.environ['PATH']}")
    return log


@pytest.mark.parametrize("case, rows", [
    ("fresh", ()),
    ("missing tool", ("claude is not installed or not on PATH.",)),
    ("version mismatch", ("but this repo pins v0.0.1.",)),
    ("missing hook shims", ("The git hooks that check each commit and push aren't installed.",)),
    ("host hook fails", ("The PreToolUse hook in .claude/settings.json fails with exit code 2",
                         "The PreToolUse hook in .codex/hooks.json fails with exit code 2")),
    ("adapter drift", (".codex/config.toml differs from what forge sync writes",)),
    ("no checks or test", ("forge.toml names no checks", "forge.toml has no test command.")),
    ("workflow skips test", ("The tests check in .github/workflows/forge.yml doesn't run "
                             "forge.toml's test command.",)),
])
def test_29_doctor(repo, gh, tmp_path, monkeypatch, case, rows):
    client, init = _fresh_client(repo, gh, tmp_path)
    assert init.returncode == 0, init.stderr
    gh.respond("auth", "status")
    if case == "missing tool":  # no claude anywhere on PATH, even on a machine that has it
        monkeypatch.setenv("PATH", os.pathsep.join(
            folder for folder in os.environ["PATH"].split(os.pathsep)
            if not shutil.which("claude", path=folder)))
    else:
        _executable(repo.bin / "claude", "#!/bin/sh\n")
        if os.name == "nt":
            (repo.bin / "claude.cmd").write_text("@exit /b 0\n", encoding="utf-8")
    log = _host_hook_forge(tmp_path, monkeypatch, "hook deny" if case == "host hook fails" else "")
    toml = client / "forge.toml"
    edit = {"version mismatch": (r'version = ".*"', 'version = "v0.0.1"'),
            "no checks or test": (r'(?s)test = .*?\nchecks = .*?\n', 'test = ""\nchecks = []\n'),
            "workflow skips test": (r"test = .*", 'test = "make test"')}.get(case)
    if edit:
        toml.write_text(re.sub(*edit, toml.read_text(encoding="utf-8"), count=1), encoding="utf-8")
    if case == "missing hook shims":
        (_hooks_folder(client) / "pre-push").unlink()
    if case == "adapter drift":
        (client / ".codex/config.toml").write_text("[features]\n", encoding="utf-8")

    done = repo.forge("doctor", cwd=client)

    if case == "fresh":
        # A repo just made by forge init: one first commit holding the scaffold and the sync
        # output, pushed, with forge.toml pinned and branch protection applied and reported.
        assert repo.git("rev-list", "--count", "HEAD", cwd=client) == "1"
        assert set(repo.git("ls-tree", "-r", "--name-only", "HEAD", cwd=client).splitlines()) == (
            LISTED | SCAFFOLD)
        assert "refs/heads/main" in repo.git("ls-remote", "origin", cwd=client)
        assert f'version = "{_version(repo)}"' in toml.read_text(encoding="utf-8")
        assert "Branch protection is on for main" in init.stdout
        [call] = [args for args in gh.calls() if args[0] == "api"]
        assert call[:4] == ["api", "--method", "PUT", "repos/{owner}/{repo}/branches/main/protection"]
        rule = json.loads(Path(call[call.index("--input") + 1]).read_text(encoding="utf-8"))
        assert rule["required_status_checks"]["contexts"] == ["tests", "forge-pr-check"]
        assert rule["required_pull_request_reviews"] is not None and rule["enforce_admins"] is True

        assert done.returncode == 0, done.stdout + done.stderr
        assert "Everything checks out" in done.stdout
        # Each host hook command ran, with a payload.
        calls = log.read_text(encoding="utf-8")
        for hook in ("context", "deny", "approval"):
            assert calls.count(f"hook {hook}\n") == 2, calls
        assert calls.count('"hook_event_name"') == 6
    else:
        assert done.returncode == 1
        for row in rows:
            assert row in done.stdout, done.stdout
        assert "\n  Fix: " in done.stdout
        assert "Next: forge doctor" in done.stderr


def test_38_host_hooks_fail_closed(repo, claude_payload, codex_payload, tmp_path):
    _on_a_branch_with_forge_toml(repo)
    assert repo.forge("sync").returncode == 0
    # forge can't launch: the one on PATH names an interpreter that doesn't exist.
    broken = tmp_path / "broken"
    broken.mkdir()
    _executable(broken / "forge", "#!/nonexistent/forge-interpreter\n")
    env = {**os.environ, "PATH": f"{broken}{os.pathsep}{os.environ['PATH']}"}
    tools = {"PreToolUse": ("Bash", {"command": "ls"}),
             "PostToolUse": ("ExitPlanMode", {"plan": "A plan"})}

    commands = _hook_commands(repo.path)
    assert len(commands) == 6
    for rel, event, command in commands:
        build = claude_payload if rel.startswith(".claude") else codex_payload
        tool, tool_input = tools.get(event, (None, None))
        if rel.startswith(".codex") and event == "PostToolUse":
            tool = "request_user_input"
        payload = build(event, tool, tool_input)
        done = subprocess.run(["sh", "-c", command], input=json.dumps(payload), env=env,
                              cwd=repo.path, capture_output=True, text=True)
        assert done.returncode == 2, (rel, event, done.stderr)
