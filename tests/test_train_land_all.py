STORY = "FORGE-TRAIN-1"
# forge land --all with a merge train: ready changes get one combined check on a temporary draft
# pull request, then merge in order. A repo made by forge init and the adopted earlier-release
# fixture, moved to this release. Only gh, Autoreview and the worker are stubs; changes are real fixes.

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import machine_cores
from test_close import env  # noqa: F401
from test_queue_land_all import _edit, _fix, _number, _settings, client  # noqa: F401
from test_conflicting_pull_requests_stop_check_waits import _publish_default

# The stub gh of test_queue_land_all, plus what the train asks of GitHub. train.json in its folder
# picks the answers: pending_until (a file the check waits for), same_name, no_drafts,
# no_create_output, rules ("strict", "unreadable"), behind, moved, changed and stray (a pull
# request number whose merge also leaves a stray file on main), red (a member whose own "lint"
# check turns red when the train's check passes) and late ("main" or "head": the first own check read
# of a member after that moves main, or the member's branch). pending_again keeps the check
# pending until its file ("path") no longer has its saved time ("mtime"). fresh answers for a head
# that is not one of its "closed" ones, as a fallback publishes: the first read says the tests still
# run, later reads say green, and a "red" member's heads fail. A ["check-pending", sha] or
# ["check-green", sha, time] entry in the call log marks the answer that came, in order with the calls.
# red_train makes a train's combined check red: "in" (a path; red only for a train that holds it), "heal"
# (a run id whose re-run turns it green) and "settle" (a second test group still runs when the check is
# first read as red, and for the first `gh pr checks` after it). "logs" maps a job id to its failed log.
# fresh may also say "failing": "tests" so a red member's new heads fail the tests check, not lint.
TRAIN_GH = r'''
cfg = json.loads((here / "train.json").read_text()) if (here / "train.json").exists() else {}
endpoint = args[-1] if args else ""
sha_of = lambda text: text.split("/commits/")[1].split("/")[0].split("?")[0]


def push(branch, name, text):
    checkout = tempfile.mkdtemp(dir=here)
    subprocess.run(["git", "clone", "-q", "-b", branch, remote, checkout], check=True)
    pathlib.Path(checkout, name).write_text(text)
    subprocess.run(["git", "add", name], cwd=checkout, check=True)
    subprocess.run(["git", "-c", "user.name=Other", "-c", "user.email=o@example.com", "commit", "-q",
                    "-m", "Other work"], cwd=checkout, check=True)
    subprocess.run(["git", "push", "-q", "origin", branch], cwd=checkout, check=True)


def train_sha(sha):
    return any(ref.startswith("refs/heads/forge-merge-train/") and oid == sha for ref, oid in heads().items())


lines = lambda rows: "".join(json.dumps(row) + "\n" for row in rows)


def broken(red):
    """The train's combined check is red: it holds the path, if one is named, and no re-run healed it."""
    tree = (here / "train-tree.txt").read_text() if (here / "train-tree.txt").exists() else ""
    return (red.get("in") is None or red["in"] in tree) and not (
        red.get("heal") and (here / ("rerun-" + red["heal"])).exists())


if args[:2] == ["pr", "checks"] and args[2].startswith("forge-merge-train/") and cfg.get("red_train") is not None:
    red = cfg["red_train"]
    link = lambda run, job: "https://github.com/acme/shop/actions/runs/%d/job/%d" % (run, job)  # noqa: E731
    first = red.get("settle") and not (here / "polled").exists()
    if red.get("settle"):
        append_json(here / "gh-calls.jsonl", ["settle-pending" if first else "settle-done"])
    (here / "polled").touch()
    rows = [{"name": "test group 1 of 2", "bucket": "fail", "link": link(2, 21)},
            {"name": "test group 2 of 2", "bucket": "pending" if first else "pass", "link": link(2, 22)},
            {"name": "Review pull request", "bucket": "fail", "link": link(1, 11)},
            {"name": "forge-pr-check", "bucket": "fail", "link": ""}]
    answer(json.dumps(rows), 1)
if args[:2] == ["run", "view"] and "--log-failed" in args and cfg.get("logs") is not None:
    answer(cfg["logs"].get(args[args.index("--job") + 1], ""))
if args[:1] == ["api"] and "/commits/" in endpoint and train_sha(sha_of(endpoint)):
    sha = sha_of(endpoint)
    if endpoint.split("?")[0].endswith("/status"):
        answer(lines([{"context": "forge-pr-check", "state": "failure"}]))
    tests = {"name": "tests", "head_sha": sha, "check_suite": {"id": 2}}
    again = cfg.get("pending_again")  # pending until that file is written again
    waiting = bool(again) and pathlib.Path(again["path"]).stat().st_mtime_ns == again["mtime"]
    if waiting or cfg.get("pending_until") and not pathlib.Path(cfg["pending_until"]).exists():
        answer(lines([{**tests, "status": "in_progress", "conclusion": None}]))
    (here / "train-tree.txt").write_text(subprocess.run(["git", "ls-tree", "-r", sha], cwd=remote,
                                                        capture_output=True, text=True).stdout)
    if not (here / "acted").exists():
        (here / "acted").touch()
        if cfg.get("moved"):
            push("main", "unrelated.py", "x = 1\n")
        if cfg.get("changed"):
            push("fix/bb", "bb_more.py", "y = 1\n")
        if cfg.get("red"):
            (here / ("checks-fix-%s.txt" % cfg["red"])).write_text(lines([
                {"name": name, "status": "completed", "conclusion": conclusion} for name, conclusion in
                (("tests", "success"), ("forge-pr-check", "success"), ("lint", "failure"))]))
    rows = [{**tests, "status": "completed", "conclusion": "success"},
            {"name": "Review pull request", "head_sha": sha, "status": "completed",
             "conclusion": "failure", "check_suite": {"id": 1}}]
    red = cfg.get("red_train")
    if red is not None and broken(red):
        later = {"name": "test group 2 of 2", "head_sha": sha, "check_suite": {"id": 2}, "conclusion": "success",
                 "status": "completed"}
        if red.get("settle") and not (here / "polled").exists():
            later.update(status="in_progress", conclusion=None)
        rows = [{**tests, "name": "test group 1 of 2", "status": "completed", "conclusion": "failure"}, later,
                rows[1]]
    if cfg.get("same_name"):
        rows.append({**rows[1], "check_suite": {"id": 3}})
        rows.append({**rows[1], "name": "forge-pr-check", "check_suite": {"id": 3}})
    answer(lines(rows))
fresh = cfg.get("fresh")
if fresh and args[:4] == ["api", "--paginate", "--jq", ".check_runs[]"] and sha_of(endpoint) not in fresh["closed"]:
    sha = sha_of(endpoint)
    own = subprocess.run(["git", "branch", "--show-current"], capture_output=True, text=True).stdout.strip()
    ok = {"name": "forge-pr-check", "status": "completed", "conclusion": "success"}
    if own == "fix/%s" % fresh.get("red"):
        failing = fresh.get("failing", "lint")
        answer(lines([{"name": "tests", "status": "completed",
                       "conclusion": "failure" if failing == "tests" else "success"}, ok]
                     + ([] if failing == "tests" else [{"name": "lint", "status": "completed", "conclusion": "failure"}])))
    if not (here / ("pending-" + sha)).exists():
        (here / ("pending-" + sha)).touch()
        append_json(here / "gh-calls.jsonl", ["check-pending", sha, str(time.time())])
        answer(lines([{"name": "tests", "status": "in_progress", "conclusion": None}, ok]))
    if not (here / ("green-" + sha)).exists():
        (here / ("green-" + sha)).touch()
        append_json(here / "gh-calls.jsonl", ["check-green", sha, str(time.time())])
if cfg.get("late") and args[:4] == ["api", "--paginate", "--jq", ".check_runs[]"]:
    if (here / "acted").exists() and not (here / "late").exists():
        (here / "late").touch()
        own = subprocess.run(["git", "branch", "--show-current"], capture_output=True, text=True).stdout.strip()
        push("main" if cfg["late"] == "main" else own, "late.py", "x = 2\n")
if args[:4] == ["api", "--paginate", "--jq", ".workflow_runs[]"] and any(a.startswith("head_sha=") for a in args):
    runs = [{"id": 1, "check_suite_id": 1, "event": "pull_request_target", "path": ".github/workflows/forge.yml@refs/heads/main"},
            {"id": 2, "check_suite_id": 2, "event": "pull_request", "path": ".github/workflows/forge.yml@refs/pull/1/merge"}]
    if cfg.get("same_name"):
        runs.append({"id": 3, "check_suite_id": 3, "event": "pull_request", "path": ".github/workflows/review.yml@refs/pull/1/merge"})
    answer(lines(runs))
if args[:1] == ["api"] and "/rules/branches/" in endpoint or "/protection/required_status_checks" in endpoint:
    if cfg.get("rules") == "unreadable":
        sys.stderr.write("HTTP 403: Resource not accessible\n")
        answer("", 1)
    strict = cfg.get("rules") == "strict"
    rule = [{"type": "required_status_checks", "parameters": {"strict_required_status_checks_policy": strict}}]
    answer(json.dumps(rule if "/rules/" in endpoint else {"strict": strict}))
if args[:2] == ["pr", "create"] and args[args.index("--head") + 1].startswith("forge-merge-train/"):
    if cfg.get("no_drafts"):
        sys.stderr.write("Draft pull requests are not supported in this repository.\n")
        answer("", 1)
    if cfg.get("no_create_output"):
        branch = args[args.index("--head") + 1]
        number = zlib.crc32(branch.encode()) % 9000 + 100
        save({"number": number, "headRefName": branch, "baseRefName": "main", "title": "Train",
              "isDraft": True, "body": "", "url": "https://github.com/acme/shop/pull/%d" % number})
        answer("")
if args[:2] == ["pr", "close"]:
    (here / ("pr-%s.json" % args[2])).unlink()
    answer("")
if args[:2] == ["pr", "view"] and cfg.get("behind") and list(here.glob("merged-*")):
    found = pr(args[2])
    if found and found["state"] == "OPEN":
        answer(json.dumps({**found, "mergeStateStatus": "BEHIND"}))
if args[:2] == ["pr", "merge"] and cfg.get("stray") == args[2]:
    push("main", "stray-" + args[2], "stray\n")
'''
MARKER = 'if args[:4] == ["api", "--paginate", "--jq", ".check_runs[]"]:'
RERUN = "main moved; Forge will merge it into this branch and run the related tests."
LATER = "so the ready changes merge one at a time, each with its own check."


