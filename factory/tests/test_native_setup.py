"""Codex-only readiness and dual-adapter scaffold regression coverage."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tomllib

import pytest

from test_gates import HARNESS, adopt, existing_repo, git, repo, run  # noqa: F401


def _hook(event: str, source, *, enabled=True, trust="trusted") -> dict:
    from forge_cli.doctor import CODEX_HOOK_CONTRACT

    hook = {
        "eventName": event,
        "sourcePath": str(source),
        "enabled": enabled,
        "trustStatus": trust,
        "command": f"sh -c 'forge{CODEX_HOOK_CONTRACT[event]}'",
        "currentHash": "sha256:trusted-by-codex",
    }
    if event == "preToolUse":
        hook["matcher"] = "Bash|apply_patch|request_user_input"
    elif event == "postToolUse":
        hook["matcher"] = "^request_user_input$"
    elif event == "sessionStart":
        hook["matcher"] = "startup|resume|clear|compact"
    return hook


def test_codex_hook_readiness_requires_exact_enabled_trusted_source(
        repo, tmp_path, monkeypatch):
    from forge_cli import doctor

    config = tmp_path / ".codex" / "hooks.json"
    config.parent.mkdir()
    config.write_text('{"hooks": {}}\n')
    valid = [_hook(event, config) for event in doctor.CODEX_HOOK_EVENTS]
    monkeypatch.setattr(doctor.shutil, "which", lambda name: f"/tools/{name}")
    monkeypatch.setattr(doctor, "_git_worktree_roots", lambda _base: ({tmp_path}, ""))
    monkeypatch.setattr(
        doctor, "_codex_hooks_inventory", lambda _binary, _base: (valid, ""))

    ok, detail = doctor.codex_hook_readiness(tmp_path)
    assert ok and "PATH-based CLI probe does not certify Codex Desktop" in detail

    for matcher in ("*", "", None):
        match_all = [dict(hook) for hook in valid]
        for hook in match_all:
            if hook["eventName"] not in {"preToolUse", "postToolUse", "sessionStart"}:
                continue
            if matcher is None:
                hook.pop("matcher", None)
            else:
                hook["matcher"] = matcher
        monkeypatch.setattr(
            doctor, "_codex_hooks_inventory",
            lambda _binary, _base, hooks=match_all: (hooks, ""),
        )
        assert doctor.codex_hook_readiness(tmp_path)[0]

    for hooks, expected in (
        ([], "did not load hooks from"),
        ([*valid[:-1], _hook("stop", config, trust="untrusted")], "not trusted"),
        ([*valid[:-1], _hook("stop", config, enabled=False)], "disabled"),
        (valid[:-1], "required hooks"),
        ([_hook(event, tmp_path / "other.json") for event in doctor.CODEX_HOOK_EVENTS],
         "did not load hooks from"),
    ):
        monkeypatch.setattr(
            doctor, "_codex_hooks_inventory",
            lambda _binary, _base, hooks=hooks: (hooks, ""),
        )
        assert expected in doctor.codex_hook_readiness(tmp_path)[1]

    wrong = [dict(hook) for hook in valid]
    wrong[0]["command"] = "sh -c 'forge hook unrelated'"
    monkeypatch.setattr(
        doctor, "_codex_hooks_inventory", lambda _binary, _base: (wrong, ""))
    assert "wrong hook command" in doctor.codex_hook_readiness(tmp_path)[1]

    wrong = [dict(hook) for hook in valid]
    next(hook for hook in wrong if hook["eventName"] == "preToolUse")["matcher"] = "Bash"
    monkeypatch.setattr(
        doctor, "_codex_hooks_inventory", lambda _binary, _base: (wrong, ""))
    assert "PreToolUse matcher" in doctor.codex_hook_readiness(tmp_path)[1]

    tools = ("Bash", "apply_patch", "request_user_input")
    config_path = repo / ".codex" / "hooks.json"
    original_config = config_path.read_bytes()
    for missing in tools:
        incomplete = [dict(hook) for hook in valid]
        next(hook for hook in incomplete
             if hook["eventName"] == "preToolUse")["matcher"] = "|".join(
                 tool for tool in tools if tool != missing)
        monkeypatch.setattr(
            doctor, "_codex_hooks_inventory",
            lambda _binary, _base, hooks=incomplete: (hooks, ""),
        )
        document = json.loads(original_config)
        document["hooks"]["PreToolUse"][0]["matcher"] = "|".join(
            tool for tool in tools if tool != missing)
        config_path.write_text(json.dumps(document), encoding="utf-8")
        ready, detail = doctor.codex_hook_readiness(tmp_path)
        code, output = run(repo, "check_dual_runtime.py", str(repo))
        assert not ready and missing in detail, detail
        assert code != 0 and f"route {missing}" in output, output
    config_path.write_bytes(original_config)

    malformed = [dict(hook) for hook in valid]
    next(hook for hook in malformed if hook["eventName"] == "preToolUse")["matcher"] = "["
    monkeypatch.setattr(
        doctor, "_codex_hooks_inventory", lambda _binary, _base: (malformed, ""))
    ready, detail = doctor.codex_hook_readiness(tmp_path)
    assert not ready and "matcher is invalid" in detail

    sources = doctor.CODEX_SESSION_START_SOURCES
    for missing in sources:
        incomplete = [dict(hook) for hook in valid]
        next(hook for hook in incomplete
             if hook["eventName"] == "sessionStart")["matcher"] = "|".join(
                 source for source in sources if source != missing)
        monkeypatch.setattr(
            doctor, "_codex_hooks_inventory",
            lambda _binary, _base, hooks=incomplete: (hooks, ""),
        )
        detail = doctor.codex_hook_readiness(tmp_path)[1]
        assert "SessionStart matcher" in detail and missing in detail


def test_codex_hook_readiness_accepts_only_identical_inherited_worktree_hooks(
        tmp_path, monkeypatch):
    from forge_cli import doctor

    main = tmp_path / "main"
    linked = tmp_path / "linked"
    subprocess.run(["git", "init", "-q", str(main)], check=True)
    subprocess.run(["git", "config", "user.email", "forge@example.invalid"], cwd=main, check=True)
    subprocess.run(["git", "config", "user.name", "Forge Tests"], cwd=main, check=True)
    config = main / ".codex" / "hooks.json"
    config.parent.mkdir()
    config.write_text('{"hooks": {"fixture": true}}\n')
    subprocess.run(["git", "add", "."], cwd=main, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "hooks"], cwd=main, check=True)
    subprocess.run(["git", "worktree", "add", "-q", "-b", "linked", str(linked)],
                   cwd=main, check=True)
    inherited = [_hook(event, config) for event in doctor.CODEX_HOOK_EVENTS]
    monkeypatch.setattr(doctor.shutil, "which", lambda name: f"/tools/{name}")
    monkeypatch.setattr(
        doctor, "_codex_hooks_inventory", lambda _binary, _base: (inherited, ""))

    assert doctor.codex_hook_readiness(linked)[0]

    config.write_text('{"hooks": {"fixture": "diverged"}}\n')
    ok, detail = doctor.codex_hook_readiness(linked)
    assert not ok and "inherited divergent hooks" in detail

    expected = json.loads((HARNESS / ".codex" / "hooks.json").read_text())
    actual = copy.deepcopy(expected)
    expected["hooks"]["PreToolUse"][0]["matcher"] = (
        "Bash|apply_patch|request_user_input"
    )
    actual["hooks"]["PreToolUse"][0]["matcher"] = (
        "Bash|Edit|Write|apply_patch|request_user_input|request_user_input_async"
    )
    (linked / ".codex" / "hooks.json").write_text(json.dumps(expected))
    config.write_text(json.dumps(actual))
    inherited = [_hook(event, config) for event in doctor.CODEX_HOOK_EVENTS]
    next(hook for hook in inherited if hook["eventName"] == "preToolUse")[
        "matcher"
    ] = actual["hooks"]["PreToolUse"][0]["matcher"]
    monkeypatch.setattr(
        doctor, "_codex_hooks_inventory", lambda _binary, _base: (inherited, ""))
    assert doctor.codex_hook_readiness(linked)[0]

    divergent_root = tmp_path / "divergent"
    divergent_config = divergent_root / ".codex" / "hooks.json"
    divergent_config.parent.mkdir(parents=True)
    divergent_source = copy.deepcopy(actual)
    divergent_source["hooks"]["Stop"][0]["hooks"][0]["command"] = "exit 0"
    divergent_config.write_text(json.dumps(divergent_source))
    mixed = inherited + [
        _hook(event, divergent_config) for event in doctor.CODEX_HOOK_EVENTS
    ]
    monkeypatch.setattr(
        doctor, "_git_worktree_roots",
        lambda _base: ({main.resolve(), linked.resolve(), divergent_root.resolve()}, ""),
    )
    monkeypatch.setattr(
        doctor, "_codex_hooks_inventory", lambda _binary, _base: (mixed, ""))
    ok, detail = doctor.codex_hook_readiness(linked)
    assert not ok and str(divergent_config) in detail

    monkeypatch.setattr(
        doctor, "_git_worktree_roots",
        lambda _base: ({main.resolve(), linked.resolve()}, ""),
    )
    monkeypatch.setattr(
        doctor, "_codex_hooks_inventory", lambda _binary, _base: (inherited, ""))
    actual["hooks"]["PreToolUse"][0]["hooks"][0]["command"] = "run something else"
    config.write_text(json.dumps(actual))
    ok, detail = doctor.codex_hook_readiness(linked)
    assert not ok and "inherited divergent hooks" in detail


def test_inherited_hook_compatibility_is_fail_closed():
    from forge_cli import doctor

    expected = json.loads((HARNESS / ".codex" / "hooks.json").read_text())

    def encoded(document, *, pretty=False):
        return json.dumps(
            document, indent=2 if pretty else None, sort_keys=pretty,
        ).encode()

    # Formatting and key order are not semantic differences.
    assert doctor._compatible_hook_source(
        encoded(expected, pretty=True), encoded(expected),
    )

    inherited = copy.deepcopy(expected)
    inherited["hooks"]["PreToolUse"][0]["matcher"] = (
        "Bash|Edit|Write|apply_patch|request_user_input|request_user_input_async"
    )
    expected["hooks"]["PreToolUse"][0]["matcher"] = (
        "Bash|apply_patch|request_user_input"
    )
    assert doctor._compatible_hook_source(encoded(expected), encoded(inherited))

    divergent = []

    missing_alias = copy.deepcopy(inherited)
    missing_alias["hooks"]["PreToolUse"][0]["matcher"] = "Bash|apply_patch"
    divergent.append(missing_alias)

    for matcher in ("Bash|.*|apply_patch|request_user_input", "(?:Bash|Edit)"):
        regex_matcher = copy.deepcopy(inherited)
        regex_matcher["hooks"]["PreToolUse"][0]["matcher"] = matcher
        divergent.append(regex_matcher)

    extra_registration = copy.deepcopy(inherited)
    extra_registration["hooks"]["PreToolUse"].append(
        copy.deepcopy(extra_registration["hooks"]["PreToolUse"][0])
    )
    divergent.append(extra_registration)

    changed_post_matcher = copy.deepcopy(inherited)
    changed_post_matcher["hooks"]["PostToolUse"][0]["matcher"] = ".*"
    divergent.append(changed_post_matcher)

    changed_command = copy.deepcopy(inherited)
    changed_command["hooks"]["Stop"][0]["hooks"][0]["command"] = "exit 0"
    divergent.append(changed_command)

    changed_metadata = copy.deepcopy(inherited)
    changed_metadata["hooks"]["Stop"][0]["hooks"][0]["timeout"] = 31
    divergent.append(changed_metadata)

    extra_event = copy.deepcopy(inherited)
    extra_event["hooks"]["Unexpected"] = []
    divergent.append(extra_event)

    extra_top_level = copy.deepcopy(inherited)
    extra_top_level["unexpected"] = True
    divergent.append(extra_top_level)

    for document in divergent:
        assert not doctor._compatible_hook_source(encoded(expected), encoded(document))

    for malformed in (b"{", b"[]", b'{"hooks": []}'):
        assert not doctor._compatible_hook_source(malformed, malformed)


def test_doctor_repairs_only_exact_plugin_max_source(tmp_path, monkeypatch):
    from forge_cli import doctor

    root = (tmp_path / ".claude" / "plugins" / "cache" / "openai-codex" /
            "codex" / "1.0.6")
    companion = root / "scripts" / "codex-companion.mjs"
    sources = {
        "scripts/codex-companion.mjs": b"companion before",
        "commands/rescue.md": b"rescue before",
        "skills/codex-cli-runtime/SKILL.md": b"skill before",
    }
    targets = {relative: content.replace(b"before", b"after")
               for relative, content in sources.items()}
    patches = {
        relative: (
            hashlib.sha256(sources[relative]).hexdigest(),
            hashlib.sha256(targets[relative]).hexdigest(),
            ((b"before", b"after"),),
        )
        for relative in sources
    }
    monkeypatch.setattr(doctor, "_CODEX_PLUGIN_MAX_PATCHES", patches)
    monkeypatch.setattr(doctor, "companion_script", lambda _home: companion)

    def install(values=sources, *, version="1.0.6"):
        for relative, content in values.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        manifest = root / ".claude-plugin" / "plugin.json"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(json.dumps({"version": version}), encoding="utf-8")

    def snapshot():
        return {relative: (root / relative).read_bytes() for relative in sources}

    install()
    before = snapshot()
    ok, detail = doctor._codex_plugin_max_status(tmp_path, fix=False)
    assert not ok and "rerun with --fix" in detail
    assert snapshot() == before

    assert doctor._codex_plugin_max_status(tmp_path, fix=True)[0]
    assert snapshot() == targets
    assert doctor._codex_plugin_max_status(tmp_path, fix=True)[0]
    assert snapshot() == targets

    mixed = dict(targets)
    mixed["commands/rescue.md"] = sources["commands/rescue.md"]
    install(mixed)
    before = snapshot()
    assert not doctor._codex_plugin_max_status(tmp_path, fix=False)[0]
    assert snapshot() == before
    assert doctor._codex_plugin_max_status(tmp_path, fix=True)[0]
    assert snapshot() == targets

    for relative in sources:
        install()
        (root / relative).write_bytes(b"local edit")
        before = snapshot()
        assert not doctor._codex_plugin_max_status(tmp_path, fix=True)[0]
        assert snapshot() == before

    install()
    missing = root / "commands" / "rescue.md"
    missing.unlink()
    before = {relative: (root / relative).read_bytes()
              for relative in sources if relative != "commands/rescue.md"}
    assert not doctor._codex_plugin_max_status(tmp_path, fix=True)[0]
    assert before == {relative: (root / relative).read_bytes()
                      for relative in before}

    install(version="1.0.7")
    before = snapshot()
    assert not doctor._codex_plugin_max_status(tmp_path, fix=True)[0]
    assert snapshot() == before

    install()
    external_root = tmp_path / "external" / "1.0.6"
    shutil.copytree(root, external_root)
    shutil.rmtree(root)
    root.symlink_to(external_root, target_is_directory=True)
    monkeypatch.setattr(
        doctor, "companion_script", lambda _home: companion.resolve())
    external_before = {
        relative: (external_root / relative).read_bytes() for relative in sources
    }
    ok, detail = doctor._codex_plugin_max_status(tmp_path, fix=True)
    assert not ok and "unsupported install path" in detail
    assert external_before == {
        relative: (external_root / relative).read_bytes() for relative in sources
    }

    root.unlink()
    install()
    external_leaf = tmp_path / "external-rescue.md"
    external_leaf.write_bytes(sources["commands/rescue.md"])
    leaf = root / "commands" / "rescue.md"
    leaf.unlink()
    leaf.symlink_to(external_leaf)
    monkeypatch.setattr(doctor, "companion_script", lambda _home: companion)
    ok, detail = doctor._codex_plugin_max_status(tmp_path, fix=True)
    assert not ok and "unsupported plugin source path" in detail
    assert external_leaf.read_bytes() == sources["commands/rescue.md"]

    install()
    outside = tmp_path / "other" / "1.0.6" / "scripts" / companion.name
    monkeypatch.setattr(doctor, "companion_script", lambda _home: outside)
    before = snapshot()
    assert not doctor._codex_plugin_max_status(tmp_path, fix=True)[0]
    assert snapshot() == before


def test_model_policy_selects_sol_work_and_luna_lite():
    from forge_cli.delegate import mode_run_config, pinned_run_config
    from forge_cli.review import CODEX_REVIEW_MODEL, CODEX_REVIEW_THINKING

    config = tomllib.loads(
        (HARNESS / ".codex" / "config.toml").read_text(encoding="utf-8"))
    explore = tomllib.loads(
        (HARNESS / ".codex" / "explore.config.toml").read_text(encoding="utf-8"))
    roles = {
        name: tomllib.loads(
            (HARNESS / ".codex" / row["config_file"]).read_text(encoding="utf-8"))
        for name, row in config["agents"].items()
        if isinstance(row, dict) and "config_file" in row
    }
    lanes = {
        lane: {
            name for name, row in roles.items()
            if (row["model"], row["model_reasoning_effort"]) == lane
        }
        for lane in {
            (row["model"], row["model_reasoning_effort"])
            for row in roles.values()
        }
    }

    assert {"model", "model_reasoning_effort", "plan_mode_reasoning_effort"}.isdisjoint(config)
    # Terra is retired. Exploration keeps a lane of its own, now Sol at medium:
    # read-heavy tracing does not need the hard-thinking effort level.
    assert lanes == {
        ("gpt-6-luna", "max"): {
            "coder", "frontend", "lite", "refactorer", "tester", "worker",
        },
        ("gpt-6-sol", "medium"): {"explorer"},
        ("gpt-6-sol", "high"): {
            "architect", "debugger", "docs-decomposer", "functional-checker",
            "griller", "performance", "planner", "planner-high", "security",
        },
    }
    assert pinned_run_config(HARNESS) == ("gpt-6-sol", "medium")
    assert (explore["model"], explore["model_reasoning_effort"]) == (
        "gpt-6-sol", "medium")
    assert mode_run_config(HARNESS, "grill")[:2] == ("gpt-6-sol", "high")
    assert mode_run_config(HARNESS, "lite")[:2] == ("gpt-6-sol", "medium")
    assert (CODEX_REVIEW_MODEL, CODEX_REVIEW_THINKING) == (
        "gpt-6-sol", "high")


SESSION_START_ADAPTERS = (".codex/hooks.json", ".claude/settings.json")
SESSION_START_SOURCES = ("startup", "resume", "clear", "compact")
HOOK_TOOL_MATRIX = {
    ".claude/settings.json": {
        "PreToolUse": ("Bash", "AskUserQuestion", "Edit", "Write", "MultiEdit", "NotebookEdit"),
        "PostToolUse": ("AskUserQuestion", "ExitPlanMode"),
    },
    ".codex/hooks.json": {
        "PreToolUse": ("Bash", "apply_patch", "request_user_input"),
        "PostToolUse": ("request_user_input",),
    },
}


def test_recovery_profile_override_keeps_only_three_forge_profiles():
    """The retained selector now checks the complete Decision 0083 registry."""
    config = tomllib.loads(
        (HARNESS / ".codex/config.toml").read_text(encoding="utf-8"))
    expected = {
        "architect", "coder", "debugger", "docs-decomposer", "explorer",
        "frontend", "functional-checker", "griller", "lite", "performance",
        "planner", "planner-high", "refactorer", "security", "tester", "worker",
    }
    configured = {
        name for name, row in config["agents"].items()
        if isinstance(row, dict) and row.get("config_file")
    }
    installed = {
        path.stem for path in (HARNESS / ".codex/agents").glob("*.toml")
    }
    assert configured == expected == installed
    assert config["sandbox_mode"] == "danger-full-access"
    assert config["approval_policy"] == "never"


def _remove_session_start_source(config, missing):
    document = json.loads(config.read_text(encoding="utf-8"))
    document["hooks"]["SessionStart"][0]["matcher"] = "|".join(
        source for source in SESSION_START_SOURCES if source != missing)
    config.write_text(json.dumps(document), encoding="utf-8")


@pytest.mark.parametrize("adapter", SESSION_START_ADAPTERS)
def test_dual_runtime_checker_accepts_session_start_match_all(repo, adapter):
    config = repo / adapter
    document = json.loads(config.read_text(encoding="utf-8"))
    document["hooks"]["SessionStart"][0]["matcher"] = "*"
    config.write_text(json.dumps(document), encoding="utf-8")

    code, out = run(repo, "check_dual_runtime.py", str(repo))

    assert code == 0, out
    for event, tools in HOOK_TOOL_MATRIX[adapter].items():
        for tool in tools:
            broken = copy.deepcopy(document)
            for entry in broken["hooks"][event]:
                matcher = entry.get("matcher") or ".*"
                if re.search(matcher, tool):
                    retained = [candidate for candidate in tools if candidate != tool
                                and re.search(matcher, candidate)]
                    entry["matcher"] = ("^(?:" + "|".join(map(re.escape, retained)) + ")$"
                                        if retained else "(?!)")
            config.write_text(json.dumps(broken), encoding="utf-8")
            code, out = run(repo, "check_dual_runtime.py", str(repo))
            assert code != 0 and f"({event}) must route {tool} to forge hook" in out
            assert all(
                f"({other_event}) must route {other} to forge hook" not in out
                for other_event, other_tools in HOOK_TOOL_MATRIX[adapter].items()
                for other in other_tools if (other_event, other) != (event, tool)
            )


@pytest.mark.parametrize("adapter", SESSION_START_ADAPTERS)
@pytest.mark.parametrize("missing", SESSION_START_SOURCES)
def test_dual_runtime_checker_requires_each_session_start_source(
        repo, adapter, missing):
    _remove_session_start_source(repo / adapter, missing)

    code, out = run(repo, "check_dual_runtime.py", str(repo))

    assert code != 0 and f"missing: {missing}" in out


@pytest.mark.parametrize("missing", SESSION_START_SOURCES)
def test_dual_runtime_checker_rejects_session_start_omission_in_both_adapters(
        repo, missing):
    for adapter in SESSION_START_ADAPTERS:
        _remove_session_start_source(repo / adapter, missing)

    code, out = run(repo, "check_dual_runtime.py", str(repo))

    assert code != 0
    assert out.count(f"missing: {missing}") == 2
