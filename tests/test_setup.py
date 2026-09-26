"""Setup: forge init, forge sync and forge doctor, and the host hooks they generate.

Each test is named test_<criterion>_<rule> after the spec's acceptance criterion it proves.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest

from test_close import PIN

# The adapter files the spec lists for both hosts, plus the generated workflow and the
# test-audit skill with its licence notice.
LISTED = {"AGENTS.md", "CLAUDE.md", ".claude/settings.json", ".claude/skills/forge/SKILL.md",
          ".claude/skills/remote-approval/SKILL.md", ".codex/hooks.json", ".codex/config.toml", ".codex/skills/forge/SKILL.md",
          ".claude/skills/forge/fde.md", ".codex/skills/forge/fde.md", ".github/workflows/forge.yml",
          *(f"{host}/skills/test-audit/{name}" for host in (".claude", ".codex")
            for name in ("SKILL.md", "NOTICE.md"))}
SCAFFOLD = {"forge.toml", "docs/product/BRIEF.md", "docs/product/DISCOVERY.md",
            "docs/specs/README.md", "docs/decisions/README.md", "plans/roadmap.json"}
NO_IMPECCABLE = ("impeccable, the one UI skill Forge requires, isn't installed where the claude "
                 "worker reads skills.\n  Fix: npx skills add pbakaus/impeccable -g\n")
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


def _autoreview(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pin: str = PIN) -> None:
    """An Autoreview helper stamped with this version, where forge doctor and close find it."""
    skill = tmp_path / "autoreview-helper"
    (skill / "scripts").mkdir(parents=True)
    (skill / "scripts" / "autoreview").write_text("", encoding="utf-8")
    (skill / ".upstream-sha").write_text(pin + "\n", encoding="utf-8")
    monkeypatch.setenv("AUTOREVIEW", str(skill / "scripts" / "autoreview"))


def _stub_forge(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failing: str = "") -> Path:
    """A forge that hook commands (host and git) find first on PATH. It logs each call and its
    input, and fails the call named by failing. The tests' own forge calls still run the real one."""
    folder, log = tmp_path / "hook-forge", tmp_path / "hook-calls.log"
    folder.mkdir()
    _executable(folder / "forge", f'#!/bin/sh\n{{ echo "$*"; cat; echo; }} >> "{log.as_posix()}"\n'
                                  f'[ "$*" != "{failing}" ]\n')
    monkeypatch.setenv("PATH", f"{folder}{os.pathsep}{os.environ['PATH']}")
    return log


def test_28_sync(repo, tmp_path, monkeypatch):
    _on_a_branch_with_forge_toml(repo)
    repo.write("AGENTS.md", "# Our agents\n\nOur own rules.\n")
    repo.write(".claude/settings.json", json.dumps({
        "permissions": {"allow": ["Bash(ls)"]},
        "hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command",
                                                                  "command": "our-guard"}]}],
                  "Stop": [{"hooks": [{"type": "command", "command": OLD_FORGE_HOOK}]}]}}))
    repo.write(".codex/config.toml", 'model = "o3"\n\n[features]\nweb_search = true\n')
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "Our own files")
    # The repo's own git hooks, from before Forge; each logs its name, arguments and input.
    hooks = _hooks_folder(repo.path)
    ours = tmp_path / "our-hooks.log"
    for name in ("pre-commit", "pre-push"):
        _executable(hooks / name, f'#!/bin/sh\n{{ echo "{name} $*"; cat; }} >> "{ours.as_posix()}"\n')

    first = repo.forge("sync")
    assert first.returncode == 0, first.stderr
    # Exactly the listed adapter files, for both hosts, and nothing else.
    changed = {line.split(None, 1)[1] for line in
               repo.git("status", "--porcelain", "-uall").splitlines()}
    assert changed == LISTED
    for rel in LISTED:
        assert f"Wrote {rel}" in first.stdout
    for shim in ("pre-commit", "pre-push"):
        assert f"exec forge hook {shim}" in (hooks / shim).read_text(encoding="utf-8")

    # The remote-approval skill starts a plainly named Remote Control session in a chosen checkout.
    skill = (repo.path / ".claude/skills/remote-approval/SKILL.md").read_text(encoding="utf-8")
    assert re.search(r'^cd <checkout> && exec claude remote-control --name "<name>"$', skill, re.M)
    assert "no IDs, hashes or branch names" in skill and "under about 30 characters" in skill

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
    # The repo's own Codex settings stay; only Codex's project hooks are switched on.
    config = tomllib.loads((repo.path / ".codex/config.toml").read_text(encoding="utf-8"))
    assert config == {"model": "o3", "features": {"web_search": True, "hooks": True}}

    # The repo's own git hooks still run first, with the same arguments and input, then Forge's.
    calls = _stub_forge(tmp_path, monkeypatch)
    repo.git("commit", "-q", "--allow-empty", "-m", "Checked by both hooks")
    repo.git("push", "-q", "origin", "fix/adapters")
    ran = ours.read_text(encoding="utf-8").splitlines()
    assert ran[0] == "pre-commit " and ran[1].startswith("pre-push origin ")
    [pushed] = [line for line in ran if line.startswith("refs/heads/fix/adapters ")]
    forge_calls = calls.read_text(encoding="utf-8")
    assert forge_calls.startswith(f"hook pre-commit\n\nhook pre-push {ran[1][len('pre-push '):]}\n"
                                  f"{pushed}\n"), forge_calls
    # ... and when one of them fails, so does the commit, before Forge's hook runs.
    _executable(hooks / "pre-commit.pre-forge", "#!/bin/sh\nexit 1\n")
    stopped = subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", "Stopped"],
                             cwd=repo.path, capture_output=True, text=True)
    assert stopped.returncode != 0
    assert calls.read_text(encoding="utf-8") == forge_calls


