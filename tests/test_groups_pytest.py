"""Pytest groups preserve upgrades and run always_test only in its assigned group.

Test-audit gate:
1. Protects the new and earlier-adopted pytest-split workflow and command behavior, including
   empty groups, failed-file retries, and always_test ownership.
2. A regression can drop the six-group default on upgrade, run the full suite in every group,
   make a genuinely empty pytest group fail, hide a failed Mocha status 5, or fail groups where
   pytest-split placed no always_test node, or hide a persistent always_test failure on retry.
3. Existing group tests cover non-pytest runners and one-group always_test behavior. They do not
   exercise pytest-split through init, upgrade, related-test selection, or grouped retries.
   The failing always_test case keeps that setting while the change selects only test_a;
   it separately guards failure ownership after the one unsplit retry.
4. Each test invokes Forge commands and the real installed pytest-split plugin; no production seam
   is needed.
"""
import json
import os
import re
import shutil
import tomllib
from pathlib import Path

import pytest

from conftest import ROOT
from test_testplace_workflow import _jobs

STORY = "FORGE-GROUPS-1/PYGROUPS"
PYTEST = "pytest tests -q"


def _git(repo, client: Path, *args: str) -> str:
    return repo.git(*args, cwd=client)


def _branch(repo, client: Path, name: str) -> None:
    _git(repo, client, "checkout", "-qb", "fix/" + name)
    fixes = client / ".factory/fixes"
    fixes.mkdir(parents=True, exist_ok=True)
    (fixes / (name + ".json")).write_text(json.dumps({
        "kind": "fix", "branch": "fix/" + name, "why": "Group related pytest tests",
        "done_when": "Related tests run in groups", "status": "started"}), encoding="utf-8")


def _remote_client(repo, client: Path, remote: Path) -> None:
    client.mkdir(parents=True, exist_ok=True)
    repo.git("init", "-q", "--bare", "-b", "main", str(remote))
    repo.git("init", "-q", "-b", "main", cwd=client)
    _git(repo, client, "remote", "add", "origin", remote.as_posix())


def _new_client(repo, gh, tmp_path: Path, name: str) -> Path:
    client = tmp_path / name
    _remote_client(repo, client, tmp_path / (name + ".git"))
    (client / "pyproject.toml").write_text(
        '[project]\nname = "groups-client"\nversion = "0.1.0"\n'
        'requires-python = ">=3.11"\n\n'
        '[dependency-groups]\ndev = ["pytest", "pytest-split"]\n',
        encoding="utf-8")
    gh.respond("api", stdout="{}")
    gh.respond("api", "repos/{owner}/{repo}/branches/main/protection", exit=1,
               stdout='{"message":"Branch not protected","status":"404"}')
    initialized = repo.forge("init", "--actions", "yes", cwd=client)
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    return client


def _adopted_client(repo, tmp_path: Path, name: str) -> Path:
    client = tmp_path / name
    shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", client)
    remote = tmp_path / (name + ".git")
    _remote_client(repo, client, remote)
    _git(repo, client, "add", "-A")
    _git(repo, client, "commit", "-qm", "Keep the earlier Forge adoption")
    _branch(repo, client, "pytest-groups")

    version = repo.forge("--version").stdout.split()[-1]
    config = (client / "forge.toml").read_text(encoding="utf-8")
    config = config.replace('version = "v1.2.2"', f'version = "{version}"')
    config = re.sub(r"^(test|fast_test|groups|always_test) = .*\n", "", config, flags=re.M)
    config = 'test = "' + PYTEST + '"\n' + config
    (client / "forge.toml").write_text(config, encoding="utf-8")
    (client / "requirements.txt").write_text("pytest-split==0.11.0\n", encoding="utf-8")
    synced = repo.forge("sync", cwd=client)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    return client


def _settings(client: Path, **values) -> None:
    config = (client / "forge.toml").read_text(encoding="utf-8")
    config = re.sub(r"^(test|fast_test|groups|always_test) = .*\n", "", config, flags=re.M)
    lines = [f"{name} = {json.dumps(value)}" for name, value in values.items()]
    (client / "forge.toml").write_text("\n".join(lines) + "\n" + config, encoding="utf-8")


def _set_base_to_head(repo, client: Path) -> None:
    head = _git(repo, client, "rev-parse", "HEAD")
    _git(repo, client, "update-ref", "refs/remotes/origin/main", head)
    _git(repo, client, "remote", "set-head", "origin", "main")


def _commit_setup(repo, client: Path, message: str) -> None:
    _git(repo, client, "add", "-A")
    _git(repo, client, "commit", "-qm", message)
    _set_base_to_head(repo, client)


