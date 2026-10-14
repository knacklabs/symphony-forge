"""Time history follows the published pull request across independent machines.

Audit: existing time tests keep one machine's logs. These command tests protect
cross-machine reconciliation, overlapping story time and human-readable rounding.
Only GitHub and review reports are faked; no Forge helper is imported.
"""
import json
import re
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from test_close import CLEAN, GREEN, STORY_DOC, approve_story, body, blocked, env, finding, run  # noqa: F401
from test_close_keeps_reviews_for_unchanged_branch_diffs import client
from test_item_time_history import row
from test_board import seen
from test_board_keys_rule import agents_md_allows_story_keys
from test_board_sections import pinned_bar_and_folding_sections
from test_board_story_history import story_history_lists_read_rounds
from test_last_task_records_story_outcome import github_merge
from test_worker import install_claude

STORY = "FORGE-BOARD-2"


def published(env, item, *, merged_at=None):
    calls = env.gh_calls("pr", "edit") or env.gh_calls("pr", "create")
    text = body(calls[-1])
    pr = {"number": 7, "headRefName": f"fix/{item}", "body": text,
          "headRefOid": env.repo.git("ls-remote", "origin", f"refs/heads/fix/{item}").split()[0],
          "title": "Keep the basket", "state": "MERGED" if merged_at else "OPEN",
          "mergedAt": merged_at, "isDraft": False,
          "mergedBy": {"login": "ana", "name": "Ana"},
          "url": "https://github.com/acme/shop/pull/7"}
    env.gh.respond("pr", "list", stdout=json.dumps([pr]))
    # Every machine's pull request lists are cached for a minute; here that minute has passed.
    for cache in env.tmp.rglob("prs-cache.json"):
        cache.unlink()
    return text


def github_list_fields(env):
    # GitHub only returns requested fields and rows matching the requested state.
    gh = env.repo.bin / "gh"
    gh.write_text(gh.read_text("utf-8").replace('sys.stdout.write(rule["stdout"])', '''output = rule["stdout"]
        if args[:2] == ["pr", "list"] and "--json" in args:
            fields = args[args.index("--json") + 1].split(",")
            state = args[args.index("--state") + 1].upper() if "--state" in args else "ALL"
            output = json.dumps([{k: v for k, v in pr.items() if k in fields}
                                 for pr in json.loads(output) if state == "ALL" or pr["state"] == state])
        sys.stdout.write(output)'''), "utf-8")


@pytest.mark.parametrize("case,previous", [("shared-fix", False), ("shared-fix", True),
                                          ("story-runway", False), ("rebuilt-history", False),
                                          ("question-wait", False), ("conflict-wait", False),
                                          ("item-totals", False), ("approved-runway-known", False),
                                          ("approved-runway-unknown", False), ("real-read-runway", False),
                                          ("read-history-batching", False), ("refresh-stale-receipt", False),
                                          ("refresh-missing-receipt", False), ("resume-published-wait", False),
                                          ("warm-checks-cache", False), ("story-full-runway", False),
                                          ("story-full-runway", True), ("bad-null-event", False),
                                          ("bad-infinite-seconds", False), ("bad-huge-seconds", False),
                                          ("bad-deep-nesting", False),
                                          ("story-done-runway", False)],
                         ids=["new-client", "earlier-adoption", "story-runway", "rebuilt-history",
                              "question-wait", "conflict-wait", "item-totals", "approved-runway-known",
                              "approved-runway-unknown", "real-read-runway", "read-history-batching",
                              "refresh-stale-receipt", "refresh-missing-receipt", "resume-published-wait",
                              "warm-checks-cache", "story-full-runway-new", "story-full-runway-adopted",
                              "bad-null-event", "bad-infinite-seconds", "bad-huge-seconds",
                              "bad-deep-nesting", "story-done-runway"])
