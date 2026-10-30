"""Review rounds leave visible follow-ups and workers can decline minor repairs.

Commands own the verdict and publication; only external tools supply fake replies.
Exercises src/forge/close.py, src/forge/review.py, src/forge/score.py and src/forge/board.py.
"""
import json
import re
import shutil
import sys
from pathlib import Path

import pytest

from conftest import FORGE_SHIM, ROOT, _install, patient
from test_close import CLEAN, GREEN, blocked, body, env, finding  # noqa: F401
from test_close_keeps_reviews_for_unchanged_branch_diffs import client as setup_client
from test_story import DOC, READER, approved_constitution, new_story
from test_fix_plan_reads_capped import _client as read_client
from test_readloop_gates import dispose_all, say
from test_records import SPEC
from test_land import ITEM, _fix, _land, _red_checks, _steps, _workers, land  # noqa: F401
from test_task import story
from test_worker import calls, install_claude

STORY = "FORGE-ROUNDS-1"

LIVE_RUN = ("Before review round two, run the real flow once (not tests or stubs). "
            "Add `Live run: <what you ran> - <what you saw>` to your `Functional check:` paragraph.")


def client(env, adopted):
    config = (env.repo.path / "forge.toml").read_text("utf-8")
    setup_client(env, adopted)
    env.commit(env.repo.path, "forge.toml", config +
               'models.grill.claude = { model = "opus", effort = "high" }\n',
               "Use the test reader and checks")
    env.repo.git("push", "-q", "origin", "main")
    env.checks(GREEN)


def note(priority, title, line=1):
    result = finding(priority, title, line=line)
    result["body"] = ("Gain 5, Work 1, Harm 5" if priority == "P0" else
                      "Gain 4, Work 1, Harm 2") + "\nCase: normal use - Saving a basket loses its quantity."
    return result


def published(env):
    return body((env.gh_calls("pr", "edit") or env.gh_calls("pr", "create"))[-1])


def known(env, where):
    shown = env.repo.forge("board", "--json", cwd=where)
    assert shown.returncode == 0, shown.stdout + shown.stderr
    return {row["title"]: row for row in json.loads(shown.stdout)["known_issues"]}


@pytest.mark.parametrize("target", ["SHOP", "invoices"])
def test_2_round_two_prompts_only_for_new_p0_gaps(repo, gh, tmp_path, target):
    # The read-stop outcomes belong to test_3. Keep one walk for each target here
    # to check the round-two prompt and its treatment of earlier notes.
    read_client(repo, gh, tmp_path, False)
    where = new_story(repo, "SHOP")
    (where / "plans/SHOP.md").write_text(DOC, encoding="utf-8")
    rel = "plans/SHOP.md" if target == "SHOP" else "docs/specs/invoices.md"
    doc = where / rel
    if target != "SHOP":
        doc.parent.mkdir(parents=True, exist_ok=True)
        doc.write_text(SPEC, encoding="utf-8")
        saved = repo.forge("spec", "save", target, cwd=where)
        assert saved.returncode == 0, saved.stdout + saved.stderr
    notes = doc.with_suffix(".read.md")
    first = "Saving has no recovery rule."
    say(repo, f"1. Blocking: {first}\n   Case: normal use - A shopper reopens a saved basket.\n"
        "   Gain 4, Work 1, Harm 2\n")
    first_read = repo.forge("read", target, cwd=where)
    assert first_read.returncode == 0, first_read.stdout + first_read.stderr
    dispose_all(notes)
    say(repo, "No findings.\n")
    second = repo.forge("read", target, cwd=where)
    assert second.returncode == 0, second.stdout + second.stderr
    assert "found nothing" in second.stdout
    calls = repo.bin / "claude-calls.jsonl"
    prompts = [json.loads(line)["prompt"] for line in calls.read_text("utf-8").splitlines()]
    assert len(prompts) == 2
    prompt = " ".join(prompts[-1].split())
    assert "P0" in prompt and "normal use" in prompt and "only" in prompt
    assert "Look for new gaps anywhere in the doc" not in prompt
    assert first in prompts[-1] and "Disposition: cut" in prompts[-1]
    assert "Is each of those findings closed?" in prompt
    text = notes.read_text("utf-8")
    assert "passed: yes\n" in text
    assert "Left open after round two" not in text
    next_step = repo.forge("next", cwd=where)
    assert next_step.returncode == 0, next_step.stdout + next_step.stderr
    assert ("Plan Mode" if target == "SHOP" else "forge spec confirm invoices") in next_step.stdout
    assert f"Next: forge read {target}" not in next_step.stdout


