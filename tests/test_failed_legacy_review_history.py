"""A failed earlier review cannot establish modern review ordinals or finding novelty.

Test-audit: existing timing-only proofs cover successful reviews and omit the
failed producer's missing step. Actual old close produces that evidence here;
modern ordinary and mechanical closes publish truthful board and PR history.
Only the external reviewer and GitHub are faked; no production seam is needed.
"""
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone

import pytest

from conftest import FORGE_SHIM, ROOT, _install
from test_close import CLEAN, FAILED, PIN, blocked, body, env, finding  # noqa: F401
from test_item_time_history import records, row
from test_story import worktree

STORY = "FIX-WHERE-TIME-WENT"


@pytest.mark.parametrize("mechanical", [False, True], ids=["ordinary", "merge-switch"])
def test_25_failed_earlier_review_keeps_retry_ordinal_and_unseen_findings_unknown(
        env, monkeypatch, mechanical):
    old = env.tmp / "old-release"
    shutil.copytree(ROOT / "tests/fixtures/forge-v1.2.2", old)
    (old / "src/forge/cli-py.txt").rename(old / "src/forge/cli.py")
    # The raw fixture omits its packaged prompt; supply compatible earlier text, not lifecycle code.
    shutil.copy2(ROOT / "tests/fixtures/pr-check-before-branch-diff/templates/review.md",
                 old / "src/forge/templates/review.md")
    _install(env.repo.bin, "old-forge", FORGE_SHIM.format(
        python=sys.executable, src=(old / "src").as_posix()))
    modern = (env.repo.path / "forge.toml").read_text("utf-8")
    earlier = modern.replace(re.search(r'version = "[^"]+"', modern)[0], 'version = "v1.2.2"')
    env.commit(env.repo.path, "forge.toml", earlier, "Use earlier Forge")
    env.repo.git("push", "-q", "origin", "main")
    began = datetime(2026, 1, 1, tzinfo=timezone.utc)
    monkeypatch.setenv("FORGE_NOW", began.isoformat())
    item = "let-the-agent-merge" if mechanical else "retain-failed-review"
    why = "Let the agent merge this repo's ready pull requests." if mechanical else "Retain failed review"
    done = ('The default branch\'s forge.toml sets merge = "agent".' if mechanical
            else "Unrecorded findings remain unknown")

    def earlier_command(*args):
        return subprocess.run([sys.executable, str(env.repo.bin / "old-forge"), *args],
                              cwd=env.repo.path, capture_output=True, text=True, timeout=60)

    started = earlier_command("fix", "start", why, "--done", done, "--slug", item)
    assert started.returncode == 0, started.stdout + started.stderr
    where = worktree(env.repo, "fix/" + item)
    if mechanical:
        # The raw fixture has no merge-enable module; this is its owner's sole settings edit.
        env.commit(where, "forge.toml", earlier + 'merge = "agent"\n', "Allow agent merges")
    else:
        env.commit(where, "app.py", "print('hello')\n", "Greet readers")
    stamp = env.tmp / "autoreview/.upstream-sha"
    old_pin = re.search(r'AUTOREVIEW_PIN = "(\w+)"',
                        (old / "src/forge/review.py").read_text("utf-8"))[1]
    stamp.write_text(old_pin + "\n", "utf-8")
    env.reviews(FAILED)
    failed = earlier_command("close", item)
    assert failed.returncode == 1, failed.stdout + failed.stderr
    assert "the model is unavailable" in failed.stderr
    saved = json.loads((where / f".factory/fixes/{item}.json").read_text("utf-8"))
    assert not any(step["step"] == "review" for step in saved["steps"])
    prior = [t for t in records(env.repo, "timings.jsonl") if t["item"] == item and t["step"] == "review"]
    assert len(prior) == 1 and prior[0]["outcome"] == "failed" and "round" not in prior[0]
    events = env.repo.path / ".git/forge/events.jsonl"
    assert not events.exists() or not any(e.get("event") == "review result" and e.get("item") == item
                                          for e in records(env.repo, "events.jsonl"))

    # Upgrade landed settings, then the outstanding branch, as an existing client does.
    env.commit(env.repo.path, "forge.toml", modern, "Upgrade Forge")
    env.repo.git("push", "-q", "origin", "main")
    env.repo.git("fetch", "-q", "origin", cwd=where)
    env.repo.git("merge", "-q", "--no-edit", "origin/main", cwd=where)
    stamp.write_text(PIN + "\n", "utf-8")
    monkeypatch.setenv("FORGE_NOW", (began + timedelta(seconds=30)).isoformat())
    env.reviews(CLEAN if mechanical else blocked(finding("P1", "Greeting disappears")))
    retried = env.close(item)
    assert retried.returncode == (0 if mechanical else 1), retried.stdout + retried.stderr
    if not mechanical:
        assert "serious findings" in retried.stderr
    else:
        assert "Ready:" in retried.stdout
    history = row(env.repo, item)["rounds"]
    assert len(history) == 2, history
    legacy, current = history
    assert legacy["worker_round"] is None and "review failed" in legacy["line"]
    assert legacy["findings"] is None and legacy["round"] is None
    assert current["round"] is None, current
    if mechanical:
        assert current["findings"] == []
    else:
        assert current["findings"] == [{"priority": "P1", "title": "Greeting disappears", "file": "app.py"}]
        assert current["new_findings"] is None and current["repeat_findings"] is None
    published = body(env.gh_calls("pr", "edit")[-1])
    assert published.index(legacy["line"]) < published.index(current["line"])
