"""Close keeps a clean review and sends only conflict repairs to Autoreview.

Test-audit: this command contract protects reuse, the patch sent to the reviewer,
and tests on merged code. A full-base fallback or a skipped test run regresses it.
Existing reuse tests create no conflicts. Only external services are faked; no
production seam is added. Cases share setup at the owning command boundary.
"""
import json
import re
import subprocess
import sys

import pytest

from test_close import CLEAN, blocked, env, finding  # noqa: F401
from test_close_keeps_reviews_for_unchanged_branch_diffs import client

STORY = "FORGE-SPLITREVIEW-1"


@pytest.mark.parametrize("previous,case", [
    (False, "clean"), (False, "conflict"), (False, "multiple"),
    (False, "extra-file"), (False, "blocked-conflict"), (False, "open-finding"),
    (False, "task-contract"), (False, "fix-contract"), (False, "skipped"),
    (True, "conflict"),
], ids=lambda value: str(value))
def test_1_close_reviews_only_conflict_repairs_and_unreviewed_edits(env, previous, case):
    client(env, previous)
    for host in (".codex", ".claude"):
        guide = env.repo.path / host / "skills/forge/SKILL.md"
        assert "only conflict repairs and later worker edits need review" in guide.read_text("utf-8")
    # A real test command records the app contents at the tested head, outside the repo.
    marker = env.tmp / "tested.jsonl"
    script = ("import json, pathlib, subprocess\n"
              "text = subprocess.check_output(['git', 'show', 'HEAD:app.py'], text=True)\n"
              f"with pathlib.Path({json.dumps(marker.as_posix())}).open('a', encoding='utf-8') as log:\n"
              "    log.write(json.dumps(text) + '\\n')\n")
    env.commit(env.repo.path, "check_merged.py", script)
    settings = (env.repo.path / "forge.toml").read_text("utf-8")
    settings = re.sub(r"^(?:test|fast_test|test_place)\s*=.*\n", "", settings, flags=re.M)
    command = subprocess.list2cmdline([sys.executable, "check_merged.py"])
    env.commit(env.repo.path, "forge.toml",
               'test_place = "local"\ntest = ' + json.dumps(command) + "\n" + settings)
    original = "".join(f"line_{number} = {number}\n" for number in range(1, 31))
    own = original.replace("line_1 = 1\n", "reviewed_line = 1\n")
    conflict = case in ("conflict", "multiple", "extra-file", "blocked-conflict")
    if conflict:
        own = own.replace("line_10 = 10\n", "branch_value = 10\n")
    env.commit(env.repo.path, "app.py", original)
    env.repo.git("push", "-q", "origin", "main")
    item, where = (env.start_fix(changes={"app.py": own}) if case == "fix-contract"
                   else env.start_task(changes={"app.py": own}))
    env.reviews(blocked(finding("P1", "Greeting is missing")) if case == "open-finding" else CLEAN)
    first = (env.close(item, "--no-review", "--by", "A Person", "--reason", "Owner chose to skip")
             if case == "skipped" else env.close(item))
    assert first.returncode == (1 if case == "open-finding" else 0), first.stdout + first.stderr
    calls = len(env.review_calls())
    if case == "task-contract":
        plan = (where / "plans/SHOP.md").read_text("utf-8")
        env.commit(where, "plans/SHOP.md", plan + "\n## For the builders\nKeep the greeting short.\n")
    elif case == "fix-contract":
        amended = env.repo.forge("fix", "amend", item, "--done", "The greeting names the shop",
                                 "--because", "The owner clarified the greeting")
        assert amended.returncode == 0, amended.stdout + amended.stderr
    incoming = original.replace("line_25 = 25\n", "incoming_line = 25\n")
    env.commit(env.repo.path, "app.py", incoming)
    env.repo.git("push", "-q", "origin", "main")
    if case == "multiple":
        env.repo.git("fetch", "origin", cwd=where)
        env.repo.git("merge", "--no-edit", "origin/main", cwd=where)
    if conflict:
        incoming = incoming.replace("line_10 = 10\n", "main_value = 10\n")
        env.commit(env.repo.path, "app.py", incoming)
        env.repo.git("push", "-q", "origin", "main")
    env.gh.respond("pr", "list", "--head", stdout='[{"number":7,"state":"OPEN",'
                   '"body":"","isDraft":false,"mergeStateStatus":"BEHIND"}]')
    env.reviews(CLEAN)
    if conflict:
        refused = env.close(item)
        assert refused.returncode == 1, refused.stdout + refused.stderr
        assert "conflict" in (refused.stdout + refused.stderr).lower()
        assert len(env.review_calls()) == calls
        env.repo.git("fetch", "origin", cwd=where)
        merge = subprocess.run(["git", "merge", "--no-edit", "origin/main"], cwd=where,
                               capture_output=True, text=True)
        assert merge.returncode != 0, merge.stdout + merge.stderr
        resolved = own.replace("branch_value = 10\n", "resolved_value = 10\n").replace(
            "line_25 = 25\n", "incoming_line = 25\n")
        env.commit(where, "app.py", resolved)
        if case == "extra-file":
            env.commit(where, "worker-only.py", "unreviewed_edit = True\n")
        if case == "blocked-conflict":
            env.reviews(blocked(finding("P1", "Conflict repair loses the greeting", line=10)))
    before = len(marker.read_text("utf-8").splitlines())
    closed = env.close(item)
    assert closed.returncode == (1 if case == "blocked-conflict" else 0), closed.stdout + closed.stderr
    tested = [json.loads(line) for line in marker.read_text("utf-8").splitlines()]
    assert len(tested) == before + 1
    assert tested[-1] == (where / "app.py").read_text("utf-8")
    assert "incoming_line = 25\n" in tested[-1]
    if case == "clean":
        assert len(env.review_calls()) == calls
        return
    assert len(env.review_calls()) == calls + 1
    patch = env.review_calls()[-1]["diff"]
    if conflict:
        assert "+resolved_value = 10" in patch
        assert "+reviewed_line = 1" not in patch
        assert "+incoming_line = 25" not in patch
        assert sum(line.startswith("@@ ") for line in patch.splitlines()) == (2 if case == "extra-file" else 1)
        assert ("+unreviewed_edit = True" in patch) == (case == "extra-file")
        assert "Earlier lines were reviewed clean at" in env.prompt()
        assert "## Repair review" not in env.prompt()
    else:
        assert "+reviewed_line = 1" in patch
        assert "Earlier lines were reviewed clean at" not in env.prompt()
    if case != "blocked-conflict":
        again = env.close(item)
        assert again.returncode == 0, again.stdout + again.stderr
        assert len(env.review_calls()) == calls + 1
