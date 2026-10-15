STORY = "FORGE-QUEUE-1"
# forge land --all: one run closes and merges every change in close, oldest first, several at
# once, on a repo made by forge init and on the adopted earlier-release fixture moved to this
# release. Only gh, Autoreview, the worker and nothing else are stubs; changes are real fixes.

import json
import os
import re
import shutil
import subprocess
import sys
import time
import zlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from conftest import GH_STUB, ROOT, _install, machine_cores
from test_close import CLEAN, GREEN, blocked, env, finding, run  # noqa: F401
from test_conflicting_pull_requests_stop_check_waits import _publish_default
from test_setup import _fresh_client
from test_story import worktree

# In front of the stub gh: one pull request per branch, a squash merge done in the bare remote as
# GitHub would, and every other call answered by the stub's queued responses.
GH = '''#!PYTHON
import json, pathlib, subprocess, sys, tempfile, time, zlib
from json_log import append_json
here = pathlib.Path(__file__).resolve().parent
args = sys.argv[1:]
remote = REMOTE


def answer(out, code=0):
    append_json(here / "gh-calls.jsonl", args)
    append_json(here / "gh-timed.jsonl", {"args": args, "at": time.time()})
    sys.stdout.write(out)
    sys.exit(code)


def heads():
    listed = subprocess.run(["git", "ls-remote", "--heads", remote], capture_output=True,
                            text=True).stdout.split()
    return dict(zip(listed[1::2], listed[0::2]))


def pr(key):
    for path in here.glob("pr-*.json"):
        found = json.loads(path.read_text("utf-8"))
        if key in (found["headRefName"], str(found["number"])):
            merged = here / ("merged-%d" % found["number"])
            if merged.exists():
                return {**found, "state": "MERGED", "headRefOid": merged.read_text()}
            refs = heads()
            head = refs.get("refs/heads/" + found["headRefName"], "")
            clean = not subprocess.run(["git", "merge-tree", "--write-tree", refs["refs/heads/main"], head],
                                       cwd=remote, capture_output=True).returncode
            return {**found, "state": "OPEN", "headRefOid": head,
                    "mergeable": "MERGEABLE" if clean else "CONFLICTING",
                    "mergeStateStatus": "CLEAN" if clean else "DIRTY"}
    return None


def save(found, **change):
    found = {**found, **change}
    (here / ("pr-%d.json" % found["number"])).write_text(json.dumps(found))


if args[:4] == ["api", "--paginate", "--jq", ".check_runs[]"]:  # a branch's own checks, if set
    branch = subprocess.run(["git", "branch", "--show-current"], capture_output=True,
                            text=True).stdout.strip()
    own = here / ("checks-" + branch.replace("/", "-") + ".txt")
    if own.exists():
        answer(own.read_text())
if args[:2] == ["api", "graphql"]:  # the board's one read of open pull requests and their checks
    nodes = []
    for path in sorted(here.glob("pr-*.json")):
        found = pr(json.loads(path.read_text("utf-8"))["headRefName"])
        if found["state"] != "OPEN":
            continue
        own = here / ("checks-" + found["headRefName"].replace("/", "-") + ".txt")
        rows = ([json.loads(line) for line in own.read_text().splitlines()] if own.exists() else
                [{"name": name, "status": "completed", "conclusion": "success"} for name in ("tests", "forge-pr-check")])
        contexts = [{"__typename": "CheckRun", "name": row["name"], "status": row["status"].upper(),
                     "conclusion": (row["conclusion"] or "").upper() or None} for row in rows]
        nodes.append({**found, "commits": {"nodes": [{"commit": {"oid": found["headRefOid"], "statusCheckRollup": {
            "contexts": {"pageInfo": {"hasNextPage": False}, "nodes": contexts}}}}]}})
    answer(json.dumps({"data": {"repository": {"pullRequests": {"nodes": nodes}}}}))
if args[:2] == ["run", "rerun"]:  # the re-run's second attempt; a healed run's checks turn green
    (here / ("rerun-" + args[2])).touch()
    heal = here / ("heal-" + args[2])
    if heal.exists():
        (here / heal.read_text()).unlink()
    answer("")
if args[:2] == ["run", "view"] and "attempt" in args:
    answer(json.dumps({"attempt": 2 if (here / ("rerun-" + args[2])).exists() else 1}))
if args[:2] == ["pr", "create"]:
    branch = args[args.index("--head") + 1]
    number = zlib.crc32(branch.encode()) % 9000 + 100
    url = "https://github.com/acme/shop/pull/%d" % number
    save({"number": number, "headRefName": branch, "baseRefName": "main", "title": "Change " + branch,
          "isDraft": "--draft" in args, "body": "", "url": url})
    answer(url + "\\n")
if args[:2] == ["pr", "ready"]:
    found = pr(args[2])
    save({key: found[key] for key in ("number", "headRefName", "baseRefName", "title", "body", "url")},
         isDraft="--undo" in args)
    answer("")
if args[:2] == ["pr", "list"] and "--head" in args:
    found = pr(args[args.index("--head") + 1])
    answer(json.dumps([found] if found else []))
if args[:2] == ["pr", "view"]:
    found = pr(args[2])
    if found is None:
        answer("no pull requests found", 1)
    answer(found["state"] + "\\n" if "--jq" in args else json.dumps(found))
if args[:2] == ["pr", "merge"]:
    head = args[args.index("--match-head-commit") + 1]
    found = pr(args[2])
    if found is None or found["state"] == "MERGED" or found["headRefOid"] != head:
        answer("", 1)
    for attempt in range(5):  # two merges at once: the later push retries on the newer main
        checkout = tempfile.mkdtemp(dir=here)
        subprocess.run(["git", "clone", "-q", remote, checkout], check=True)
        for step in (["fetch", "-q", "origin", found["headRefName"]],
                     ["merge", "-q", "--squash", "FETCH_HEAD"],
                     ["commit", "-q", "-m", args[args.index("--subject") + 1]]):
            if subprocess.run(["git", *step], cwd=checkout, capture_output=True).returncode:
                answer("Pull request is not mergeable: the merge commit cannot be cleanly created.", 1)
        if not subprocess.run(["git", "push", "-q", "origin", "main"], cwd=checkout,
                              capture_output=True).returncode:
            break
    (here / ("merged-%d" % found["number"])).write_text(head)
    answer("")
'''

