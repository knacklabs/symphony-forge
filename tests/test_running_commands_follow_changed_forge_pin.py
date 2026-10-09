"""An in-flight command hands off before an old release parses upgraded settings."""
STORY = "repin-mid-run"

import json
import re
import shutil
import sys
import tomllib
from pathlib import Path

import pytest

from conftest import FORGE_SHIM, ROOT, _install
from test_close import CLEAN, blocked, body, env, finding  # noqa: F401
from test_close_waits_for_review_loop_choice import stopped
from test_land import ITEM, URL, _fix, _workers, land  # noqa: F401


def _earlier_release(env):
    # Keep the command under test, but reproduce an earlier release's version and settings
    # vocabulary. Removing fast_test's accepted key makes continuing in the old process fail.
    source = env.tmp / "earlier-source"
    shutil.copytree(ROOT / "src" / "forge", source / "forge",
                    ignore=shutil.ignore_patterns("__pycache__"))
    packaging = tomllib.loads((ROOT / "pyproject.toml").read_text("utf-8"))
    bundled = packaging["tool"]["hatch"]["build"]["targets"]["wheel"]["force-include"]
    for original, packaged in bundled.items():
        target = source / packaged
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / original, target)
    version = source / "forge" / "__init__.py"
    version.write_text(re.sub(r'__version__ = "[^"]+"', '__version__ = "1.2.2"',
                             version.read_text("utf-8")), "utf-8")
    config = source / "forge" / "repo.py"
    config.write_text(config.read_text("utf-8").replace(', "fast_test": str', ''), "utf-8")
    _install(env.repo.bin, "forge", FORGE_SHIM.format(python=sys.executable,
                                                     src=source.as_posix()))
    selected_bin = env.tmp / "current-bin"
    selected_bin.mkdir()
    _install(selected_bin, "forge", FORGE_SHIM.format(python=sys.executable,
                                                     src=(ROOT / "src").as_posix()))
    # Only uv's package acquisition is faked: the selected release runs the real CLI and
    # its actual close, tests, review and GitHub checks decide whether this command succeeds.
    _install(env.repo.bin, "uv", f'''#!{sys.executable}
import json, os, pathlib, sys
args = sys.argv[1:]
here = pathlib.Path(__file__).resolve().parent
with open(here / "uv-calls.jsonl", "a", encoding="utf-8") as log:
    log.write(json.dumps({{"args": args, "cwd": os.getcwd()}}) + "\\n")
os.environ["PATH"] = {json.dumps(selected_bin.as_posix())} + os.pathsep + os.environ["PATH"]
sys.path.insert(0, {json.dumps((ROOT / 'src').as_posix())})
if args[:4] == ["run", "--isolated", "--no-project", "--with"]:
    assert args[5:8] == ["python", "-I", "-c"], args
    exec(args[8])
    sys.exit(0)
assert args[:3] == ["tool", "run", "--from"], args
assert args[4] == "forge", args
from forge.cli import main
sys.argv = ["forge", *args[5:]]
sys.exit(main())
''')


def _upgrade_default(env, upgraded):
    env.commit(env.repo.path, "forge.toml", upgraded, "Upgrade Forge")
    env.repo.git("push", "-q", "origin", "main")


def _worker_merges_upgrade(env, upgraded):
    # The model edits and merges git; Forge decides whether and how its command continues.
    worker = (env.repo.bin / "claude").read_text("utf-8")
    upgrade = f'''import subprocess
root = pathlib.Path({json.dumps(env.repo.path.as_posix())})
if (root / "forge.toml").read_text("utf-8") != {json.dumps(upgraded)}:
    (root / "forge.toml").write_text({json.dumps(upgraded)}, encoding="utf-8")
    for args in (["add", "forge.toml"], ["commit", "-q", "-m", "Upgrade Forge"],
                 ["push", "-q", "origin", "main"]):
        subprocess.run(["git", "-C", str(root), *args], check=True)
subprocess.run(["git", "fetch", "-q", "origin"], check=True)
subprocess.run(["git", "merge", "-q", "--no-edit", "origin/main"], check=True)
'''
    _install(env.repo.bin, "claude", worker.replace('if not int(os.environ.get(',
             upgrade + '\nif not int(os.environ.get(', 1))


@pytest.mark.parametrize("adoption", ["fresh", "earlier-adopted"])
@pytest.mark.parametrize("stage", ["land-build", "land-fix", "close-merge", "land-merge",
                                   "land-guide-conflict", "close-guide-conflict"])