def test_5_how_it_went_is_shared_and_story_time_counts_each_instant_once(env, monkeypatch, case, previous):
    if case == "story-full-runway":
        client(env, previous)
        story_full_runway(env, monkeypatch)
        return
    if case == "story-done-runway":
        client(env, previous)
        story_full_runway(env, monkeypatch, done=True)
        return
    if case == "warm-checks-cache":
        warm_checks_cache(env, monkeypatch)
        return
    if case == "story-runway":
        story_runway(env, monkeypatch)
        return
    if case == "rebuilt-history":
        rebuilt_history(env)
        return
    if case.startswith("bad-"):
        malformed_record(env, case)
        return
    if case == "question-wait":
        question_wait(env, monkeypatch)
        return
    if case == "conflict-wait":
        conflict_wait(env, monkeypatch)
        return
    if case == "item-totals":
        item_totals(env, monkeypatch)
        return
    if case.startswith("approved-runway-"):
        approved_runway(env, monkeypatch, case == "approved-runway-known")
        return
    if case == "real-read-runway":
        real_read_runway(env, monkeypatch)
        return
    if case == "read-history-batching":
        read_history_batching(env, monkeypatch)
        return
    if case.startswith("refresh-") or case == "resume-published-wait":
        shared_ready_refresh(env, monkeypatch, case == "refresh-missing-receipt",
                             case == "resume-published-wait")
        return
    client(env, previous)
    github_list_fields(env)
    version = env.repo.forge("--version").stdout.split()[-1]
    env.commit(env.repo.path, "forge.toml", f'version = "{version}"\nstage = "live"\n'
               'workers = "claude"\ntest = "echo passed"\nchecks = ["tests", "forge-pr-check"]\n'
               'models.build = { model = "opus", effort = "high" }\n')
    env.repo.git("push", "-q", "origin", "main")
    started = env.repo.forge("fix", "start", "Keep the basket", "--done", "The basket stays",
                             "--slug", "keep-basket")
    assert started.returncode == 0, started.stderr
    item = "keep-basket"
    # Locate the worktree through git, without assuming Forge's sibling-folder convention.
    listing = env.repo.git("worktree", "list", "--porcelain")
    where = next(Path(block.splitlines()[0].removeprefix("worktree "))
                 for block in listing.split("\n\n") if f"branch refs/heads/fix/{item}" in block)
    env.commit(where, "app.py", "print('basket')\n")
    env.reviews(blocked(finding("P1", "Basket disappears")))
    env.checks([run("tests", None, "queued"), run("forge-pr-check")])
    first = env.close(item)
    assert first.returncode == 1, first.stdout + first.stderr
    published(env, item)
    machine_a = env.repo.path
    remote = env.repo.git("remote", "get-url", "origin")
    machine_b = env.tmp / "second-machine"
    env.repo.git("clone", "-q", remote, str(machine_b))
    env.repo.path = machine_b
    resumed = env.tmp / "resumed-basket"
    env.repo.git("worktree", "add", "-q", "-b", f"fix/{item}", str(resumed), f"origin/fix/{item}")
    assert not (machine_b / ".git/forge/events.jsonl").exists()
    env.commit(resumed, "app.py", "print('keep basket')\n")
    env.checks(GREEN)
    second = env.close(item)
    assert second.returncode == 1, second.stdout + second.stderr
    published(env, item)
    env.commit(resumed, "app.py", "print('basket stays')\n")
    env.reviews(CLEAN)
    third = env.close(item)
    assert third.returncode == 0, third.stdout + third.stderr
    published(env, item)
    fixed_now = datetime.now(timezone.utc) + timedelta(seconds=60)
    monkeypatch.setenv("FORGE_NOW", fixed_now.isoformat())
    on_b = row(env.repo, item)
    assert [(r["new_findings"], r["repeat_findings"]) for r in on_b["rounds"]] == [(1, 0), (0, 1), (0, 0)]
    assert on_b["time_breakdown"]["waiting_for_ci"] is not None
    assert on_b["approved_by"] is None
    assert on_b["started_by"] == "Forge Test"
    assert on_b["gates"]["review"]["status"] == "clean"
    assert on_b["stage"] == "ready"
    env.repo.path = machine_a
    on_a = row(env.repo, item)
    assert on_a["stage"] == "ready"
    next_step = env.repo.forge("next")
    assert next_step.returncode == 0, next_step.stderr
    assert any("keep-basket" in line and "is ready" in line
               for line in next_step.stdout.splitlines())
    for field in ("intervals", "time_breakdown", "rounds", "total_seconds",
                  "working_seconds", "waiting_seconds", "unknown_seconds"):
        assert on_a[field] == on_b[field], field
    # A's stale local logs must not erase B's reviews when A publishes next.
    env.repo.git("merge", "--no-edit", f"origin/fix/{item}", cwd=where)
    reviewed = len(env.review_calls())
    again = env.close(item)
    assert again.returncode == 0, again.stdout + again.stderr
    assert len(env.review_calls()) == reviewed, "The published clean review must survive the move"
    published(env, item)
    after = row(env.repo, item)
    assert after["rounds"][:2] == on_b["rounds"][:2]
    # Reusing the clean review adds a new CI result and advances its open wait.
    assert [(r["new_findings"], r["repeat_findings"]) for r in after["rounds"]] == [(1, 0), (0, 1), (0, 0)]
    assert "CI passed, then passed" in after["rounds"][2]["line"]
    # A's old local receipt and the unchanged PR body cannot approve a newer PR head.
    env.repo.path = machine_b
    env.repo.git("fetch", "-q", "origin")
    env.repo.git("merge", "--no-edit", f"origin/fix/{item}", cwd=resumed)
    env.commit(resumed, "app.py", "print('basket stays after another change')\n")
    env.repo.git("push", "-q", "origin", f"fix/{item}", cwd=resumed)
    published(env, item)
    env.repo.path = machine_a
    assert row(env.repo, item)["stage"] != "ready"
    next_step = env.repo.forge("next")
    assert next_step.returncode == 0, next_step.stderr
    assert not any("basket" in line.lower() and "is ready" in line
                   for line in next_step.stdout.splitlines())
    env.repo.path = machine_b
    updated = env.close(item)
    assert updated.returncode == 0, updated.stdout + updated.stderr
    published(env, item)
    env.repo.path = machine_a
    assert row(env.repo, item)["stage"] == "ready"
    merged_at = (fixed_now + timedelta(seconds=30)).isoformat()
    published(env, item, merged_at=merged_at)
    monkeypatch.setenv("FORGE_NOW", (fixed_now + timedelta(hours=1)).isoformat())
    done = row(env.repo, item)
    waits = [interval for interval in done["intervals"] if interval["category"] == "waiting_for_owner"]
    assert datetime.fromisoformat(waits[-1]["end"]) == datetime.fromisoformat(merged_at)
    monkeypatch.setenv("FORGE_NOW", (fixed_now + timedelta(hours=2)).isoformat())
    assert row(env.repo, item)["total_seconds"] == done["total_seconds"]
    assert done["time_breakdown"]["waiting_for_owner"] > on_b["time_breakdown"]["waiting_for_owner"]
    assert done["merged_by"] in ("Ana", {"login": "ana", "name": "Ana"})


