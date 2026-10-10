"""Fast is chosen at the real Forge command / Codex app-server boundary."""
import json
import os
import shutil
import subprocess

import pytest

from conftest import ROOT, _install, patient
from test_close import GREEN, env  # noqa: F401
from test_codex_resume import _resuming
from test_codex_worker import _codex_repo, _sent, sdk_data  # noqa: F401
from test_setup import _fresh_client
from test_upgrade_command import RELEASE, unsynced_up  # noqa: F401

STORY = "FIX-CODEX-FAST-WHEN-NEEDED"
NOTICE = ("Codex Fast is now on when it matters: when other planned work waits "
          "or after the first repair round.")


def _tiers(repo, tiers):
    # Vendor metadata never chooses Forge's tier; the real command does that.
    stub = (ROOT / "tests/stubs/codex-app-server").read_text("utf-8")
    if tiers != "missing":
        stub = stub.replace('"supportedReasoningEfforts": [',
                            '"serviceTiers": ' + repr(tiers) + ', "supportedReasoningEfforts": [')
    _install(repo.bin, "codex-app-server", stub)


def _policy(repo, folder, mode):
    config = folder / "forge.toml"
    text = config.read_text("utf-8")
    text = "\n".join(line for line in text.splitlines() if not line.startswith("codex_fast ="))
    config.write_text(f'codex_fast = {json.dumps(mode)}\n{text}\n', "utf-8")
    repo.git("add", "forge.toml", cwd=folder)
    repo.git("commit", "-qm", "Choose Codex speed", cwd=folder)


@pytest.mark.parametrize("item, mode, tiers, expected", [
    ("HELP", None, [{"id": "priority", "name": "Fast"}], "default"),
    ("PAGE", None, [{"id": "vendor-fast", "name": "Fast"}], "vendor-fast"),
    ("PAGE", "off", [{"id": "priority", "name": "Fast"}], "default"),
    ("HELP", "always", [{"id": "priority", "name": "Speed"}], "priority"),
    ("PAGE", "always", [], "default"),
    ("PAGE", "always", None, "default"),
    ("PAGE", "always", "missing", "default"),
])
def test_1_codex_uses_fast_for_waited_on_work_and_honors_the_setting(
        repo, monkeypatch, sdk_data, item, mode, tiers, expected):
    # Previously all work ignored Fast; models without a tier must remain usable.
    folder, calls = _codex_repo(repo, monkeypatch, sdk_data)
    _tiers(repo, tiers)
    if item == "HELP":
        started = repo.forge("task", "start", "BOARD/HELP")
        assert started.returncode == 0, started.stdout + started.stderr
        folder = repo.path.parent / f"{repo.path.name}-BOARD-HELP"
    if mode:
        _policy(repo, folder, mode)
    worked = repo.forge("work", f"BOARD/{item}")
    assert worked.returncode == 0, worked.stdout + worked.stderr
    assert _sent(calls, "turn/start")[-1].get("serviceTierForTurn") == expected
    if expected != "default" or mode == "always":
        assert _sent(calls, "model/list")


def test_2_repair_rounds_use_fast_and_off_clears_it_on_the_same_conversation(
        repo, monkeypatch, sdk_data):
    folder, calls, _ = _resuming(repo, monkeypatch, sdk_data)
    # The next plan has no waiting work, so only the repair round can enable Fast.
    from test_task import DOC, story
    doc = DOC.replace("| `tests/test_words.py` | PAGE |", "| `tests/test_words.py` | none |")
    story(repo, doc=doc, approved=doc)
    first = repo.forge("work", "BOARD/PAGE")
    assert first.returncode == 0, first.stdout + first.stderr
    assert _sent(calls, "turn/start")[-1].get("serviceTierForTurn") == "default"
    second = repo.forge("work", "BOARD/PAGE")
    assert second.returncode == 0, second.stdout + second.stderr
    assert _sent(calls, "turn/start")[-1].get("serviceTierForTurn") == "priority"
    _policy(repo, folder, "off")
    third = repo.forge("work", "BOARD/PAGE")
    assert third.returncode == 0, third.stdout + third.stderr
    assert _sent(calls, "turn/start")[-1].get("serviceTierForTurn") == "default"
    assert len(_sent(calls, "thread/start")) == 1
    assert _sent(calls, "thread/resume")


@pytest.mark.parametrize("mode, words", [
    ("needed", "when other planned work waits or after the first repair round"),
    ("off", "off"),
    ("always", "always"),
])
def test_3_doctor_reports_the_codex_fast_policy(repo, mode, words):
    repo.write("forge.toml", f'codex_fast = {json.dumps(mode)}\n'
               f'version = "{repo.forge("--version").stdout.split()[-1]}"\n')
    checked = repo.forge("doctor")
    lines = [line.lower() for line in checked.stdout.splitlines() if "codex fast" in line.lower()]
    assert len(lines) == 1, checked.stdout + checked.stderr
    assert words in lines[0]


@pytest.mark.parametrize("value, problem", [
    ('"sometimes"', "codex_fast must be one of needed, off, always"),
    ("true", "codex_fast must be a string"),
])
def test_5_invalid_fast_settings_name_the_problem_and_next_action(repo, value, problem):
    repo.write("forge.toml", f'codex_fast = {value}\n'
               f'version = "{repo.forge("--version").stdout.split()[-1]}"\n')
    refused = repo.forge("doctor")
    assert refused.returncode == 1
    assert refused.stderr == f"forge.toml is not usable: {problem}.\nNext: forge doctor\n"


def test_4_init_and_previous_release_upgrade_deliver_the_default_and_guidance(
        unsynced_up, tmp_path):
    up, repo = unsynced_up, unsynced_up.repo
    client, made = _fresh_client(repo, up.env.gh, tmp_path)
    assert made.returncode == 0, made.stdout + made.stderr
    checked = repo.forge("doctor", cwd=client)
    assert "when other planned work waits or after the first repair round" in checked.stdout
    for host in (".codex", ".claude"):
        skill = (client / host / "skills/forge/SKILL.md").read_text("utf-8")
        assert "codex_fast" in skill and '"off"' in skill and '"always"' in skill

    # Actual files generated by the previous release land before the real upgrade command.
    patient(lambda: shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                                   dirs_exist_ok=True))
    repo.git("switch", "-qc", "adoption")
    repo.git("add", "-A")
    repo.git("commit", "-qm", "Adopt the previous Forge release")
    repo.git("switch", "-q", "main")
    repo.git("merge", "-q", "--ff-only", "adoption")
    repo.git("push", "-q", "origin", "main")
    up.env.checks(GREEN)
    upgraded = up.run(RELEASE)
    assert upgraded.returncode == 0, upgraded.stdout + upgraded.stderr
    assert upgraded.stdout.splitlines().count(NOTICE) == 1
    for host in (".codex", ".claude"):
        assert "codex_fast" in up.show(f"{host}/skills/forge/SKILL.md")
    installed = tmp_path / "uvbin" / ("forge.cmd" if os.name == "nt" else "forge")
    checked = subprocess.run([str(installed), "doctor"], cwd=up.folder,
                             capture_output=True, text=True, timeout=60)
    assert "when other planned work waits or after the first repair round" in checked.stdout
