"""A long item's pull request time record has a fixed size: recent rounds keep their own
time summary, older rounds fold into one totals line, and the board still shows its total time.

Audit: a real work and close round records one round; the test repeats that round's own
records as 200 earlier rounds with many findings, since 200 real rounds would take too
long. A real close then publishes the body, and a fresh clone's board reads it alone.
Only GitHub and the reviewer are external fakes.
"""
import json
import re
from datetime import datetime, timedelta

import pytest

from test_close import STORY_DOC, body, env, finding, report  # noqa: F401
from test_close_keeps_reviews_for_unchanged_branch_diffs import client
from test_item_time_history import row
from test_pull_request_body_limit import publish_snapshot
from test_worker import install_claude

STORY = "FIX-PR-TIME-RECORD-SUMMARIES"
EARLIER = 200
BUDGET = 40_000  # well inside GitHub's 64 KB limit


def shifted(value, hours):
    return (datetime.fromisoformat(value) - timedelta(hours=hours)).isoformat()


def repeat_round(template, number, offset, worker_round):
    """Copy the recorded round as an earlier one with its own ids, times and eleven findings."""
    copies = {}
    for name in ("events", "timings"):
        for record in template[name]:
            copy = {**record, "round": worker_round}
            for key in ("id", "run_id", "lane_id", "wait_id"):
                if isinstance(copy.get(key), str):
                    copy[key] += f"-{number}"
            for key in ("at", "start"):
                if isinstance(copy.get(key), str):
                    copy[key] = shifted(copy[key], offset)
            if copy.get("event") == "review result":
                copy.update(review_round=number, outcome="clean", findings=[
                    {"title": f"Basket finding {number}.{n}: " + "quantity detail " * 4,
                     "priority": "P2", "file": f"basket/{n}.py"} for n in range(10)]
                    + [{"title": "Basket label stays unclear", "priority": "P3", "file": "app.py"}])
            copies.setdefault(name, []).append(copy)
    return copies


# ponytail: hundreds of seeded rounds through real closes; under a full parallel run they need more than the 150 s default.
@pytest.mark.timeout(600)
@pytest.mark.parametrize("shape", ["many-worker-rounds", "one-worker-round", "long-current-round",
                                   "repeated-ci-closes", "story-part"])