def item_totals(env, monkeypatch):
    began = datetime(2026, 10, 10, 10, tzinfo=timezone.utc)
    at = lambda seconds: (began + timedelta(seconds=seconds)).isoformat()
    monkeypatch.setenv("FORGE_NOW", at(60))
    state = {"steps": [{"step": "start", "at": at(0)}]}
    fix, _ = env.start_fix(**state)
    part, _ = env.start("SHOP/T1", "task/SHOP-T1", ".factory/stories/SHOP/tasks/T1.json", state,
                        {"app.py": "print('saved basket')\n"})
    events, timings = [], []
    for item in (fix, part):
        events.extend([
            {"id": item + "-phase", "item": item, "round": 1, "event": "work phase", "phase": "building", "at": at(10)},
            {"id": item + "-worker", "item": item, "round": 1, "event": "run start", "kind": "worker", "at": at(10)},
            {"id": item + "-end", "item": item, "round": 1, "event": "run end", "kind": "worker", "run_id": item + "-worker", "at": at(20)},
            {"id": item + "-wait", "item": item, "round": 1, "event": "owner wait start", "reason": "merge", "at": at(45)},
            {"id": item + "-wait-end", "item": item, "round": 1, "event": "owner wait end", "wait_id": item + "-wait", "at": at(55)},
        ])
        timings.extend([
            {"item": item, "round": 1, "step": "review", "start": at(25), "seconds": 5, "outcome": "clean"},
            {"item": item, "round": 1, "step": "CI wait", "start": at(30), "seconds": 10, "outcome": "passed"},
        ])
    top = env.repo.path / ".git/forge"
    top.mkdir(exist_ok=True)
    for name, records in (("events", events), ("timings", timings)):
        (top / f"{name}.jsonl").write_text("".join(json.dumps(record) + "\n" for record in records), "utf-8")
    expected = [(0, 10, "unknown"), (10, 20, "working"), (20, 25, "unknown"),
                (25, 30, "working"), (30, 40, "waiting"), (40, 45, "unknown"),
                (45, 55, "waiting"), (55, 60, "unknown")]
    for item in (fix, part):
        current = row(env.repo, item)
        assert [(interval["start"], interval["end"], interval["kind"]) for interval in current["intervals"]] == [
            (at(start), at(end), kind) for start, end, kind in expected]
        for kind, seconds in (("working", 15), ("waiting", 20), ("unknown", 25)):
            assert current[f"{kind}_seconds"] == seconds
        assert current["total_seconds"] == 60
        assert current["time_breakdown"]["nothing_running"] == 15


def approved_runway(env, monkeypatch, known):
    began = datetime(2026, 10, 10, 10, tzinfo=timezone.utc)
    at = lambda seconds: (began + timedelta(seconds=seconds)).isoformat()
    monkeypatch.setenv("FORGE_NOW", at(60))
    approve_story(env.repo, STORY_DOC)
    listing = env.repo.git("worktree", "list", "--porcelain")
    story_tree = next(Path(block.splitlines()[0].removeprefix("worktree "))
                      for block in listing.split("\n\n") if "branch refs/heads/story/SHOP" in block)
    notes = (story_tree / "plans/SHOP.read.md").read_text("utf-8")
    notes = re.sub(r"^read_at:.*$", "read_at: " + at(0), notes, flags=re.M)
    notes = re.sub(r"^seconds:.*\n", "", notes, flags=re.M)
    if known:
        notes = notes.replace("\n---", "\nseconds: 10\n---", 1)
    env.commit(story_tree, "plans/SHOP.read.md", notes)
    env.repo.git("push", "-q", "origin", "story/SHOP", cwd=story_tree)
    current = row(env.repo, "SHOP")
    assert current["approved_by"] == "Forge Test"
    assert current["gates"]["plan_read"]["status"] == "passed"
    assert current["children"] == []
    assert current["total_seconds"] == (70 if known else 60)
    assert current["working_seconds"] == (10 if known else 0)
    assert current["waiting_seconds"] == 0
    assert current["unknown_seconds"] == 60
    assert current["time_breakdown"] == {"working": 10 if known else 0, "waiting": 0, "unknown": 60}
    assert current["intervals"][-1] == {"start": at(0), "end": at(60), "kind": "unknown"}


def real_read_runway(env, monkeypatch):
    read_at = datetime(2026, 10, 10, 10, tzinfo=timezone.utc)
    monkeypatch.setenv("FORGE_NOW", read_at.isoformat())
    # This helper executes the real read command and approval hook; no receipt is inserted.
    approve_story(env.repo, STORY_DOC)
    monkeypatch.setenv("FORGE_NOW", (read_at + timedelta(seconds=60)).isoformat())
    current = row(env.repo, "SHOP")
    assert current["approved_by"] == "Forge Test"
    assert current["gates"]["plan_read"]["status"] == "passed"
    assert current["time_breakdown"]["working"] > 0
    assert current["time_breakdown"]["waiting"] == 0
    assert current["time_breakdown"]["unknown"] == 60
    assert any(interval["kind"] == "working" and datetime.fromisoformat(interval["end"]) == read_at
               for interval in current["intervals"])
    assert current["total_seconds"] == pytest.approx(current["time_breakdown"]["working"] + 60)


