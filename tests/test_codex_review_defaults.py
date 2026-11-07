"""Shipped settings reach real read and close commands, including working prototypes."""
from pathlib import Path

import pytest

from conftest import ROOT
from test_close import GREEN, env  # noqa: F401
from test_codex_worker import _sent, sdk_data  # noqa: F401
from test_fix_the_owner_moved_this_repo_s_workers_from import _codex
from test_prototype_build import _accept_build_decision
from test_setup import _fresh_client

STORY = "FIX-REVIEW-ON-TERRA-MAX"


@pytest.mark.parametrize("scenario", ["new-docs", "new-working-prototype", "forge-source"])
def test_1_shipped_settings_run_codex_reads_and_reviews_on_terra_max(
        env, tmp_path, monkeypatch, sdk_data, scenario):
    # Contract: shipped settings reach the real read and close boundaries, including
    # the prototype path that otherwise replaces review effort with medium.
    # Existing reader/override tests replace these settings and cannot catch routing
    # failures with init or Forge's actual tables. Reuse external stubs, with no seam.
    repo = env.repo
    if scenario == "forge-source":
        env.commit(repo.path, "forge.toml", (ROOT / "forge.toml").read_text("utf-8"),
                   "Use the actual Forge settings")
    else:
        client, initialized = _fresh_client(repo, env.gh, tmp_path)
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr
        repo.path = client
    repo.git("push", "-q", "origin", "main")
    if scenario == "new-working-prototype":
        _accept_build_decision(repo)
    started = repo.forge("fix", "start", "Check default review", "--done", "The review uses Terra",
                         "--kind", "backend")
    assert started.returncode == 0, started.stdout + started.stderr
    where = Path(started.stdout.splitlines()[0].rsplit(" in ", 1)[1])
    if scenario == "new-docs":
        env.commit(where, "README.md", "Client guide.\n", "Add client guide")
    else:
        env.commit(where, "app.py", "print('demo')\n", "Build the demo")
    repo.path = where
    log = _codex(repo, monkeypatch, sdk_data)
    monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.setenv("STUB_SAY", "No findings.")
    env.commit(where, "docs/specs/review-defaults.md", "# Review defaults\n\nUse the shipped models.\n",
               "Describe the model check")
    read = repo.forge("read", "review-defaults")
    assert read.returncode == 0, read.stdout + read.stderr
    [start] = _sent(log, "thread/start")
    assert start["config"]["model"] == "gpt-6.1-terra"
    assert start["config"]["model_reasoning_effort"] == "max"
    env.checks(GREEN)
    closed = env.close("check-default-review")
    assert closed.returncode == 0, closed.stdout + closed.stderr
    [call] = env.review_calls()
    args = call["args"]
    assert args[args.index("--model") + 1] == "codex=gpt-6.1-terra"
    assert args[args.index("--thinking") + 1] == "codex=max"
    if scenario == "new-working-prototype":
        assert "demo breakage" in env.prompt().lower()