@pytest.fixture
def train(client, monkeypatch):
    env = client
    gh = env.repo.bin / "gh"
    gh.write_text(gh.read_text("utf-8").replace(MARKER, TRAIN_GH + MARKER, 1), "utf-8")
    machine_cores(env.repo, 20)  # ten agent places, so no change waits for a place
    monkeypatch.setenv("FORGE_CHECKS_WAIT", "300")
    env.remote = Path(env.repo.git("remote", "get-url", "origin")).as_posix()
    env.common = Path(env.repo.git("rev-parse", "--path-format=absolute", "--git-common-dir"))
    return env


def _all(env):
    return env.repo.forge("land", "--all", timeout=600)


def _stub(env, **answers) -> None:
    (env.repo.bin / "train.json").write_text(json.dumps(answers), "utf-8")


def _ready(env, monkeypatch, slugs, first=1, files=None) -> dict[str, str]:
    """Real fixes, each closed ready on its own file; the head each one was closed at."""
    heads = {}
    for day, slug in enumerate(slugs, first):
        changed = (files or {}).get(slug, {f"{slug}.py": f"print('{slug}')\n"})
        where = _fix(env, monkeypatch, slug, day, changed, status="working")
        if "forge.toml" in changed:  # close accepts a settings change only when the fix says so
            amended = env.repo.forge("fix", "amend", slug, "--done", "forge.toml sets cold_read_rounds",
                                     "--because", "The fix changes a setting", cwd=where)
            assert amended.returncode == 0, amended.stdout + amended.stderr
        closed = env.repo.forge("close", slug)
        assert closed.returncode == 0, closed.stdout + closed.stderr
        heads[slug] = env.repo.git("rev-parse", "HEAD", cwd=where)
    return heads


