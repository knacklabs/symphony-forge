STORY = "FORGE-LAND-1"
# forge land: one command builds a started task or fix, closes it, runs fix rounds, and merges it
# or hands it to a human. It runs the real forge command against the stub gh, Autoreview and claude.

import json
import re
import sys
from pathlib import Path

import pytest

from conftest import GH_STUB, _install
from test_close import CLEAN, GREEN, blocked, env, finding, run  # noqa: F401
from test_codex_worker import _codex_repo, _sent, sdk_data  # noqa: F401
from test_worker import calls

ITEM, BRANCH = "tidy-readme", "fix/tidy-readme"
URL = "https://github.com/acme/shop/pull/7"
RUNS = ["api", "--paginate", "--jq", ".check_runs[]"]
# forge work's own "Building <item> with <worker> ..." line is not one of land's steps.
STEPS = re.compile(r"(Building(?! \S+ with )|Closing|Fix round|Re-running"
                   r"|Merging|Stopped"
                   r"|\S+ is ready; a human)")

# In front of the stub gh: a pull request whose head is the remote branch's, a squash merge done
# in the bare remote as GitHub would, and queued answers (the last repeats) for calls that change.
GH = '''#!{python}
import json, pathlib, subprocess, sys
here = pathlib.Path(__file__).resolve().parent
args = sys.argv[1:]
remote = {remote!r}


def answer(out, code=0):
    with open(here / "gh-calls.jsonl", "a", encoding="utf-8") as log:
        log.write(json.dumps(args) + "\\n")
    sys.stdout.write(out)
    sys.exit(code)


def heads():
    listed = subprocess.run(["git", "ls-remote", "--heads", remote], capture_output=True,
                            text=True).stdout.split()
    return dict(zip(listed[1::2], listed[0::2]))


merged = here / "github-merged"
if args[:2] == ["pr", "list"] and "--head" in args and merged.exists():
    answer(json.dumps([{{"number": 7, "state": "MERGED", "body": "", "isDraft": False}}]))
if args[:2] == ["pr", "view"]:
    state = "MERGED" if merged.exists() else "OPEN"
    oid = (merged.read_text() if merged.exists() else "0" * 40 if (here / "head-moved").exists()
           else heads().get("refs/heads/" + args[2], ""))
    if "--jq" in args:
        answer(state + "\\n")
    answer(json.dumps({{"number": 7, "state": state, "baseRefName": "main", "headRefName": args[2],
                       "headRefOid": oid, "title": "Tidy readme", "isDraft": False, "url": {url!r}}}))
if args[:2] == ["pr", "merge"]:
    head = args[args.index("--match-head-commit") + 1]
    branch = next((ref for ref, oid in heads().items() if oid == head), None)
    if branch is None:
        answer("", 1)
    checkout = here / "github-merge"
    subprocess.run(["git", "clone", "-q", remote, str(checkout)], check=True)
    for step in (["fetch", "-q", "origin", branch], ["merge", "-q", "--squash", "FETCH_HEAD"],
                 ["commit", "-q", "-m", args[args.index("--subject") + 1]],
                 ["push", "-q", "origin", "main"]):
        subprocess.run(["git", *step], cwd=checkout, check=True, capture_output=True)
    merged.write_text(head)
    answer("")
queues = here / "gh-queues.json"
rules = json.loads(queues.read_text("utf-8")) if queues.exists() else []
for rule in rules:
    if args[:len(rule["args"])] == rule["args"]:
        out = rule["outs"].pop(0) if len(rule["outs"]) > 1 else rule["outs"][0]
        queues.write_text(json.dumps(rules), "utf-8")
        answer(out)
'''

# The stub claude, committing a file as a worker does when its round succeeds.
COMMITS = '''if not int(os.environ.get("STUB_CLAUDE_EXIT", "0")):
    import subprocess
    done = len(list(pathlib.Path.cwd().glob("work-*.txt")))
    pathlib.Path(f"work-{done + 1}.txt").write_text("worked\\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], check=True)
    subprocess.run(["git", "commit", "-q", "-m", "Worker round"], check=True)
print("stub claude: built it")'''