def read_history_batching(env, monkeypatch):
    began = datetime(2026, 10, 10, 10, tzinfo=timezone.utc)
    at = lambda seconds: (began + timedelta(seconds=seconds)).isoformat()
    monkeypatch.setenv("FORGE_NOW", at(220))
    for key in ("SHOP", "PACK"):
        approve_story(env.repo, STORY_DOC, key)
    listing = env.repo.git("worktree", "list", "--porcelain")
    trees = {key: next(Path(block.splitlines()[0].removeprefix("worktree "))
                       for block in listing.split("\n\n") if f"branch refs/heads/story/{key}" in block)
             for key in ("SHOP", "PACK")}
    original = (trees["SHOP"] / "plans/SHOP.read.md").read_text("utf-8")
    counts = {"json": [], "html": []}
    for rounds in (2, 10):
        previous = ""
        for number in range(1, rounds + 1):
            notes = re.sub(r"^read_at:.*$", "read_at: " + at(number * 20), original, flags=re.M)
            notes = re.sub(r"^round:.*$", "round: " + str(number), notes, flags=re.M)
            notes = re.sub(r"^(?:seconds|notes_seen):.*\n", "", notes, flags=re.M)
            fields = "\nseconds: 5" + ("\nnotes_seen: " + previous if previous else "")
            notes = notes.replace("\n---", fields + "\n---", 1)
            # Historical notes are actual Git objects, including objects unreachable from refs.
            stored = subprocess.run(["git", "hash-object", "-w", "--stdin"], cwd=env.repo.path,
                                    input=notes, capture_output=True, text=True, encoding="utf-8", check=True)
            previous = stored.stdout.strip()
        for key, tree in trees.items():
            env.commit(tree, f"plans/{key}.read.md", notes)
            env.repo.git("push", "-q", "origin", f"story/{key}", cwd=tree)
        for mode in ("json", "html"):
            trace = env.tmp / f"git-{mode}-{rounds}.jsonl"
            monkeypatch.setenv("GIT_TRACE2_EVENT", trace.as_posix())
            page = env.tmp / "read-history-board.html"
            result = env.repo.forge("board", *(('--json',) if mode == "json" else ('--out', str(page))))
            monkeypatch.delenv("GIT_TRACE2_EVENT")
            assert result.returncode == 0, result.stdout + result.stderr
            if mode == "json":
                items = {item["id"]: item for item in json.loads(result.stdout)["items"]}
                for key in trees:
                    assert items[key]["time_breakdown"] == {
                        "working": rounds * 5, "waiting": 0, "unknown": 205 - rounds * 5}
                    assert items[key]["total_seconds"] == 205
            recorded = [json.loads(line) for line in trace.read_text("utf-8").splitlines()]
            commands = [event["argv"] for event in recorded if event["event"] == "start"]
            calls = [argv for argv in commands if "cat-file" in argv]
            assert all("blob" not in argv for argv in calls), calls
            counts[mode].append(len(calls))
    assert 0 < counts["json"][0] == counts["json"][1] <= 2, counts
    assert 0 < counts["html"][0] == counts["html"][1] <= 3, counts


def warm_checks_cache(env, monkeypatch):
    github_list_fields(env)
    item, where = env.start_fix(round=1)
    env.reviews(blocked(finding("P1", "Basket disappears")))
    first = env.close(item)
    assert first.returncode == 1, first.stdout + first.stderr
    old_body = published(env, item)
    old_head = env.repo.git("ls-remote", "origin", f"refs/heads/fix/{item}").split()[0]
    old_pr = {"number": 7, "headRefName": f"fix/{item}", "headRefOid": old_head,
              "title": "Keep the basket", "body": old_body, "isDraft": False,
              "url": "https://github.com/acme/shop/pull/7",
              "commits": {"nodes": [{"commit": {"oid": old_head, "statusCheckRollup": {
                  "contexts": {"pageInfo": {"hasNextPage": False}, "nodes": [
                      {"__typename": "CheckRun", "name": name, "status": "COMPLETED",
                       "conclusion": "SUCCESS"} for name in ("tests", "forge-pr-check")]}}}}]}}
    env.gh.respond("api", "graphql", stdout=json.dumps({"data": {"repository": {
        "pullRequests": {"nodes": [old_pr]}}}}))
    machine = env.repo.path
    observer = env.tmp / "cached-checks-observer"
    env.repo.git("clone", "-q", env.repo.git("remote", "get-url", "origin"), str(observer))
    at = datetime.now(timezone.utc) + timedelta(seconds=60)
    monkeypatch.setenv("FORGE_NOW", at.isoformat())
    env.repo.path = observer
    env.repo.git("worktree", "add", "-q", "-b", f"fix/{item}",
                 str(env.tmp / "cached-checks-worktree"), f"origin/fix/{item}")
    assert row(env.repo, item)["gates"]["review"]["status"] == "blocked"
    calls = len(env.gh_calls("api", "graphql"))
    env.repo.path = machine
    env.commit(where, "app.py", "print('basket retained')\n")
    env.reviews(CLEAN)
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    published(env, item)
    assert env.repo.git("ls-remote", "origin", f"refs/heads/fix/{item}").split()[0] != old_head
    env.repo.path = observer
    monkeypatch.setenv("FORGE_NOW", (at + timedelta(seconds=30)).isoformat())
    current = row(env.repo, item)
    page = env.tmp / "cached-checks-board.html"
    rendered = env.repo.forge("board", "--out", str(page))
    next_step = env.repo.forge("next")
    assert rendered.returncode == 0, rendered.stdout + rendered.stderr
    assert next_step.returncode == 0, next_step.stdout + next_step.stderr
    assert len(env.gh_calls("api", "graphql")) == calls, "Checks remain cached inside the same minute"
    visible = seen(page)
    observations = {"json": current["stage"] == "ready" and
                    current["gates"]["review"]["status"] == "clean" and len(current["rounds"]) == 2,
                    "checks": current["pr"]["checks"] == "unknown",
                    "html": "Readme greets new readers Fix Ready to merge" in visible,
                    "next": any(item in line and "is ready" in line for line in next_step.stdout.splitlines())}
    assert all(observations.values()), (observations, current["stage"], next_step.stdout, visible)


