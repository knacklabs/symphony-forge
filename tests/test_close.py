"""forge close: the close rule for tasks and fixes, the review loop and the check wait.

Each test is named test_<criterion>_<rule> after the spec's acceptance criterion it proves.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
from pathlib import Path

import pytest

import conftest

ROOT = Path(__file__).resolve().parents[1]
PIN = re.search(r'AUTOREVIEW_PIN = "(\w+)"',
                (ROOT / "src" / "forge" / "review.py").read_text("utf-8"))[1]

# The real codex behind the review launcher: records the folder it was started in, and its commit.
CODEX_STUB = '''#!{python}
import json, pathlib, subprocess, sys
args = sys.argv[1:]
folder = args[args.index("-C") + 1]
head = subprocess.run(["git", "-C", folder, "rev-parse", "HEAD"], capture_output=True,
                      text=True).stdout.strip()
log = pathlib.Path(__file__).resolve().parent / "codex-calls.jsonl"
with open(log, "a", encoding="utf-8") as calls:
    calls.write(json.dumps({{"folder": folder, "head": head}}) + "\\n")
'''

STORY_DOC = """# Shoppers can save a basket

## What changes for you
Shoppers can save a basket and come back to it.

## Why
Shoppers lose their basket when they leave.

## Done when
1. A shopper can save a basket.
2. A saved basket comes back after sign-in.

## Tasks
| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing |
|---|---|---|---|---|---|---|---|
| T1 | Save a basket | Shoppers can save their basket with one click | 1 | `app.py` | `tests/test_app.py` | — | no |
| T2 | Show a saved basket | A saved basket shows again after sign-in | 2 | `show.py` | `tests/test_show.py` | T1 | yes |

New moving parts: none

