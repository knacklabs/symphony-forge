"""Close keeps using the source checkout when its default branch gets a new release pin.

Test audit: the real close command must finish when the unpublished tag is unavailable.
One case has the release bump arrive during close and conflict on a generated guide; the other
starts from main after the fix worktree already merged that bump. Existing pin tests cover
published releases, not either source-release path. The uv stub replaces package resolution only.
"""
import json
import re
import sys

import pytest

from conftest import FORGE_SHIM, IDLE_MACHINE, _install
from test_close_requires_current_workflow import source_checkout
from test_close import env  # noqa: F401
from test_land import ITEM, _fix, land  # noqa: F401
from test_running_commands_follow_changed_forge_pin import _earlier_release

STORY = "FIX-CLOSE-CATCHES-WORKFLOW-DRIFT"
GUIDE = ".codex/skills/forge/SKILL.md"


@pytest.mark.parametrize("stage", ["merge-arrives-during-close", "worktree-already-merged"])
@pytest.mark.platform
def test_3_close_runs_an_unpublished_source_pin_after_default_moves(land, stage, monkeypatch):
    env = land
    repo = env.repo
    current = source_checkout(env)
    major, minor, patch = map(int, re.fullmatch(r"v(\d+)\.(\d+)\.(\d+)", current).groups())
    future = f"v{major}.{minor}.{patch + 1}"
    current_plain, future_plain = current.removeprefix("v"), future.removeprefix("v")
    where = _fix(env, "working", worked=True)
    base_guide = (repo.path / GUIDE).read_text("utf-8")

    if stage == "merge-arrives-during-close":
        worker_guide = base_guide.replace("# Forge", "# Worker Forge", 1)
        assert worker_guide != base_guide
        env.commit(where, GUIDE, worker_guide, "Update the worker guide")

    writer = env.tmp / "future-release"
    remote = repo.git("remote", "get-url", "origin")
    repo.git("clone", "-q", remote, writer.as_posix(), cwd=env.tmp)
    settings_path = writer / "forge.toml"
    settings = settings_path.read_text("utf-8")
    settings = re.sub(r'^version = "[^"\n]+"',
                      f'version = "{future}"\nfast_test = ""', settings, count=1, flags=re.M)
    assert settings != settings_path.read_text("utf-8")
    settings_path.write_text(settings, "utf-8")
    version_file = writer / "src/forge/__init__.py"
    source = version_file.read_text("utf-8")
    updated = re.sub(r'__version__ = "[^"]+"', f'__version__ = "{future_plain}"', source, count=1)
    assert updated != source
    version_file.write_text(updated, "utf-8")
    repo.git("checkout", "-qb", "fix/future-release", cwd=writer)
    record = writer / ".factory/fixes/future-release.json"
    record.parent.mkdir(parents=True, exist_ok=True)
    record.write_text(json.dumps({"kind": "fix", "branch": "fix/future-release",
        "status": "working", "why": "Prepare an unpublished release",
        "done_when": "The release source is ready"}), "utf-8")
    _install(repo.bin, "forge", FORGE_SHIM.format(python=sys.executable,
                                                    src=(writer / "src").as_posix()))
    synced = repo.forge("sync", cwd=writer)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    if stage == "merge-arrives-during-close":
        future_guide = (writer / GUIDE).read_text("utf-8").replace("# Forge", "# Future Forge", 1)
        assert future_guide != base_guide
        (writer / GUIDE).write_text(future_guide, "utf-8")
    record.unlink()
    hooks = env.tmp / "future-release-hooks"
    hooks.mkdir()
    repo.git("config", "core.hooksPath", hooks.as_posix(), cwd=writer)
    repo.git("add", "-A", cwd=writer)
    repo.git("commit", "-qm", "Prepare the unpublished release", cwd=writer)
    repo.git("push", "-q", "origin", "HEAD:main", cwd=writer)
    repo.git("tag", current)
    # The final release sorts after its release candidate, even though the final tag is absent.
    repo.git("tag", f"{future}-rc.1")

    if stage == "worktree-already-merged":
        repo.git("fetch", "-q", "origin", cwd=where)
        repo.git("merge", "-q", "--no-edit", "origin/main", cwd=where)

    _earlier_release(env)
    earlier = env.tmp / "earlier-source" / "forge" / "__init__.py"
    installed = earlier.read_text("utf-8")
    installed = re.sub(r'__version__ = "[^"]+"',
                       f'__version__ = "{current_plain}"', installed, count=1)
    earlier.write_text(installed, "utf-8")
    calls = repo.bin / "uv-calls.jsonl"
    _install(repo.bin, "uv", f'''#!{sys.executable}
import json, os, pathlib, sys
if hasattr(os, "getloadavg"):
    os.getloadavg = lambda: (0.0, 0.0, 0.0)
args = sys.argv[1:]
with open({json.dumps(calls.as_posix())}, "a", encoding="utf-8") as log:
    log.write(json.dumps({{"args": args, "cwd": os.getcwd()}}) + "\\n")
if args[:3] != ["run", "--project", args[2] if len(args) > 2 else ""]:
    print("Failed to resolve --with requirement from the unpublished release", file=sys.stderr)
    sys.exit(1)
project = pathlib.Path(args[2])
sys.path.insert(0, str(project / "src"))
if len(args) > 3 and args[3] == "forge":
    exec({IDLE_MACHINE!r})
    from forge.cli import main
    sys.exit(main(args[4:]))
program = args.index("python")
assert args[program:program + 3] == ["python", "-I", "-c"], args
exec(args[program + 3])
''')
    monkeypatch.delenv("FORGE_PINNED_RUN", raising=False)

    # Invoke close from main while Forge is installed one release behind the pin.
    done = repo.forge("close", ITEM)

    assert done.returncode == 0, done.stdout + done.stderr
    assert "Ready:" in done.stdout
    assert "Failed to resolve --with requirement" not in done.stdout + done.stderr
    dispatches = [json.loads(line) for line in calls.read_text("utf-8").splitlines()]
    assert dispatches and all(call["args"][:2] == ["run", "--project"] for call in dispatches)
    if stage == "merge-arrives-during-close":
        assert f"Forge pin changed from {current} to {future}; continuing forge close with {future}." \
            in done.stdout + done.stderr
        assert len(dispatches) == 2
        assert dispatches[0]["args"][1:3] == ["--project", where.as_posix()]
        assert "--python" in dispatches[0]["args"]
        assert dispatches[1]["args"] == ["run", "--project", where.as_posix(), "forge", "close", ITEM]
        assert (where / GUIDE).read_text("utf-8") == (
            repo.path / "src/forge/templates/skill.md").read_text("utf-8")
    else:
        assert len(dispatches) == 1
        assert dispatches[0]["args"] == ["run", "--project", where.as_posix(),
                                          "forge", "close", ITEM]