def shared_ready_refresh(env, monkeypatch, missing, wait_first):
    install_claude(env.repo)
    config = env.repo.path / "forge.toml"
    env.commit(env.repo.path, "forge.toml", config.read_text("utf-8")
               + 'models.lite = { model = "sonnet", effort = "medium" }\n')
    env.repo.git("push", "-q", "origin", "main")
    item, _ = env.start_fix(round=1)
    first = env.close(item)
    assert first.returncode == 0, first.stderr
    published(env, item)
    machine_a = env.repo.path
    remote = env.repo.git("remote", "get-url", "origin")
    machine_b = env.tmp / "new-ready-machine"
    env.repo.git("clone", "-q", remote, str(machine_b))
    env.repo.path = machine_b
    resumed = env.tmp / "new-ready-worktree"
    env.repo.git("worktree", "add", "-q", "-b", f"fix/{item}", str(resumed), f"origin/fix/{item}")
    env.commit(resumed, "app.py", "print('newer ready basket')\n")
    at = datetime.now(timezone.utc) + timedelta(seconds=60)
    monkeypatch.setenv("FORGE_NOW", at.isoformat())
    ready = env.close(item)
    assert ready.returncode == 0, ready.stdout + ready.stderr
    published(env, item)
    peer = env.tmp / "ready-observer"
    env.repo.git("clone", "-q", remote, str(peer))
    env.repo.path = peer
    assert row(env.repo, item)["stage"] == "ready"
    env.repo.path = machine_a
    if missing:
        # A's successful publication event remains; only its obsolete local receipt is absent.
        (machine_a / ".git/forge/ready" / f"{item}.json").unlink()
    stub = env.repo.bin / "claude"
    source = stub.read_text("utf-8")
    if not wait_first:
        stub.write_text(source.replace('print("stub claude: built it")',
                                       'print("\\n\\nQuestion: May I reuse the existing basket parser?")'), "utf-8")
    monkeypatch.setenv("FORGE_NOW", (at + timedelta(seconds=30)).isoformat())
    worked = env.repo.forge("work", item)
    assert worked.returncode == 0, worked.stdout + worked.stderr
    if not wait_first:
        assert "Question: May I reuse the existing basket parser?" in worked.stdout
    published(env, item)
    env.repo.path = peer
    monkeypatch.setenv("FORGE_NOW", (at + timedelta(seconds=60)).isoformat())
    refreshed = row(env.repo, item)
    if not wait_first:
        assert refreshed["stage"] == "ready", "Refreshing older local history cannot revoke the published PR head's readiness"
    waits = [interval for interval in refreshed["intervals"]
             if interval["category"] == "waiting_for_owner"
             and at <= datetime.fromisoformat(interval["start"])
             and (wait_first or datetime.fromisoformat(interval["start"]) < at + timedelta(seconds=30))]
    wait = max(waits, key=lambda interval: interval["end"])
    assert datetime.fromisoformat(wait["end"]) == at + timedelta(seconds=30)
    if wait_first:
        monkeypatch.setenv("FORGE_NOW", (at + timedelta(seconds=90)).isoformat())
        assert row(env.repo, item)["waiting_seconds"] == refreshed["waiting_seconds"]
        return
    env.repo.path = machine_a
    stub.write_text(source, "utf-8")
    answered = env.repo.forge("work", item, "--note", "Yes, reuse the existing parser")
    assert answered.returncode == 0, answered.stdout + answered.stderr
    published(env, item)
    env.repo.path = peer
    assert row(env.repo, item)["stage"] == "ready"


def question_wait(env, monkeypatch):
    install_claude(env.repo)
    config = env.repo.path / "forge.toml"
    env.commit(env.repo.path, "forge.toml", config.read_text("utf-8")
               + 'models.lite = { model = "sonnet", effort = "medium" }\n')
    env.repo.git("push", "-q", "origin", "main")
    item, _ = env.start_fix(round=1)
    stub = env.repo.bin / "claude"
    source = stub.read_text("utf-8")
    asking = source.replace('print("stub claude: built it")',
                            'print("\\n\\nQuestion: May I reuse the basket parser?")')
    stub.write_text(asking, "utf-8")
    asked = env.repo.forge("work", item)
    assert asked.returncode == 0, asked.stderr
    assert "Question: May I reuse the basket parser?" in asked.stdout
    assert not env.gh_calls("pr", "create") and not env.gh_calls("pr", "edit")
    stub.write_text(source, "utf-8")
    answered = env.repo.forge("work", item, "--note", "Yes, reuse it")
    assert answered.returncode == 0, answered.stderr
    closed = env.close(item)
    assert closed.returncode == 0, closed.stderr
    published(env, item)
    at = datetime.now(timezone.utc) + timedelta(seconds=60)
    monkeypatch.setenv("FORGE_NOW", at.isoformat())
    stub.write_text(asking, "utf-8")
    asked = env.repo.forge("work", item)
    assert asked.returncode == 0, asked.stderr
    published(env, item)
    machine_a = env.repo.path
    peer = env.tmp / "question-peer"
    env.repo.git("clone", "-q", env.repo.git("remote", "get-url", "origin"), str(peer))
    env.repo.path = peer
    monkeypatch.setenv("FORGE_NOW", (at + timedelta(seconds=30)).isoformat())
    waiting = row(env.repo, item)
    assert any(interval["category"] == "waiting_for_owner"
               and datetime.fromisoformat(interval["start"]) >= at
               for interval in waiting["intervals"])
    env.repo.path = machine_a
    stub.write_text(source, "utf-8")
    answered = env.repo.forge("work", item, "--note", "Yes, keep the existing parser")
    assert answered.returncode == 0, answered.stderr
    published(env, item)
    env.repo.path = peer
    monkeypatch.setenv("FORGE_NOW", (at + timedelta(seconds=90)).isoformat())
    after = row(env.repo, item)
    wait = next(interval for interval in after["intervals"]
                if interval["category"] == "waiting_for_owner"
                and at <= datetime.fromisoformat(interval["start"]) < at + timedelta(seconds=30))
    assert datetime.fromisoformat(wait["end"]) == at + timedelta(seconds=30)