# Each fix's review answers come from its own queue, picked by the fix's name in the prompt, so
# concurrent closes don't share one.
OWN_REVIEWS = '''args = sys.argv[1:]
_said = " ".join(args) + " ".join(Path(path).read_text("utf-8")
                                  for flag, path in zip(args, args[1:]) if flag == "--prompt-file")
for _own in Path(os.environ["AUTOREVIEW_STUB"]).parent.glob("reviews-fix-*.json"):
    if "Why: Change " + _own.stem[len("reviews-fix-"):] + "\\n" in _said:
        os.environ["AUTOREVIEW_STUB"] = str(_own)
        with open(_own.with_name("review-starts.jsonl"), "a") as _log:  # when this fix's close got here
            import time
            _log.write(json.dumps({"fix": _own.stem[len("reviews-fix-"):], "at": time.time()}) + "\\n")
        _wait = _own.with_name("wait-" + _own.stem[len("reviews-fix-"):])  # until the file it names exists
        for _ in range(600 if _wait.exists() else 0):
            if Path(_wait.read_text()).exists():
                break
            time.sleep(0.1)
'''
SHARED = "".join(f"line {n}\n" for n in range(1, 8))


@pytest.fixture(params=["new", "adopted"])
def client(env, request):
    repo = env.repo
    config = (repo.path / "forge.toml").read_text("utf-8") + 'merge = "agent"\n'
    if request.param == "new":
        path, made = _fresh_client(repo, env.gh, env.tmp)
        assert made.returncode == 0, made.stderr
        repo.path = path
        repo.git("switch", "-qc", "fix/upgrade-client")
    else:
        repo.git("switch", "-qc", "fix/upgrade-client")
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path, dirs_exist_ok=True)
        repo.git("add", "-A")
        repo.git("commit", "-qm", "Adopt the earlier release")
    repo.write(".factory/fixes/upgrade-client.json", json.dumps({
        "kind": "fix", "branch": "fix/upgrade-client", "status": "working",
        "why": "Refresh client guidance", "done_when": "Guidance uses this release"}))
    repo.write("shared.py", SHARED)
    env.commit(repo.path, "forge.toml", config)
    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stderr
    repo.git("add", "-A")
    repo.git("commit", "-qm", "Refresh client guidance", "--allow-empty")
    remote = Path(repo.git("remote", "get-url", "origin")).as_posix()
    _publish_default(repo, remote)
    repo.git("switch", "main")
    repo.git("merge", "--ff-only", "fix/upgrade-client")
    _install(repo.bin, "gh", GH.replace("PYTHON", sys.executable).replace("REMOTE", repr(remote))
             + GH_STUB.format(python=sys.executable).split("\n", 1)[1])
    _install(repo.bin, "claude", (ROOT / "tests/stubs/claude").read_text("utf-8"))
    stub = Path(os.environ["AUTOREVIEW"])
    stub.write_text(stub.read_text("utf-8").replace("args = sys.argv[1:]\n", OWN_REVIEWS, 1), "utf-8")
    env.checks(GREEN)
    return env