@pytest.fixture
def land(env, tmp_path):
    root = Path(__file__).resolve().parent
    stub = (root / "stubs" / "claude").read_text("utf-8")
    _install(env.repo.bin, "claude", stub.replace('print("stub claude: built it")', COMMITS))
    _install(env.repo.bin, "gh", GH.format(python=sys.executable, remote=str(tmp_path / "remote.git"),
                                           url=URL) + GH_STUB.format(python=sys.executable).split("\n", 1)[1])
    toml = env.repo.path / "forge.toml"
    env.commit(env.repo.path, "forge.toml", toml.read_text("utf-8")
               + 'models.lite = { model = "opus", effort = "high" }\n')
    env.repo.git("push", "-q", "origin", "main")
    return env


def _agent(env, extra: str = 'merge = "agent"\n') -> None:
    env.commit(env.repo.path, "forge.toml", (env.repo.path / "forge.toml").read_text("utf-8") + extra)
    env.repo.git("push", "-q", "origin", "main")


def _fix(env, status: str = "started", worked: bool = False, changes: dict | None = None,
         **state: str) -> Path:
    """A fix as forge fix start leaves it; worked: as a finished forge work leaves it."""
    where = env.tmp / "repo-fix-tidy-readme"
    env.repo.git("worktree", "add", "-q", "-b", BRANCH, str(where))
    lines = {"branch": BRANCH, "status": status, "kind": "fix", "why": "Readme greets new readers",
             "done_when": "The readme opens with a greeting", **state}
    env.commit(where, f".factory/fixes/{ITEM}.json", json.dumps(lines),
               f"{ITEM} is working" if worked else f"Start the fix: {lines['why']}")
    for path, text in (changes or ({"app.py": "print('hello')\n"} if worked else {})).items():
        env.commit(where, path, text, "Worker round")
    return where


def _queue(env, args: list[str], *outs: str) -> None:
    path = env.repo.bin / "gh-queues.json"
    rules = json.loads(path.read_text("utf-8")) if path.exists() else []
    path.write_text(json.dumps(rules + [{"args": args, "outs": list(outs)}]), "utf-8")


def _runs(*looks: list[dict]) -> list[str]:
    return ["".join(json.dumps(row) + "\n" for row in look) for look in looks]


def _land(env, item: str = ITEM):
    return env.repo.forge("land", item)


def _steps(done) -> list[str]:
    return [line for line in done.stdout.splitlines() if STEPS.match(line)]


def _workers(env) -> list[dict]:
    return calls(env.repo.bin / "claude-calls.jsonl")


def _refusal(done) -> list[str]:
    return done.stderr.splitlines()[-2:]


def _unbuilt_fix_built_once_then_merged(env):
    _agent(env)
    _fix(env)
    done = _land(env)
    assert done.returncode == 0, done.stdout + done.stderr
    assert _steps(done) == [f"Building {ITEM}.", f"Closing {ITEM}.", f"Merging {ITEM}."]
    assert len(_workers(env)) == 1
    assert len(env.gh_calls("pr", "merge")) == 1


def _working_fix_closes_without_a_worker(env):
    _fix(env, "working", worked=True)
    done = _land(env)
    assert done.returncode == 0, done.stderr
    assert _steps(done) == [f"Closing {ITEM}.", f"{ITEM} is ready; a human merges its pull request: {URL}"]
    assert not _workers(env)


def _made_by_forge_closes_without_a_worker(env, kind):
    _fix(env, changes={"notes.md": "Done\n"}, kind=kind)
    done = _land(env)
    assert done.returncode == 0, done.stderr
    assert _steps(done)[0] == f"Closing {ITEM}."
    assert not _workers(env)


