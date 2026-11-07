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
from test_close import GREEN, env  # noqa: F401
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
    # Package-only Nx projects are shipped by the optional assistant module. Their
    # presence must not break selection for another project. No dependency is installed.
    assistant = client / "libs/assistant"
    shutil.copytree(ROOT / "src/forge/templates/skills/agents/assistant-module/typescript/libs/assistant",
                    assistant)
    package_case = _run_list(node, client, tools, ["web"], base)
    shutil.rmtree(assistant)
    # Newly written library tests must enter the selected check even if the library
    # had no tests, and thus no Nx test target, when the app was first created.
    added_test = client / "libs/auth/server/src/affected-added.test.ts"
    added_test.write_text("import { it } from 'vitest'; it('new failure', () => { throw Error('failed'); });\n",
                          encoding="utf-8")
    repo.git("add", added_test.relative_to(client).as_posix(), cwd=client)
    added_case = _run_list(node, client, tools, ["@app/auth-server"], base)
    repo.git("reset", "-q", "HEAD", "--", added_test.relative_to(client).as_posix(), cwd=client)
    added_test.unlink()
    regressions = []
    if package_case.returncode or "Affected parts: web" not in package_case.stdout:
        regressions.append(package_case.stdout + package_case.stderr)
    selected_tests = [line for line in added_case.stdout.splitlines() if "vitest run" in line]
    if added_case.returncode or not any(
            "affected-added.test.ts" in line or "libs/auth/server/src" in line
            for line in selected_tests):
        regressions.append("New library test was not selected:\n" + added_case.stdout + added_case.stderr)
    assert not regressions, "\n".join(regressions)
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

    # Every library owns its lint target. The three initial test owners also keep
    # their own source filters; the real Vitest file partition is checked live.
    for library in sorted((client / "libs").glob("*/*")):
        package = json.loads((library / "package.json").read_text(encoding="utf-8"))
        relative = library.relative_to(client).as_posix()
        source = next((library / "src").rglob("*.ts"))
        original = source.read_bytes()
        source.write_bytes(original + b"\n// selected library lint\n")
        listed = _run_list(node, client, tools, [package["name"]], base)
        source.write_bytes(original)
        assert listed.returncode == 0, listed.stdout + listed.stderr
        assert f"run {package['name']}:lint" in listed.stdout, listed.stdout
        assert f"eslint {relative}" in listed.stdout, listed.stdout
        if relative in ("libs/core/server", "libs/history/server", "libs/shared/util"):
            assert f"run {package['name']}:test" in listed.stdout, listed.stdout
            assert f"{relative}/src" in listed.stdout, listed.stdout

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
    # This fixture builds an already-adopted history, not a new Forge work item.
    # Reuse the upgrade fixture's hook-free setup commands; the upgrade itself
    # still runs the installed release's real hooks and close.
    hook_setup = ["-c", f"core.hooksPath={unsynced_up.tmp / 'no-hooks'}"]
    repo.git(*hook_setup, "commit", "-q", "-m", "Sync the earlier adopted app")
    repo.git("switch", "-q", "main")
    repo.git("merge", "-q", "--ff-only", "fix/agent-accounts-upgrade")
    repo.git(*hook_setup, "push", "-q", "origin", "main")
    # New-app init installs a broad API response. Restore the upgrade fixture's
    # check/status streams before the real release's close reads them.
    # The earlier-adopted app also exercises the missing-name refusal and retry.
    unsynced_up.env.checks(GREEN, [{}])
    unnamed = unsynced_up.run(RELEASE)
    assert unnamed.returncode == 1, unnamed.stdout + unnamed.stderr
    assert "GitHub reported no check name." in unnamed.stderr, unnamed.stderr
    assert "Next: forge close upgrade-forge-to-v9-9-9" in unnamed.stderr, unnamed.stderr
    unsynced_up.env.checks(GREEN)
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
