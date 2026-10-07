"""Missing quick-test settings get advice without changing the repo's tests."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

from conftest import ROOT, FORGE_SHIM, _install
from test_fix_new_repos_get_claude_as_their_worker_by import _new_repo
from test_upgrade_command import RELEASE, unsynced_up  # noqa: F401
from test_close import env  # noqa: F401

STORY = "FIX-REPOS-WITHOUT-A-QUICK-TEST-SETTING-DON-T"
pytestmark = pytest.mark.usefixtures("isolated_codex_home")

# Command-boundary cases protect runner selection, setup preservation and advice-only
# behavior. Existing setup coverage only checks the skill, not command output.
CASES = [
    ("python", "uv run pytest", {}, "forge test --pytest {base}"),
    ("vitest", "npm ci && npm test", {"scripts": {"test": "vitest run"},
        "devDependencies": {"vitest": "1"}},
        "npm ci && npm test -- --changed {base} --passWithNoTests"),
    ("jest", "pnpm install --frozen-lockfile && pnpm exec jest", {"devDependencies": {"jest": "1"}},
        "pnpm install --frozen-lockfile && pnpm exec jest --changedSince {base} --passWithNoTests"),
    ("npm-jest", "npm ci && npm run unit", {"scripts": {"unit": "jest --runInBand"}},
        "npm ci && npm run unit -- --changedSince {base} --passWithNoTests"),
    ("npm-exec-vitest", "npm ci && npm exec vitest run", {},
        "npm ci && npm exec -- vitest run --changed {base} --passWithNoTests"),
    ("npm-exec-jest", "npm ci && npm exec jest", {},
        "npm ci && npm exec -- jest --changedSince {base} --passWithNoTests"),
    ("npm-exec-package", "npm ci && npm exec --package=vitest --workspace=web vitest run", {},
        "npm ci && npm exec --package=vitest --workspace=web -- vitest run --changed {base} --passWithNoTests"),
    ("npm-exec-workspace", "npm ci && npm exec --package jest -w web jest", {},
        "npm ci && npm exec --package jest -w web -- jest --changedSince {base} --passWithNoTests"),
    ("npm-exec-cache", "npm ci && npm exec --cache 'cache folder' --workspace vitest jest", {},
        "npm ci && npm exec --cache 'cache folder' --workspace vitest -- jest --changedSince {base} --passWithNoTests"),
    ("yarn-vitest", "yarn install --immutable && yarn unit", {"scripts": {"unit": "vitest run"}},
        "yarn install --immutable && yarn unit --changed {base} --passWithNoTests"),
    ("mixed", "uv run pytest && npm ci && npx --no-install vitest run", {"devDependencies": {"vitest": "1"}},
        "forge test --pytest {base} && npm ci && npx --no-install vitest run --changed {base} --passWithNoTests"),
    ("local-runner", "npm ci && ./node_modules/.bin/jest", {"devDependencies": {"jest": "1"}},
        "npm ci && ./node_modules/.bin/jest --changedSince {base} --passWithNoTests"),
    *[(kind, command, {}, None) for kind, command in (
        ("go", "go test ./..."), ("rust", "cargo test"), ("java", "mvn test"),
        ("dotnet", "dotnet test"), ("ruby", "bundle exec rspec"))],
    ("configured", "uv run pytest", {}, None),
]


def _inputs(folder, kind, command, package):
    if kind in ("python", "mixed", "configured"):
        (folder / "pyproject.toml").write_text('[project]\nname = "client"\nversion = "1.0"\n', "utf-8")
    if package:
        (folder / "package.json").write_text(json.dumps(package), "utf-8")
    path = folder / "forge.toml"
    lines = [line for line in path.read_text("utf-8").splitlines()
             if not line.startswith(("test =", "fast_test ="))]
    lines.insert(1, "test = " + json.dumps(command))
    if kind == "configured":
        lines.insert(1, 'fast_test = "our existing quick command"')
    path.write_text("\n".join(lines) + "\n", "utf-8")


def _advice(done, expected):
    lines = [line.strip() for line in done.stdout.splitlines() if line.strip().startswith("fast_test =")]
    assert lines == ([] if expected is None else ["fast_test = " + json.dumps(expected)]), done.stdout + done.stderr


@pytest.mark.parametrize("kind,command,package,expected", CASES, ids=[case[0] for case in CASES])
def test_1_doctor_suggests_the_new_clients_test_kind(repo, gh, tmp_path, kind, command, package, expected):
    client = _new_repo(repo, gh, tmp_path)
    assert repo.forge("init", cwd=client).returncode == 0
    _inputs(client, kind, command, package)
    before = (client / "forge.toml").read_bytes()
    done = repo.forge("doctor", cwd=client)
    _advice(done, expected)
    assert (client / "forge.toml").read_bytes() == before
    for host in (".claude", ".codex"):
        skill = " ".join((client / host / "skills/forge/SKILL.md").read_text("utf-8").split())
        assert "`forge doctor` and `forge upgrade` print one suggested" in skill
        assert "Mixed repos get one part per kind." in skill
        assert "Go, Rust, Java, .NET and Ruby get no suggestion." in skill


@pytest.mark.parametrize("entry", ["doctor", "upgrade"])
@pytest.mark.parametrize("runner,flag", [("vitest", "--changed"), ("jest", "--changedSince")])
@pytest.mark.parametrize("shared", [False, True], ids=["related-python", "shared-python-input"])
@pytest.mark.parametrize("invocation", ["exec", "script"])
def test_4_running_the_mixed_suggestion_runs_each_test_kind_once(unsynced_up, entry, runner, flag, shared, invocation):
    up = unsynced_up
    repo = up.repo
    # Real pytest proves selection and execution. npm is a third-party boundary stub;
    # it records arguments without deciding whether Forge picked the right runners.
    _install(repo.bin, "npm", f'''#!{sys.executable}
import json, pathlib, sys
path = pathlib.Path("node-calls.jsonl")
with path.open("a", encoding="utf-8") as out:
    out.write(json.dumps(sys.argv[1:]) + "\\n")
''')
    node = f"npm exec {runner}" if invocation == "exec" else "npm test"
    command = f'"{Path(sys.executable).as_posix()}" -m pytest tests -q && npm ci && npm run lint && {node}'
    _inputs(repo.path, "mixed", command, {"scripts": {"test": runner}})
    repo.write("tests/test_related.py", 'from pathlib import Path\ndef test_related():\n'
               '    with Path("python-ran.txt").open("a", encoding="utf-8") as out:\n'
               '        out.write("ran")\n')
    if not shared:
        repo.write("tests/test_unrelated.py", "raise AssertionError('unrelated collected')\n")
    else:
        repo.write("tests/test_unrelated.py", 'from pathlib import Path\ndef test_other_python():\n'
                   '    Path("other-python-ran.txt").write_text("ran", encoding="utf-8")\n')
    repo.git("add", "-A")
    repo.git("commit", "-qm", "Set up mixed tests")
    repo.git("push", "-q", "origin", "main")
    base = repo.git("rev-parse", "HEAD")
    repo.write("conftest.py" if shared else "tests/test_related.py",
               "# Shared input\n" if shared else
               (repo.path / "tests/test_related.py").read_text("utf-8") + "# Changed test\n")
    repo.git("add", "-A")
    repo.git("commit", "-qm", "Change Python tests")
    repo.git("push", "-q", "origin", "main")
    if entry == "upgrade":
        (repo.bin / "uv-install-fails").touch()
        advised = up.run(RELEASE)
    else:
        advised = repo.forge("doctor")
    lines = [line for line in advised.stdout.splitlines() if line.startswith("fast_test =")]
    assert len(lines) == 1, advised.stdout + advised.stderr
    quick = tomllib.loads(lines[0])["fast_test"].replace("{base}", base)
    done = subprocess.run(quick, cwd=repo.path, shell=True, capture_output=True, text=True,
                          env={**os.environ, "PYTHONPATH": str(ROOT / "src")}, timeout=60)
    assert done.returncode == 0, done.stdout + done.stderr
    assert (repo.path / "python-ran.txt").read_text("utf-8") == "ran"
    if shared:
        assert (repo.path / "other-python-ran.txt").read_text("utf-8") == "ran"
    calls = [json.loads(line) for line in (repo.path / "node-calls.jsonl").read_text("utf-8").splitlines()]
    launch = ["exec", "--", runner] if invocation == "exec" else ["test", "--"]
    assert calls == [["ci"], ["run", "lint"], [*launch, flag, base, "--passWithNoTests"]]


@pytest.mark.parametrize("generation", ["new", "previous-release"])
@pytest.mark.parametrize("runner,flag", [("vitest", "--changed"), ("jest", "--changedSince")])
def test_5_generated_node_settings_get_advice_without_replacing_the_test_command(unsynced_up, generation, runner, flag):
    up = unsynced_up
    repo = up.repo
    client = _new_repo(repo, up.env.gh, up.tmp)
    (client / "package.json").write_text(json.dumps({"scripts": {"test": runner}}), "utf-8")
    if generation == "previous-release":
        old = up.tmp / "previous-release"
        shutil.copytree(ROOT / "tests/fixtures/forge-v1.2.2", old)
        (old / "src/forge/cli-py.txt").rename(old / "src/forge/cli.py")
        _install(repo.bin, "old-forge", FORGE_SHIM.format(python=sys.executable, src=str(old / "src")))
        made = subprocess.run([sys.executable, str(repo.bin / "old-forge"), "init"],
                              cwd=client, capture_output=True, text=True, timeout=60)
    else:
        made = repo.forge("init", cwd=client)
    assert made.returncode == 0, made.stdout + made.stderr
    settings = client / "forge.toml"
    before = settings.read_bytes()
    assert tomllib.loads(before.decode("utf-8"))["test"] == "[ ! -f package.json ] || (npm ci && npm test)"
    expected = f"[ ! -f package.json ] || (npm ci && npm test -- {flag} {{base}} --passWithNoTests)"
    checked = repo.forge("doctor", cwd=client)
    # Make the app manifest available in the upgrade worktree. Forge's generated settings
    # are never edited: this is the command a real new/previous-release client received.
    repo.git("add", "package.json", cwd=client)
    repo.git("-c", f"core.hooksPath={up.tmp / 'no-hooks'}", "commit", "-qm", "Add client tests", cwd=client)
    repo.git("-c", f"core.hooksPath={up.tmp / 'no-hooks'}", "push", "-q", "origin", "main", cwd=client)
    (repo.bin / "uv-install-fails").touch()
    upgraded = repo.forge("upgrade", RELEASE, cwd=client)
    assert "Installing Forge" in upgraded.stderr, upgraded.stdout + upgraded.stderr
    _advice(upgraded, expected)
    _advice(checked, expected)
    assert settings.read_bytes() == before


@pytest.mark.parametrize("kind,command,package,expected", CASES, ids=[case[0] for case in CASES])
def test_2_upgrade_suggests_the_previously_adopted_clients_test_kind(unsynced_up, kind, command, package, expected):
    up = unsynced_up
    shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", up.repo.path, dirs_exist_ok=True)
    _inputs(up.repo.path, kind, command, package)
    up.repo.git("switch", "-q", "-c", "adoption")
    up.repo.git("add", "-A")
    up.repo.git("commit", "-q", "-m", "Adopt earlier Forge")
    up.repo.git("switch", "-q", "main")
    up.repo.git("merge", "-q", "--ff-only", "adoption")
    up.repo.git("push", "-q", "origin", "main")
    before = tomllib.loads(up.toml())
    # Advice must survive failure at the third-party install boundary, without requiring
    # the client's full tests or review to succeed first.
    (up.repo.bin / "uv-install-fails").touch()
    done = up.run(RELEASE)
    assert "Installing Forge" in done.stderr, done.stdout + done.stderr
    _advice(done, expected)
    assert tomllib.loads(up.toml()) == before


def test_3_successful_upgrade_keeps_the_suggestion_and_ships_the_guidance(unsynced_up):
    up = unsynced_up
    shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", up.repo.path, dirs_exist_ok=True)
    _inputs(up.repo.path, "python", 'python -c "print(123)"', {})
    up.repo.git("switch", "-q", "-c", "adoption")
    up.repo.git("add", "-A")
    up.repo.git("commit", "-q", "-m", "Adopt earlier Forge")
    up.repo.git("switch", "-q", "main")
    up.repo.git("merge", "-q", "--ff-only", "adoption")
    up.repo.git("push", "-q", "origin", "main")
    done = up.run(RELEASE)
    assert done.returncode == 0, done.stdout + done.stderr
    _advice(done, "forge test --pytest {base}")
    assert "Ready:" in done.stdout
    upgraded = tomllib.loads(up.show("forge.toml"))
    assert upgraded["test"] == 'python -c "print(123)"'
    assert "fast_test" not in upgraded
    for host in (".claude", ".codex"):
        skill = " ".join(up.show(f"{host}/skills/forge/SKILL.md").split())
        assert "`forge doctor` and `forge upgrade` print one suggested" in skill