def conflict_wait(env, monkeypatch):
    env.commit(env.repo.path, "app.py", "print('old basket')\n")
    env.repo.git("push", "-q", "origin", "main")
    item, where = env.start_fix({"app.py": "print('branch basket')\n"}, round=1)
    env.commit(env.repo.path, "app.py", "print('main basket')\n")
    env.repo.git("push", "-q", "origin", "main")
    at = datetime.now(timezone.utc) + timedelta(seconds=60)
    monkeypatch.setenv("FORGE_NOW", at.isoformat())
    closed = env.close(item)
    assert closed.returncode == 1 and "conflicts in app.py" in closed.stderr
    assert env.gh_calls("pr", "create"), "The first-close conflict must still publish its pull request"
    published(env, item)
    monkeypatch.setenv("FORGE_NOW", (at + timedelta(seconds=30)).isoformat())
    waiting = row(env.repo, item)
    assert any(interval["category"] == "waiting_for_owner"
               and datetime.fromisoformat(interval["start"]) == at
               for interval in waiting["intervals"])
    # Resolve the real merge, keeping the branch's basket behavior.
    env.repo.git("merge", "--no-edit", "-X", "ours", "origin/main", cwd=where)
    ready = env.close(item)
    assert ready.returncode == 0, ready.stdout + ready.stderr
    published(env, item)
    monkeypatch.setenv("FORGE_NOW", (at + timedelta(seconds=90)).isoformat())
    after = row(env.repo, item)
    wait = next(interval for interval in after["intervals"]
                if interval["category"] == "waiting_for_owner"
                and datetime.fromisoformat(interval["start"]) == at)
    assert datetime.fromisoformat(wait["end"]) == at + timedelta(seconds=30)
    # A later conflict keeps the pull request's earlier findings instead of a made-up result.
    env.commit(where, "app.py", "print('branch basket again')\n")
    env.reviews(blocked(finding("P1", "Basket disappears")))
    assert env.close(item).returncode == 1
    published(env, item)
    env.commit(env.repo.path, "app.py", "print('newer main basket')\n")
    env.repo.git("push", "-q", "origin", "main")
    conflicted = env.close(item)
    assert conflicted.returncode == 1 and "conflicts in app.py" in conflicted.stderr
    assert "Basket disappears" in body(env.gh_calls("pr", "edit")[-1]).split("## How it went")[0]


def malformed_record(env, case):
    """A PR author can edit the shared record; any malformed value counts as no record."""
    item, _ = env.start_fix(round=1)
    first = env.close(item)
    assert first.returncode == 0, first.stderr
    text = body(env.gh_calls("pr", "edit")[-1])
    def spoil(match):
        record = json.loads(match[1])
        record["rebuilt"] = True  # visible only while the record is read
        if case == "bad-null-event":
            record["events"][0]["event"] = None
        elif case != "bad-deep-nesting":
            record["timings"][0]["seconds"] = float("inf") if case == "bad-infinite-seconds" else 1e308
        nested = ', "deep": ' + "[" * 100_000 + "]" * 100_000 if case == "bad-deep-nesting" else ""
        return "<!-- forge:time-record " + json.dumps(record)[:-1] + nested + "} -->"
    text = re.sub(r"<!-- forge:time-record (\{.*?\}) -->", spoil, text, flags=re.S)
    env.gh.respond("pr", "list", stdout=json.dumps([{
        "number": 7, "headRefName": f"fix/{item}", "state": "OPEN", "isDraft": False,
        "headRefOid": env.repo.git("ls-remote", "origin", f"refs/heads/fix/{item}").split()[0],
        "body": text, "title": "Keep the basket", "url": "https://github.com/acme/shop/pull/7"}]))
    shared = row(env.repo, item)
    assert not shared.get("rebuilt") and shared["rounds"], shared
    shown = env.repo.forge("next")
    assert shown.returncode == 0, shown.stdout + shown.stderr
    again = env.close(item)
    assert again.returncode == 0, again.stdout + again.stderr