def test_1_running_command_continues_under_the_pin_merged_from_upgraded_default(
        land, adoption, stage, monkeypatch):
    env = land
    current = env.repo.forge("--version").stdout.split()[-1]
    if adoption == "earlier-adopted":
        fixture = ROOT / "tests" / "fixtures" / "adopted-v1.2.2" / "client"
        for path in fixture.rglob("*"):
            if path.is_file():
                target = env.repo.path / path.relative_to(fixture)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target)
        env.repo.git("add", "-A")
        env.repo.git("commit", "-q", "-m", "Repo adopted on the earlier release")
    original = (env.repo.path / "forge.toml").read_text("utf-8")
    original = re.sub(r'version = "[^"]+"', 'version = "v1.2.2"', original)
    original = original.replace('workers = "codex"', 'workers = "claude"')
    original = original.replace('model = "gpt-6.1-sol"', 'model = "opus"')
    original = re.sub(r'^subagents = .*\n|^subagent_effort = .*\n', '', original, flags=re.M)
    env.commit(env.repo.path, "forge.toml", original, "Run the pinned earlier release")
    guide_conflict = stage.endswith("guide-conflict")
    guide = ".codex/skills/forge/SKILL.md"
    if guide_conflict:
        baseline = ((env.repo.path / guide).read_text("utf-8")
                    if (env.repo.path / guide).exists() else
                    (ROOT / "src" / "forge" / "templates" / "skill.md").read_text("utf-8"))
        env.commit(env.repo.path, guide, baseline.replace("# Forge", "# Earlier Forge", 1),
                   "Keep the earlier generated guide")
    env.repo.git("push", "-q", "origin", "main")
    where = _fix(env, "started" if stage == "land-build" else "working",
                 worked=stage != "land-build")
    upgraded = original.replace('version = "v1.2.2"',
                                f'version = "{current}"\nfast_test = ""')
    if guide_conflict:
        env.commit(where, guide, baseline.replace("# Forge", "# Worker Forge", 1),
                   "Refresh the worker's generated guide")
        env.commit(env.repo.path, guide, baseline.replace("# Forge", "# Default Forge", 1),
                   "Refresh the default branch's generated guide")
    if stage in ("close-merge", "land-merge") or guide_conflict:
        _upgrade_default(env, upgraded)
    else:
        if stage == "land-fix":
            env.reviews(blocked(finding("P1", "The greeting needs fixing")), CLEAN)
        _worker_merges_upgrade(env, upgraded)
    _earlier_release(env)
    monkeypatch.setenv("FORGE_PINNED_RUN", "v1.2.2")
    command = "close" if stage.startswith("close-") else "land"
    done = env.repo.forge(command, ITEM, cwd=where)
    assert done.returncode == 0, done.stdout + done.stderr
    notice = (f"Forge pin changed from v1.2.2 to {current}; "
              f"continuing forge {command} with {current}.")
    assert (done.stdout + done.stderr).splitlines().count(notice) == 1
    assert "Ready:" in done.stdout
    if command == "land":
        assert f"a human merges its pull request: {URL}" in done.stdout
    assert len(_workers(env)) == (1 if stage in ("land-build", "land-fix") else 0)
    assert len(env.review_calls()) == (2 if stage == "land-fix" else 1)
    assert env.gh_calls("pr", "ready")
    assert env.gh_calls("api", "--paginate", "--jq", ".check_runs[]")
    env.repo.git("merge-base", "--is-ancestor", "origin/main", "HEAD", cwd=where)
    assert env.repo.git("diff", "--name-only", "--diff-filter=U", cwd=where) == ""
    assert not Path(env.repo.git("rev-parse", "--path-format=absolute", "--git-path",
                                 "MERGE_HEAD", cwd=where)).exists()
    dispatches = [json.loads(line) for line in
                  (env.repo.bin / "uv-calls.jsonl").read_text("utf-8").splitlines()]
    if guide_conflict:
        sync_dispatch, dispatch = dispatches
        # Conflict regeneration uses the new release's files, keeping the repo's hooks.
        assert sync_dispatch["args"][:8] == ["run", "--isolated", "--no-project", "--with",
            f"git+https://github.com/knacklabs/symphony-forge@{current}", "python", "-I", "-c"]
        assert Path(sync_dispatch["cwd"]) == where
        # Full sync used to install hooks here. File-only regeneration must leave this
        # unsynced fixture's local hooks absent, as well as preserve hooks that already exist.
        hooks = Path(env.repo.git("rev-parse", "--path-format=absolute", "--git-path",
                                  "hooks", cwd=where))
        assert not (hooks / "pre-commit").exists()
        assert not (hooks / "pre-push").exists()
        assert (where / guide).read_text("utf-8") == (
            ROOT / "src" / "forge" / "templates" / "skill.md").read_text("utf-8")
    else:
        [dispatch] = dispatches
    assert dispatch["args"] == ["tool", "run", "--from",
        f"git+https://github.com/knacklabs/symphony-forge@{current}", "forge", command, ITEM]
    assert Path(dispatch["cwd"]) == where