def _blobs(listing: str) -> dict[str, str]:
    """Path to blob id from git ls-tree -r output."""
    return {path: meta.split()[2] for meta, path in (line.split("\t") for line in listing.splitlines())}


def _train_branches(env) -> list[str]:
    return [line.split("\t")[1] for line in env.repo.git("ls-remote", "--heads", env.remote).splitlines()
            if "forge-merge-train/" in line]


def _merge_heads(env) -> list[tuple[str, str]]:
    return [(call[2], call[call.index("--match-head-commit") + 1]) for call in env.gh_calls("pr", "merge")]


def _push_to_main(env, name: str, text: str) -> None:
    other = env.tmp / f"other-{name}"
    env.repo.git("clone", "-q", env.remote, str(other))
    env.commit(other, name, text, "Other work")
    env.repo.git("push", "-q", "origin", "main", cwd=other)


def _train_head(call) -> bool:
    return call[call.index("--head") + 1].startswith("forge-merge-train/")


def _everyone_merges_alone(env, done, slugs, moved=(), held=False) -> None:
    """Each goes through its own close and checks, which a train member never does, then merges. The
    ones in `moved` also find the default branch moved before their merge, which is certain only when
    a merge came before they started; changes that start together race for it. With `held`, the
    stub said that the tests of each new head still ran at first: no merge may come before the
    answer that turned green, which Forge only reads again after waiting."""
    lines = done.stdout.splitlines()
    for slug in slugs:
        assert f"{slug} merged." in lines and f"{slug}: Closing {slug}." in lines, done.stdout + done.stderr
    for slug in moved:
        assert any(line.startswith(f"{slug}: ") and RERUN in line for line in lines), done.stdout
    # Each waited for its own CI: GitHub's checks for the head it merged were read before its merge.
    calls = env.gh.calls()
    for slug in slugs:
        at = max(n for n, call in enumerate(calls) if call[:3] == ["pr", "merge", _number(f"fix/{slug}")])
        head = calls[at][calls[at].index("--match-head-commit") + 1]
        assert any(f"/commits/{head}/check-runs" in arg for call in calls[:at] for arg in call), (slug, done.stdout)
        if held:
            pending = next((n for n, call in enumerate(calls) if call[:2] == ["check-pending", head]), None)
            green = next((n for n, call in enumerate(calls) if call[:2] == ["check-green", head]), None)
            assert None not in (pending, green) and pending < green < at, (slug, done.stdout)  # it waited for green
            assert float(calls[green][2]) - float(calls[pending][2]) >= 30, (slug, done.stdout)  # over several polls


def _restarted(env) -> list[list[str]]:
    """GitHub calls that start CI again on a head: a re-run, a dispatch or a POST to the API."""
    return [call for call in env.gh.calls() if call[:2] in (["run", "rerun"], ["workflow", "run"])
            or call[:1] == ["api"] and "POST" in call]


