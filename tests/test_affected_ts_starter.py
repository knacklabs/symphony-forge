"""The generated TypeScript starter selects checks at its command boundary."""
import json
import os
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

from conftest import _install
from test_close import env  # noqa: F401
from test_setup import _fresh_client
from test_upgrade_command import RELEASE, unsynced_up  # noqa: F401

STORY = "FORGE-AFFECTED-1"
ROOT = Path(__file__).resolve().parents[1]


def _selection_tools(folder: Path, log: Path) -> None:
    """Stub Corepack's Nx response; the generated selector stays real."""
    folder.mkdir()
    _install(folder, "corepack", f'''#!{sys.executable}
import json, os, pathlib, sys
args = sys.argv[1:]
if args[:5] != ["pnpm", "exec", "nx", "show", "projects"]:
    sys.exit("unexpected Corepack command: " + " ".join(args))
with pathlib.Path({json.dumps(str(log))}).open("a", encoding="utf-8") as calls:
    calls.write(json.dumps(args) + "\\n")
print(os.environ["FORGE_NX_PROJECTS"])
''')


def _run_list(node: str, client: Path, tools: Path, affected, base: str | None):
    env = os.environ | {
        "PATH": str(tools) + os.pathsep + os.environ["PATH"],
        "FORGE_NX_PROJECTS": json.dumps(affected),
    }
    args = [node, "scripts/test.mjs", "--list"]
    if base:
        args.append(base)
    return subprocess.run(
        args, cwd=client, env=env, capture_output=True, text=True, encoding="utf-8", timeout=120,
    )