def test_2_land_keeps_its_three_fix_round_limit_after_the_worker_changes_the_pin(
        land, monkeypatch):
    env = land
    current = env.repo.forge("--version").stdout.split()[-1]
    original = re.sub(r'version = "[^"]+"', 'version = "v1.2.2"',
                      (env.repo.path / "forge.toml").read_text("utf-8"))
    env.commit(env.repo.path, "forge.toml", original, "Run the pinned earlier release")
    env.repo.git("push", "-q", "origin", "main")
    where = _fix(env, "working", worked=True)
    failing_test = json.dumps(f'"{sys.executable}" -c "raise SystemExit(1)"')
    upgraded = original.replace('version = "v1.2.2"',
        f'version = "{current}"\nfast_test = ""\ntest = {failing_test}')
    env.reviews(blocked(finding("P1", "The greeting needs fixing")), CLEAN)
    _worker_merges_upgrade(env, upgraded)
    _earlier_release(env)
    monkeypatch.setenv("FORGE_PINNED_RUN", "v1.2.2")
    done = env.repo.forge("land", ITEM, cwd=where)
    assert done.returncode == 1, done.stdout + done.stderr
    assert len(_workers(env)) == 3, done.stdout + done.stderr
    assert f"Stopped after 3 fix rounds: {ITEM} still has the failing tests." in done.stdout
    notice = (f"Forge pin changed from v1.2.2 to {current}; "
              f"continuing forge land with {current}.")
    assert (done.stdout + done.stderr).splitlines().count(notice) == 1
    assert "Ready:" not in done.stdout
    assert not env.gh_calls("pr", "ready")
    [dispatch] = [json.loads(line) for line in
                  (env.repo.bin / "uv-calls.jsonl").read_text("utf-8").splitlines()]
    assert dispatch["args"] == ["tool", "run", "--from",
        f"git+https://github.com/knacklabs/symphony-forge@{current}", "forge", "land", ITEM]
    assert Path(dispatch["cwd"]) == where


def test_3_close_continues_the_current_human_accept_choice_under_changed_pin(
        land, monkeypatch):
    env = land
    current = env.repo.forge("--version").stdout.split()[-1]
    original = re.sub(r'version = "[^"]+"', 'version = "v1.2.2"',
                      (env.repo.path / "forge.toml").read_text("utf-8"))
    env.commit(env.repo.path, "forge.toml", original, "Run the pinned earlier release")
    env.repo.git("push", "-q", "origin", "main")
    _earlier_release(env)
    monkeypatch.setenv("FORGE_PINNED_RUN", "v1.2.2")
    item, where = stopped(env)
    reviewed = len(env.review_calls())
    upgraded = original.replace('version = "v1.2.2"',
                                f'version = "{current}"\nfast_test = ""')
    _upgrade_default(env, upgraded)
    reason = "The human accepts the remaining greeting defect for this version"
    args = ["close", item, "--resolve", "accept", "--reason", reason]
    done = env.repo.forge(*args, cwd=where)
    assert done.returncode == 0, done.stdout + done.stderr
    assert "Ready:" in done.stdout
    notice = (f"Forge pin changed from v1.2.2 to {current}; "
              f"continuing forge close with {current}.")
    assert (done.stdout + done.stderr).splitlines().count(notice) == 1
    assert len(env.review_calls()) == reviewed
    assert reason in body(env.gh_calls("pr", "edit")[-1])
    # The held pull request is already open, so continuing close only needs its checks.
    assert env.gh_calls("api", "--paginate", "--jq", ".check_runs[]")
    [dispatch] = [json.loads(line) for line in
                  (env.repo.bin / "uv-calls.jsonl").read_text("utf-8").splitlines()]
    assert dispatch["args"] == ["tool", "run", "--from",
        f"git+https://github.com/knacklabs/symphony-forge@{current}", "forge", *args]
    assert Path(dispatch["cwd"]) == where

    _install(env.repo.bin, "forge", FORGE_SHIM.format(python=sys.executable,
                                                     src=(ROOT / "src").as_posix()))
    replayed = env.repo.forge(*args, cwd=where)
    assert replayed.returncode == 1
    assert "Record the human's choice only on a stopped review loop" in replayed.stderr