## Risks
Risks: none
"""


def finding(priority: str, title: str, file: str = "app.py", line: int = 1) -> dict:
    # confidence, category and column are fields Forge doesn't use; it must ignore them.
    return {"title": title, "body": f"Evidence for: {title}", "priority": priority,
            "confidence": 0.8, "category": "bug",
            "code_location": {"file_path": file, "line": line, "column": 1}}


def report(*findings: dict, status: str = "") -> dict:
    return {"findings": list(findings),
            "overall_correctness": "patch is incorrect" if findings else "patch is correct",
            "overall_explanation": "Read the diff and its callers.", "overall_confidence": 0.9,
            "review_status": status or ("findings" if findings else "scoped-clean"),
            "usage": {"input_tokens": 1}}


def blocked(*findings: dict) -> dict:
    return {"exit": 1, "report": report(*findings)}


def run(name: str, conclusion: str | None = "success", status: str = "completed") -> dict:
    return {"name": name, "status": status, "conclusion": conclusion,
            "app": {"slug": "github-actions"}}


CLEAN = {"exit": 0, "report": report()}
FAILED = {"exit": 3, "report": None, "say": "codex: the model is unavailable"}
INCOMPLETE = {"exit": 2, "report": report(status="incomplete"),
              "say": "autoreview incomplete: selected scope could not be certified"}
# "lint" and "release" aren't named in forge.toml; a check GitHub skipped (a job that runs only on
# tags) doesn't block unless forge.toml names it.
GREEN = [run("tests"), run("forge-pr-check"), run("lint"), run("release", "skipped")]


class Forge:
    """A repo on Forge with a stub Autoreview and green checks, where tasks and fixes start."""

    def __init__(self, repo: conftest.Repo, gh: conftest.StubGh, tmp: Path):
        self.repo, self.gh, self.tmp = repo, gh, tmp
        self.queue = tmp / "reviews.json"

    def reviews(self, *answers: dict) -> None:
        """The stub Autoreview's answers, in order; the last one repeats."""
        self.queue.write_text(json.dumps(list(answers)), "utf-8")

    def review_calls(self) -> list[dict]:
        log = self.queue.with_suffix(".calls.jsonl")
        return [json.loads(line) for line in log.read_text("utf-8").splitlines()] if log.exists() else []

    def prompt(self) -> str:
        args = self.review_calls()[-1]["args"]
        return args[args.index("--prompt") + 1]

    def codex_calls(self) -> list[dict]:
        return [json.loads(line) for line in
                (self.repo.bin / "codex-calls.jsonl").read_text("utf-8").splitlines()]

    def checks(self, runs: list[dict], statuses: list[dict] | None = None) -> None:
        # gh api --paginate --jq '<field>[]' prints one object per line across every page.
        lines = lambda rows: "".join(json.dumps(row) + "\n" for row in rows)  # noqa: E731
        self.gh.respond("api", "--paginate", "--jq", ".check_runs[]", stdout=lines(runs))
        self.gh.respond("api", "--paginate", "--jq", ".statuses[]", stdout=lines(statuses or []))

    def open_pr(self, body: str, state: str = "OPEN", draft: bool = False) -> None:
        self.gh.respond("pr", "list", "--head", stdout=json.dumps(
            [{"number": 7, "state": state, "body": body, "isDraft": draft}]))

    def gh_calls(self, *prefix: str) -> list[list[str]]:
        return [call for call in self.gh.calls() if call[:len(prefix)] == list(prefix)]

    def commit(self, where: Path, rel: str, text: str, message: str = "More work") -> str:
        (where / rel).parent.mkdir(parents=True, exist_ok=True)
        (where / rel).write_text(text, "utf-8")
        self.repo.git("add", "-A", cwd=where)
        self.repo.git("commit", "-q", "-m", message, cwd=where)
        return self.repo.git("rev-parse", "HEAD", cwd=where)

    def start(self, item: str, branch: str, rel: str, state: dict,
              changes: dict[str, str]) -> tuple[str, Path]:
        """What `forge task start` and `forge fix start` (WORK) do, until they land: a branch in its
        own worktree with the item's state, then the worker's commit."""
        where = self.tmp / branch.replace("/", "-")
        self.repo.git("worktree", "add", "-q", "-b", branch, str(where))
        self.commit(where, rel, json.dumps({"branch": branch, "status": "working", **state}), "Start")
        for path, text in changes.items():
            self.commit(where, path, text, "Work")
        return item, where

    def start_fix(self, changes: dict[str, str] | None = None, **state: str) -> tuple[str, Path]:
        lines = {"kind": "fix", "why": "Readme greets new readers",
                 "done_when": "The readme opens with a greeting", **state}
        return self.start("tidy-readme", "fix/tidy-readme", ".factory/fixes/tidy-readme.json",
                          lines, changes or {"app.py": "print('hello')\n"})

    def start_task(self, task: str = "T1", changes: dict[str, str] | None = None,
                   ) -> tuple[str, Path]:
        return self.start(f"SHOP/{task}", f"task/SHOP-{task}",
                          f".factory/stories/SHOP/tasks/{task}.json", {},
                          changes or {"app.py": "print('saved')\n", "other.py": "x = 1\n"})

    def close(self, item: str, *extra: str):
        return self.repo.forge("close", item, *extra)


def body(call: list[str]) -> str:
    """The body a gh call was given (read before the next close rewrites the file)."""
    return Path(call[call.index("--body-file") + 1]).read_text("utf-8")


@pytest.fixture
def env(repo, gh, tmp_path, monkeypatch) -> Forge:
    skill = tmp_path / "autoreview"
    (skill / "scripts").mkdir(parents=True)
    shutil.copy(ROOT / "tests" / "stubs" / "autoreview", skill / "scripts" / "autoreview")
    (skill / ".upstream-sha").write_text(PIN + "\n", "utf-8")
    monkeypatch.setenv("AUTOREVIEW", str(skill / "scripts" / "autoreview"))
    monkeypatch.setenv("AUTOREVIEW_STUB", str(tmp_path / "reviews.json"))
    monkeypatch.setenv("FORGE_CHECKS_WAIT", "0")
    monkeypatch.delenv("CODEX_BIN", raising=False)
    conftest._install(repo.bin, "codex", CODEX_STUB.format(python=sys.executable))
    version = repo.forge("--version").stdout.split()[-1]
    repo.write("forge.toml", f'version = "{version}"\nchecks = ["tests", "forge-pr-check"]\n'
                             'interfaces = ["**/routes/**"]\n'
                             'models.build = { model = "opus", effort = "high" }\n')
    repo.write("plans/SHOP.md", STORY_DOC)
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "Run on Forge")
    repo.git("push", "-q", "origin", "main")
    gh.respond("pr", "list", stdout="[]")
    gh.respond("pr", "create", stdout="https://github.com/acme/shop/pull/7\n")
    gh.respond("pr", "edit")
    gh.respond("pr", "ready")
    forge = Forge(repo, gh, tmp_path)
    forge.reviews(CLEAN)
    forge.checks(GREEN)
    return forge