def _failed_worker_stops_then_builds_again(env, monkeypatch):
    _fix(env)
    monkeypatch.setenv("STUB_CLAUDE_EXIT", "3")
    failed = _land(env)
    assert failed.returncode == 1
    assert _steps(failed) == [f"Building {ITEM}.", f"Stopped: {ITEM} needs you."]
    problem, next_step = _refusal(failed)
    assert problem.startswith("The worker stopped with exit code 3; its log is ")
    assert next_step == f"Next: forge work {ITEM}"
    monkeypatch.delenv("STUB_CLAUDE_EXIT")
    again = _land(env)
    assert again.returncode == 0, again.stderr
    assert _steps(again)[:2] == [f"Building {ITEM}.", f"Closing {ITEM}."]
    assert len(_workers(env)) == 2


def _merged_while_close_looks(env):
    _agent(env)
    _fix(env, "working", worked=True)
    opened = json.dumps([{"number": 7, "state": "OPEN", "body": "", "isDraft": False}])
    _queue(env, ["pr", "list", "--head"], opened, opened.replace("OPEN", "MERGED"))
    done = _land(env)
    assert done.returncode == 0, done.stderr
    assert f"The pull request for {ITEM} is merged." in done.stdout
    assert "is ready;" not in done.stdout
    assert not env.gh_calls("pr", "merge")


def _merged_after_close_returned(env):
    # Open when land and close look, merged by the time close returns Ready: land closes again,
    # so close's own merged path reports it, and with a human merging there is nothing to hand off.
    _fix(env, "working", worked=True)
    opened = json.dumps([{"number": 7, "state": "OPEN", "body": "", "isDraft": False}])
    _queue(env, ["pr", "list", "--head"], opened, opened, opened.replace("OPEN", "MERGED"))
    done = _land(env)
    assert done.returncode == 0, done.stderr
    assert _steps(done) == [f"Closing {ITEM}."] * 2
    assert f"Ready: {ITEM} has a clean review" in done.stdout
    assert done.stdout.rstrip().endswith(f"The pull request for {ITEM} is merged.")
    assert not env.gh_calls("pr", "merge")


def _no_checks_named(env):
    where = _fix(env, "working", worked=True)
    env.commit(where, "forge.toml", (where / "forge.toml").read_text("utf-8").replace(
        'checks = ["tests", "forge-pr-check"]', "checks = []"))
    done = _land(env)
    assert done.returncode == 1
    assert _steps(done) == [f"Closing {ITEM}.", f"Stopped: {ITEM} needs you."]
    assert _refusal(done) == ["forge.toml names no checks for close to wait for.", "Next: forge doctor"]


def _unsynced_upgrade(env):
    where = _fix(env, "working", worked=True)
    env.commit(where, "forge.toml", re.sub(r'version = "[^"]*"', 'version = "v9.9.9"',
                                           (where / "forge.toml").read_text("utf-8")))
    done = _land(env)
    assert done.returncode == 1
    assert _steps(done) == [f"Closing {ITEM}.", f"Stopped: {ITEM} needs you."]
    problem, next_step = _refusal(done)
    assert problem.startswith("This fix pins Forge v9.9.9, but Forge v")
    assert next_step.endswith(f"@v9.9.9, then forge close {ITEM}")


def _already_merged(env):
    _agent(env)
    _fix(env)
    _queue(env, ["pr", "list", "--head"], json.dumps([{"number": 7, "state": "MERGED", "body": ""}]))
    done = _land(env)
    assert done.returncode == 0, done.stderr
    assert f"The pull request for {ITEM} is merged." in done.stdout
    assert not _workers(env)
    assert not env.gh_calls("pr", "merge")


def _story_key_and_malformed_item_refused(env):
    head = env.repo.git("rev-parse", "HEAD")
    for item in ("SHOP", "Not an item!"):
        done = _land(env, item)
        assert done.returncode == 1
        assert _refusal(done) == [f"{item!r} is not a story key, a KEY/TASK task or a fix name.",
                                  "Next: forge next"]
        assert not done.stdout
    assert env.repo.git("rev-parse", "HEAD") == head and not env.repo.git("status", "--porcelain")


def _merge_switch_refused(env):
    done = _land(env, "let-the-agent-merge")
    assert done.returncode == 1
    assert _refusal(done) == [
        "let-the-agent-merge changes the merge setting in forge.toml, so only the repo owner merges "
        "its pull request.", "Next: the repo owner merges its pull request, then forge next"]
    assert not env.gh.calls()