@pytest.mark.parametrize("adopted,case", [(False, "p0"), (False, "p1"), (True, "p0")])
def test_4_round_two_reviews_only_round_one_findings_and_p0s_that_happen_in_normal_use(env, adopted, case):
    client(env, adopted)
    old = note("P1", "Saving loses quantities")
    env.reviews(blocked(old))
    item, where = env.start_task(changes={"app.py": "save = False\n\nlegacy = True\n"})
    reviewed = env.repo.git("rev-parse", "HEAD", cwd=where).strip()
    first = env.close(item)
    assert first.returncode == 1 and old["title"] in first.stderr, first.stdout + first.stderr
    env.commit(where, "app.py", "save = True\n\nlegacy = True\n", "Repair saving")
    new = note(case.upper(), "Saving breaks the main path" if case == "p0" else
               "Legacy output loses quantities", line=3)
    env.reviews(blocked(new))
    closed = env.close(item)
    if case == "p0":
        assert closed.returncode == 1 and new["title"] in closed.stderr, closed.stdout + closed.stderr
    else:
        assert closed.returncode == 1, closed.stdout + closed.stderr
        assert "reached the round limit with open findings" in closed.stderr
        assert new["title"] in closed.stderr
    assert len(env.review_calls()) == 2
    prompt = " ".join(env.prompt().split())
    assert old["title"] in prompt
    assert "fixed" in prompt and "not fixed" in prompt
    assert "only" in prompt and "P0" in prompt and "normal use" in prompt
    assert "main path" in prompt and "Harm 4" in prompt
    args = env.review_calls()[-1]["args"]
    assert args[args.index("--base") + 1] == reviewed


@pytest.mark.parametrize("adopted,case", [(False, "rare finding"), (False, "declined"),
                                         (False, "declined p0"), (False, "rare note"),
                                         (True, "declined")])
def test_5_rare_cases_and_declined_findings_do_not_block(env, adopted, case):
    client(env, adopted)
    if case == "rare note":
        _install(env.repo.bin, "claude", READER.format(python=sys.executable))
        (env.repo.bin / "claude-says.md").write_text(
            "1. Blocking: An unusual basket import loses a quantity.\n"
            "   Gain 4, Work 1, Harm 4\n"
            "   Case: rare - An operator edits the import file during saving.\n", encoding="utf-8")
        env.commit(env.repo.path, "plans/roadmap.json", json.dumps({"items": [{"key": "SHOP"}]}))
        env.repo.git("push", "-q", "origin", "main")
        approved_constitution(env.repo)
        where = new_story(env.repo, "SHOP")
        (where / "plans/SHOP.md").write_text(DOC, encoding="utf-8")
        read = env.repo.forge("read", "SHOP")
        assert read.returncode == 0, read.stdout + read.stderr
        notes = (where / "plans/SHOP.read.md").read_text("utf-8")
        assert "passed: yes\n" in notes and "An unusual basket import" in notes
        call = json.loads((env.repo.bin / "claude-calls.jsonl").read_text("utf-8").splitlines()[-1])
        prompt = call["prompt"]
    else:
        entry = note("P0" if case == "declined p0" else "P1", "Saving loses quantities")
        if case == "rare finding":
            entry["body"] = ("Gain 4, Work 1, Harm 4\n"
                             "Case: rare - An operator edits the import file during saving.")
        env.reviews(blocked(entry))
        # A story part permits the worker-decline flow before the review limit.
        item, where = env.start_fix() if case == "rare finding" else env.start_task()
        first = env.close(item)
        if case == "rare finding":
            assert first.returncode == 0, first.stdout + first.stderr
            assert entry["title"] in published(env).split("Follow-ups:", 1)[1]
        else:
            assert first.returncode == 1 and entry["title"] in first.stderr, first.stdout + first.stderr
            decline = "Declined: Saving loses quantities (app.py): not worth the code - The repair costs more than this case."
            env.repo.git("commit", "--allow-empty", "-q", "-m", "Keep the current save flow", "-m", decline,
                         cwd=where)
            reused = env.close(item)
            assert len(env.review_calls()) == 1, reused.stdout + reused.stderr
            if case == "declined p0":
                assert reused.returncode == 1 and entry["title"] in reused.stderr, reused.stdout + reused.stderr
                return
            assert reused.returncode == 0 and "Ready" in reused.stdout, reused.stdout + reused.stderr
            assert known(env, where)[entry["title"]]["reason"].startswith("Declined as not worth the code:")
            env.commit(where, "app.py", "print('hello reader')\n", "Clarify the greeting")
            later = env.close(item)
            assert later.returncode == 0, later.stdout + later.stderr
            assert len(env.review_calls()) == 2
            assert decline in env.prompt()
        prompt = env.prompt()
    assert "Review rules" in prompt and "recorded owner decision" in prompt
    assert "Decided:" in prompt and "Ruling:" in prompt