# --- criterion 2: gates check outcomes, and every refusal names the next command ------------

def _review_fails_twice(env):
    env.reviews(FAILED)
    return {"item": env.start_fix()[0], "reviews": 2,
            "problem": "Autoreview did not finish a review twice in a row: "
                       "codex: the model is unavailable.",
            "next": "forge doctor, then forge close tidy-readme"}


def _review_incomplete_twice(env):
    env.reviews(INCOMPLETE)
    return {"item": env.start_fix()[0], "reviews": 2,
            "problem": "Autoreview did not finish a review twice in a row: "
                       "it reported the review as incomplete.",
            "next": "forge doctor, then forge close tidy-readme"}


def _open_serious_finding(env):
    env.reviews(blocked(finding("P0", "Saving drops the basket", line=2)))
    return {"item": env.start_fix()[0],
            "problem": "The review left serious findings open: finding 1 (Saving drops the basket).",
            "next": 'forge work tidy-readme, or forge close tidy-readme --dismiss <n> '
                    '--because "<file:line> <reason>"'}


def _red_check(env):
    # One matrix variant failed while another still runs: red at once, no waiting.
    env.checks([run("tests (ubuntu-latest)", "failure"),
                run("tests (windows-latest)", None, "in_progress"),
                run("forge-pr-check"), run("lint")])
    return {"draft": True, "item": env.start_fix()[0], "problem": "Checks failed on the pull request: tests.",
            "next": "forge work tidy-readme"}


def _red_check_not_named(env):
    # Every check on the head must be green, not only the ones forge.toml names.
    env.checks([run("tests"), run("forge-pr-check"), run("lint", "failure")],
               [{"context": "ci/deploy-preview", "state": "error"}])
    return {"draft": True, "item": env.start_fix()[0],
            "problem": "Checks failed on the pull request: lint, ci/deploy-preview.",
            "next": "forge work tidy-readme"}


def _skipped_named_check(env):
    # A named check GitHub skipped tested nothing, so it is red.
    env.checks([run("tests", "skipped"), run("forge-pr-check")])
    return {"draft": True, "item": env.start_fix()[0],
            "problem": "Checks failed on the pull request: tests.",
            "next": "forge work tidy-readme"}


def _pending_check_not_named(env):
    env.checks([run("tests"), run("forge-pr-check"), run("lint", None, "queued")])
    return {"draft": True, "item": env.start_fix()[0],
            "problem": "The checks are not green yet: lint is still running.",
            "next": "forge close tidy-readme"}


def _pending_check(env):
    env.checks([run("tests (ubuntu-latest)", None, "in_progress"), run("forge-pr-check")])
    return {"draft": True, "item": env.start_fix()[0],
            "problem": "The checks are not green yet: tests is still running.",
            "next": "forge close tidy-readme"}


def _missing_required_check(env):
    env.checks([run("tests")])
    return {"draft": True, "item": env.start_fix()[0],
            "problem": "The checks are not green yet: forge-pr-check has not reported.",
            "next": "forge close tidy-readme"}


def _github_api_error(env):
    env.gh.respond("api", stdout="HTTP 502: Bad Gateway", exit=1)
    return {"draft": True, "item": env.start_fix()[0],
            "problem": "The checks are not green yet: GitHub did not answer: HTTP 502: Bad Gateway.",
            "next": "forge close tidy-readme"}


