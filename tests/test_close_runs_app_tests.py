"""Audit: real close executes a script; the old default skips it with review-only
checks. Existing cases set an explicit place or have no checks. Reuse their
client fixtures without a production seam. Doctor owns full-suite advice.
"""
import json
import sys

import pytest
from conftest import _install

from test_close import env  # noqa: F401
from test_testplace_settings import configure
from test_testplace_upgrade import prepare_adopted_client
from test_setup import _fresh_client, doctor_sdks, sdk_data  # noqa: F401

STORY = "FIX-CI-MODE-NEEDS-A-TEST-CHECK"


@pytest.mark.platform
@pytest.mark.parametrize("adopted", [False, True])
@pytest.mark.parametrize("checks", [["forge-pr-check"], ["tests", "forge-pr-check"]])
def test_1_close_runs_app_tests_unless_a_required_check_does(env, adopted, checks):
    if adopted:
        synced = prepare_adopted_client(env, checks)
        if checks == ["forge-pr-check"]:
            assert "forge.toml names no app test check" in synced
    else:
        configure(env, "local", checks)
        text = (env.repo.path / "forge.toml").read_text("utf-8")
        env.commit(env.repo.path, "forge.toml", text.replace('test_place = "local"\n', ""))
        env.repo.git("push", "-q", "origin", "main")
    item, where = env.start_fix()
    env.open_pr("")
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    receipt = where / "test-count"
    if "tests" in checks:
        assert not receipt.exists()
        assert any(".check_runs[]" in call for call in env.gh.calls())
    else:
        assert receipt.read_text("utf-8") == "run\n"
        assert "tests passed on this machine" in closed.stdout


@pytest.mark.platform
@pytest.mark.parametrize(("test", "fast", "warn", "adopted"), [
    ("runner {base}", "runner", True, False),
    ("vitest run --changed", "", True, False),
    ("jest --onlyChanged", "", True, False),
    ("forge test --pytest main", "", True, False),
    ("pytest tests", "pytest tests", False, False),
    ("vitest run", "vitest run --changed {base}", False, False),
    ("vitest run --changed", "", True, True),
])
def test_2_doctor_warns_about_a_selected_nightly_command(
        repo, gh, tmp_path, monkeypatch, env, doctor_sdks, test, fast, warn, adopted):
    if adopted:
        prepare_adopted_client(env, ["forge-pr-check"])
        client = repo.path
    else:
        client, initialized = _fresh_client(repo, gh, tmp_path)
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    path = client / "forge.toml"
    text = "\n".join(line for line in path.read_text("utf-8").splitlines()
                     if line.partition("=")[0].strip() not in {"test", "fast_test"})
    path.write_text("test = " + json.dumps(test) + "\nfast_test = " + json.dumps(fast) + "\n" + text + "\n", "utf-8")
    gh.respond("auth", "status")
    _install(repo.bin, "codex", f'#!{sys.executable}\nprint("Logged in using ChatGPT")\n')
    codex_home = tmp_path / "trusted-codex"
    codex_home.mkdir()
    (codex_home / "config.toml").write_text(
        f'[projects.{json.dumps(str(client))}]\ntrust_level = "trusted"\n', "utf-8")
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    repo.git("checkout", "-b", "fix/test-command", cwd=client)
    synced = repo.forge("sync", cwd=client)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    result = repo.forge("doctor", cwd=client)
    assert result.returncode == 0, result.stdout + result.stderr
    assert ("The nightly full run needs test to run the full suite" in result.stdout) == warn
