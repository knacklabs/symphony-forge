"""Command-level agreement for waiting and overlapping parts.

Test audit: Stale ancestry and GitHub-only merges can make next offer refused
work. Existing admission tests do not compare both commands for these inputs.
Only external services are faked; no production test seam is needed.
"""
import json
import re
import sys

import pytest

from conftest import GH_STUB, _install
from test_close import env  # noqa: F401
from test_last_task_records_story_outcome import github_merge
from test_stack_start import DOC, configured, reviewed, start
from test_task import story

STORY = "FORGE-FULLCAP-1"


@pytest.mark.parametrize("case,previous", [
    (case, previous) for case in ("behind", "one-base", "two-bases", "overlap", "github-only", "unreviewed-chain")
    for previous in (False, True) if not previous or case == "behind"
])
def test_2_next_lists_only_parts_task_start_accepts(env, case, previous):
    repo = configured(env, previous, setting="off" if case == "overlap" else None)
    doc = DOC.replace("| D |", "| P3 |").replace("| F |", "| W |").replace("| A, E |", "| E, B |")
    if case == "github-only":
        doc = doc.replace("| E, B |", "| A, E |")
    elif case == "overlap":
        # Earlier approvals can still have independent parts with overlapping Scope.
        doc = doc.replace("| C | Extend work | Extend the first value | 1 | `app.py` | `tests/test_work.py` | A | no |",
                          "| C | Extend work | Extend the first value | 1 | `app.py` | `tests/test_work.py` | none | no |")
    story(repo, doc, doc, "STACK")
    repo.git("push", "-q", "origin", "story/STACK")
    if case == "unreviewed-chain":
        start(repo, "A")
    else:
        reviewed(env, "A")
    part, problem = "B", None
    if case == "unreviewed-chain":
        problem = "STACK/B builds on STACK/A, whose latest changes haven't passed review."
    elif case in ("two-bases", "github-only"):
        if case == "two-bases":
            reviewed(env, "B")
        reviewed(env, "E")
        if case == "github-only":
            env.gh.respond("pr", "list", "--state", "merged", stdout=json.dumps([
                {"headRefName": "task/STACK-E"}]))
        part = "W"
        problem = "STACK/W waits for STACK/E, STACK/B, so it starts once all but one of them merge."
        if case == "github-only":
            problem = "STACK/W waits for STACK/A, STACK/E, so it starts once all but one of them merge."
    elif case == "overlap":
        part = "C"
        problem = "STACK/C would change app.py, which STACK/A is changing and hasn't merged yet."
    elif case == "behind":
        reviewed(env, "B")
        reviewed(env, "E")
        for base in ("E", "A"):
            _install(repo.bin, "gh", GH_STUB.format(python=sys.executable))
            github_merge(env, f"task/STACK-{base}")
            merged = repo.forge("merge", f"STACK/{base}")
            assert merged.returncode == 0, merged.stdout + merged.stderr
            (repo.bin / "github-merged").unlink()
            (repo.bin / "github-merge").rename(repo.bin / f"github-merge-{base}")
        part = "W"
        problem = "STACK/W waits for STACK/B to include the merge of STACK/A from main."
    shown = repo.forge("next")
    assert shown.returncode == 0, shown.stdout + shown.stderr
    # Every task start line is an offer, with or without a comment after its item.
    offered = set(re.findall(r"^Next: forge task start (\S+)(?:\s|$)", shown.stdout, re.M))
    if problem is not None:
        refused = repo.forge("task", "start", f"STACK/{part}")
        assert refused.returncode == 1, refused.stdout + refused.stderr
        assert refused.stderr.splitlines()[0] == problem
        assert f"STACK/{part}" not in offered, shown.stdout
        assert problem in shown.stdout, shown.stdout
        for item in sorted(offered):
            accepted = repo.forge("task", "start", item)
            assert accepted.returncode == 0, accepted.stdout + accepted.stderr
    if case == "behind":
        _install(repo.bin, "gh", GH_STUB.format(python=sys.executable))
        env.gh.respond("pr", "list", "--head", "task/STACK-B", "--state", "all",
                       stdout=json.dumps([{"number": 8, "state": "OPEN", "body": "",
                                           "isDraft": False, "baseRefName": "main"}]))
        closed = env.close("STACK/B")
        assert closed.returncode == 0, closed.stdout + closed.stderr
        shown = repo.forge("next")
    elif case == "github-only":
        github_merge(env, "task/STACK-E")
        merged = repo.forge("merge", "STACK/E")
        assert merged.returncode == 0, merged.stdout + merged.stderr
        shown = repo.forge("next")
    elif problem is not None:
        return
    offered = set(re.findall(r"^Next: forge task start (\S+)(?:\s|$)", shown.stdout, re.M))
    assert f"STACK/{part}" in offered, shown.stdout + shown.stderr
    for item in sorted(offered):
        accepted = repo.forge("task", "start", item)
        assert accepted.returncode == 0, accepted.stdout + accepted.stderr
