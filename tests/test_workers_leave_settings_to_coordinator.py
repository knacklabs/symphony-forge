"""Worker commits leave settings to an explicitly scoped settings fix."""
import json
import shutil
import subprocess
import sys

import pytest

from conftest import ROOT, _install
from test_codex_worker import MODELS, _toml, sdk_data  # noqa: F401
from test_setup import _fresh_client
from test_task import DOC, story
from test_worker import calls, install_claude

STORY = "worker-no-settings"


@pytest.fixture(params=[False, True], ids=["new-client", "previous-adoption"])
def client(repo, gh, tmp_path, request):
    if request.param:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
    else:
        repo.path, initialized = _fresh_client(repo, gh, tmp_path)
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    repo.git("switch", "-q", "-c", "fix/settings-setup")
    version = repo.forge("--version").stdout.split()[-1]
    config = (repo.path / "forge.toml").read_text("utf-8")
    config = config.replace('version = "v1.2.2"', f'version = "{version}"')
    config = config.replace('workers = "codex"', 'workers = "claude"').replace(
        'workers = "split"', 'workers = "claude"')
    repo.write("forge.toml", config)
    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stdout + synced.stderr
    repo.git("add", "-A")
    # Fixture setup predates an active Forge item; commits under test use the installed hook.
    repo.git("-c", f"core.hooksPath={tmp_path / 'no-hooks'}", "commit", "-q", "-m", "Setup")
    repo.git("switch", "-q", "main")
    repo.git("merge", "-q", "--ff-only", "fix/settings-setup")
    repo.git("-c", f"core.hooksPath={tmp_path / 'no-hooks'}", "push", "-q", "origin", "main")
    return repo


@pytest.mark.parametrize("case", ["unrelated-worker", "settings-fix", "release-bump", "coordinator"])
def test_1_worker_settings_commits_require_named_done_when(client, monkeypatch, case):
    # The old hook accepted an unrelated worker's settings edit. Only an explicit
    # Done-when now allows it; a note mentioning settings grants no permission.
    named = case in ("settings-fix", "release-bump")
    done = "Update forge.toml settings" if named else "Correct the spelling"
    started = client.forge("fix", "start", "Correct spelling", "--done", done)
    assert started.returncode == 0, started.stdout + started.stderr
    folder = client.path.parent / f"{client.path.name}-fix-correct-spelling"
    config = folder / "forge.toml"
    config.write_text(config.read_text("utf-8") + "\n# Settings change\n", "utf-8")
    if case == "release-bump":
        config.write_text(config.read_text("utf-8").replace(
            client.forge("--version").stdout.split()[-1], "v9.9.9", 1), "utf-8")
    client.git("add", "forge.toml", cwd=folder)
    before = client.git("rev-parse", "HEAD", cwd=folder)
    if case != "coordinator":
        monkeypatch.setenv("FORGE_WORKER", "1")
    committed = subprocess.run(["git", "commit", "-q", "-m", "Change settings"], cwd=folder,
                               capture_output=True, text=True, encoding="utf-8")
    if case == "unrelated-worker":
        assert committed.returncode != 0
        assert committed.stderr == (
            "Workers leave forge.toml to the coordinator; settings change in their own fix "
            "whose Done-when names forge.toml.\n"
            "Next: report the needed settings change in your last message.\n")
        assert client.git("rev-parse", "HEAD", cwd=folder) == before
        # An unstaged settings edit must not block an unrelated staged product change.
        client.git("restore", "--staged", "forge.toml", cwd=folder)
        (folder / "spelling.txt").write_text("Correct spelling\n", "utf-8")
        client.git("add", "spelling.txt", cwd=folder)
        client.git("commit", "-q", "-m", "Correct spelling", cwd=folder)
    else:
        assert committed.returncode == 0, committed.stdout + committed.stderr
        assert client.git("rev-parse", "HEAD", cwd=folder) != before


def test_2_fresh_and_resumed_workers_report_needed_settings_changes(client):
    log = install_claude(client)
    started = client.forge("fix", "start", "Correct spelling", "--done", "Correct the spelling")
    assert started.returncode == 0, started.stdout + started.stderr
    for round_number in (1, 2):
        worked = client.forge("work", "correct-spelling", "--note", "fast_test needs a command")
        assert worked.returncode == 0, worked.stdout + worked.stderr
        call = calls(log)[-1]
        assert ("--resume" in call["args"]) == (round_number == 2)
        brief = " ".join(call["brief"].split())
        assert "Workers never edit `forge.toml`." in brief
        assert "Report a needed settings change in your last message instead." in brief
        assert "Never edit it even temporarily." in brief
        assert "To run an extra suite, run its command directly alongside `forge test`." in brief


