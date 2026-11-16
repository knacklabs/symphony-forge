"""Forge's outgoing Codex config stays quiet despite user and project preferences."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from conftest import FORGE_SHIM, ROOT, _install
from test_close import GREEN, env  # noqa: F401
from test_codex_resume import _resuming
from test_codex_worker import _sent, sdk_data  # noqa: F401
from test_setup import _fresh_client, _version

STORY = "FIX-CODEX-WORKER-READER-AND-REVIEW-THREADS-S"
QUIET = {
    "model_verbosity": "low",
    "model_reasoning_summary": "none",
    "developer_instructions": "Write no progress commentary. Write only the final handoff and any question.",
}


def test_1_worker_start_resume_and_review_force_quiet_config(env, monkeypatch, sdk_data, tmp_path, claude_session):
    # Contract owner: real Forge commands and pinned SDK, faking only Codex/Autoreview.
    # Previously only model/effort were sent, allowing noisy user or project settings to win.
    repo = env.repo
    folder, calls, _ = _resuming(repo, monkeypatch, sdk_data)
    noisy = ('model_verbosity = "high"\nmodel_reasoning_summary = "detailed"\n'
             'developer_instructions = "Report progress after every step."\n')
    home = Path(os.environ["CODEX_HOME"]) / "config.toml"
    home.write_text(noisy + home.read_text(encoding="utf-8"), encoding="utf-8")
    (folder / ".codex").mkdir(exist_ok=True)
    (folder / ".codex/config.toml").write_text(noisy, encoding="utf-8")
    repo.git("add", "-A", cwd=folder)
    repo.git("commit", "-qm", "Prefer chatty Codex", cwd=folder)
    for _ in range(2):
        done = repo.forge("work", "BOARD/PAGE")
        assert done.returncode == 0, done.stdout + done.stderr
    [start] = _sent(calls, "thread/start")
    assert _sent(calls, "thread/resume")
    for request in [start, *_sent(calls, "thread/resume")]:
        assert {key: request["config"].get(key) for key in QUIET} == QUIET

    # The release also reaches a new client.
    _install(repo.bin, "codex-app-server", (ROOT / "tests/stubs/codex-app-server").read_text(encoding="utf-8"))
    client, made = _fresh_client(repo, env.gh, tmp_path)
    assert made.returncode == 0, made.stdout + made.stderr
    started = repo.forge("fix", "start", "Keep the reader quiet", "--done",
                         "The reader uses quiet settings", "--kind", "mechanical", cwd=client)
    assert started.returncode == 0, started.stdout + started.stderr
    client = Path(started.stdout.splitlines()[0].rsplit(" in ", 1)[1])
    for checkout in (client,):
        synced = repo.forge("sync", cwd=checkout)
        assert synced.returncode == 0, synced.stdout + synced.stderr
        with home.open("a", encoding="utf-8") as trusted:
            trusted.write(f'\n[projects.{json.dumps(str(checkout))}]\ntrust_level = "trusted"\n')
        # Read-only turns now enter through cold reads; questions belong to the session explorer.
        doc = checkout / "docs/specs/quiet-reader.md"
        doc.parent.mkdir(parents=True, exist_ok=True)
        doc.write_text("# Quiet reader\n", "utf-8")
        monkeypatch.setenv("STUB_CODEX_TEXT", "No findings.")
        asked = repo.forge("read", "quiet-reader", cwd=checkout)
        assert asked.returncode == 0, asked.stdout + asked.stderr
        request = _sent(calls, "thread/start")[-1]
        assert {key: request["config"].get(key) for key in QUIET} == QUIET

    # Record the actual Codex argv after Forge's review launcher, rather than the helper's args.
    _install(repo.bin, "codex", '''#!/usr/bin/env python3
import json, pathlib, sys
pathlib.Path(__file__).with_name("review-config.json").write_text(json.dumps(sys.argv[1:]))
''')
    monkeypatch.delenv("CODEX_BIN")
    env.commit(repo.path, "forge.toml", 'checks = ["tests", "forge-pr-check"]\n'
               + (repo.path / "forge.toml").read_text(encoding="utf-8"))
    repo.git("push", "-q", "origin", "main")
    item, _ = env.start_fix()
    env.checks(GREEN)
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    argv = json.loads((repo.bin / "review-config.json").read_text(encoding="utf-8"))
    settings = dict(value.split("=", 1) for flag, value in zip(argv, argv[1:]) if flag == "-c")
    assert {key: json.loads(settings.get(key, "null")) for key in QUIET} == QUIET