def _merge_conflict(env):
    _fix(env, "working", worked=True, changes={"README.md": "# Hello, shoppers\n"})
    env.commit(env.repo.path, "README.md", "# Welcome\n")
    env.repo.git("push", "-q", "origin", "main")
    done = _land(env)
    assert done.returncode == 1
    assert _steps(done) == [f"Closing {ITEM}.", f"Stopped: {ITEM} needs you."]
    assert _refusal(done)[0] == "Merging main into fix/tidy-readme conflicts in README.md."
    assert not _workers(env)


ONE = [_unbuilt_fix_built_once_then_merged, _working_fix_closes_without_a_worker,
       _failed_worker_stops_then_builds_again, _merged_while_close_looks,
       _merged_after_close_returned, _no_checks_named,
       _unsynced_upgrade, _already_merged, _story_key_and_malformed_item_refused,
       _merge_switch_refused, _merge_conflict, "story-done", "migrate"]


@pytest.mark.parametrize("case", ONE, ids=lambda case: case if isinstance(case, str) else case.__name__.strip("_"))
def test_1_one_command_builds_closes_and_waits(land, monkeypatch, case):
    if isinstance(case, str):
        _made_by_forge_closes_without_a_worker(land, case)
    elif case is _failed_worker_stops_then_builds_again:
        case(land, monkeypatch)
    else:
        case(land)


# --- 2: fix rounds ------------------------------------------------------------------------

BLOCKER = finding("P1", "Saving drops the greeting")
FINDINGS_ROUND = "the review's serious findings"
FAILING = [{"name": "tests", "bucket": "fail",
            "link": "https://github.com/acme/shop/actions/runs/5/job/9"}]


def _red_checks(env, bucket: str = "fail") -> None:
    env.gh.respond("pr", "checks", stdout=json.dumps([{**FAILING[0], "bucket": bucket}]), exit=1)
    env.gh.respond("run", "view", "--job", "9", stdout="AssertionError: no greeting in README\n")


def _blocked_once_then_clean(env):
    _agent(env)
    _fix(env, "working", worked=True)
    env.reviews(blocked(BLOCKER), CLEAN)
    done = _land(env)
    assert done.returncode == 0, done.stderr
    assert _steps(done) == [f"Closing {ITEM}.", f"Fix round 1 of 3: the worker fixes {FINDINGS_ROUND}.",
                            f"Closing {ITEM}.", f"Merging {ITEM}."]
    [worker] = _workers(env)
    assert "Saving drops the greeting" in worker["brief"]


def _three_blocked_reviews_hold_the_fourth(env):
    # Previously land exhausted its fix budget after a fourth blocked review;
    # now close's any-file hold stops that review before Autoreview runs.
    where = _fix(env, "working", worked=True)
    env.reviews(blocked(BLOCKER))
    done = _land(env)
    assert done.returncode == 1
    rounds = [f"Fix round {n} of 3: the worker fixes {FINDINGS_ROUND}." for n in (1, 2, 3)]
    assert _steps(done) == [step for n in rounds for step in (f"Closing {ITEM}.", n)] + [
        f"Closing {ITEM}.", f"Stopped: {ITEM} needs you."]
    assert _refusal(done) == [
        f"Review round 4 of {ITEM} still finds serious problems in app.py, which an earlier "
        "round flagged too, so Forge stops sending the worker back. Ask the human "
        "to narrow the part, split it, or accept the remaining findings.",
        f'Next: forge close {ITEM} --resolve <narrow|split|accept> --reason "<human\'s choice>"']
    assert len(_workers(env)) == 3
    assert len(env.review_calls()) == 3
    assert not env.gh_calls("pr", "merge")
    record = json.loads((where / f".factory/fixes/{ITEM}.json").read_text("utf-8"))
    assert record["review"]["dismissals"] == []


