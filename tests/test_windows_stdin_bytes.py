"""Forge sends a program's stdin as the exact UTF-8 bytes on every OS.

Audit: this Mac cannot run Windows, so the forge process loads a sitecustomize that does what
Windows text-mode stdin does (each "\\n" written becomes "\\r\\n"). The stub GitHub records the
exact bytes of the bounded body piped to `gh pr merge` and refuses one over its limit.
"""
import json
import re
import shutil

import pytest

from conftest import ROOT
from test_close import CLEAN, GREEN, env  # noqa: F401
from test_last_task_records_story_outcome import github_merge
from test_pull_request_body_limit import LIMIT, latest_body, reject_oversized_bodies

STORY = "windows-stdin-bytes"

WINDOWS_STDIN = '''import subprocess
_save = subprocess.Popen._save_input
def _save_input(self, input):
    # Windows writes text-mode stdin through a TextIOWrapper that turns "\\n" into "\\r\\n".
    if self.text_mode and isinstance(input, str):
        input = input.replace("\\n", "\\r\\n")
    return _save(self, input)
subprocess.Popen._save_input = _save_input
'''


def start_new_client(env):
    """A client repo set up by this release's forge init, checked out fresh."""
    repo = env.repo
    client, remote = env.tmp / "new-client", env.tmp / "new-client.git"
    repo.git("init", "-q", "--bare", "-b", "main", str(remote))
    repo.git("init", "-q", "-b", "main", str(client))
    repo.git("remote", "add", "origin", str(remote), cwd=client)
    env.gh.respond("api", stdout="{}")
    initialized = repo.forge("init", cwd=client)
    assert initialized.returncode == 0, initialized.stderr
    repo.git("clone", "-q", str(remote), str(env.tmp / "new-checkout"))
    repo.path = env.tmp / "new-checkout"
    keep_review_settings(env)


def keep_review_settings(env):
    """The stub review's settings, keeping the client's generated files."""
    version = env.repo.forge("--version").stdout.split()[-1]
    env.commit(env.repo.path, "forge.toml", f'version = "{version}"\nworkers = "claude"\n'
               'checks = ["tests", "forge-pr-check"]\n'
               'models.build = { model = "opus", effort = "high" }\n')


def adopt_earlier_release(env):
    """A client repo adopted on an earlier release, then upgraded and synced to this one."""
    repo = env.repo
    repo.git("switch", "-qc", "fix/upgrade-client")
    shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path, dirs_exist_ok=True)
    repo.git("add", "-A")
    repo.git("commit", "-qm", "Adopt the previous release")
    env.commit(repo.path, ".factory/fixes/upgrade-client.json", json.dumps({
        "kind": "fix", "branch": "fix/upgrade-client", "why": "Upgrade Forge",
        "done_when": "The client uses this release", "status": "started"}))
    config = repo.path / "forge.toml"
    version = repo.forge("--version").stdout.split()[-1]
    config.write_text(config.read_text().replace('"v1.2.2"', json.dumps(version)))
    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stderr
    repo.git("add", "-A")
    repo.git("commit", "-qm", "Upgrade Forge")
    # The owner's merge lands the upgrade; a fresh clone stands in for it (main refuses commits).
    checkout = env.tmp / "upgraded-checkout"
    remote = repo.git("remote", "get-url", "origin")
    repo.git("clone", "-q", "--branch", "fix/upgrade-client", str(repo.path), str(checkout))
    repo.path = checkout
    repo.git("remote", "set-url", "origin", remote)
    repo.git("switch", "-qc", "main")
    repo.git("push", "-q", "origin", "main")
    repo.git("fetch", "-q", "origin")
    repo.git("remote", "set-head", "origin", "main")
    keep_review_settings(env)


@pytest.mark.parametrize("history", ["new", "adopted"])
def test_1_a_bounded_pull_request_body_reaches_github_with_unchanged_newlines(
        env, monkeypatch, history):
    if history == "adopted":
        adopt_earlier_release(env)
    else:
        start_new_client(env)
    env.commit(env.repo.path, "forge.toml",
               (env.repo.path / "forge.toml").read_text("utf-8") + 'merge = "agent"\n')
    env.repo.git("push", "-q", "origin", "main")
    windows = env.tmp / "windows-stdin"
    windows.mkdir()
    (windows / "sitecustomize.py").write_text(WINDOWS_STDIN, "utf-8")
    monkeypatch.setenv("PYTHONPATH", str(windows))
    item, where = env.start_fix()
    # Thousands of distinct proof lines: the body is cut to GitHub's limit but keeps its newlines.
    message = "Greet readers\n\nProof list:\n" + "".join(f"- checked greeting {n}\n" for n in range(6_000))
    message_file = env.tmp / "proof-message.txt"
    message_file.write_bytes(message.encode("utf-8"))
    env.repo.git("commit", "-q", "--amend", "--file", str(message_file), cwd=where)
    env.open_pr("")
    env.checks(GREEN)
    env.reviews(CLEAN)
    reject_oversized_bodies(env)
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    text = latest_body(env)
    github_merge(env, "fix/tidy-readme")
    gh = env.repo.bin / "gh"
    gh.write_text(gh.read_text("utf-8").replace('"isDraft": False', f'"isDraft": False, "body": {text!r}'),
                  "utf-8")
    reject_oversized_bodies(env)
    merged = env.repo.forge("merge", item)
    assert merged.returncode == 0, merged.stdout + merged.stderr
    sent = latest_body(env)
    assert json.loads((env.repo.bin / "submitted-bodies.jsonl").read_text("utf-8").splitlines()[-1])[
        "operation"] == "merge"
    # A body this close to the limit with this many lines would exceed it if any newline grew.
    assert len(sent.encode("utf-8")) + sent.count("\n") > LIMIT
    assert "\r" not in sent
    assert re.search(r"shorten|omit|trim", sent, re.I)
    assert "- checked greeting 0" in env.repo.git("log", "-1", "--format=%B", "origin/main")