def _no_checks_named(env):
    env.commit(env.repo.path, "forge.toml",
               env.repo.path.joinpath("forge.toml").read_text("utf-8").replace(
                   'checks = ["tests", "forge-pr-check"]', "checks = []"))
    return {"item": env.start_fix()[0],
            "problem": "forge.toml names no checks for close to wait for.", "next": "forge doctor"}


def _not_started(env):
    # An earlier fix merged, so its state is on main and in every branch started since; only a
    # worktree on the branch that state names counts as that fix's.
    env.commit(env.repo.path, ".factory/fixes/old-fix.json",
               json.dumps({"branch": "fix/old-fix", "why": "Old", "done_when": "Done"}))
    env.start_fix()
    return {"item": "old-fix",
            "problem": "Forge has not started old-fix in any worktree of this repo.",
            "next": "forge next"}


def _merge_conflict(env):
    item, where = env.start_fix({"README.md": "# Hello, shoppers\n"})
    env.commit(env.repo.path, "README.md", "# Welcome\n")
    env.repo.git("push", "-q", "origin", "main")
    return {"item": item, "clean": where,
            "problem": "Merging main into fix/tidy-readme conflicts in README.md.",
            "next": re.compile(r"Next: git -C .+ merge origin/main, fix the conflicts and commit, "
                               r"then forge close tidy-readme")}


def _bad_dismissal(env):
    env.reviews(blocked(finding("P1", "Not done: The readme opens with a greeting")))
    item = env.start_fix()[0]
    env.close(item)
    return {"item": item, "args": ["--dismiss", "1", "--because", "it is fine"],
            "problem": "Each --dismiss needs a finding number from the latest review and its own "
                       "--because that starts with the file:line proving that finding wrong.",
            "next": 'forge close tidy-readme --dismiss <n> --because "<file:line> <reason>"'}


def _stale_dismissal(env):
    env.reviews(blocked(finding("P1", "Not done: The readme opens with a greeting")))
    item, where = env.start_fix()
    env.close(item)
    env.commit(where, "app.py", "print('hello again')\n")
    return {"item": item, "args": ["--dismiss", "1", "--because", "app.py:1 it greets here"],
            "problem": "The branch changed since the review those finding numbers came from.",
            "next": "forge close tidy-readme"}


def _dismissal_cites_no_such_line(env):
    env.reviews(blocked(finding("P1", "Not done: The readme opens with a greeting")))
    item = env.start_fix()[0]  # app.py has one line
    env.close(item)
    return {"item": item, "args": ["--dismiss", "1", "--because", "app.py:3 it greets here"],
            "problem": "app.py:3 is not a line of the reviewed commit, so it can't prove a "
                       "finding wrong.",
            "next": 'forge close tidy-readme --dismiss <n> --because "<file:line> <reason>"'}


def _dismissal_cites_no_such_file(env):
    env.reviews(blocked(finding("P1", "Not done: The readme opens with a greeting")))
    item = env.start_fix()[0]
    env.close(item)
    return {"item": item, "args": ["--dismiss", "1", "--because", "greet.py:1 it greets here"],
            "problem": "greet.py:1 is not a line of the reviewed commit, so it can't prove a "
                       "finding wrong.",
            "next": 'forge close tidy-readme --dismiss <n> --because "<file:line> <reason>"'}


def _helper_not_pinned(env):
    helper = os.environ["AUTOREVIEW"]
    (Path(helper).parents[1] / ".upstream-sha").write_text("0" * 40, "utf-8")
    return {"item": env.start_fix()[0],
            "problem": f"The Autoreview helper at {helper} is not the pinned version {PIN} "
                       f"(found: {'0' * 40}).",
            "next": "forge doctor"}


def _task_row_missing(env):
    return {"item": env.start_task("T9")[0],
            "problem": "plans/SHOP.md has no usable Tasks row for T9.",
            "next": "fix that row in plans/SHOP.md, then forge close SHOP/T9"}