@pytest.mark.timeout(900)
@pytest.mark.parametrize("variant", ["plain", "same-name", "no-create-output", "member-red"])
def test_1_ready_changes_merge_after_one_combined_check(train, monkeypatch, request, variant):
    env = train
    if variant != "plain" and request.node.callspec.params["client"] == "adopted":
        pytest.skip("new repos only")
    base = _blobs(env.repo.git("ls-tree", "-r", "origin/main"))
    workflow = env.repo.git("show", "origin/main:.github/workflows/forge.yml")
    heads = _ready(env, monkeypatch, ("aa", "bb", "cc"))
    _fix(env, monkeypatch, "dd", 4, {"dd.py": "print('dd')\n"})  # still in review
    env.repo.git("push", "-q", "origin", "HEAD:refs/heads/forge-merge-train/keep")
    keep = env.repo.git("rev-parse", "HEAD")
    _stub(env, pending_until=str(env.common / "forge" / "ready" / "dd.json"),
          same_name=variant == "same-name", no_create_output=variant == "no-create-output",
          red="bb" if variant == "member-red" else None)
    done = _all(env)
    lines = done.stdout.splitlines()
    out = done.stdout + done.stderr
    if variant == "same-name":
        assert "Train: testing 3 ready changes together: aa, bb, cc." in lines, out
        assert not any("the combined check passed" in line for line in lines), out
        assert any(line.startswith("Train: the combined check failed: Checks failed on the pull request: "
                                   "Review pull request, forge-pr-check.") and line.endswith(
            "The ready changes merge one at a time, each with its own check.") for line in lines), out
        _everyone_merges_alone(env, done, ("aa", "bb", "cc"))
        return
    assert "Train: testing 3 ready changes together: aa, bb, cc." in lines, out
    assert "Train: the combined check passed. Forge merges 3 changes in order." in lines, out
    if variant == "member-red":
        # bb's own check turned red while the train ran: it keeps today's gate, so it stops with that
        # failure, and cc, the member after it, merges one at a time. aa merged before bb's check.
        assert done.returncode == 1, out
        assert "- bb: Checks failed on the pull request: lint." in lines, out
        assert not env.gh_calls("pr", "merge", _number("fix/bb")), out
        assert not any(line.startswith("aa: ") and RERUN in line for line in lines), out
        assert any(line.startswith("cc: ") and RERUN in line for line in lines), out
        summary = next(line for line in lines if line.startswith("Merged ("))
        assert summary.startswith("Merged (3): aa, ") and summary.endswith(
            " · Ready to merge (0): none · Needs you (1): bb"), out
        return
    assert done.returncode == 0, out
    created = [call for call in env.gh_calls("pr", "create") if _train_head(call)]
    assert len(created) == 1 and "--draft" in created[0], out
    branch = created[0][created[0].index("--head") + 1]
    assert re.fullmatch(r"forge-merge-train/[0-9a-f]{12}", branch), out
    assert created[0][created[0].index("--title") + 1] == "Forge merge train: aa, bb, cc (do not merge)"
    tree = _blobs((env.repo.bin / "train-tree.txt").read_text("utf-8"))
    for slug, head in heads.items():
        assert tree[f"{slug}.py"] == env.repo.git("rev-parse", f"{head}:{slug}.py"), out
    assert all(tree[path] == blob for path, blob in base.items()), out
    merges = _merge_heads(env)
    assert [number for number, _ in merges[:3]] == [_number(f"fix/{slug}") for slug in ("aa", "bb", "cc")], out
    assert [head for _, head in merges[:3]] == [heads[slug] for slug in ("aa", "bb", "cc")], out
    assert merges[3][0] == _number("fix/dd"), out
    # dd stayed out of the train, so it merges after it with today's re-run line; the members do not.
    assert not any(line.startswith(("aa: ", "bb: ", "cc: ")) and "moved; Forge will merge it into this branch"
                   in line for line in lines), out
    assert any(line.startswith("dd: ") and RERUN in line for line in lines), out
    assert not _restarted(env), out  # no member's own workflow starts again; each head is the closed one
    if variant == "no-create-output":
        assert len(env.gh_calls("pr", "list", "--head", branch)) == 1, out
    assert env.gh_calls("pr", "close") == [["pr", "close", _number(branch)]], out
    assert env.repo.git("ls-remote", "--heads", env.remote, "refs/heads/forge-merge-train/keep").split()[0] == keep
    assert _train_branches(env) == ["refs/heads/forge-merge-train/keep"], out
    assert env.repo.git("show", "origin/main:.github/workflows/forge.yml") == workflow
    assert lines[-1] == "Merged (4): aa, bb, cc, dd · Ready to merge (0): none · Needs you (0): none", out


def _rival(env, files: dict[str, str]) -> None:
    """Another change reaches the default branch after the fixes closed."""
    other = env.tmp / "rival"
    env.repo.git("clone", "-q", env.remote, str(other))
    for path, text in files.items():
        env.commit(other, path, text, "Other work")
    env.repo.git("push", "-q", "origin", "main", cwd=other)


def _roadmap(*keys: str) -> str:
    return json.dumps({"items": [{"key": key} for key in keys]}, indent=1) + "\n"