def _fix(env, monkeypatch, slug: str, day: int, files: dict[str, str], status: str = "reviewing",
         message: str = "Worker round", answer: dict = CLEAN, **state) -> Path:
    """forge fix start on a given day (its start commit dates the change), then the worker's
    commit, with the status a close part-way through leaves."""
    with monkeypatch.context() as dated:
        dated.setenv("GIT_COMMITTER_DATE", f"2026-01-{day:02d}T12:00:00")
        started = env.repo.forge("fix", "start", f"Change {slug}", "--done", f"{slug} is changed",
                                 "--slug", slug)
    assert started.returncode == 0, started.stdout + started.stderr
    where = worktree(env.repo, f"fix/{slug}")
    (env.tmp / f"reviews-fix-{slug}.json").write_text(json.dumps([answer]), "utf-8")
    for path, text in files.items():
        (where / path).write_text(text, encoding="utf-8")
    record = where / ".factory" / "fixes" / f"{slug}.json"
    record.write_text(json.dumps({**json.loads(record.read_text("utf-8")), "status": status, **state}),
                      encoding="utf-8")
    env.repo.git("add", "-A", cwd=where)
    env.repo.git("commit", "-q", "-m", message, cwd=where)
    return where


def _settings(env, **values: str) -> None:
    """The default branch's forge.toml with these settings, published as the fixture publishes it."""
    repo = env.repo
    repo.git("switch", "fix/upgrade-client")
    kept = [line for line in (repo.path / "forge.toml").read_text("utf-8").splitlines()
            if line.partition("=")[0].strip() not in values]
    env.commit(repo.path, "forge.toml", "\n".join(kept + [f"{key} = {json.dumps(value)}"
                                                         for key, value in values.items()]) + "\n")
    _publish_default(repo, Path(repo.git("remote", "get-url", "origin")).as_posix())
    repo.git("switch", "main")
    repo.git("merge", "--ff-only", "fix/upgrade-client")


def _edit(line: int, text: str) -> str:
    lines = SHARED.splitlines(keepends=True)
    lines[line - 1] = text + "\n"
    return "".join(lines)


def _all(env, cwd: Path | None = None):
    return env.repo.forge("land", "--all", cwd=cwd)


def _places(env) -> int:
    return json.loads(env.repo.forge("lanes", "--json").stdout)["agents"]["size"]


def _in_close(env, *slugs: str) -> dict[str, tuple[float, float]]:
    """When each fix was in close: from its review's start, which only its own close reaches, to
    GitHub's merge of it, from the times the stub Autoreview and stub gh recorded."""
    started = {row["fix"]: row["at"] for row in map(json.loads, (env.tmp / "review-starts.jsonl")
                                                    .read_text("utf-8").splitlines())}
    timed = [json.loads(line) for line in (env.repo.bin / "gh-timed.jsonl").read_text("utf-8").splitlines()]
    return {slug: (started[slug], next(call["at"] for call in timed
                                       if call["args"][:3] == ["pr", "merge", _number(f"fix/{slug}")]))
            for slug in slugs}