def _write_related_tests(client: Path, receipts: Path, *, assert_source: bool) -> None:
    (client / "src").mkdir(exist_ok=True)
    (client / "tests").mkdir(exist_ok=True)
    (client / "src/cart.py").write_text("VALUE = 1\n", encoding="utf-8")
    for name in ("a", "b"):
        source_check = (
            "    source = Path(__file__).resolve().parents[1] / 'src' / 'cart.py'\n"
            "    assert source.read_text(encoding='utf-8') == 'VALUE = 2\\n'\n"
            if assert_source else "")
        (client / f"tests/test_{name}.py").write_text(
            "from pathlib import Path\n"
            f"receipt = Path({json.dumps((receipts / (name + '.log')).as_posix())})\n"
            f"# src/cart.py\ndef test_{name}():\n"
            + source_check
            + f"    with receipt.open('a', encoding='utf-8') as log:\n"
              f"        log.write({json.dumps(name + ':')} + __import__('os').environ['FORGE_GROUP'] + '\\n')\n",
            encoding="utf-8")


def _group(repo, client: Path, monkeypatch, group: int, groups: int):
    monkeypatch.setenv("FORGE_GROUP", str(group))
    monkeypatch.setenv("FORGE_GROUPS", str(groups))
    return repo.forge("test", "--change", cwd=client)


def _recorded_group(receipts: Path, name: str) -> list[str]:
    path = receipts / (name + ".log")
    return path.read_text(encoding="utf-8").splitlines() if path.exists() else []


@pytest.mark.platform
def test_3_pytest_repos_keep_six_groups_and_new_repos_start_with_one(
        repo, gh, tmp_path, monkeypatch):
    new = _new_client(repo, gh, tmp_path, "new-pytest-client")
    fresh_settings = tomllib.loads((new / "forge.toml").read_text(encoding="utf-8"))
    assert fresh_settings.get("groups") == 1
    fresh_tests = _jobs((new / ".github/workflows/forge.yml").read_text(encoding="utf-8"))["tests"]
    assert "group: [1]" in fresh_tests

    client = _adopted_client(repo, tmp_path, "earlier-pytest-client")
    settings = tomllib.loads((client / "forge.toml").read_text(encoding="utf-8"))
    assert "groups" not in settings
    workflow = (client / ".github/workflows/forge.yml").read_text(encoding="utf-8")
    tests_job = _jobs(workflow)["tests"]
    assert "group: [1, 2, 3, 4, 5, 6]" in tests_job
    assert 'run: "forge test --change"' in tests_job
    assert "--splits" not in workflow
    _settings(client, test=PYTEST, fast_test="forge test --pytest {base}")
    doctor = repo.forge("doctor", cwd=client)
    assert "does not run forge test --change" not in doctor.stdout + doctor.stderr
    assert ("The pull request's tests check runs related tests. The nightly full run covers the rest"
            in doctor.stdout)

    _settings(client, test=PYTEST, groups=2)
    receipts = tmp_path / "related-test-groups"
    receipts.mkdir()
    _write_related_tests(client, receipts, assert_source=True)
    synced = repo.forge("sync", cwd=client)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    tests_job = _jobs((client / ".github/workflows/forge.yml").read_text(encoding="utf-8"))["tests"]
    assert "group: [1, 2]" in tests_job
    _commit_setup(repo, client, "Set up two related pytest files")
    _branch(repo, client, "related-pytest-groups")
    (client / "src/cart.py").write_text("VALUE = 2\n", encoding="utf-8")
    _git(repo, client, "add", "src/cart.py")
    _git(repo, client, "commit", "-qm", "Change the cart")

    for group in (1, 2):
        before_a, before_b = _recorded_group(receipts, "a"), _recorded_group(receipts, "b")
        result = _group(repo, client, monkeypatch, group, 2)
        assert result.returncode == 0, result.stdout + result.stderr
        after_a, after_b = _recorded_group(receipts, "a"), _recorded_group(receipts, "b")
        assert len(after_a) + len(after_b) == len(before_a) + len(before_b) + 1
        assert (len(after_a) > len(before_a)) != (len(after_b) > len(before_b))
    assert {line.rsplit(":", 1)[1] for line in _recorded_group(receipts, "a") +
            _recorded_group(receipts, "b")} == {"1", "2"}
    assert len(_recorded_group(receipts, "a")) == 1
    assert len(_recorded_group(receipts, "b")) == 1

    empty = _group(repo, client, monkeypatch, 3, 3)
    assert empty.returncode == 0, empty.stdout + empty.stderr
    assert "This group got no tests to run." in empty.stdout + empty.stderr

    _settings(client, test=PYTEST, fast_test="pytest -q", groups=2)
    direct_empty = _group(repo, client, monkeypatch, 3, 3)
    assert direct_empty.returncode == 0, direct_empty.stdout + direct_empty.stderr
    assert "This group got no tests to run." in direct_empty.stdout + direct_empty.stderr

    _settings(client, test=PYTEST, groups=2)
    before_a = _recorded_group(receipts, "a")
    before_b = _recorded_group(receipts, "b")
    (client / "tests/test_b.py").write_text(
        "from pathlib import Path\n"
        f"receipt = Path({json.dumps((receipts / 'b.log').as_posix())})\n"
        "# src/cart.py\n"
        "def test_b():\n"
        "    with receipt.open('a', encoding='utf-8') as log:\n"
        "        log.write('b:' + __import__('os').environ['FORGE_GROUP'] + '\\n')\n"
        "    assert False, 'failed test b'\n",
        encoding="utf-8")
    failed_groups = [_group(repo, client, monkeypatch, group, 2) for group in (1, 2)]
    assert sum(result.returncode != 0 for result in failed_groups) == 1
    failure = next(result for result in failed_groups if result.returncode != 0)
    assert "tests/test_b.py::test_b" in failure.stdout + failure.stderr
    assert len(_recorded_group(receipts, "b")) - len(before_b) == 2
    assert len(_recorded_group(receipts, "a")) - len(before_a) == 1
    assert all("This group got no tests to run." not in result.stdout + result.stderr
               for result in failed_groups)

    mocha_dir = client / "node_modules" / ".bin"
    mocha_dir.mkdir(parents=True, exist_ok=True)
    mocha = mocha_dir / "mocha"
    mocha.write_text("#!/bin/sh\nexit 5\n", encoding="utf-8")
    mocha.chmod(0o755)
    (mocha_dir / "mocha.cmd").write_text("@exit /b 5\n", encoding="utf-8")
    monkeypatch.setenv("PATH", str(mocha_dir) + os.pathsep + os.environ["PATH"])
    _settings(client, test="mocha", groups=2)
    non_pytest = _group(repo, client, monkeypatch, 1, 2)
    assert non_pytest.returncode == 5
    assert "This group got no tests to run." not in non_pytest.stdout + non_pytest.stderr