@pytest.mark.parametrize("case", ["tests", "session"])
def test_3_land_runs_at_most_one_fix_round(
        land, monkeypatch, case):
    if case == "tests":
        # Run a real client test command. Its assertion checks the client's actual stdout;
        # the worker's unrelated commit cannot repair the failed greeting by itself.
        command = f'"{Path(sys.executable).as_posix()}" verify.py'
        land.commit(land.repo.path, "verify.py", "import subprocess, sys\n"
                    "actual = subprocess.run([sys.executable, 'app.py'], check=True, "
                    "capture_output=True, text=True)\n"
                    "assert actual.stdout == 'welcome\\n', 'client greeting missing'\n")
        config = (land.repo.path / "forge.toml").read_text("utf-8")
        config = re.sub(r"(?m)^test_place\s*=.*(?:\r?\n|$)", "", config)
        land.commit(land.repo.path, "forge.toml", 'test_place = "local"\n'
                    + "test = " + json.dumps(command) + "\n" + config)
        land.repo.git("push", "-q", "origin", "main")
    where = _fix(land, "working", worked=True)
    # The old three-repair contract becomes one repair for local tests and session CI checks.
    from test_close import run
    land.reviews(CLEAN)
    if case == "session":
        land.checks([run("tests", "failure"), run("forge-pr-check")])
        _red_checks(land)
    what = "the failing tests" if case == "tests" else "the failing checks"
    expected = f"Stopped after one fix round: {ITEM} still has {what}."
    if case == "tests":
        stopped = _land(land)
        assert stopped.returncode == 1, stopped.stdout + stopped.stderr
        assert _steps(stopped) == [f"Closing {ITEM}.",
                                  f"Fix round 1 of 1: the worker fixes {what}.",
                                  f"Closing {ITEM}.", expected]
        assert "client greeting missing" in stopped.stdout + stopped.stderr
        assert "client greeting missing" in _workers(land)[0]["brief"]
        assert len(_workers(land)) == 1 and len(land.review_calls()) == 2
        return

    from test_tools_session_hold import Session
    monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
    monkeypatch.setenv("CLAUDECODE", "1")
    # Exercise the native handback round limit rather than the installed SDK route.
    monkeypatch.setenv("XDG_DATA_HOME", str(land.tmp / "without-claude-sdk"))
    host = Session(land.repo, land.tmp / "host", "claude-session")
    try:
        first = host.forge("land", ITEM)
        assert first.returncode == 0, first.stdout + first.stderr
        assert _steps(first) == [f"Closing {ITEM}.",
                                 "Fix round 1 of 1: the worker fixes the failing checks."]
        land.commit(where, "round-1.txt", "Repaired tests\n", "Worker round")
        number = re.search(r"--round (\d+)", first.stdout)[1]
        handed = host.forge("handback", ITEM, "--round", number, "--subagent", "w1", input="Fixed.")
        assert handed.returncode == 0, handed.stdout + handed.stderr
        stopped = host.forge("land", ITEM)
        assert stopped.returncode == 1, stopped.stdout + stopped.stderr
        assert _steps(stopped) == [f"Closing {ITEM}.", expected]
        assert len(land.review_calls()) == 2 and not _workers(land)
    finally:
        host.close()