def _red(env, slug: str, status: str = "completed", conclusion: str | None = "failure") -> None:
    """This fix's own checks on GitHub: tests in the given state."""
    (env.repo.bin / f"checks-fix-{slug}.txt").write_text("".join(json.dumps(row) + "\n" for row in (
        run("tests", conclusion, status), run("forge-pr-check"))), "utf-8")


def _reviews(env, slug: str) -> int:
    log = env.tmp / f"reviews-fix-{slug}.calls.jsonl"
    return len(log.read_text("utf-8").splitlines()) if log.exists() else 0


def _number(branch: str) -> str:
    return str(zlib.crc32(branch.encode()) % 9000 + 100)


def _first(env, *prefix: str, contains: str = "") -> int:
    calls = env.gh.calls()
    return next(n for n, call in enumerate(calls) if call[:len(prefix)] == list(prefix)
                and (not contains or contains in call))


def test_1_one_run_starts_changes_oldest_first_and_merges_each(client, monkeypatch):
    env = client
    machine_cores(env.repo, 4)  # two agent places for three changes
    for args in ((), ("cherry", "--all")):
        neither = env.repo.forge("land", *args)
        assert neither.returncode == 1
        assert neither.stderr.endswith("Give one change or --all, not both and not neither.\n"
                                       "Next: forge land <item>, or forge land --all\n")
    # Named against their age, so only the start date can order them.
    cherry = _fix(env, monkeypatch, "cherry", 1, {"cherry.py": "print('cherry')\n"})
    _fix(env, monkeypatch, "banana", 2, {"banana.py": "print('banana')\n"})
    _fix(env, monkeypatch, "apple", 3, {"apple.py": "print('apple')\n"})
    started = _fix(env, monkeypatch, "draft", 4, {"draft.py": "x = 1\n"}, status="started")
    untouched = env.repo.git("rev-parse", "HEAD", cwd=started)
    gone = _fix(env, monkeypatch, "gone", 6, {"gone.py": "x = 1\n"})  # its pull request merged already
    number = int(_number("fix/gone"))
    (env.repo.bin / f"pr-{number}.json").write_text(json.dumps({
        "number": number, "headRefName": "fix/gone", "baseRefName": "main", "title": "Gone", "isDraft": False,
        "body": "", "url": f"https://github.com/acme/shop/pull/{number}"}), "utf-8")
    (env.repo.bin / f"merged-{number}").write_text(env.repo.git("rev-parse", "HEAD", cwd=gone), "utf-8")
    # A real close of a fifth fix, waiting for its still-running CI while the run starts.
    busy = _fix(env, monkeypatch, "busy", 5, {"busy.py": "x = 1\n"})
    _red(env, "busy", "in_progress", None)
    forge = [sys.executable, str(env.repo.bin / "forge")]
    waiting = subprocess.Popen([*forge, "close", "busy"], cwd=busy, env={**os.environ, "FORGE_CHECKS_WAIT": "600"},
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(600):
            if ["pr", "view", "fix/busy", "--json", "mergeable,headRefOid"] in env.gh.calls():
                break
            time.sleep(0.2)
        # The draft stays in place: a Windows process can hold its starting folder open.
        # Two runs started at the same moment: one works, the other refuses.
        runs = [subprocess.Popen([*forge, "land", "--all"], cwd=where, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, encoding="utf-8") for where in (started, env.repo.path)]
        (out, err), (other, refused) = (run.communicate(timeout=600) for run in runs)
    finally:
        waiting.kill()
        waiting.wait()
    if runs[0].returncode == 1:
        (out, err), (other, refused) = (other, refused), (out, err)
        runs.reverse()
    assert runs[0].returncode == 0, out + err
    assert runs[1].returncode == 1, out + err + refused
    assert refused.endswith("A land run already works in this repo.\n"
                            "Next: wait for it to end, then forge land --all\n")
    assert not other, out + err + refused
    lines = out.splitlines()
    assert [line for line in lines if line.startswith("Starting ")] == [
        "Starting cherry.", "Starting banana.", "Starting apple."], out + err + refused
    # Each change enters close, by its own Closing line, before the next one starts.
    entries = [lines.index(f"{slug}: Closing {slug}.") for slug in ("cherry", "banana", "apple")]
    starts = [lines.index(f"Starting {slug}.") for slug in ("cherry", "banana", "apple")]
    assert starts[0] < entries[0] < starts[1] < entries[1] < starts[2] < entries[2], out
    places = _places(env)
    assert places == 2
    spans = _in_close(env, "cherry", "banana", "apple")
    # The two oldest start together, so both are in close before either merges; the newest enters
    # only once one of them has merged and freed its place.
    first_merge = min(spans["cherry"][1], spans["banana"][1])
    assert max(spans["cherry"][0], spans["banana"][0]) < first_merge < spans["apple"][0], spans
    assert sorted(spans, key=lambda slug: spans[slug][0])[-1] == "apple", spans
    assert "Left out gone: its pull request already merged." in lines, out + err + refused
    assert "Left out draft: its builder is not done yet." in lines, out + err + refused
    assert "Left out busy: another command works on it." in lines, out + err + refused
    assert "Starting busy." not in lines and "Starting draft." not in lines, out + err + refused
    assert env.repo.git("rev-parse", "HEAD", cwd=started) == untouched, out + err + refused
    assert len(env.gh_calls("pr", "merge")) == 3, out + err + refused
    assert not cherry.exists(), out + err + refused
    assert re.fullmatch(r"Merged \(3\): .+ · Ready to merge \(0\): none · Needs you \(0\): none", lines[-1]), out + err + refused
    # The close waiting for CI was killed: the next run takes its change again.
    (env.repo.bin / "checks-fix-busy.txt").unlink()
    again = _all(env)
    assert again.returncode == 0, again.stdout + again.stderr
    assert "Starting busy." in again.stdout.splitlines() and "busy merged." in again.stdout.splitlines(), again.stdout


@pytest.mark.parametrize("older", ["merges", "stops"])
def test_2_a_change_sharing_a_file_waits_for_the_older_one(client, monkeypatch, older):
    env = client
    machine_cores(env.repo, 4)  # two agent places, as on CI: fewer places than changes
    answer = CLEAN if older == "merges" else blocked(finding("P1", "Saving drops line one", "shared.py"))
    _fix(env, monkeypatch, "aa", 1, {"shared.py": _edit(1, "first")}, answer=answer,
         message="Worker round\n\nSpotted: bug shared.py:4 line four repeats itself")
    _fix(env, monkeypatch, "bb", 2, {"shared.py": _edit(7, "last")})
    _fix(env, monkeypatch, "cc", 3, {"other.py": "x = 1\n"},
         message="Worker round\n\nSpotted: simplify shared.py:2 line two could go")
    if older == "merges":
        _fix(env, monkeypatch, "dd", 4, {"shared.py": _edit(4, "middle")}, status="working")
        closed = env.repo.forge("close", "dd")
        assert closed.returncode == 0, closed.stdout + closed.stderr
    else:  # closed ready earlier, then its check failed: no longer ready, so it waits too
        _fix(env, monkeypatch, "ee", 4, {"shared.py": _edit(4, "middle")}, status="working")
        closed = env.repo.forge("close", "ee")
        assert closed.returncode == 0, closed.stdout + closed.stderr
        _red(env, "ee")
    done = _all(env)
    lines = done.stdout.splitlines()
    assert "bb waits for aa: both change shared.py." in lines, done.stdout
    assert not any(line.startswith(("cc waits", "dd waits")) for line in lines), done.stdout
    assert _reviews(env, "bb") == 1, done.stdout
    end = "aa merged." if older == "merges" else "aa stopped: The review left serious findings open: finding 1 (Saving drops line one)."
    assert end in lines and lines.index(end) < lines.index("Starting bb."), done.stdout
    if older == "merges":
        assert done.returncode == 0, done.stdout + done.stderr
        assert _first(env, "pr", "merge", _number("fix/aa")) < _first(env, "pr", "create", contains="fix/bb")
        if _places(env) >= 2:
            assert lines.index("Starting cc.") < lines.index("aa merged.")
        assert re.fullmatch(r"Merged \(4\): .+ · Ready to merge \(0\): none · Needs you \(0\): none", lines[-1])
    else:
        assert done.returncode == 1, done.stdout
        assert "bb merged." in lines, done.stdout
        assert "ee waits for aa: both change shared.py." in lines, done.stdout
        summary = next(n for n, line in enumerate(lines) if line.startswith("Merged ("))
        assert re.fullmatch(r"Merged \(2\): .+ · Ready to merge \(0\): none · Needs you \(2\): aa, ee",
                            lines[summary]), done.stdout
        assert lines[summary + 1:summary + 3] == [
            "- aa: The review left serious findings open: finding 1 (Saving drops line one).",
            "  Next: forge land aa"]


def test_3_a_failed_check_naming_none_of_the_files_runs_again_once(client, monkeypatch):
    env = client
    # Close runs fast_test, so only its passed record says the tests passed here.
    _settings(env, test=f"{sys.executable} -c \"print(1)\"", fast_test=f"{sys.executable} -c pass")
    for day, (slug, run_id) in enumerate((("flaky", "5"), ("broken", "6")), 1):
        _fix(env, monkeypatch, slug, day, {f"{slug}.py": "x = 1\n"})
        _red(env, slug)
        env.gh.respond("pr", "checks", f"fix/{slug}", exit=1, stdout=json.dumps([{
            "name": "tests", "bucket": "fail", "link": f"https://github.com/acme/shop/actions/runs/{run_id}/job/9{run_id}"}]))
        env.gh.respond("run", "view", "--job", f"9{run_id}", stdout="ConnectionResetError: the runner lost its network\n")
    (env.repo.bin / "heal-5").write_text("checks-fix-flaky.txt", "utf-8")  # only flaky's re-run passes
    done = _all(env)
    assert done.returncode == 1, done.stdout + done.stderr
    lines = done.stdout.splitlines()
    for slug in ("flaky", "broken"):
        assert (f"{slug}: Re-running tests once: its failure names none of this change's files and the tests "
                "passed here.") in lines, done.stdout
    assert sorted(env.gh_calls("run", "rerun")) == [["run", "rerun", "5", "--failed"], ["run", "rerun", "6", "--failed"]]
    assert "flaky merged." in lines, done.stdout
    assert not env.gh_calls("pr", "merge", _number("fix/broken"))
    summary = next(n for n, line in enumerate(lines) if line.startswith("Merged ("))
    assert lines[summary:] == ["Merged (1): flaky · Ready to merge (0): none · Needs you (1): broken",
                               "- broken: Checks failed on the pull request: tests.", "  Next: forge land broken"], done.stdout


def test_4_a_change_that_needs_you_stops_alone(client, monkeypatch):
    env = client
    _fix(env, monkeypatch, "stuck", 1, {"stuck.py": "x = 1\n"},
         answer=blocked(finding("P1", "Saving drops the basket", "stuck.py")))
    _fix(env, monkeypatch, "clean", 2, {"clean.py": "x = 1\n"})
    held = _fix(env, monkeypatch, "loop", 3, {"loop.py": "x = 1\n"}, status="hotspot",
                stop={"file": "loop.py", "round": 4, "at": datetime.now(timezone.utc).isoformat()},
                review={"findings": [finding("P1", "Saving loses the name", "loop.py")], "dismissals": []})
    # A stuck worker's stop, and a review loop stop nobody answered for 31 minutes.
    _fix(env, monkeypatch, "worn", 4, {"worn.py": "x = 1\n"}, status="hotspot",
         stop={"question": "Worn keeps failing the same test. Switch, same, narrow or split?", "tool": "claude"})
    late = _fix(env, monkeypatch, "late", 5, {"late.py": "x = 1\n"}, status="hotspot",
                stop={"file": "late.py", "round": 4,
                      "at": (datetime.now(timezone.utc) - timedelta(minutes=31)).isoformat()},
                review={"findings": [{"title": "Saving drops the date", "priority": "P1", "file": "late.py",
                                      "line": 1, "body": "Gain 3, Work 2, Harm 1\nThe date is lost."}],
                        "dismissals": []})
    # A required check GitHub skipped fails close's check gate: forge land is its repair step.
    _fix(env, monkeypatch, "skip", 6, {"skip.py": "x = 1\n"})
    _red(env, "skip", conclusion="skipped")
    record = held / ".factory" / "fixes" / "loop.json"
    before = record.read_bytes(), env.repo.git("rev-parse", "HEAD", cwd=held)
    done = _all(env)
    assert done.returncode == 1, done.stdout + done.stderr
    lines = done.stdout.splitlines()
    assert "clean merged." in lines, done.stdout
    assert "Starting loop." not in lines
    # Close's own 30-minute default answered the overdue stop, so that change closed and merged.
    assert lines[0].startswith("Nobody answered the review loop stop in 30 minutes, so Forge recorded "
                               "the repo's default choice: narrow"), done.stdout
    assert "late merged." in lines and not late.exists(), done.stdout
    summary = next(n for n, line in enumerate(lines) if line.startswith("Merged ("))
    assert re.fullmatch(r"Merged \(2\): (clean, late|late, clean) · Ready to merge \(0\): none · "
                        r"Needs you \(4\): stuck, loop, worn, skip", lines[summary]), done.stdout
    tail = "\n".join(lines[summary + 1:])
    assert tail.startswith("- stuck: The review left serious findings open: finding 1 "
                           "(Saving drops the basket).\n  Next: forge land stuck\n- loop: Review round ")
    assert "Saving loses the name" in tail and "Accept, narrow or split?" in tail
    assert '  Next: forge close loop --resolve <narrow|split|accept> --reason "<human\'s choice>"\n- worn: ' in tail
    assert tail.endswith("Ask the human:\nWorn keeps failing the same test. Switch, same, narrow or split?\n"
                         '  Next: forge close worn --resolve <switch|same|narrow|split> --reason "<human\'s choice>"\n'
                         "- skip: Checks failed on the pull request: tests.\n  Next: forge land skip"), done.stdout
    assert not (env.repo.bin / "claude-calls.jsonl").exists()
    assert not env.gh_calls("pr", "merge", _number("fix/stuck"))
    assert (record.read_bytes(), env.repo.git("rev-parse", "HEAD", cwd=held)) == before


def test_5_a_human_merge_run_closes_all_and_lists_them_oldest_first(client, monkeypatch):
    env = client
    machine_cores(env.repo, 4)  # two agent places
    _settings(env, merge="human")
    _fix(env, monkeypatch, "aa", 1, {"shared.py": _edit(1, "first")})
    _fix(env, monkeypatch, "bb", 2, {"shared.py": _edit(7, "last")})
    # The older review goes on only once the newer change is ready: both are in close at once,
    # and the newer one ends first.
    common = Path(env.repo.git("rev-parse", "--path-format=absolute", "--git-common-dir"))
    (env.tmp / "wait-aa").write_text(str(common / "forge" / "ready" / "bb.json"), "utf-8")
    done = _all(env)
    assert done.returncode == 0, done.stdout + done.stderr
    lines = done.stdout.splitlines()
    assert not any(" waits for " in line for line in lines), done.stdout
    ready = [line.split(": ", 1)[0] for line in lines if " is ready; a human merges its pull request: " in line]
    assert ready == ["bb", "aa"], done.stdout  # the newer one ends first, so the list is sorted
    assert not env.gh_calls("pr", "merge")
    url = "https://github.com/acme/shop/pull/{}".format
    assert lines[-1] == (f"Merged (0): none · Ready to merge (2): aa {url(_number('fix/aa'))}, "
                         f"bb {url(_number('fix/bb'))} · Needs you (0): none"), done.stdout
