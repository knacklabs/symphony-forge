"""Full runs reject empty suites, but allow empty partitions of a nonempty suite.

Test-audit: Protect the command's exit and repair message. Empty collection can
falsely pass today. Existing full-run tests only use nonempty suites. Drive real
pytest and Forge commands without a production seam.
"""
import json

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
    command = 'python -m pytest tests -q'
    _settings(client, test=command, groups=2)
    gh.respond("api", "--method", "POST", stdout="{}")

    def publish():
        repo.git("add", "-A", cwd=client)
        repo.git("commit", "--allow-empty", "-qm", "Configure full suite", cwd=client)
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
    for workers in ("", " -n 2"):
        _settings(client, test=command + workers, groups=2)
        publish()
        for group in (1, 2):
            monkeypatch.setenv("FORGE_GROUP", str(group))
            ran = repo.forge("test", "--full", cwd=client)
            assert ran.returncode == 0, ran.stdout + ran.stderr
            if group == 2:
                assert "This group got no tests to run." in ran.stdout
    # A successful wrapper conceals pytest exit 5, leaving only header lines.
    monkeypatch.delenv("FORGE_GROUP")
    monkeypatch.delenv("FORGE_GROUPS")
    _settings(client, test=command + ' -k absent || python -c "pass"')
    publish()
    selected_none = repo.forge("test", "--full", cwd=client)
    assert selected_none.returncode != 0, selected_none.stdout + selected_none.stderr
    assert "Set test in forge.toml to run the whole suite." in selected_none.stdout
    # Other runners have no pytest receipt. A real unittest suite must stay green.
    (client / "unittest_suite.py").write_text(
        "import unittest\nclass Suite(unittest.TestCase):\n"
        "    def test_real(self):\n        self.assertEqual(2 + 2, 4)\n"
        "unittest.main()\n", encoding="utf-8")
    _settings(client, test="python unittest_suite.py")
    publish()
    ran = repo.forge("test", "--full", cwd=client)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    # Stub only the external runner's text protocol, not Forge's classification.
    for message in ("No test files found, exiting with code 0", "No tests found, exiting with code 0"):
        _settings(client, test="python -c " + json.dumps(f"print({message!r})"))
        publish()
        ran = repo.forge("test", "--full", cwd=client)
        assert ran.returncode != 0, ran.stdout + ran.stderr
        assert "Set test in forge.toml to run the whole suite." in ran.stdout