@pytest.mark.parametrize("case", ["task", "ui", "continued-ui", "backend"])
def test_6_a_user_facing_change_asks_for_one_live_run_and_refuses_nothing_without_it(
        env, case):
    client(env, adopted=case != "task")
    log = install_claude(env.repo)
    if case == "task":
        story(env.repo)
        started = env.repo.forge("task", "start", "BOARD/PAGE")
        item, branch = "BOARD/PAGE", "task/BOARD-PAGE"
    else:
        kind = "backend" if case == "backend" else "ui"
        started = env.repo.forge("fix", "start", "Show the saved basket", "--done",
                                 "A returning shopper sees their saved basket", "--kind", kind)
        item, branch = "show-the-saved-basket", "fix/show-the-saved-basket"
    assert started.returncode == 0, started.stdout + started.stderr
    listed = env.repo.git("worktree", "list", "--porcelain")
    where = Path(re.search(rf"^worktree (.+)\n[^\n]*\nbranch refs/heads/{branch}$", listed, re.M)[1])
    if case == "continued-ui":
        # The first real worker receives the saved pre-upgrade full brief. Keep its actual
        # conversation record so the current command must supply the new request on resume.
        earlier = env.tmp / "earlier-forge-src"
        patient(lambda: shutil.copytree(ROOT / "src/forge", earlier / "forge", dirs_exist_ok=True,
                                        ignore=shutil.ignore_patterns("__pycache__")))
        # Match the wheel's bundled authoring guidance when copying current worker code.
        patient(lambda: shutil.copytree(ROOT / ".codex/skills/test-audit",
                                        earlier / "forge/templates/skills/test-audit", dirs_exist_ok=True))
        patient(lambda: shutil.copy(ROOT / "tests/fixtures/worker-brief-before-delegation.md",
                                    earlier / "forge/templates/brief.md"))
        launcher = env.repo.bin / "forge"
        current = launcher.read_text("utf-8")
        try:
            patient(lambda: launcher.write_text(FORGE_SHIM.format(
                python=Path(sys.executable).as_posix(), src=earlier.as_posix()), "utf-8"))
            worked = env.repo.forge("work", item)
        finally:
            patient(lambda: launcher.write_text(current, "utf-8"))
    else:
        worked = env.repo.forge("work", item)
    assert worked.returncode == 0, worked.stdout + worked.stderr
    brief = " ".join(calls(log)[-1]["brief"].split())
    if case == "backend":
        assert "Live run:" not in brief
        return
    if case == "continued-ui":
        assert "Live run:" not in brief
    else:
        assert LIVE_RUN in brief
    if case in ("task", "continued-ui"):
        # Both task and UI-fix continuations must carry the request in their shorter brief.
        worked = env.repo.forge("work", item)
        assert worked.returncode == 0, worked.stdout + worked.stderr
        resumed = calls(log)[-1]
        brief = " ".join(resumed["brief"].split())
        assert "The earlier brief in this conversation still applies." in brief
        assert resumed["options"].get("resume")
    assert LIVE_RUN in brief
    if case == "ui":
        env.commit(where, "app.py", "print('saved basket')\n",
                   "Show the saved basket\n\nFunctional check: Opened the basket and saw its saved contents.")
        assert "Live run:" not in env.repo.git("log", "-1", "--format=%B", cwd=where)
        closed = env.close(item)
        assert closed.returncode == 0, closed.stdout + closed.stderr
        assert len(env.review_calls()) == 1