GATES = [_review_fails_twice, _review_incomplete_twice, _open_serious_finding, _red_check,
         _red_check_not_named, _skipped_named_check, _pending_check_not_named, _pending_check,
         _missing_required_check, _github_api_error, _no_checks_named,
         _not_started, _merge_conflict, _bad_dismissal, _stale_dismissal,
         _dismissal_cites_no_such_line, _dismissal_cites_no_such_file, _helper_not_pinned,
         _task_row_missing]


@pytest.mark.parametrize("case", GATES, ids=lambda case: case.__name__.strip("_"))
def test_2_gates_check_outcomes(env, case):
    want = case(env)
    if want.get("draft"):  # a draft left by an earlier blocked review
        env.open_pr("", draft=True)
    done = env.close(want["item"], *want.get("args", []))
    assert done.returncode == 1, done.stdout + done.stderr
    problem, next_line = done.stderr.splitlines()[-2:]
    assert problem == want["problem"]
    if isinstance(want["next"], re.Pattern):
        assert want["next"].fullmatch(next_line), next_line
    else:
        assert next_line == f"Next: {want['next']}"
    if "reviews" in want:  # a failed or incomplete run is retried once, then close stops
        assert len(env.review_calls()) == want["reviews"]
    if "clean" in want:  # the conflicting merge was undone
        assert env.repo.git("status", "--porcelain", cwd=want["clean"]) == ""
    if want.get("draft"):  # not green: still a draft; green on a retry: ready for review
        assert not env.gh_calls("pr", "ready")
        env.checks(GREEN)
        assert env.close(want["item"]).returncode == 0
        assert env.gh_calls("pr", "ready") == [["pr", "ready", "7"]]
        # gh prints only the JSON fields asked for, so the draft state must be requested.
        listing = env.gh_calls("pr", "list")[-1]
        assert "isDraft" in listing[listing.index("--json") + 1].split(",")


# --- criterion 18: close, for a task and for a fix ----------------------------------------