def _on_main(env, path: str, text: str) -> None:
    """A file on the default branch before any fix starts, as the repo's earlier work."""
    env.repo.git("switch", "fix/upgrade-client")
    env.commit(env.repo.path, path, text)
    _publish_default(env.repo, env.remote)
    env.repo.git("switch", "main")
    env.repo.git("merge", "--ff-only", "fix/upgrade-client")


def _stacked(env, monkeypatch, base_merged: bool) -> None:
    """A fix built on another fix, closed ready. The base's pull request merges before the run (the
    fix is then closed ready again) or stays open."""
    base = _fix(env, monkeypatch, "jb", 7, {"jb.py": "print('jb')\n"}, status="working")
    assert env.repo.forge("close", "jb").returncode == 0
    main, env.repo.path = env.repo.path, base
    try:
        _fix(env, monkeypatch, "jj", 8, {"jj.py": "print('jj')\n"}, status="working")
    finally:
        env.repo.path = main
    assert env.repo.forge("close", "jj").returncode == 0
    if base_merged:
        merged = env.repo.forge("merge", "jb")
        assert merged.returncode == 0, merged.stdout + merged.stderr
        closed = env.repo.forge("close", "jj")
        assert closed.returncode == 0, closed.stdout + closed.stderr


@pytest.mark.timeout(1800)
@pytest.mark.parametrize("variant", ["out", "taken", "taken-same", "no-drafts", "rule", "behind", "stale", "stacked",
                                     "human", "no-app-check", "lint-only", "switched", "older", "alone"])