def rebuilt_history(env):
    config = env.repo.path / "forge.toml"
    env.commit(env.repo.path, "forge.toml", config.read_text("utf-8") + 'merge = "agent"\n')
    env.repo.git("push", "-q", "origin", "main")
    item, _ = env.start_fix(round=1)
    first = env.close(item)
    assert first.returncode == 0, first.stderr
    text = body(env.gh_calls("pr", "edit")[-1])
    # The backfill producer belongs to another task; mark its third-party PR input here.
    def mark(match):
        record = json.loads(match[1])
        record["rebuilt"] = True
        return "<!-- forge:time-record " + json.dumps(record) + " -->"
    text = re.sub(r"<!-- forge:time-record (\{.*?\}) -->", mark, text, flags=re.S)
    env.gh.respond("pr", "list", stdout=json.dumps([{
        "number": 7, "headRefName": f"fix/{item}", "state": "OPEN", "isDraft": False,
        "headRefOid": env.repo.git("ls-remote", "origin", f"refs/heads/fix/{item}").split()[0],
        "body": text, "title": "Keep the basket", "url": "https://github.com/acme/shop/pull/7"}]))
    assert row(env.repo, item)["rebuilt"] is True
    for _ in range(2):
        continued = env.close(item)
        assert continued.returncode == 0, continued.stderr
        text = published(env, item)
        assert row(env.repo, item)["rebuilt"] is True
        assert "Rebuilt from history." in re.sub(r"<!--.*?-->", "", text, flags=re.S)
    github_merge(env, f"fix/{item}")
    gh = env.repo.bin / "gh"
    source = gh.read_text("utf-8")
    source = source.replace('"isDraft": False', f'"isDraft": False, "body": {text!r}')
    gh.write_text(source.replace('if args[:2] == ["pr", "merge"]:',
                                 'if args[:2] == ["pr", "merge"]:\n    sys.exit(1)'), "utf-8")
    refused = env.repo.forge("merge", item)
    assert refused.returncode == 1
    published(env, item)
    assert row(env.repo, item)["stage"] == "ready", "A refused GitHub merge must keep shared readiness"
    gh.write_text(source, "utf-8")
    merged = env.repo.forge("merge", item)
    assert merged.returncode == 0, merged.stdout + merged.stderr
    assert "Rebuilt from history." in env.repo.git("log", "-1", "--format=%B", "origin/main")
    assert row(env.repo, item)["rebuilt"] is True


def story_full_runway(env, monkeypatch, done=False):
    began = datetime(2026, 9, 20, 10, tzinfo=timezone.utc)
    at = lambda seconds: (began + timedelta(seconds=seconds)).isoformat()

    def clock(seconds):
        for name in ("FORGE_NOW", "GIT_AUTHOR_DATE", "GIT_COMMITTER_DATE"):
            monkeypatch.setenv(name, at(seconds))

    clock(0)
    approve_story(env.repo, STORY_DOC)
    listing = env.repo.git("worktree", "list", "--porcelain")
    story_tree = next(Path(block.splitlines()[0].removeprefix("worktree "))
                      for block in listing.split("\n\n") if "branch refs/heads/story/SHOP" in block)
    notes = (story_tree / "plans/SHOP.read.md").read_text("utf-8")
    notes = re.sub(r"^read_at:.*$", "read_at: " + at(20), notes, flags=re.M)
    notes = re.sub(r"^seconds:.*$", "seconds: 10", notes, flags=re.M)
    clock(20)
    env.commit(story_tree, "plans/SHOP.read.md", notes)
    env.repo.git("merge", "-q", "--ff-only", "story/SHOP")
    env.repo.git("push", "-q", "origin", "main")
    clock(30)
    first = env.repo.forge("task", "start", "SHOP/T1")
    assert first.returncode == 0, first.stdout + first.stderr
    tree = Path(first.stdout.splitlines()[0].rsplit(" in ", 1)[1])
    env.commit(tree, "app.py", "print('saved basket')\n")
    clock(60)
    env.repo.git("merge", "-q", "--ff-only", "task/SHOP-T1")
    env.repo.git("push", "-q", "origin", "main", "task/SHOP-T1")
    github_list_fields(env)
    env.gh.respond("pr", "list", stdout=json.dumps([{
        "number": 7, "headRefName": "task/SHOP-T1", "state": "MERGED", "mergedAt": at(60),
        "body": "Saved baskets remain available", "title": "Save a basket", "isDraft": False,
        "headRefOid": env.repo.git("rev-parse", "task/SHOP-T1"),
        "url": "https://github.com/acme/shop/pull/7"}]))
    if done:
        # The story is recorded done 40 seconds after its last part merged; that tail still counts.
        record = env.repo.path / ".factory/stories/SHOP/story.json"
        state = json.loads(record.read_text("utf-8"))
        env.commit(env.repo.path, ".factory/stories/SHOP/story.json",
                   json.dumps({**state, "status": "done", "finished": at(100)}))
        env.repo.git("push", "-q", "origin", "main")
        top = env.repo.path / ".git/forge"
        (top / "events.jsonl").write_text("".join(json.dumps(event) + "\n" for event in [
            {"id": "T1-start", "item": "SHOP/T1", "event": "run start", "kind": "worker", "at": at(30)},
            {"id": "T1-end", "item": "SHOP/T1", "event": "run end", "kind": "worker",
             "run_id": "T1-start", "at": at(50)}]), "utf-8")
        clock(200)
        current = row(env.repo, "SHOP")
        assert current["stage"] == "done"
        assert current["intervals"][-1]["end"] == at(100)
        assert current["total_seconds"] == 100
        return
    clock(864000)
    second = env.repo.forge("task", "start", "SHOP/T2")
    assert second.returncode == 0, second.stdout + second.stderr
    events = []
    for item, start, end in (("SHOP/T1", 30, 50), ("SHOP/T2", 864010, 864030)):
        events.extend([
            {"id": item + "-phase", "item": item, "event": "work phase", "phase": "building", "at": at(start)},
            {"id": item + "-start", "item": item, "event": "run start", "kind": "worker", "at": at(start)},
            {"id": item + "-end", "item": item, "event": "run end", "kind": "worker", "run_id": item + "-start", "at": at(end)},
        ])
    events.append({"id": "first-merge-wait", "item": "SHOP/T1", "event": "owner wait start",
                   "reason": "merge", "at": at(50)})
    top = env.repo.path / ".git/forge"
    (top / "events.jsonl").write_text("".join(json.dumps(event) + "\n" for event in events), "utf-8")
    (top / "timings.jsonl").write_text("", "utf-8")
    clock(864040)
    current = row(env.repo, "SHOP")
    assert [child["id"] for child in current["children"]] == ["SHOP/T2"]
    assert current["intervals"][0] == {"start": at(0), "end": at(10), "kind": "unknown"}
    assert current["total_seconds"] == 864040
    assert current["time_breakdown"] == {"working": 50, "waiting": 10, "unknown": 863980}