@pytest.mark.parametrize("kind", ["task", "fix"])
def test_18_close(env, kind):
    toml = env.repo.path / "forge.toml"  # the review kind's model and effort go to Autoreview
    env.commit(env.repo.path, "forge.toml", toml.read_text("utf-8")
               + '\n[models.review]\nmodel = "gpt-6-astra"\neffort = "high"\n')
    item, where = env.start_task() if kind == "task" else env.start_fix()
    branch = "task/SHOP-T1" if kind == "task" else "fix/tidy-readme"
    moved = env.commit(env.repo.path, "NEWS.md", "The shop opens.\n")  # main moves on meanwhile
    env.repo.git("push", "-q", "origin", "main")
    env.reviews(blocked(finding("P1", "Not done: A shopper can save a basket"),
                        finding("P2", "Simpler: drop the cache → a dict")))

    first = env.close(item)

    # The default branch is merged in first, and Autoreview reviews that head, read-only.
    assert first.returncode == 1
    [call] = env.review_calls()
    env.repo.git("merge-base", "--is-ancestor", moved, call["head"])  # raises if main wasn't merged
    options = dict(zip(call["args"][::2], call["args"][1::2]))
    assert {name: options[name] for name in ("--mode", "--base", "--engine", "--max-priority",
                                             "--model", "--thinking")} == {
        "--mode": "branch", "--base": "origin/main", "--engine": "codex", "--max-priority": "P3",
        "--model": "codex=gpt-6-astra", "--thinking": "codex=high"}
    assert "--json-output" in options
    assert [codex["head"] for codex in env.codex_calls()] == [call["head"]]  # it read that tree
    # The instructions: scope and what's outside it, the Done-when items (only covered ones
    # block), the tests with the test-audit rule, and the Simpler rule with New moving parts.
    prompt = options["--prompt"]
    if kind == "task":
        scope, rest = prompt.split("outside that scope")
        outside, rest = rest.split("## Done when")
        covered, context = rest.split("context only")
        assert "- app.py" in scope and "- other.py" in outside and "app.py" not in outside
        assert "- 1. A shopper can save a basket." in covered and "Not done: <the item>" in covered
        assert "- 2. A saved basket comes back after sign-in." in context
        assert "- tests/test_app.py" in context and "New moving parts: none" in prompt
    else:
        for line in ("Why: Readme greets new readers", "Done when: The readme opens with a greeting",
                     "`Not done: The readme opens with a greeting`"):
            assert line in prompt
    assert "## Test audit" in prompt and "`Simpler: <what to cut> → <what replaces it>`" in prompt
    # A serious finding blocks, so the pull request opens as a draft; the advisory one is listed;
    # the result is committed and pushed.
    [create] = env.gh_calls("pr", "create")
    assert create[2] == "--draft" and not env.gh_calls("pr", "ready")
    assert "1. P1 Not done: A shopper can save a basket (app.py:1): blocks the merge" in body(create)
    assert "2. P2 Simpler: drop the cache → a dict (app.py:1): advisory" in body(create)
    assert env.repo.git("status", "--porcelain", cwd=where) == ""
    assert env.repo.git("ls-remote", "origin", branch).split()[0] == env.repo.git(
        "rev-parse", "HEAD", cwd=where)
    env.open_pr(body(create), draft=True)

    # Green checks alone don't promote it: the serious finding still blocks, so it stays a draft.
    env.checks(GREEN)
    blocked_again = env.close(item)
    assert blocked_again.returncode == 1 and not env.gh_calls("pr", "ready")

    # A dismissal cites the line that proves the finding wrong; the committed review still covers
    # the head (only state moved it), so no new round runs, and close waits for green checks.
    second = env.close(item, "--dismiss", "1", "--because", "app.py:1 the basket is saved here")
    assert second.returncode == 0, second.stderr
    assert len(env.review_calls()) == 1
    assert ("1. P1 Not done: A shopper can save a basket (app.py:1): dismissed because app.py:1 "
            "the basket is saved here") in body(env.gh_calls("pr", "edit")[-1])
    assert second.stdout.splitlines()[-1] == (
        f"Ready: {item} has a clean review and green checks. A human merges its pull request.")
    # The checks close waited for are on the pushed head, and nothing was committed after them.
    pushed = env.repo.git("ls-remote", "origin", branch).split()[0]
    assert pushed == env.repo.git("rev-parse", "HEAD", cwd=where)
    assert all(f"/commits/{pushed}/" in call[-1] for call in env.gh_calls("api")[-2:])
    # Right after the checks are green, close marks the draft ready for review.
    assert env.gh.calls()[-3:] == [*env.gh_calls("api")[-2:], ["pr", "ready", "7"]]

    # A new commit needs a new round; the older result and its dismissal no longer count, so the
    # finding blocks again and the ready pull request goes back to a draft.
    env.open_pr(body(env.gh_calls("pr", "edit")[-1]))
    env.commit(where, "app.py", "print('saved twice')\n")
    third = env.close(item)
    assert third.returncode == 1
    rounds = env.review_calls()
    assert len(rounds) == 2 and rounds[1]["head"] != rounds[0]["head"]
    assert "dismissed" not in body(env.gh_calls("pr", "edit")[-1])
    assert env.gh_calls("pr", "ready") == [["pr", "ready", "7"], ["pr", "ready", "7", "--undo"]]

    # A repo that allows no drafts (a private one on GitHub's free plan): the pull request opens,
    # and stays, ready for review, and forge-pr-check still blocks its merge.
    no_drafts = "GraphQL: Draft pull requests are not supported in this repository.\n"
    env.gh.respond("pr", "create", "--draft", stderr=no_drafts, exit=1)
    env.gh.respond("pr", "ready", "7", "--undo", stderr=no_drafts, exit=1)
    env.gh.respond("pr", "list", "--head", stdout="[]")  # no pull request yet
    fourth = env.close(item)
    refused, create = env.gh_calls("pr", "create")[-2:]
    assert refused == [*create[:2], "--draft", *create[2:]]
    env.open_pr(body(create))
    fifth = env.close(item)
    assert env.gh_calls("pr", "ready")[-1] == ["pr", "ready", "7", "--undo"]
    for done in (fourth, fifth):
        assert done.returncode == 1 and (
            "This repo doesn't allow draft pull requests, so the pull request is ready for review; "
            "forge-pr-check still blocks its merge.") in done.stdout.splitlines()
    # Once the story's last part merges, close names `forge story done`: criterion 42's test.


