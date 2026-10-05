"""Missing quick-test settings get advice without changing the repo's tests."""
from __future__ import annotations

import json
import shutil
import tomllib

import pytest

from conftest import ROOT
from test_fix_new_repos_get_claude_as_their_worker_by import _new_repo
from test_upgrade_command import RELEASE, unsynced_up  # noqa: F401
from test_close import env  # noqa: F401

STORY = "FIX-REPOS-WITHOUT-A-QUICK-TEST-SETTING-DON-T"

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