def _red_check_gives_a_fix_round(env):
    _agent(env)
    _fix(env, "working", worked=True)
    _queue(env, RUNS, *_runs([run("tests", "failure"), run("forge-pr-check")], GREEN))
    _red_checks(env)
    done = _land(env)
    assert done.returncode == 0, done.stderr
    assert _steps(done) == [f"Closing {ITEM}.", "Fix round 1 of 3: the worker fixes the failing checks.",
                            f"Closing {ITEM}.", f"Merging {ITEM}."]
    [worker] = _workers(env)
    assert "### tests" in worker["brief"] and "no greeting in README" in worker["brief"]


def _red_without_a_failing_check_stops(env, conclusion, bucket):
    _fix(env, "working", worked=True)
    env.checks([run("tests", conclusion), run("forge-pr-check")])
    _red_checks(env, bucket)
    done = _land(env)
    assert done.returncode == 1
    assert _steps(done) == [f"Closing {ITEM}.", f"Stopped: {ITEM} needs you."]
    assert _refusal(done) == ["Checks failed on the pull request: tests.", f"Next: forge work {ITEM}"]
    assert not _workers(env) and not env.gh_calls("run", "rerun")


def _blocked_red_blocked_red(env):
    _fix(env, "working", worked=True)
    env.reviews(blocked(BLOCKER), CLEAN, blocked(BLOCKER), CLEAN)
    env.checks([run("tests", "failure"), run("forge-pr-check")])
    _red_checks(env)
    done = _land(env)
    assert done.returncode == 1
    whats = [FINDINGS_ROUND, "the failing checks", FINDINGS_ROUND]
    assert _steps(done) == [step for n, what in enumerate(whats, 1) for step in (
        f"Closing {ITEM}.", f"Fix round {n} of 3: the worker fixes {what}.")] + [
        f"Closing {ITEM}.", f"Stopped after 3 fix rounds: {ITEM} still has the failing checks."]
    assert _refusal(done) == ["Checks failed on the pull request: tests.", f"Next: forge work {ITEM}"]


def _dismissed_before_land(env):
    _agent(env)
    where = _fix(env, "working", worked=True)
    env.reviews(blocked(BLOCKER))
    assert env.close(ITEM).returncode == 1
    dismissed = env.close(ITEM, "--dismiss", "1", "--because", "app.py:1 it greets here")
    assert dismissed.returncode == 0, dismissed.stderr
    env.commit(where, "notes.md", "More\n", "Worker round")
    done = _land(env)
    assert done.returncode == 0, done.stderr
    assert _steps(done) == [f"Closing {ITEM}.", f"Merging {ITEM}."]
    assert not _workers(env)
    record = json.loads(env.repo.git("show", f"origin/main:.factory/fixes/{ITEM}.json"))
    assert [d["because"] for d in record["review"]["dismissals"]] == ["app.py:1 it greets here"]


def _codex_question_stops(repo, monkeypatch, sdk_data, gh):
    _, log = _codex_repo(repo, monkeypatch, sdk_data)
    question = "Question: May I use the existing parser?"
    monkeypatch.setenv("STUB_SAY", "\n\n" + question)
    gh.respond("pr", "list", stdout="[]")
    done = repo.forge("land", "BOARD/PAGE")
    assert done.returncode == 1, done.stdout + done.stderr
    assert [line for line in done.stdout.splitlines() if STEPS.match(line)] == [
        "Building BOARD/PAGE.", "Closing BOARD/PAGE.", "Stopped: BOARD/PAGE needs you."], done.stdout + done.stderr
    assert done.stderr.endswith(f"The worker is waiting for an answer:\n{question}\n"
                                'Next: forge work BOARD/PAGE --note "<answer>"\n')
    assert len(_sent(log, "turn/start")) == 1


TWO = [_blocked_once_then_clean, _three_blocked_reviews_hold_the_fourth, _red_check_gives_a_fix_round,
       ("cancelled", "cancel"), ("skipped", "skipping"), _blocked_red_blocked_red,
       _dismissed_before_land, _codex_question_stops]