@pytest.mark.parametrize("previous", [False, True], ids=["new-client", "earlier-adoption"])
def test_1_long_item_keeps_recent_round_times_and_older_totals_within_a_fixed_body_size(
        env, previous, shape, monkeypatch):
    repeated_closes = shape != "many-worker-rounds"
    client(env, previous)
    version = env.repo.forge("--version").stdout.split()[-1]
    env.commit(env.repo.path, "forge.toml", f'version = "{version}"\nstage = "live"\n'
               'workers = "claude"\ntest = "echo passed"\n'
               'checks = ["tests", "forge-pr-check"]\n'
               'models.build = { model = "opus", effort = "high" }\n')
    env.repo.git("push", "-q", "origin", "main")
    # The CI case starts fresh, so its review round has a known number.
    if shape == "story-part":  # a story's only part, so the story's time is the part's time
        item, where = env.start_approved_task("\n".join(
            line for line in STORY_DOC.splitlines() if not line.startswith("| T2 |")))
    else:
        item, where = env.start_fix() if shape == "repeated-ci-closes" else env.start_fix(round=EARLIER)
    install_claude(env.repo)
    env.reviews({"exit": 0, "report": report(finding("P2", "Basket label stays unclear"))})
    worked = env.repo.forge("work", item)
    assert worked.returncode == 0, worked.stdout + worked.stderr
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    env.open_pr(body(env.gh_calls("pr", "edit")[-1]))

    logs = env.repo.path / ".git/forge"
    recorded = {name: [json.loads(line) for line in (logs / f"{name}.jsonl").read_text("utf-8").splitlines()]
                for name in ("events", "timings")}
    mine = {name: [r for r in rows if r.get("item") == item] for name, rows in recorded.items()}
    number = max(r["round"] for r in mine["events"] if isinstance(r.get("round"), int))
    assert number >= EARLIER or shape in ("repeated-ci-closes", "story-part")
    # The round's merge wait is still open; a later round's work would have ended it.
    template = {name: [r for r in rows if r.get("round") == number and r.get("event") != "owner wait start"]
                for name, rows in mine.items()}
    # Repeated closes put every review in the one worker round; otherwise each has its own.
    earlier = [repeat_round(template, n, EARLIER - n + 1, number if repeated_closes else n)
               for n in range(1, EARLIER)] if shape in ("many-worker-rounds", "one-worker-round", "story-part") else []
    if shape == "repeated-ci-closes":
        # Closing again on an unchanged commit reuses the review but waits for CI each time.
        checks = {name: [r for r in rows if r.get("kind") == "ci" or r.get("event") == "CI result"
                         or r.get("step") == "CI wait"] for name, rows in template.items()}
        assert checks["events"] and checks["timings"]
        earlier = [{name: [{**r, **{key: f"{r[key]}-ci-{n}" for key in ("id", "run_id", "lane_id") if key in r},
                            **{key: (datetime.fromisoformat(r[key]) + timedelta(milliseconds=n)).isoformat()
                               for key in ("at", "start") if isinstance(r.get(key), str)}}
                           for r in found] for name, found in checks.items()} for n in range(1, 400)]
    if shape == "long-current-round":
        # As many live progress records as a run of over two hours leaves, one per ten seconds.
        run = next(r for r in template["events"] if r.get("event") == "run start")
        began = datetime.fromisoformat(run["at"])
        earlier = [{"events": [{"id": f"progress-{n}", "item": item, "event": "progress", "kind": "progress",
                                "run_id": run["id"], "round": number, "done": n, "total": 900,
                                "at": (began + timedelta(seconds=n / 100)).isoformat(),
                                "recorded_at": (began + timedelta(seconds=n / 100)).isoformat()}]}
                   for n in range(900)]
    for name in ("events", "timings"):
        rows = [r for copies in earlier for r in copies.get(name, [])] + recorded[name]
        (logs / f"{name}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), "utf-8")

    if shape != "repeated-ci-closes":
        env.commit(where, "app.py", "print('basket label is clear')\n")
    if not repeated_closes:
        worked = env.repo.forge("work", item)
        assert worked.returncode == 0, worked.stdout + worked.stderr
        env.open_pr(body(env.gh_calls("pr", "edit")[-1]))
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    published = body(env.gh_calls("pr", "edit")[-1])
    assert len(published.encode("utf-8")) < BUDGET
    assert "shortened" not in published

    # Another machine with no local logs accounts for every round from the pull request alone.
    publish_snapshot(env, item, published)
    clone = env.tmp / "peer-clone"
    env.repo.git("clone", "-q", env.repo.git("remote", "get-url", "origin"), str(clone))
    env.repo.path = clone
    # One fixed clock, so the part and its story measure open waits to the same instant.
    monkeypatch.setenv("FORGE_NOW", (datetime.now().astimezone() + timedelta(minutes=5)).isoformat())
    shared = row(env.repo, item)
    lines = [r["line"] for r in shared["rounds"]]
    # The board's total time is the sum of its parts.
    parts = sum(shared[f"{kind}_seconds"] for kind in ("working", "waiting", "unknown"))
    assert abs(shared["total_seconds"] - parts) < 1
    if shape == "story-part":
        # Folded intervals keep their working and waiting time in the story's total.
        result = env.repo.forge("board", "--json")
        story = next(i for i in json.loads(result.stdout)["items"] if i["id"] == "SHOP")
        assert abs(story["waiting_seconds"] - shared["waiting_seconds"]) < 1, (story, shared)
        # The story also counts its plan reads as working, a few seconds here; the shared record keeps milliseconds.
        assert -0.01 <= story["working_seconds"] - shared["working_seconds"] < 5, (story, shared)
        assert story["unknown_seconds"] <= shared["unknown_seconds"] + 1
        assert abs(story["total_seconds"] - shared["total_seconds"]) < 1, (story, shared)
        # Anyone can edit the body: a folded entry with a word or a negative number never breaks the board.
        record = re.search(r"<!-- forge:time-record (\{.*?\}) -->", published, re.S)
        for minutes, value in ((10, "about an hour"), (15, -5)):
            # A later clock, so the board fetches the edited pull request rather than its saved copy.
            monkeypatch.setenv("FORGE_NOW", (datetime.now().astimezone() + timedelta(minutes=minutes)).isoformat())
            data = json.loads(record[1])
            data["summary"]["folded"]["working"] = value
            publish_snapshot(env, item, published.replace(record[1], json.dumps(data)))
            edited = env.repo.forge("board", "--json")
            assert edited.returncode == 0, edited.stderr
            assert any(i["id"] == "SHOP" for i in json.loads(edited.stdout)["items"])
        return
    if shape == "repeated-ci-closes":
        assert shared["time_breakdown"]["waiting_for_ci"] is not None
        # The CI retries fold into their own review round's line, which keeps its number and times.
        assert re.match(rf"Round {number}: .*review \w+ \(\d+ seconds?\).*CI passed[^;]*\(\d+ seconds?\)", lines[-1]), lines
        assert "Round unknown" not in "".join(lines) and shared["rounds"][-1]["repeat_findings"] is not None
        return
    if shape == "long-current-round":
        assert len(lines) == 2 and all(re.search(r"review \w+ \(\d+ (?:second|minute)", line) for line in lines), lines
        assert re.search(r"building \w+ \(\d+ (?:second|minute)", lines[0]), lines
        return
    # Older rounds fold into one totals line; the recent ones keep their own line each.
    folded, recent = lines[0], lines[1:]
    last = int(re.match(r"Rounds 1–(\d+): .*reviewing .*findings: \d+ new, \d+ repeated$", folded)[1])
    assert len(recent) < 20, lines
    numbers = [int(re.match(r"Round (\d+):", line)[1]) for line in recent]
    assert numbers[0] in (last, last + 1) and numbers == sorted(numbers), lines
    for line in recent:  # each recent line keeps its own stage times
        assert re.search(r"review \w+ \(\d+ (?:second|minute)", line), line
    assert "Basket label stays unclear" in recent[-1]
    assert shared["rounds"][-1]["repeat_findings"] == 1
    # The total spans all 200 earlier rounds.
    assert shared["total_seconds"] > (number - 1) * 3600
    # Clean reviews do not pile up across rounds.
    assert len(shared["clean_reviews"]) <= 2, shared["clean_reviews"]


# ponytail: hundreds of seeded rounds through real closes; under a full parallel run they need more than the 150 s default.
@pytest.mark.timeout(600)
def test_2_story_counts_two_parts_overlapping_folded_time_once(env, monkeypatch):
    client(env, False)
    version = env.repo.forge("--version").stdout.split()[-1]
    env.commit(env.repo.path, "forge.toml", f'version = "{version}"\nstage = "live"\n'
               'workers = "claude"\ntest = "echo passed"\n'
               'checks = ["tests", "forge-pr-check"]\n'
               'models.build = { model = "opus", effort = "high" }\n')
    env.repo.git("push", "-q", "origin", "main")
    # Both parts can run at once, so their long histories overlap in time.
    first, _ = env.start_approved_task(STORY_DOC.replace("| T1 | yes |", "| — | yes |"))
    started = env.repo.forge("task", "start", "SHOP/T2")
    assert started.returncode == 0, started.stdout + started.stderr
    install_claude(env.repo)
    env.reviews({"exit": 0, "report": report(finding("P2", "Basket label stays unclear"))})
    logs = env.repo.path / ".git/forge"
    prs = []
    for number, item in enumerate((first, "SHOP/T2"), 7):
        env.open_pr("")
        for _ in range(2):  # the second close publishes the record after the old rounds were added
            worked = env.repo.forge("work", item)
            assert worked.returncode == 0, worked.stdout + worked.stderr
            closed = env.close(item)
            assert closed.returncode == 0, closed.stdout + closed.stderr
            env.open_pr(body(env.gh_calls("pr", "edit")[-1]))
            if _:
                break
            recorded = {name: [json.loads(line) for line in (logs / f"{name}.jsonl").read_text("utf-8").splitlines()]
                        for name in ("events", "timings")}
            mine = {name: [r for r in rows if r.get("item") == item] for name, rows in recorded.items()}
            current = max(r["round"] for r in mine["events"] if isinstance(r.get("round"), int))
            template = {name: [r for r in rows if r.get("round") == current and r.get("event") != "owner wait start"]
                        for name, rows in mine.items()}
            # Back to back, so the folded time has little idle time for both parts to share.
            times = [datetime.fromisoformat(r.get("at") or r["start"]) for rows in template.values() for r in rows]
            span = (max(times) - min(times)).total_seconds() / 3600
            earlier = [repeat_round(template, n, (EARLIER - n) * span, current) for n in range(1, EARLIER)]
            for name in ("events", "timings"):
                rows = [r for copies in earlier for r in copies.get(name, [])] + recorded[name]
                (logs / f"{name}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), "utf-8")
        branch = f"task/{item.replace('/', '-')}"
        prs.append({"number": number, "state": "OPEN", "isDraft": False, "title": item,
                    "body": body(env.gh_calls("pr", "edit")[-1]), "headRefName": branch,
                    "headRefOid": env.repo.git("ls-remote", "origin", f"refs/heads/{branch}").split()[0],
                    "url": f"https://github.com/acme/shop/pull/{number}"})
    env.gh.respond("pr", "list", stdout=json.dumps(prs))
    clone = env.tmp / "peer-clone"
    env.repo.git("clone", "-q", env.repo.git("remote", "get-url", "origin"), str(clone))
    env.repo.path = clone
    monkeypatch.setenv("FORGE_NOW", (datetime.now().astimezone() + timedelta(minutes=5)).isoformat())
    result = env.repo.forge("board", "--json")
    assert result.returncode == 0, result.stderr
    story = next(i for i in json.loads(result.stdout)["items"] if i["id"] == "SHOP")
    parts = {child["id"]: child for child in story["children"]}
    assert all(parts[item].get("folded_seconds") for item in (first, "SHOP/T2")), parts
    # The parts overlap, so the story's time is their union, counted once.
    assert abs(story["total_seconds"] - max(p["total_seconds"] for p in parts.values())) < 1, story
    assert story["unknown_seconds"] >= 0
    assert abs(sum(story[f"{k}_seconds"] for k in ("working", "waiting", "unknown")) - story["total_seconds"]) < 1
    for kind in ("working", "waiting"):
        assert story[f"{kind}_seconds"] <= sum(p[f"{kind}_seconds"] for p in parts.values()) + 5, (kind, story)


def long_body(note):
    return {**note, "body": "Gain 1, Work 1, Harm 1\n" + "The saved basket detail goes on. " * 100}


@pytest.mark.parametrize("huge", ["long-titles", "long-bodies"])
def test_3_one_huge_review_keeps_its_counts_and_round_line_within_the_record_budget(env, monkeypatch, huge):
    client(env, False)
    version = env.repo.forge("--version").stdout.split()[-1]
    env.commit(env.repo.path, "forge.toml", f'version = "{version}"\nstage = "live"\n'
               'workers = "claude"\ntest = "echo passed"\n'
               'checks = ["tests", "forge-pr-check"]\n'
               'models.build = { model = "opus", effort = "high" }\n')
    env.repo.git("push", "-q", "origin", "main")
    item, _ = env.start_fix()
    install_claude(env.repo)
    # Long titles fill the review result; short titles with long bodies fill the clean review saved by close.
    env.reviews({"exit": 0, "report": report(*[
        finding("P2", f"Basket note {n}: " + "the quantity label could be clearer " * 6, f"basket/{n}.py")
        if huge == "long-titles" else long_body(finding("P2", f"Basket note {n}", f"basket/{n}.py"))
        for n in range(200 if huge == "long-titles" else 20)])})
    worked = env.repo.forge("work", item)
    assert worked.returncode == 0, worked.stdout + worked.stderr
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    # Closing again once ready publishes close's saved clean review with the record.
    env.open_pr(body(env.gh_calls("pr", "edit")[-1]))
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    published = body(env.gh_calls("pr", "edit")[-1])
    assert len(published.encode("utf-8")) <= 65_536
    record = re.search(r"<!-- forge:time-record .*? -->", published, re.S)[0]
    assert len(record.encode("utf-8")) < 24_000  # the record's own fixed budget, with room for escaping

    publish_snapshot(env, item, published)
    clone = env.tmp / "peer-clone"
    env.repo.git("clone", "-q", env.repo.git("remote", "get-url", "origin"), str(clone))
    env.repo.path = clone
    shared = row(env.repo, item)
    assert shared["rounds"][-1]["line"].startswith("Round 1: "), shared["rounds"]
    assert re.search(r"review \w+ \(\d+ seconds?\)", shared["rounds"][-1]["line"])
    assert shared["rounds"][-1]["new_findings"] == (200 if huge == "long-titles" else 20)
