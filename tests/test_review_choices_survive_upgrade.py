"""Choices remain usable on reviews written before review merge bases were recorded."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import FORGE_SHIM, ROOT
from test_close import env  # noqa: F401
from test_close_waits_for_review_loop_choice import stopped
from test_hotspot_stop import saved
from test_review_choices_apply_to_unchanged_work import _records_stop

STORY = "the-owner-s-review-loop-choice-often-can"


def _old_stop(env, monkeypatch, records, merge_before_stop=False):
    source = env.tmp / "old-source"
    shutil.copytree(ROOT / "src/forge", source / "forge",
                    ignore=shutil.ignore_patterns("__pycache__"))
    fixture = ROOT / "tests/fixtures/review-before-choice-base"
    for name in ("close.py", "review.py"):
        shutil.copy(fixture / name, source / "forge" / name)
    launcher = env.tmp / "old-forge"
    launcher.write_text(FORGE_SHIM.format(python=Path(sys.executable).as_posix(),
                                         src=source.as_posix()), "utf-8")

    def old_close(item, *args):
        if merge_before_stop and len(env.review_calls()) == 2:
            env.commit(env.repo.path, "BEFORE.md", "Upstream work before the stopped review\n")
            env.repo.git("push", "-q", "origin", "main")
        return subprocess.run([sys.executable, str(launcher), "close", item, *args],
                              cwd=env.repo.path, capture_output=True, text=True,
                              encoding="utf-8", timeout=120)

    with monkeypatch.context() as old:
        old.setattr(env, "close", old_close)
        item, where = _records_stop(env) if records else stopped(env)
    result = saved(where, item)["review"]
    assert "branch_diff" in result and "base" not in result
    return item, where


@pytest.mark.parametrize("choice", ["accept", "dismiss"])
@pytest.mark.parametrize("drift", ["default", "records", "merged-default"])
def test_6_pre_upgrade_stopped_reviews_keep_the_owners_choice(env, monkeypatch, choice, drift):
    item, where = _old_stop(env, monkeypatch, drift == "records", drift == "merged-default")
    if drift != "records":
        env.repo.git("merge", "-q", "--ff-only", saved(where, item)["review"]["commit"])
        env.commit(env.repo.path, "NEWS.md", "Other work landed\n")
        env.repo.git("push", "-q", "origin", "main")
    before = len(env.review_calls())
    if choice == "accept":
        result = env.close(item, "--resolve", "accept", "--reason", "Owner accepts this work")
        assert result.returncode == 0, result.stdout + result.stderr
        assert len(env.review_calls()) == before
        if drift == "records":
            result = env.close(item)
            assert result.returncode == 0, result.stdout + result.stderr
            assert len(env.review_calls()) == before
    else:
        result = env.close(item, "--resolve", "narrow", "--reason", "Owner keeps this small")
        assert result.returncode == 0, result.stderr
        args = ["--dismiss", "1", "--because", "src/a.py:1 Proven safe"]
        if drift == "records":
            args += ["--dismiss", "2", "--because", "app.py:1 The result is implemented"]
        result = env.close(item, *args)
        assert result.returncode == 0, result.stdout + result.stderr
        assert "Ready:" in result.stdout


@pytest.mark.parametrize("change", ["code", "contract"])
def test_7_pre_upgrade_reviews_still_refuse_unreviewed_work(env, monkeypatch, change):
    item, where = _old_stop(env, monkeypatch, True)
    if change == "code":
        env.commit(where, "app.py", "print('unreviewed')\n")
    else:
        state = saved(where, item)
        state["done_when"] += "; a new requirement"
        env.commit(where, f".factory/fixes/{item}.json", json.dumps(state))
    before = len(env.review_calls())
    result = env.close(item, "--resolve", "accept", "--reason", "Owner accepts")
    assert result.returncode == 1
    assert "code or scope changed since the stopped review" in result.stderr
    assert len(env.review_calls()) == before