def test_2_changes_that_cannot_join_stay_out(train, monkeypatch, request, variant):
    env = train
    adopted = request.node.callspec.params["client"] == "adopted"
    if adopted and variant != "out":
        pytest.skip("new repos only")
    if variant == "out" and not adopted:
        _on_main(env, "plans/roadmap.json", _roadmap("A-1"))
    shared = lambda text: {"shared.py": _edit(1, text)}  # noqa: E731
    if variant == "out" and not adopted:
        heads = _ready(env, monkeypatch, ("aa", "bb", "cc", "dd", "ee", "kk"), files={
            "aa": {"a.py": "print('aa')\n"}, "bb": shared("first"), "cc": shared("other"),
            "dd": {"forge.toml": (env.repo.path / "forge.toml").read_text("utf-8") + "cold_read_rounds = 1\n"},
            "ee": {"shared.py": _edit(7, "mine")}, "kk": {"plans/roadmap.json": _roadmap("A-1", "K-1")}})
    elif variant == "out":
        heads = _ready(env, monkeypatch, ("aa", "bb", "cc"), files={"bb": shared("first"), "cc": shared("other")})
    elif variant == "stacked":  # a ready fix built on the ready, unmerged fix jb
        heads = _ready(env, monkeypatch, ("aa", "bb"))
        _stacked(env, monkeypatch, base_merged=False)
    elif variant == "alone":  # only aa can join: bb clashes with the default branch
        heads = _ready(env, monkeypatch, ("aa", "bb"), files={"bb": {"shared.py": _edit(7, "mine")}})
        _rival(env, {"shared.py": _edit(7, "rival")})
    else:
        if variant == "human":
            _settings(env, merge="human")
        if variant == "switched":  # ready under laptop tests, then the default branch moves to CI
            _settings(env, test_place="local")
        heads = _ready(env, monkeypatch, ("aa", "bb", "cc"))
        if variant == "switched":
            _settings(env, test_place="ci")
        if variant == "older":  # ready by an earlier release's evidence: no ready record of its own
            (env.common / "forge" / "ready" / "bb.json").unlink()
    if variant == "out" and not adopted:
        _stacked(env, monkeypatch, base_merged=True)
        heads.update(_ready(env, monkeypatch, ("ff", "gg", "hh"), first=9))
        _rival(env, {"shared.py": _edit(7, "rival"), "plans/roadmap.json": _roadmap("A-1", "Z-1")})
    if variant in ("taken", "taken-same"):
        # The branch name the train would take, held by someone else, with an open pull request.
        monkeypatch.setenv("GIT_AUTHOR_DATE", "2026-01-01T12:00:00")
        monkeypatch.setenv("GIT_COMMITTER_DATE", "2026-01-01T12:00:00")
        tip = env.repo.git("rev-parse", "origin/main")
        for slug in ('aa', 'bb', 'cc'):
            tree = env.repo.git("merge-tree", "--write-tree", tip, heads[slug]).split()[0]
            tip = env.repo.git("commit-tree", tree, "-p", tip, "-p", heads[slug], "-m", "Forge merge train")
        taken = f"forge-merge-train/{tip[:12]}"
        stranger = tip if variant == "taken-same" else env.repo.git(  # the very commit the train would push
            "commit-tree", env.repo.git("rev-parse", "HEAD^{tree}"), "-p", env.repo.git("rev-parse", "HEAD"),
            "-m", "Someone else's work")
        env.repo.git("push", "-q", "origin", f"{stranger}:refs/heads/{taken}")
        (env.repo.bin / "pr-77.json").write_text(json.dumps({
            "number": 77, "headRefName": taken, "baseRefName": "main", "title": "Mine", "isDraft": False,
            "body": "", "url": "https://github.com/acme/shop/pull/77"}), "utf-8")
    if variant == "stale":  # the remote's settings say laptop tests; the main checkout still says CI
        _rival(env, {"forge.toml": (env.repo.path / "forge.toml").read_text("utf-8") + 'test_place = "local"\n'})
    if variant in ("no-app-check", "lint-only"):  # CI is the place, but no required check runs the app's tests
        kept = [line for line in (env.repo.path / "forge.toml").read_text("utf-8").splitlines()
                if not line.startswith("checks =")]
        required = '["forge-pr-check"]' if variant == "no-app-check" else '["lint", "forge-pr-check"]'
        _rival(env, {"forge.toml": "\n".join(kept + [f"checks = {required}", 'test_place = "ci"']) + "\n"})
    ready = env.common / "forge" / "ready" / "hh.json"  # hh closes again while the train waits
    _stub(env, pending_again={"path": str(ready), "mtime": ready.stat().st_mtime_ns} if variant == "out" and not adopted else None,
          no_drafts=variant == "no-drafts",
          rules={"rule": "strict", "behind": "unreadable"}.get(variant), behind=variant == "behind")
    done = _all(env)
    lines = done.stdout.splitlines()
    text = done.stdout + done.stderr
    created = [call for call in env.gh_calls("pr", "create") if _train_head(call)]
    if variant == "out":
        stays = {"cc": "it clashes with a change already in the train.",
                 "dd": "it changes forge.toml.", "ee": "it clashes with the default branch.",
                 "kk": "it clashes with the default branch.",
                 "hh": "the train already has five changes."}
        if adopted:
            assert "cc stays out of the train: it clashes with a change already in the train." in lines, text
            assert "Train: testing 2 ready changes together: aa, bb." in lines, text
        else:
            for slug, why in stays.items():
                assert f"{slug} stays out of the train: {why}" in lines, text
            assert "Train: testing 5 ready changes together: aa, bb, jj, ff, gg." in lines, text
            assert lines.index("gg merged.") < lines.index("hh merged."), text
            assert lines.index("hh: Closing hh.") < lines.index("aa merged."), text
            assert [number for number, _ in _merge_heads(env)][1:6] == [  # jb merged before the run
                _number(f"fix/{slug}") for slug in ("aa", "bb", "jj", "ff", "gg")], text
            for slug in ("dd", "kk", "hh"):  # cc and ee really clash: they stop for the worker
                assert any(line.startswith(f"{slug}: ") and RERUN in line for line in lines), text
            assert "Needs you (2): cc, ee" in done.stdout, text
    elif variant == "stacked":
        assert "jj stays out of the train: it builds on jb, which has not merged." in lines, text
        assert "Train: testing 3 ready changes together: aa, bb, jb." in lines, text
        assert lines.index("jb merged.") < lines.index("jj merged."), text
        assert [number for number, _ in _merge_heads(env)] == [
            _number(f"fix/{slug}") for slug in ("aa", "bb", "jb", "jj")], text
        assert any(line.startswith("jj: ") and RERUN in line for line in lines), text
    elif variant in ("taken", "taken-same"):  # no train, one line; the branch and its pull request stay
        assert f"Train: could not create {taken}, {LATER}" in lines, text
        assert not created and not env.gh_calls("pr", "close"), text
        assert env.repo.git("ls-remote", "--heads", env.remote, f"refs/heads/{taken}").split()[0] == stranger
        assert (env.repo.bin / "pr-77.json").exists()
        _everyone_merges_alone(env, done, ('aa', 'bb', 'cc'))
    elif variant == "switched":
        for slug in ("aa", "bb", "cc"):
            assert f"{slug} stays out of the train: it was ready before the default branch changed forge.toml." in lines, text
        assert not any(line.startswith("Train: testing") for line in lines) and not created, text
        _everyone_merges_alone(env, done, ("aa", "bb", "cc"))
    elif variant == "older":
        assert "bb stays out of the train: it has no ready record from its own close." in lines, text
        assert "Train: testing 2 ready changes together: aa, cc." in lines, text
        _everyone_merges_alone(env, done, ("bb",))  # the train never ran bb's merge, so bb closed first
        assert "Merged (3): " in done.stdout and "Needs you (0): none" in done.stdout, text
    elif variant == "alone":
        assert "bb stays out of the train: it clashes with the default branch." in lines, text
        assert not any(line.startswith("Train: testing") for line in lines) and not created, text
    elif variant == "no-drafts":
        assert f"Train: this repo allows no draft pull requests, {LATER}" in lines, text
        assert _train_branches(env) == [], text
        _everyone_merges_alone(env, done, ('aa', 'bb', 'cc'))
    elif variant in ("rule", "behind"):
        line = ("Train: GitHub requires each pull request to be up to date with main, so a train cannot save "
                "checks. The ready changes merge one at a time.")
        assert line in lines, text
        if variant == "rule":
            assert not created and _train_branches(env) == [], text
            _everyone_merges_alone(env, done, ('aa', 'bb', 'cc'))
        else:
            assert lines.index("aa merged.") < lines.index(line), text
            _everyone_merges_alone(env, done, ("bb", "cc"), moved=("bb", "cc"))  # aa merged before they started
    elif variant == "human":  # nothing merges in a human-merge run, so nothing is tested together
        assert not any(line.startswith("Train:") for line in lines) and not created, text
        assert not env.gh_calls("pr", "merge"), text
        assert lines[-1].startswith("Merged (0): none · Ready to merge (3): aa "), text
    else:  # stale, no-app-check, lint-only
        assert not any(line.startswith("Train:") for line in lines), text
        assert not created, text