@pytest.mark.parametrize("case", TWO, ids=lambda case: "-".join(case) if isinstance(case, tuple)
                         else case.__name__.strip("_"))
def test_2_fix_rounds_stop_after_three(request, monkeypatch, case):
    if case is _codex_question_stops:
        case(request.getfixturevalue("repo"), monkeypatch, request.getfixturevalue("sdk_data"),
             request.getfixturevalue("gh"))
    elif isinstance(case, tuple):
        _red_without_a_failing_check_stops(request.getfixturevalue("land"), *case)
    else:
        case(request.getfixturevalue("land"))


# --- 3: merge or hand off -----------------------------------------------------------------

def _agent_merges_once(env):
    _agent(env)
    _fix(env, "working", worked=True)
    done = _land(env)
    assert done.returncode == 0, done.stderr
    # The stub gh merges only when --match-head-commit is the remote branch's head, as GitHub does.
    [merged] = env.gh_calls("pr", "merge")
    assert "--match-head-commit" in merged
    assert env.repo.git("show", "origin/main:app.py") == "print('hello')"
    assert env.repo.git("ls-remote", "--heads", "origin", BRANCH) == ""


def _human_merges(env):
    _fix(env, "working", worked=True)
    done = _land(env)
    assert done.returncode == 0, done.stderr
    assert _steps(done)[-1] == f"{ITEM} is ready; a human merges its pull request: {URL}"
    assert not env.gh_calls("pr", "merge")


def _prototype_before_signoff_merges(env):
    _agent(env, 'repo = "client"\nstage = "prototype"\n')
    _fix(env, "working", worked=True)
    done = _land(env)
    assert done.returncode == 0, done.stderr
    assert _steps(done)[-1] == f"Merging {ITEM}."
    assert len(env.gh_calls("pr", "merge")) == 1


def _migrate_and_adopt_hand_off(env, kind):
    _agent(env)
    _fix(env, "working", worked=True, kind=kind)
    done = _land(env)
    assert done.returncode == 0, done.stderr
    assert _steps(done)[-1] == f"{ITEM} is ready; a human merges its pull request: {URL}"
    assert not env.gh_calls("pr", "merge")


def _head_moved_after_ready(env):
    _agent(env)
    _fix(env, "working", worked=True)
    (env.repo.bin / "head-moved").write_text("")
    done = _land(env)
    assert done.returncode == 1
    assert _steps(done)[-2:] == [f"Merging {ITEM}.", f"Stopped: {ITEM} needs you."]
    assert _refusal(done) == [f"The pull request's head changed since Forge recorded {ITEM} ready.",
                              f"Next: forge close {ITEM}"]
    assert not env.gh_calls("pr", "merge")


def _remote_branch_kept_then_tidied(env):
    _agent(env)
    where = _fix(env, "working", worked=True)
    hook = env.tmp / "remote.git" / "hooks" / "pre-receive"
    hook.write_text("#!/bin/sh\nwhile read old new ref; do\n"
                    '  [ "$new" = 0000000000000000000000000000000000000000 ] && exit 1\ndone\nexit 0\n')
    hook.chmod(0o755)
    kept = _land(env)
    assert kept.returncode == 1
    assert _refusal(kept) == [f"Forge could not delete the remote branch for {ITEM}.",
                              f"Next: check the branch on GitHub, then forge merge {ITEM}"]
    assert len(env.gh_calls("pr", "merge")) == 1
    hook.unlink()
    tidied = _land(env)
    assert tidied.returncode == 0, tidied.stderr
    assert len(env.gh_calls("pr", "merge")) == 1
    assert not where.exists()


THREE = [_agent_merges_once, _human_merges, _prototype_before_signoff_merges, "migrate", "adopt",
         _head_moved_after_ready, _remote_branch_kept_then_tidied]


@pytest.mark.parametrize("case", THREE, ids=lambda case: case if isinstance(case, str) else case.__name__.strip("_"))
def test_3_merges_only_where_the_agent_may(land, case):
    if isinstance(case, str):
        _migrate_and_adopt_hand_off(land, case)
    else:
        case(land)