@pytest.mark.platform
def test_5_typescript_starter_selects_its_affected_parts(repo, gh, tmp_path, unsynced_up):
    # Contract: init keeps the full nightly command and adds a selectable command, and the
    # generated app lists only the suites for the selected projects. A missing fast_test,
    # stale script, or wrong project target would break a new app's pull request check.
    # Existing tests check init's full test setting and Python selection, but not this TS path.
    # The real Forge init and generated Node command own the boundary; only Corepack/Nx are
    # stubbed as the external selection provider. No production test seam is needed.
    client, initialized = _fresh_client(repo, gh, tmp_path, "--starter")
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    settings = tomllib.loads((client / "forge.toml").read_text(encoding="utf-8"))
    assert settings["test"] == "node scripts/test.mjs"
    assert settings.get("fast_test") == "node scripts/test.mjs {base}"
    assert (client / "scripts/affected.mjs").is_file()

    phrase = ("New repos leave `fast_test` unset, except a new starter, whose init writes one for "
              "its own script")
    assert phrase in " ".join((ROOT / "docs/guide.md").read_text(encoding="utf-8").split())
    assert phrase in " ".join((ROOT / "src/forge/templates/skill.md").read_text(
        encoding="utf-8").split())

    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is required to run the generated TypeScript selection command")
    tools = tmp_path / "selection-tools"
    calls = tmp_path / "nx-calls.jsonl"
    _selection_tools(tools, calls)
    base = repo.git("rev-parse", "HEAD", cwd=client)
    changes = (
        ("apps/web/src/index.css", "\n/* affected selection check */\n", ["web"],
         ("Affected parts: web", "run web:lint", "run web:typecheck", "run web:test",
          "run web:e2e", "docker compose"), ("run api:test", "test:api")),
        ("apps/api/src/main.ts", "\n// affected selection check\n", ["api"],
         ("Affected parts: api", "run api:test", "apps/api/vitest.config.ts", "docker compose"),
         ("run web:e2e", "playwright test")),
        ("libs/shared/util/src/index.ts", "\n// affected selection check\n",
         ["@app/shared-util", "web"],
         ("Affected parts: @app/shared-util, web", "run @app/shared-util:test",
          "run web:test", "libs/shared/util/src", "apps/web/src"), ("run api:test",)),
    )
    for relative, added, affected, expected, absent in changes:
        changed = client / relative
        changed.write_text(changed.read_text(encoding="utf-8") + added, encoding="utf-8")
        listed = _run_list(node, client, tools, affected, base)
        repo.git("checkout", "--", Path(relative).as_posix(), cwd=client)
        assert listed.returncode == 0, listed.stdout + listed.stderr
        output = listed.stdout
        for item in expected:
            assert item in output, (item, output)
        for item in absent:
            assert item not in output, (item, output)
        if affected == ["@app/shared-util", "web"]:
            assert output.count("vitest run") == 2, output

    readme = client / "README.md"
    readme.write_text(readme.read_text(encoding="utf-8") + "\nSelection fallback check.\n",
                      encoding="utf-8")
    listed = _run_list(node, client, tools, [], base)
    repo.git("checkout", "--", "README.md", cwd=client)
    assert listed.returncode == 0, listed.stdout + listed.stderr
    for item in ("Affected parts: all", "test:api", "test:hooks", "test:browser"):
        assert item in listed.stdout
    full = _run_list(node, client, tools, ["api", "web"], None)
    assert full.returncode == 0, full.stdout + full.stderr
    for item in ("Affected parts: all", "test:api", "test:hooks", "test:browser"):
        assert item in full.stdout

    logged = [json.loads(line) for line in calls.read_text(encoding="utf-8").splitlines()]
    assert logged and all(
        call[:5] == ["pnpm", "exec", "nx", "show", "projects"]
        and "--affected" in call and "--json" in call
        and f"--base={base}" in call for call in logged
    )

    # An earlier app keeps its own test command and files after the Forge release is updated.
    from test_mcp import ADOPTED, _adopted_files_after_sync

    sentinel = repo.path / "scripts/custom.mjs"
    sentinel.parent.mkdir(parents=True, exist_ok=True)
    sentinel.write_text("custom app script\n", encoding="utf-8")
    sentinel_before = sentinel.read_bytes()
    before, after = _adopted_files_after_sync(repo)
    assert after == before
    assert sentinel.read_bytes() == sentinel_before
    old_config = (ADOPTED / "forge.toml").read_text(encoding="utf-8")
    version = repo.forge("--version").stdout.split()[-1]
    assert (repo.path / "forge.toml").read_text(encoding="utf-8") == old_config.replace(
        '"v1.2.2"', json.dumps(version))
    adopted_settings = tomllib.loads((repo.path / "forge.toml").read_text(encoding="utf-8"))
    assert adopted_settings["test"] == 'python -c "print(123)"'
    assert "fast_test" not in adopted_settings
    assert not (repo.path / "scripts/affected.mjs").exists()

    # The historical fixture has no workflow. The first sync above supplies the current
    # workflow; an actual installer upgrade must then change only its release pin.
    configuration = (repo.path / "forge.toml").read_text(encoding="utf-8")
    workflow = (repo.path / ".github/workflows/forge.yml").read_text(encoding="utf-8")
    owned = {path.relative_to(repo.path).as_posix(): path.read_bytes()
             for folder in ("apps", "libs", "scripts")
             for path in (repo.path / folder).rglob("*") if path.is_file()}
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "Sync the earlier adopted app")
    repo.git("switch", "-q", "main")
    repo.git("merge", "-q", "--ff-only", "fix/agent-accounts-upgrade")
    repo.git("push", "-q", "origin", "main")
    upgraded = unsynced_up.run(RELEASE)
    assert upgraded.returncode == 0, upgraded.stdout + upgraded.stderr
    upgraded_root = unsynced_up.folder
    assert (upgraded_root / "forge.toml").read_text(encoding="utf-8") == configuration.replace(
        json.dumps(version), json.dumps(RELEASE))
    assert (upgraded_root / ".github/workflows/forge.yml").read_text(
        encoding="utf-8") == workflow.replace(version, RELEASE)
    after_upgrade = {path.relative_to(upgraded_root).as_posix(): path.read_bytes()
                     for folder in ("apps", "libs", "scripts")
                     for path in (upgraded_root / folder).rglob("*") if path.is_file()}
    assert after_upgrade == owned