def _failed_log(*paths: str) -> str:
    """A failed job's log; a path is written as the runner of the platform writes it."""
    return "".join(f"FAILED tests/test_x.py - AssertionError in {os.path.join(*path.split('/'))}\n" for path in paths)


@pytest.mark.platform
@pytest.mark.timeout(900)
@pytest.mark.parametrize("variant", ["one", "two"])
def test_3_a_failure_in_one_change_takes_it_out(train, monkeypatch, request, variant):
    env = train
    if variant == "two" and request.node.callspec.params["client"] == "adopted":
        pytest.skip("new repos only")
    _on_main(env, "src/base.py", "x = 0\n")
    slugs, broken = (("aa", "bb", "cc"), "bb") if variant == "one" else (("aa", "bb"), "aa")
    heads = _ready(env, monkeypatch, slugs, files={broken: {f"src/{broken}.py": f"print('{broken}')\n"}})
    _stub(env, red_train={"in": f"src/{broken}.py", "settle": variant == "one"},
          logs={"21": _failed_log(f"src/{broken}.py")},
          fresh={"closed": list(heads.values()), "red": broken, "failing": "tests"})
    done = _all(env)
    lines = done.stdout.splitlines()
    text = done.stdout + done.stderr
    others = [slug for slug in slugs if slug != broken]
    leaves = (f"Train: the combined check failed in files of {broken}. {broken} leaves the train and merges "
              "last, one at a time, with its own check.")
    first = f"Train: testing {len(slugs)} ready changes together: {', '.join(slugs)}."
    assert lines.index(first) < lines.index(leaves), text
    calls = env.gh.calls()
    # Every job finished before any log was read: the read that showed no job running came first.
    pending = next(n for n, call in enumerate(calls) if call == ["settle-pending"] ) if variant == "one" else None
    if variant == "one":
        settled = calls.index(["settle-done"])
        logged = next(n for n, call in enumerate(calls) if call[:2] == ["run", "view"] and "--log-failed" in call)
        assert pending < settled < logged, text
    created = [call for call in env.gh_calls("pr", "create") if _train_head(call)]
    merges = _merge_heads(env)
    if variant == "one":
        assert lines.index(leaves) < lines.index("Train: testing 2 ready changes together: aa, cc."), text
        assert len(created) == 2 and len(env.gh_calls("pr", "close")) == 2, text
        assert "Train: the combined check passed. Forge merges 2 changes in order." in lines, text
        assert [(n, h) for n, h in merges] == [(_number(f"fix/{slug}"), heads[slug]) for slug in others], text
        assert not any(f"{slug}: Closing {slug}." in lines for slug in others), text  # no re-run of their own
        assert lines.index("cc merged.") < lines.index(f"Starting {broken}."), text
    else:
        assert len(created) == 1 and len(env.gh_calls("pr", "close")) == 1, text
        assert merges == [(_number("fix/bb"), heads["bb"])], text  # one member alone goes at once
        assert "bb: Closing bb." in lines and lines.index("bb merged.") < lines.index("Starting aa."), text
    # The change that left merges last, with today's re-run: main moved, so a new head holds it, and
    # GitHub's checks for that head are red.
    assert any(line.startswith(f"{broken}: ") and RERUN in line for line in lines), text
    env.repo.git("fetch", "-q", "origin")
    pushed = env.repo.git("rev-parse", f"origin/fix/{broken}")
    assert pushed != heads[broken], text
    env.repo.git("merge-base", "--is-ancestor", "origin/main", pushed)
    assert any(f"/commits/{pushed}/check-runs" in arg for call in calls for arg in call), text
    assert not env.gh_calls("pr", "merge", _number(f"fix/{broken}")), text
    assert done.returncode == 1, text
    summary = next(line for line in lines if line.startswith("Merged ("))
    assert summary == (f"Merged ({len(others)}): {', '.join(others)} · Ready to merge (0): none · "
                       f"Needs you (1): {broken}"), text
    assert f"- {broken}: Checks failed on the pull request: tests." in lines, text
    if variant == "one":  # a second run takes bb into no train: its own check is red, so it is not ready
        again = _all(env)
        assert not any(line.startswith("Train:") and "bb" in line for line in again.stdout.splitlines()), again.stdout
        assert len([call for call in env.gh_calls("pr", "create") if _train_head(call)]) == 2