@pytest.mark.platform
@pytest.mark.parametrize("adopted", [False, True], ids=["new", "earlier-adopted"])
@pytest.mark.parametrize("persistent", [False, True], ids=["passing", "persistent"])
def test_5_always_tests_pass_in_their_owning_group(
        repo, gh, tmp_path, monkeypatch, adopted, persistent):
    client = (_adopted_client(repo, tmp_path, "always-adopted-client") if adopted else
              _new_client(repo, gh, tmp_path, "always-new-client"))
    _branch(repo, client, "always-test-groups")
    _settings(client, test=PYTEST, groups=2,
              always_test=["tests/test_b.py::test_b"])
    receipts = tmp_path / ("always-adopted" if adopted else "always-new")
    receipts.mkdir()
    _write_related_tests(client, receipts, assert_source=False)
    if persistent:
        required = client / "tests/test_b.py"
        required.write_text(required.read_text("utf-8") +
                            "    assert False, 'required test b failed'\n", encoding="utf-8")
    synced = repo.forge("sync", cwd=client)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    _commit_setup(repo, client, "Set up always_test group ownership")
    (client / "tests/test_a.py").write_text(
        "from pathlib import Path\n"
        f"receipt = Path({json.dumps((receipts / 'a.log').as_posix())})\n"
        "def test_a():\n"
        "    with receipt.open('a', encoding='utf-8') as log:\n"
        "        log.write('a:' + __import__('os').environ['FORGE_GROUP'] + '\\n')\n",
        encoding="utf-8")
    _git(repo, client, "add", "tests/test_a.py")
    _git(repo, client, "commit", "-qm", "Change only the selected test")

    results = {group: _group(repo, client, monkeypatch, group, 2) for group in (1, 2)}
    required_runs = _recorded_group(receipts, "b")
    assert len(required_runs) == (2 if persistent else 1)
    owner = int(required_runs[0].rsplit(":", 1)[1])
    assert {int(line.rsplit(":", 1)[1]) for line in required_runs} == {owner}
    assert [group for group, result in results.items() if result.returncode != 0] == (
        [owner] if persistent else []), "\n".join(
            result.stdout + result.stderr for result in results.values())
    if persistent:
        failure = results[owner].stdout + results[owner].stderr
        assert "tests/test_b.py::test_b" in failure
        assert all("This group got no tests to run." not in result.stdout + result.stderr
                   for result in results.values())
    assert len(_recorded_group(receipts, "a")) == 1
    assert int(_recorded_group(receipts, "a")[0].rsplit(":", 1)[1]) == 3 - owner
