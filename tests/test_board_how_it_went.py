"""Time history follows the published pull request across independent machines.

Audit: existing time tests keep one machine's logs. These command tests protect
cross-machine reconciliation, overlapping story time and human-readable rounding.
Only GitHub and review reports are faked; no Forge helper is imported.
"""
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from test_close import CLEAN, GREEN, STORY_DOC, body, blocked, env, finding, run  # noqa: F401
from test_close_keeps_reviews_for_unchanged_branch_diffs import client
from test_item_time_history import row
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
    return text


@pytest.mark.parametrize("case,previous", [("shared-fix", False), ("shared-fix", True),
                                          ("story-runway", False), ("rebuilt-history", False),
                                          ("question-wait", False), ("conflict-wait", False)],
                         ids=["new-client", "earlier-adoption", "story-runway", "rebuilt-history",
                              "question-wait", "conflict-wait"])
def test_5_how_it_went_is_shared_and_story_time_counts_each_instant_once(env, monkeypatch, case, previous):
    if case == "story-runway":
        story_runway(env, monkeypatch)
        return
    if case == "rebuilt-history":
        rebuilt_history(env)
        return
    if case == "question-wait":
        question_wait(env, monkeypatch)
        return
    if case == "conflict-wait":
        conflict_wait(env, monkeypatch)
        return
    client(env, previous)
    # GitHub only returns requested fields, including for older PRs outside GraphQL's window.
    gh = env.repo.bin / "gh"
    gh.write_text(gh.read_text("utf-8").replace('sys.stdout.write(rule["stdout"])', '''output = rule["stdout"]
        if args[:2] == ["pr", "list"] and "--json" in args:
            fields = args[args.index("--json") + 1].split(",")
            state = args[args.index("--state") + 1].upper() if "--state" in args else "ALL"
            output = json.dumps([{k: v for k, v in pr.items() if k in fields}
                                 for pr in json.loads(output) if state == "ALL" or pr["state"] == state])
        sys.stdout.write(output)'''), "utf-8")
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
    for field in ("intervals", "time_breakdown", "rounds", "total_seconds"):
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
    assert current["time_breakdown"] == {"working": 60, "waiting": 0, "unknown": 10}
    assert current["intervals"]


def test_12_plain_times_round_review_times_in_board_and_pull_request(env):
    item, _ = env.start_fix(round=1)
    closed = env.close(item)
    assert closed.returncode == 0, closed.stderr
    top = env.repo.path / ".git/forge"
    timings = [json.loads(line) for line in (top / "timings.jsonl").read_text("utf-8").splitlines()]
    for timing in timings:
        if timing.get("item") == item and timing.get("step") == "review":
            timing["seconds"] = 15.001
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