@pytest.mark.platform
@pytest.mark.timeout(900)
@pytest.mark.parametrize("variant", ["flake", "still-red", "several"])
def test_4_a_failure_naming_no_change_runs_again_once(train, monkeypatch, request, variant):
    env = train
    if variant != "flake" and request.node.callspec.params["client"] == "adopted":
        pytest.skip("new repos only")
    heads = _ready(env, monkeypatch, ("aa", "bb", "cc"))
    logs = {"flake": "ConnectionResetError: the runner lost its network\n", "still-red": "Process exited with code 1\n",
            "several": _failed_log("aa.py", "bb.py")}[variant]
    _stub(env, red_train={"heal": "2"} if variant == "flake" else {}, logs={"21": logs})
    done = _all(env)
    lines = done.stdout.splitlines()
    text = done.stdout + done.stderr
    assert done.returncode == 0, text
    summary = "Merged (3): aa, bb, cc · Ready to merge (0): none · Needs you (0): none"
    assert lines[-1] == summary, text
    one_by_one = "so each change merges one at a time with its own check."
    reruns = env.gh_calls("run", "rerun")
    if variant == "flake":
        assert "Train: the combined check failed in no change's files. Forge runs the failed jobs again once." in lines, text
        assert reruns == [["run", "rerun", "2", "--failed"]], text
        assert "Train: the combined check passed. Forge merges 3 changes in order." in lines, text
        assert [(n, h) for n, h in _merge_heads(env)] == [(_number(f"fix/{slug}"), heads[slug])
                                                        for slug in ("aa", "bb", "cc")], text
        assert not any(f"{slug}: Closing {slug}." in lines for slug in ("aa", "bb", "cc")), text
        return
    assert not any("the combined check passed" in line for line in lines), text
    if variant == "still-red":
        assert "Train: the combined check failed in no change's files. Forge runs the failed jobs again once." in lines, text
        assert reruns == [["run", "rerun", "2", "--failed"]], text
        assert f"Train: the combined check failed again, {one_by_one}" in lines, text
    else:
        assert f"Train: the combined check failed in files of aa and bb, {one_by_one}" in lines, text
        assert not reruns, text
    _everyone_merges_alone(env, done, ("aa", "bb", "cc"))


@pytest.mark.timeout(900)
@pytest.mark.parametrize("variant", ["moved", "changed", "late-main", "late-head", "differs"])
def test_5_the_default_branch_must_hold_what_the_train_tested(train, monkeypatch, request, variant):
    env = train
    if variant != "moved" and request.node.callspec.params["client"] == "adopted":
        pytest.skip("new repos only")
    heads = _ready(env, monkeypatch, ("aa", "bb", "cc"))
    # late-*: the move comes while the first member's own merge runs, after Forge looked at main and
    # the pull request, so only the merge itself can catch it.
    # moved and changed hold the tests of every head a fallback publishes at first, and moved also fails
    # bb's new heads (not the heads closed before), so a fallback's own CI can hold and stop its merge.
    fresh = {"closed": list(heads.values()), "red": "bb" if variant == "moved" else None}
    _stub(env, moved=variant == "moved", changed=variant == "changed",
          fresh=fresh if variant in ("moved", "changed") else None,
          late=variant.removeprefix("late-") if variant.startswith("late-") else None,
          stray=_number("fix/cc") if variant == "differs" else None)
    done = _all(env)
    lines = done.stdout.splitlines()
    text = done.stdout + done.stderr
    merges = _merge_heads(env)
    if variant in ("moved", "late-main"):
        assert ("Train: main no longer matches what the train tested, so the remaining changes merge one at a "
                "time, each with its own check.") in lines, text
        # Main moved before every member's merge, so each one finds it moved and runs its own check.
        if variant == "late-main":
            _everyone_merges_alone(env, done, ("aa", "bb", "cc"), moved=("aa", "bb", "cc"))
        else:  # bb's new head has a red check, so bb stops on it while aa and cc merge
            _everyone_merges_alone(env, done, ("aa", "cc"), moved=("aa", "cc"), held=True)
            assert "- bb: Checks failed on the pull request: lint." in lines, text
            assert not env.gh_calls("pr", "merge", _number("fix/bb")), text
    elif variant in ("changed", "late-head"):
        stale = "bb" if variant == "changed" else "aa"
        assert (f"Train: {stale} changed after the combined check, so it and the remaining changes merge one at a "
                "time.") in lines, text
        # It merges with the head it has now. late-head offers the tested head, as the move came after
        # Forge looked, and GitHub refuses it; changed never offers it.
        ours = [head for number, head in merges if number == _number(f"fix/{stale}")]
        assert ours and ours[-1] != heads[stale], text
        if variant == "changed":
            assert heads[stale] not in ours and (_number("fix/aa"), heads["aa"]) in merges, text
            assert "aa merged." in lines and "aa: Closing aa." not in lines, text  # aa took the train
        # aa merged in the train before changed's others started, so they found main moved; late-head
        # starts all three together.
        _everyone_merges_alone(env, done, ("bb", "cc") if variant == "changed" else ("aa", "bb", "cc"),
                               moved=("bb", "cc") if variant == "changed" else (), held=variant == "changed")
    else:
        note = ("Train: after the last merge, main does not match what the train tested. Check main: the next "
                "pull request check or the nightly full run tests it.")
        summary = next(n for n, line in enumerate(lines) if line.startswith("Merged ("))
        assert done.returncode == 0, text
        assert [n for n, line in enumerate(lines) if line == note] == [
            lines.index("cc merged.") + 1, len(lines) - 1] and lines.index(
            "Train: the combined check passed. Forge merges 3 changes in order.") < summary, text
