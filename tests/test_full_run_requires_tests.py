"""Full runs reject empty suites, but allow empty partitions of a nonempty suite.

Test-audit: Protect the command's exit and repair message. Empty collection can
falsely pass today. Existing full-run tests only use nonempty suites. Drive real
pytest and Forge commands without a production seam.
"""
import json
import sys

import pytest

from test_groups_pytest import _adopted_client, _new_client, _settings

STORY = "FIX-FULL-RUN-FAILS-WITH-NO-TESTS"


@pytest.mark.platform
@pytest.mark.parametrize("adopted", [False, True], ids=["new", "earlier-adopted"])
def test_1_full_run_fails_when_it_ran_no_tests(repo, gh, tmp_path, monkeypatch, adopted):
    for name in ("PYTEST_ADDOPTS", "FORGE_GROUP", "FORGE_GROUPS", "GITHUB_RUN_ID"):
        monkeypatch.delenv(name, raising=False)
    client = (_adopted_client(repo, tmp_path, "empty-client") if adopted else
              _new_client(repo, gh, tmp_path, "empty-client"))
    hooks = tmp_path / "empty-hooks"
    hooks.mkdir()
    repo.git("config", "core.hooksPath", hooks.as_posix(), cwd=client)
    (client / ".gitignore").write_text("__pycache__/\n.pytest_cache/\n", encoding="utf-8")
    tests = client / "tests"
    tests.mkdir(exist_ok=True)
    suite = tests / "test_suite.py"
    suite.write_text("# No tests yet.\n", encoding="utf-8")
    command = f'{json.dumps(sys.executable)} -m pytest tests -q'
    _settings(client, test=command, groups=2)
    gh.respond("api", "--method", "POST", stdout="{}")

    def publish():
        repo.git("add", "-A", cwd=client)
        repo.git("commit", "-qm", "Configure full suite", cwd=client)
        repo.git("push", "-q", "origin", "HEAD:main", cwd=client)

    publish()
    empty = repo.forge("test", "--full", cwd=client)
    assert empty.returncode != 0, empty.stdout + empty.stderr
    assert "Set test in forge.toml to run the whole suite." in empty.stdout
    if adopted:
        return  # Earlier adoption uses the same runtime path.
    monkeypatch.setenv("GITHUB_RUN_ID", "123")
    monkeypatch.setenv("FORGE_GROUPS", "2")
    for group in (1, 2):
        monkeypatch.setenv("FORGE_GROUP", str(group))
        empty = repo.forge("test", "--full", cwd=client)
        assert empty.returncode != 0, empty.stdout + empty.stderr
        assert "Set test in forge.toml to run the whole suite." in empty.stdout
    suite.write_text("def test_real():\n    assert True\n", encoding="utf-8")
    publish()
    for group in (1, 2):
        monkeypatch.setenv("FORGE_GROUP", str(group))
        ran = repo.forge("test", "--full", cwd=client)
        assert ran.returncode == 0, ran.stdout + ran.stderr
    # A successful wrapper conceals pytest exit 5, leaving only header lines.
    monkeypatch.delenv("FORGE_GROUP")
    monkeypatch.delenv("FORGE_GROUPS")
    _settings(client, test=command + ' -k absent || ' + f'{json.dumps(sys.executable)} -c "pass"')
    publish()
    selected_none = repo.forge("test", "--full", cwd=client)
    assert selected_none.returncode != 0, selected_none.stdout + selected_none.stderr
    assert "Set test in forge.toml to run the whole suite." in selected_none.stdout