# --- criterion 19: the functional check -----------------------------------------------------

MISSING_CHECK = finding("P1", "Not done: functional check", "show.py")
HOLLOW_CHECK = {**MISSING_CHECK, "body": "The check says only 'it works'; nothing was exercised."}
STALE_CHECK = {**MISSING_CHECK, "body": "The only check is in an older commit's message."}


@pytest.mark.parametrize("task, answer, refused", [
    ("T2", blocked(MISSING_CHECK), True), ("T2", blocked(HOLLOW_CHECK), True),
    ("T2", blocked(STALE_CHECK), True), ("T2", CLEAN, False), ("T1", CLEAN, False)],
    ids=["missing", "hollow", "stale", "user-facing-clean", "not-user-facing"])
def test_19_functional_check(env, task, answer, refused):
    # A user-facing task's review is told to report a missing or hollow functional check as a P1
    # `Not done`; close refuses on that finding and passes once the check is there.
    item, where = env.start_task(task, {"show.py": "print('basket')\n"})
    check = "Functional check: signed in as a shopper and saw the saved basket."
    stale = answer == blocked(STALE_CHECK)
    if task == "T2" and (stale or not refused):  # the worker ends its last commit with its check
        env.commit(where, "show.py", "print('saved basket')\n", f"Show the basket\n\n{check}")
    if stale:  # a later commit has none, so the older check no longer counts
        env.commit(where, "show.py", "print('saved basket twice')\n", "Tidy the basket")
    env.reviews(answer)
    done = env.close(item)
    assert ("`Not done: functional check`" in env.prompt()) is (task == "T2")
    if refused:
        assert done.returncode == 1
        assert done.stderr.splitlines()[-2] == (
            "The review left serious findings open: finding 1 (Not done: functional check).")
        assert "None: the worker's last commit message has no `Functional check:`" in env.prompt()
        [create] = env.gh_calls("pr", "create")
        assert check not in env.prompt() and check not in body(create)
    else:
        assert done.returncode == 0, done.stderr
    if task == "T2" and not refused:
        # Forge reads the check from the commit, hands it to the reviewer and copies it into the
        # pull request's Forge block.
        assert check in env.prompt()
        [create] = env.gh_calls("pr", "create")
        assert f"\n{check}\n<!-- forge:end -->" in body(create)


# --- criterion 27: the pull request's title and summary ----------------------------------------

@pytest.mark.parametrize("kind, title, summary", [
    ("task", "Save a basket", "Shoppers can save their basket with one click"),
    ("fix", "Readme greets new readers", "The readme opens with a greeting")])
def test_27_title_and_summary(env, kind, title, summary):
    item, where = env.start_task() if kind == "task" else env.start_fix()
    env.reviews(CLEAN, blocked(finding("P3", "Simpler (existing): the old loop")))
    assert env.close(item).returncode == 0
    [create] = env.gh_calls("pr", "create")
    assert create[create.index("--title") + 1] == title
    assert "--draft" not in create  # a clean review opens ready for review
    assert body(create).splitlines()[0] == summary

    # Someone adds a line under Forge's block; the next round replaces only the block.
    edited = body(create) + "Checked by hand on the staging shop.\n"
    env.open_pr(edited)
    env.commit(where, "app.py", "print('tidied')\n")
    assert env.close(item).returncode == 0
    [edit] = env.gh_calls("pr", "edit")
    assert "--title" not in edit
    begin, end = "<!-- forge:begin -->", "<!-- forge:end -->"
    assert body(edit).split(begin)[0] == edited.split(begin)[0]
    assert body(edit).split(end)[1] == edited.split(end)[1]
    assert "Simpler (existing): the old loop" in body(edit) and body(edit).count(begin) == 1