def _fresh_client(repo, gh, tmp_path: Path) -> tuple[Path, subprocess.CompletedProcess[str]]:
    """A repo with no commits and an empty origin, set up with forge init."""
    client, remote = tmp_path / "client", tmp_path / "client.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(client)], check=True)
    repo.git("remote", "add", "origin", str(remote), cwd=client)
    gh.respond("api", stdout="{}")
    # What GitHub answers for a branch with no protection yet.
    gh.respond("api", "repos/{owner}/{repo}/branches/main/protection", exit=1,
               stdout='{"message":"Branch not protected","status":"404"}')
    return client, repo.forge("init", cwd=client)


@pytest.mark.parametrize("case, rows", [
    ("fresh", ()),
    ("missing tool", ("claude is not installed or not on PATH.",)),
    ("version mismatch", ("but this repo pins v0.0.1.",)),
    ("missing hook shims", ("The git hooks that check each commit and push aren't installed.",)),
    ("forge's own repo without git hooks", ()),
    ("host hook fails", ("The PreToolUse hook in .claude/settings.json fails with exit code 2",
                         "The PreToolUse hook in .codex/hooks.json fails with exit code 2")),
    ("adapter drift", (".codex/config.toml differs from what forge sync writes",)),
    ("remote-approval skill drift",
     (".claude/skills/remote-approval/SKILL.md differs from what forge sync writes",)),
    ("tampered hook command", (".claude/settings.json differs from what forge sync writes",)),
    ("no checks or test", (
        "forge.toml names no checks, so close has nothing to wait for.\n"
        "  Fix: ask your agent to set checks in forge.toml\n",
        "forge.toml has no test command.\n"
        "  Fix: ask your agent to set test in forge.toml, then run forge sync\n")),
    ("workflow skips test", ("The tests check in .github/workflows/forge.yml doesn't run "
                             "forge.toml's test command.",)),
    ("codex doesn't trust the project", ()),
    ("no impeccable", (NO_IMPECCABLE,)),
    ("impeccable only for codex", (NO_IMPECCABLE,)),
    ("impeccable only in the repo's .agents", (NO_IMPECCABLE,)),
    ("impeccable in CLAUDE_CONFIG_DIR", ()),
])
def test_29_doctor(repo, gh, tmp_path, monkeypatch, case, rows):
    client, init = _fresh_client(repo, gh, tmp_path)
    assert init.returncode == 0, init.stderr
    gh.respond("auth", "status")
    _autoreview(tmp_path, monkeypatch)
    home = tmp_path / "home"  # so skills installed on this machine don't count
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    codex_home = tmp_path / "codex"  # the user's Codex config, which records trusted projects
    codex_home.mkdir()
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    claude_config = tmp_path / "claude-config"  # $CLAUDE_CONFIG_DIR, read instead of ~/.claude
    if case == "impeccable in CLAUDE_CONFIG_DIR":
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(claude_config))
    else:
        monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    # impeccable where the configured worker (claude, from forge init) reads skills, or only
    # where Codex reads them, or only in the repo's .agents (Claude Code never reads that), or
    # nowhere.
    skills = {"no impeccable": None, "impeccable only for codex": codex_home,
              "impeccable only in the repo's .agents": client / ".agents",
              "impeccable in CLAUDE_CONFIG_DIR": claude_config}.get(case, home / ".claude")
    if skills:
        skill = skills / "skills" / "impeccable" / "SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text("---\nname: impeccable\n---\n", encoding="utf-8")
    if case != "codex doesn't trust the project":
        (codex_home / "config.toml").write_text(
            f'[projects.{json.dumps(str(client))}]\ntrust_level = "trusted"\n', encoding="utf-8")
    if case == "missing tool":  # no claude anywhere on PATH, even on a machine that has it
        monkeypatch.setenv("PATH", os.pathsep.join(
            folder for folder in os.environ["PATH"].split(os.pathsep)
            if not shutil.which("claude", path=folder)))
    else:
        _executable(repo.bin / "claude", "#!/bin/sh\n")
        if os.name == "nt":
            (repo.bin / "claude.cmd").write_text("@exit /b 0\n", encoding="utf-8")
    log = _stub_forge(tmp_path, monkeypatch, "hook deny" if case == "host hook fails" else "")
    toml = client / "forge.toml"
    edit = {"version mismatch": (r'version = ".*"', 'version = "v0.0.1"'),
            "no checks or test": (r'(?s)test = .*?\nchecks = .*?\n', 'test = ""\nchecks = []\n'),
            "workflow skips test": (r"test = .*", 'test = "make test"'),
            "forge's own repo without git hooks": ('repo = "client"', 'repo = "forge-source"'),
            }.get(case)
    if edit:
        toml.write_text(re.sub(*edit, toml.read_text(encoding="utf-8"), count=1), encoding="utf-8")
    if case == "forge's own repo without git hooks":  # the workflow installs Forge from its checkout
        repo.git("checkout", "-q", "-b", "fix/own", cwd=client)  # sync refuses on main
        assert repo.forge("sync", cwd=client).returncode == 0
    if case in ("missing hook shims", "forge's own repo without git hooks"):
        (_hooks_folder(client) / "pre-push").unlink()
    if case == "adapter drift":
        (client / ".codex/config.toml").write_text("[features]\n", encoding="utf-8")
    if case == "remote-approval skill drift":
        (client / ".claude/skills/remote-approval/SKILL.md").write_text("old\n", encoding="utf-8")
    marker = tmp_path / "tampered-hook-ran"
    if case == "tampered hook command":  # a Forge-looking hook that also runs something else
        settings = client / ".claude/settings.json"
        data = json.loads(settings.read_text(encoding="utf-8"))
        data["hooks"]["PreToolUse"][0]["hooks"][0]["command"] = (
            f'forge hook deny; echo ran > "{marker.as_posix()}"')
        settings.write_text(json.dumps(data), encoding="utf-8")

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
        # It reads the branch's protection first (a new repo has none), then sets Forge's rule.
        read, call = [args for args in gh.calls() if args[0] == "api"]
        assert read == ["api", "repos/{owner}/{repo}/branches/main/protection"]
        assert call[:4] == ["api", "--method", "PUT", "repos/{owner}/{repo}/branches/main/protection"]
        rule = json.loads(Path(call[call.index("--input") + 1]).read_text(encoding="utf-8"))
        assert rule["required_status_checks"]["checks"] == [{"context": "tests"},
                                                            {"context": "forge-pr-check"}]
        assert rule["required_pull_request_reviews"] is not None and rule["enforce_admins"] is True

        assert done.returncode == 0, done.stdout + done.stderr
        assert done.stdout.startswith("Everything checks out"), done.stdout
        # Each host hook command ran, with a payload.
        calls = log.read_text(encoding="utf-8")
        for hook in ("context", "deny", "approval"):
            assert calls.count(f"hook {hook}\n") == 2, calls
        assert calls.count('"hook_event_name"') == 6
    elif case == "codex doesn't trust the project":
        # Advice, not a failure, and "everything checks out" never hides it.
        assert done.returncode == 0, done.stdout + done.stderr
        assert "- Note: Codex runs this repo's hooks only in a project it trusts" in done.stdout
        assert f'trust_level = "trusted" to {codex_home / "config.toml"}' in done.stdout
        assert "Everything else checks out" in done.stdout
    elif case in ("impeccable in CLAUDE_CONFIG_DIR", "forge's own repo without git hooks"):
        # Forge's own repo runs without the git hooks until the switch, so doctor doesn't ask.
        assert done.returncode == 0, done.stdout + done.stderr
        assert done.stdout.startswith("Everything checks out"), done.stdout
    else:
        assert done.returncode == 1
        for row in rows:
            assert row in done.stdout, done.stdout
        assert "\n  Fix: " in done.stdout
        assert done.stderr.startswith("forge doctor found ") and done.stderr.endswith(
            " problem(s); each row above gives its fix.\nNext: forge doctor\n"), done.stderr
        if case == "tampered hook command":
            # Doctor never ran it; only the untouched Codex deny hook ran.
            assert not marker.exists()
            assert log.read_text(encoding="utf-8").count("hook deny\n") == 1


def test_38_host_hooks_fail_closed(repo, claude_payload, codex_payload, tmp_path):
    _on_a_branch_with_forge_toml(repo)
    assert repo.forge("sync").returncode == 0
    # forge can't launch: the only forge on PATH names an interpreter that doesn't exist. Every
    # other one comes off PATH, because dash (Ubuntu's sh) skips a forge it can't start and runs
    # the next one.
    broken = tmp_path / "broken"
    broken.mkdir()
    _executable(broken / "forge", "#!/nonexistent/forge-interpreter\n")
    path = [folder for folder in os.environ["PATH"].split(os.pathsep)
            if not (Path(folder) / "forge").is_file()]
    env = {**os.environ, "PATH": os.pathsep.join([str(broken), *path])}
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
