"""Reviews use the chosen tool and leave model and effort to Autoreview."""
import json
import re
import shutil

import pytest

from conftest import ROOT, patient
from test_setup import _fresh_client, _stub_forge

from test_close import env  # noqa: F401

STORY = "FORGE-TOOLS-1"


@pytest.mark.parametrize("tools,engine", [("claude", "claude"), ("codex", "codex"),
                                         ("both", "codex"), ("new doctor", ""),
                                         ("adopted doctor", "")])
def test_7_reviews_use_the_repos_tool_and_autoreviews_defaults(env, tmp_path, monkeypatch, tools, engine):
    if not engine:
        _doctor_defaults(env, tmp_path, monkeypatch, tools == "adopted doctor")
        return
    settings = env.repo.path / "forge.toml"
    env.commit(env.repo.path, "forge.toml", settings.read_text("utf-8")
               + f'\ntools = "{tools}"\n'
               + '\n[models.review.claude]\nmodel = "sonnet"\neffort = "high"\n'
               + '\n[models.review.codex]\nmodel = "gpt-6-astra"\neffort = "xhigh"\n')
    env.repo.git("push", "-q", "origin", "main")
    item, _ = env.start_fix()
    env.open_pr("Readme greets new readers")
    done = env.close(item)
    assert done.returncode == 0, done.stdout + done.stderr
    [call] = env.review_calls()
    args = call["args"]
    assert args[args.index("--engine") + 1] == engine
    assert "--model" not in args and "--thinking" not in args


def _doctor_defaults(env, tmp_path, monkeypatch, adopted):
    repo = env.repo
    if adopted:
        client = repo.path
        patient(lambda: shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", client,
                                         dirs_exist_ok=True))
        repo.git("add", "-A", cwd=client)
        repo.git("commit", "-qm", "Adopt earlier Forge", cwd=client)
        version = repo.forge("--version").stdout.split()[-1]
        config = client / "forge.toml"
        config.write_text(re.sub(r'^version = .*$', f'version = "{version}"',
                                 config.read_text("utf-8"), flags=re.M), "utf-8")
        repo.git("commit", "-qam", "Pin current Forge", cwd=client)
        repo.git("push", "-q", "origin", "main", cwd=client)
    else:
        client, initialized = _fresh_client(repo, env.gh, tmp_path)
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    started = repo.forge("fix", "start", "Upgrade settings", "--done", "Settings work", cwd=client)
    assert started.returncode == 0, started.stdout + started.stderr
    client = type(client)(started.stdout.splitlines()[0].rsplit(" in ", 1)[1])
    config = client / "forge.toml"
    # The client chooses Claude workers; settings remain byte for byte through sync and doctor.
    config.write_text(re.sub(r'^workers = .*$', 'workers = "claude"',
                             config.read_text("utf-8"), flags=re.M), "utf-8")
    before = config.read_bytes()
    synced = repo.forge("sync", cwd=client)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    assert config.read_bytes() == before
    repo.git("add", "-A", cwd=client)
    repo.git("commit", "-qm", "Upgrade Forge files", cwd=client)
    env.gh.respond("auth", "status")
    codex_home = tmp_path / "doctor-codex"
    codex_home.mkdir()
    (codex_home / "config.toml").write_text(
        f'[projects.{json.dumps(str(client))}]\ntrust_level = "trusted"\n', "utf-8")
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.delenv("CLAUDECODE", raising=False)
    _stub_forge(tmp_path, monkeypatch)
    checked = repo.forge("doctor", cwd=client)
    assert checked.returncode == 0, checked.stdout + checked.stderr
    note = "- Note: reviews don't use forge.toml's review model; Autoreview runs on its own default model and effort."
    assert checked.stdout.count(note) == int(adopted)
    assert config.read_bytes() == before