def story_runway(env, monkeypatch):
    began = datetime(2026, 10, 9, 10, tzinfo=timezone.utc)
    at = lambda seconds: (began + timedelta(seconds=seconds)).isoformat()
    monkeypatch.setenv("FORGE_NOW", at(60))
    first, _ = env.start_approved_task(STORY_DOC)
    second, _ = env.start_task("T2", {"show.py": "print('basket')\n"})
    events = []
    for item, start, end in ((first, 0, 30), (second, 20, 50)):
        events.extend([
            {"id": item + "-phase", "item": item, "round": 1, "event": "work phase", "phase": "building", "at": at(start)},
            {"id": item + "-start", "item": item, "round": 1, "event": "run start", "kind": "worker", "at": at(start)},
            {"id": item + "-end", "item": item, "round": 1, "event": "run end", "kind": "worker", "run_id": item + "-start", "at": at(end)},
        ])
    top = env.repo.path / ".git/forge"
    top.mkdir(exist_ok=True)
    (top / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events), "utf-8")
    listing = env.repo.git("worktree", "list", "--porcelain")
    story_tree = next(Path(block.splitlines()[0].removeprefix("worktree "))
                      for block in listing.split("\n\n") if "branch refs/heads/story/SHOP" in block)
    # The published approved plan owns these notes, independently of main's copy.
    env.commit(story_tree, "plans/SHOP.read.md", "---\nreader: claude\nread_at: " + at(0)
               + "\nround: 1\npassed: yes\nseconds: 10\n---\n\n## Round 1\n\nNo findings.\n")
    env.repo.git("push", "-q", "origin", "story/SHOP", cwd=story_tree)
    current = row(env.repo, "SHOP")
    assert current["approved_by"] == "Forge Test"
    assert row(env.repo, first)["approved_by"] == "Forge Test"
    assert current["total_seconds"] == 70
    assert current["working_seconds"] == 60
    assert current["waiting_seconds"] == 0
    assert current["unknown_seconds"] == 10
    assert current["time_breakdown"] == {"working": 60, "waiting": 0, "unknown": 10}
    assert current["intervals"]


@pytest.mark.parametrize("case", ["plain-times", *(f"{part}-{history}" for part in ("sections", "history", "keys")
                                                   for history in ("new", "adopted-v1.2.2"))])
def test_12_getting_around_the_board_and_telling_items_apart(request, case):
    """Plain times; the pinned bar and folding sections; story histories with their cold-read
    rounds; the shipped line allowing story keys. Each case gets the fixtures it needs."""
    if case == "plain-times":
        plain_times(request.getfixturevalue("env"))
        return
    part, history = case.split("-", 1)
    repo, gh, tmp_path = (request.getfixturevalue(name) for name in ("repo", "gh", "tmp_path"))
    if part == "sections":
        pinned_bar_and_folding_sections(repo, gh, tmp_path, history)
    elif part == "history":
        story_history_lists_read_rounds(repo, gh, tmp_path, request.getfixturevalue("claude_payload"), history)
    else:
        agents_md_allows_story_keys(repo, gh, tmp_path, history)


def plain_times(env):
    """15.001-second review times read in rounded plain units in the board and pull request."""
    item, _ = env.start_fix(round=1)
    closed = env.close(item)
    assert closed.returncode == 0, closed.stderr
    top = env.repo.path / ".git/forge"
    timings = [json.loads(line) for line in (top / "timings.jsonl").read_text("utf-8").splitlines()]
    for timing in timings:
        if timing.get("item") == item and timing.get("step") == "review":
            # 15.4 still rounds to whole seconds and leaves room for overlapping CI waits on slow runners.
            timing["seconds"] = 15.4
    (top / "timings.jsonl").write_text("".join(json.dumps(t) + "\n" for t in timings), "utf-8")
    current = row(env.repo, item)
    assert "15 seconds" in current["rounds"][0]["line"]
    again = env.close(item)
    assert again.returncode == 0, again.stderr
    text = body(env.gh_calls("pr", "edit")[-1])
    assert "15 seconds" in text
    page = env.tmp / "board.html"
    rendered = env.repo.forge("board", "--out", str(page))
    assert rendered.returncode == 0, rendered.stderr
    for output in (text, page.read_text("utf-8"), current["rounds"][0]["line"]):
        assert not re.search(r"\d+\.\d+ ?s", re.sub(r"<!--.*?-->", "", output, flags=re.S))