@pytest.mark.parametrize("covered", [False, True], ids=["context-only", "covered-item"])
def test_3_task_permission_comes_from_its_current_covered_done_when(client, monkeypatch, covered):
    # A settings mention in another task's criterion must not authorize this task.
    number = "1. The board shows every story." if covered else "2. Each story has a state sentence."
    doc = DOC.replace(number, number + " Update forge.toml.")
    story(client, doc=doc, approved=doc)
    started = client.forge("task", "start", "BOARD/API")
    assert started.returncode == 0, started.stdout + started.stderr
    folder = client.path.parent / f"{client.path.name}-BOARD-API"
    config = folder / "forge.toml"
    config.write_text(config.read_text("utf-8") + "\n# Settings change\n", "utf-8")
    client.git("add", "forge.toml", cwd=folder)
    monkeypatch.setenv("FORGE_WORKER", "1")
    committed = subprocess.run(["git", "commit", "-q", "-m", "Change settings"], cwd=folder,
                               capture_output=True, text=True, encoding="utf-8")
    assert (committed.returncode == 0) == covered, committed.stdout + committed.stderr
    if not covered:
        assert "settings change in their own fix" in committed.stderr


@pytest.mark.parametrize("family", ["claude", "codex"])
@pytest.mark.parametrize("case", ["unstaged", "staged", "named", "failed"])
def test_4_worker_round_restores_uncommitted_settings_unless_done_when_names_them(
        client, monkeypatch, sdk_data, tmp_path, family, case):
    # The fake model edits files; real forge work owns restoration, permission and hand-back.
    if family == "claude":
        install_claude(client)
        worker = client.bin / "claude"
        source = worker.read_text("utf-8")
        insertion = 'print("stub claude: built it")'
        cwd = "pathlib.Path.cwd()"
        if case == "failed":
            monkeypatch.setenv("STUB_CLAUDE_EXIT", "1")
    else:
        client.git("switch", "-q", "fix/settings-setup")
        client.write("forge.toml", _toml(client.forge("--version").stdout.split()[-1],
                                        "codex", MODELS, "client"))
        client.git("-c", f"core.hooksPath={tmp_path / 'no-hooks'}", "commit", "-qam", "Use Codex")
        client.git("switch", "-q", "main")
        client.git("merge", "-q", "--ff-only", "fix/settings-setup")
        client.git("-c", f"core.hooksPath={tmp_path / 'no-hooks'}", "push", "-q", "origin", "main")
        worker = client.bin / "codex-app-server"
        source = (ROOT / "tests/stubs/codex-app-server").read_text("utf-8")
        insertion = '                if os.environ.get("STUB_CODEX_TOUCH"):'
        cwd = "pathlib.Path(cwd)"
        monkeypatch.setenv("XDG_DATA_HOME", str(sdk_data))
        home = tmp_path / "settings-codex-home"
        home.mkdir()
        (home / "config.toml").write_text(
            f'[projects.{json.dumps(str(client.path))}]\ntrust_level = "trusted"\n', "utf-8")
        monkeypatch.setenv("CODEX_HOME", str(home))
        monkeypatch.setenv("CODEX_BIN", str(worker.with_suffix(".cmd") if sys.platform == "win32" else worker))
        if case == "failed":
            monkeypatch.setenv("STUB_CODEX_STATUS", "failed")
    edit = f'''settings = {cwd} / "forge.toml"
settings.write_text(settings.read_text("utf-8") + "\\n# Temporary worker settings\\n", encoding="utf-8")
({cwd} / "product.txt").write_text("Product work\\n", encoding="utf-8")
'''
    if case == "staged":
        edit += f'import subprocess\nsubprocess.run(["git", "add", "forge.toml"], cwd={cwd}, check=True)\n'
    indent = " " * 16 if family == "codex" else ""
    edit = "".join(indent + line + "\n" for line in edit.splitlines())
    _install(client.bin, worker.name, source.replace(insertion, edit + insertion, 1))
    named = case == "named"
    started = client.forge("fix", "start", "Correct spelling", "--done",
                           "Update forge.toml" if named else "Correct the spelling")
    assert started.returncode == 0, started.stdout + started.stderr
    folder = client.path.parent / f"{client.path.name}-fix-correct-spelling"
    before = (folder / "forge.toml").read_bytes()
    worked = client.forge("work", "correct-spelling")
    assert worked.returncode == (1 if case == "failed" else 0), worked.stdout + worked.stderr
    message = "Restored uncommitted forge.toml changes from this branch; settings change in their own fix."
    if named:
        assert (folder / "forge.toml").read_bytes().startswith(before)
        assert (folder / "forge.toml").read_bytes() != before
        assert message not in worked.stdout
    else:
        assert (folder / "forge.toml").read_bytes() == before
        assert client.git("status", "--porcelain", "--", "forge.toml", cwd=folder) == ""
        assert message in worked.stdout
    assert (folder / "product.txt").read_text("utf-8") == "Product work\n"
