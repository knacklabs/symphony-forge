"""The spotted list: forge close records what workers and reviews noticed outside the change in
one shared file, git merges it by Forge's rule, and every worker brief asks for it.

Each test is named test_<n>_<rule> after the Done-when item of STORY it proves.
"""
from __future__ import annotations

import json
import shlex
import subprocess

import pytest

from test_close import CLEAN, blocked, env, finding  # noqa: F401 (env is a fixture)
from test_codex_worker import _codex_repo, _sent, sdk_data  # noqa: F401 (sdk_data is a fixture)
from test_task import story
from test_worker import calls, install_claude

STORY = "FORGE-SPOTTED-1"
LIST = "plans/spotted.json"
FIX = "tidy-readme"
PARAGRAPH = ("Note anything you spot outside your item instead of fixing it: end a commit "
             "message's body with one line each, `Spotted: <bug|simplify|edge|improve> "
             "<path>:<line> <one plain sentence>`. Never widen this change for one, and never edit "
             "`plans/spotted.json`; Forge keeps it. The one exception is a bug that stops your item "
             "from working: fix it and name it in your handoff.")


def entry(kind: str, path: str, line: int, text: str, source: str, item: str = FIX,
          status: str = "open", closed_by: str | None = None) -> dict:
    key = "\t".join([kind, path, text] + ([item] if source == "blocking" else []))
    return {"key": key, "kind": kind, "path": path, "line": line, "text": text, "from": source,
            "item": item, "status": status, "closed_by": closed_by}


def listed(where) -> list[dict]:
    return json.loads((where / LIST).read_text("utf-8"))["items"]


def note(env, where, message: str) -> None:
    """A worker's empty commit whose message is kept byte for byte, CR endings included."""
    env.repo.git("commit", "-q", "--allow-empty", "--cleanup=verbatim", "-m", message, cwd=where)


def subjects(env, where, *paths: str) -> list[str]:
    return env.repo.git("log", "--format=%s", "HEAD", "--", *paths, cwd=where).splitlines()


def _close_records_the_workers_spotted_lines(env):
    item, where = env.start_fix({"app.py": "print('hello')\n", "lib/cart.py": "cart = []\n",
                                 "my file.py": "x = 1\n"})
    note(env, where, "Work\n\nSpotted: bug app.py:3 Totals  skip   refunds.\r\n"
                     "Spotted: simplify .\\lib\\cart.py:12 The cart rebuilds its index twice.\n"
                     "Spotted: typo app.py:1 An unknown kind.\n"
                     "Spotted: bug app.py A line without a number.\n"
                     "Spotted: bug gone.py:1 A file that isn't in the tree.\n"
                     "Spotted: bug my file.py:1 A path with a space.\n")

    closed = env.close(item)

    assert closed.returncode == 0, closed.stderr
    assert listed(where) == [
        entry("bug", "app.py", 3, "Totals skip refunds.", "worker"),
        entry("simplify", "lib/cart.py", 12, "The cart rebuilds its index twice.", "worker")]
    assert (where / LIST).read_bytes().endswith(b"}\n") and b"\r" not in (where / LIST).read_bytes()
    # Only close's review commit wrote it.
    assert subjects(env, where, LIST) == [f"Review of {item}: clean"]


def _close_records_the_reviews_findings_and_dismissals(env):
    env.reviews(blocked(
        finding("P2", "Simpler: merge the two loops", line=2),
        finding("P3", "Simpler (existing): drop the wrapper", line=3),
        finding("P2", "Empty basket crashes totals", line=4),
        finding("P3", "Name the tax constant", line=5),
        finding("P2", "Later: cache prices", line=6),
        finding("P1", "Saving drops the basket", line=7),
        finding("P1", "Simpler: one save path", line=8)))
    item, where = env.start_fix()

    refused = env.close(item)

    assert refused.returncode == 1 and "serious findings" in refused.stderr
    wanted = [entry("simplify", "app.py", 2, "Simpler: merge the two loops", "review"),
              entry("simplify", "app.py", 3, "Simpler (existing): drop the wrapper", "review"),
              entry("edge", "app.py", 4, "Empty basket crashes totals", "review"),
              entry("improve", "app.py", 5, "Name the tax constant", "review"),
              entry("bug", "app.py", 7, "Saving drops the basket", "blocking"),
              entry("simplify", "app.py", 8, "Simpler: one save path", "blocking")]
    assert listed(where) == sorted(wanted, key=lambda e: e["key"])
    assert subjects(env, where, LIST) == [f"Review of {item}: blocked"]

    # Dismissing a blocking finding closes its entry.
    env.close(item, "--dismiss", "6", "--because", "app.py:1 saving keeps the basket")
    wanted[4] = entry("bug", "app.py", 7, "Saving drops the basket", "blocking",
                      status="done", closed_by="dismissed")
    assert listed(where) == sorted(wanted, key=lambda e: e["key"])
    assert len(env.review_calls()) == 1


def _each_problem_is_kept_once(env):
    item, where = env.start_fix()
    line = "Spotted: edge app.py:1 Empty basket crashes totals"
    note(env, where, f"One\n\n{line}\n")
    note(env, where, f"Two\n\n{line}\n")
    env.reviews(blocked(finding("P2", "Empty basket crashes totals", line=9)))
    assert env.close(item).returncode == 0
    # A second close after new work reviews again and adds nothing new.
    env.commit(where, "app.py", "print('hi')\n")
    assert env.close(item).returncode == 0
    assert len(env.review_calls()) == 2
    assert listed(where) == [entry("edge", "app.py", 1, "Empty basket crashes totals", "worker")]


def _a_serious_finding_counts_once_per_change(env):
    env.reviews(blocked(finding("P1", "Saving drops the basket")))
    first, _ = env.start_fix()
    assert env.close(first).returncode == 1
    env.repo.git("merge", "-q", "--no-edit", "fix/tidy-readme")
    env.repo.git("push", "-q", "origin", "main")
    second, there = env.start("save-fix", "fix/save-fix", ".factory/fixes/save-fix.json",
                              {"kind": "fix", "why": "Saving works", "done_when": "It saves"},
                              {"app.py": "print('save')\n"})
    assert env.close(second).returncode == 1
    assert listed(there) == [entry("bug", "app.py", 1, "Saving drops the basket", "blocking",
                                   item=second),
                             entry("bug", "app.py", 1, "Saving drops the basket", "blocking")]


def _a_reused_review_still_records_new_lines(env):
    item, where = env.start_fix()
    assert env.close(item).returncode == 0
    assert not (where / LIST).exists()  # nothing spotted: no file
    assert env.repo.git("show", "--name-only", "--format=", "HEAD", cwd=where) == (
        ".factory/fixes/tidy-readme.json")
    note(env, where, "Notes\n\nSpotted: improve app.py:1 The greeting is hard-coded.\n")

    assert env.close(item).returncode == 0
    assert len(env.review_calls()) == 1
    assert subjects(env, where)[0] == f"Review of {item}: clean"
    assert listed(where) == [entry("improve", "app.py", 1, "The greeting is hard-coded.", "worker")]
    head = env.repo.git("rev-parse", "HEAD", cwd=where)
    assert env.close(item).returncode == 0
    assert env.repo.git("rev-parse", "HEAD", cwd=where) == head


def _naming_the_list_in_done_when_never_makes_the_review_stale(env):
    item, where = env.start_fix(done_when="plans/spotted.json lists what workers spot")
    assert env.close(item).returncode == 0
    note(env, where, "Notes\n\nSpotted: improve app.py:1 The greeting is hard-coded.\n")
    assert env.close(item).returncode == 0
    assert env.close(item).returncode == 0
    assert len(env.review_calls()) == 1


def _not_json(env):
    _an_unreadable_list_is_refused_with_its_repair(env, "not json\n", "it isn't JSON")


def _an_entry_without_its_item(env):
    _an_unreadable_list_is_refused_with_its_repair(
        env, json.dumps({"items": [{k: v for k, v in entry("bug", "app.py", 1, "x", "worker").items()
                                    if k != "item"}]}),
        "entry 1 doesn't have exactly the fields key, kind, path, line, text, from, item, status, "
        "closed_by")


def _refused(env, item, where) -> tuple[str, str]:
    refused = env.close(item)
    assert refused.returncode == 1 and not env.review_calls()
    problem, _, next_line = refused.stderr.strip().partition("\nNext: ")
    assert next_line.endswith(f", commit it, then forge close {item}")
    return problem, next_line.removesuffix(f", commit it, then forge close {item}")


def _an_unreadable_list_is_refused_with_its_repair(env, text, problem):
    item, where = env.start_fix()
    env.commit(where, LIST, text, "Edit the list by hand")
    said, repair = _refused(env, item, where)
    assert said == f"plans/spotted.json isn't a list Forge can read: {problem}."
    # No readable copy was ever committed, so the repair removes the file.
    assert repair == f"git -C {where} rm -q {LIST}"
    subprocess.run(shlex.split(repair), check=True)
    env.repo.git("commit", "-q", "-m", "Repair the list", cwd=where)
    assert env.close(item).returncode == 0 and len(env.review_calls()) == 1


def _the_repair_restores_the_last_readable_copy(env):
    env.reviews(blocked(finding("P3", "Name the tax constant")), CLEAN)
    item, where = env.start_fix()
    assert env.close(item).returncode == 0
    env.commit(where, "app.py", "print('hi')\n")
    assert env.close(item).returncode == 0  # round 2 no longer raises it; the entry stays
    kept = listed(where)
    assert kept == [entry("improve", "app.py", 1, "Name the tax constant", "review")]
    readable = env.repo.git("log", "-1", "--format=%H", "--", LIST, cwd=where)
    env.commit(where, LIST, "{broken", "Edit the list by hand")
    calls_before = len(env.review_calls())

    refused = env.close(item)
    assert refused.returncode == 1 and len(env.review_calls()) == calls_before
    repair = f"git -C {where} checkout {readable} -- {LIST}"
    assert refused.stderr == (f"plans/spotted.json isn't a list Forge can read: it isn't JSON.\n"
                              f"Next: {repair}, commit it, then forge close {item}\n")
    subprocess.run(shlex.split(repair), check=True)
    env.repo.git("commit", "-q", "-m", "Repair the list", cwd=where)
    assert env.close(item).returncode == 0
    assert listed(where) == kept


# --- the merge rule -------------------------------------------------------------------------

def _git(repo, *args: str) -> subprocess.CompletedProcess[str]:
    # These branches aren't Forge's, so Forge's own commit hook would refuse them.
    return subprocess.run(["git", "-c", "core.hooksPath=no-hooks", *args], cwd=repo.path,
                          capture_output=True, text=True, encoding="utf-8")


def _commit_list(repo, items: list[dict], message: str) -> None:
    repo.write(LIST, json.dumps({"items": items}, indent=2) + "\n")
    assert _git(repo, "add", LIST).returncode == 0
    assert _git(repo, "commit", "-q", "-m", message).returncode == 0


def _merge(repo, ours: str, theirs: str) -> list[dict]:
    repo.git("checkout", "-q", ours)
    merged = _git(repo, "merge", "-q", "--no-edit", theirs)
    assert merged.returncode == 0, merged.stdout + merged.stderr
    assert repo.git("status", "--porcelain") == ""
    return sorted(listed(repo.path), key=lambda e: e["key"])


def _synced(repo, gitattributes: str | None) -> None:
    repo.git("checkout", "-q", "-b", "fix/spotted")
    # The checkout's own version, so this Forge runs sync rather than an older release.
    version = repo.forge("--version").stdout.split()[-1]
    repo.write("forge.toml", f'version = "{version}"\ntest = "echo ok"\n'
                             'checks = ["tests", "forge-pr-check"]\n')
    if gitattributes is not None:
        repo.write(".gitattributes", gitattributes)
    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stderr
    rules = (repo.path / ".gitattributes").read_text("utf-8").splitlines()
    assert rules.count("plans/roadmap.json merge=forge-roadmap") == 1
    assert rules.count("plans/spotted.json merge=forge-roadmap") == 1
    repo.git("add", "-A")
    assert _git(repo, "commit", "-q", "-m", "Synced").returncode == 0


def _sync_adds_the_rule_once(env):
    repo = env.repo
    _synced(repo, "*.png binary\nplans/roadmap.json merge=forge-roadmap\n")
    assert (repo.path / ".gitattributes").read_text("utf-8") == (
        "*.png binary\nplans/roadmap.json merge=forge-roadmap\n"
        "plans/spotted.json merge=forge-roadmap\n")
    again = repo.forge("sync")
    assert again.returncode == 0 and "Wrote .gitattributes" not in again.stdout


def _git_merges_the_list_by_forges_rule(env):
    repo = env.repo
    _synced(repo, None)
    a, b, c, d = (entry("bug", "app.py", n, text, "worker") for n, text in
                  enumerate(["A one", "B two", "C three", "D four"], 1))
    # Both branches create the file.
    repo.git("branch", "makes-b")
    repo.git("checkout", "-q", "-b", "makes-a")
    _commit_list(repo, [a, c], "A and C")
    repo.git("checkout", "-q", "makes-b")
    _commit_list(repo, [b, d], "B and D")
    assert _merge(repo, "makes-a", "makes-b") == [a, b, c, d]

    # Both branches add entries whose keys interleave with the ones they share.
    repo.git("checkout", "-q", "-b", "base", "fix/spotted")
    _commit_list(repo, [a, c], "Base")
    repo.git("branch", "adds-b")
    repo.git("checkout", "-q", "-b", "adds-a")
    _commit_list(repo, [a, b, c], "Add B")
    repo.git("checkout", "-q", "adds-b")
    _commit_list(repo, [a, c, d], "Add D")
    assert _merge(repo, "adds-a", "adds-b") == [a, b, c, d]

    # Open on one side, done on the other: done wins whichever side git calls ours.
    done = {**a, "status": "done", "closed_by": "fix-totals"}
    repo.git("checkout", "-q", "-b", "keeps", "base")
    _commit_list(repo, [a, c, d], "Add D again")
    repo.git("checkout", "-q", "-b", "closes", "base")
    _commit_list(repo, [done, c], "Close A")
    repo.git("branch", "closes-again")
    assert _merge(repo, "keeps", "closes") == [done, c, d]
    assert _merge(repo, "closes-again", "keeps") == [done, c, d]


@pytest.mark.parametrize("case", [
    _close_records_the_workers_spotted_lines, _close_records_the_reviews_findings_and_dismissals,
    _each_problem_is_kept_once, _a_serious_finding_counts_once_per_change,
    _a_reused_review_still_records_new_lines,
    _naming_the_list_in_done_when_never_makes_the_review_stale, _not_json,
    _an_entry_without_its_item, _the_repair_restores_the_last_readable_copy,
    _sync_adds_the_rule_once, _git_merges_the_list_by_forges_rule])
def test_1_close_keeps_one_shared_spotted_list(env, case):
    case(env)


# --- item 2: every worker brief asks for Spotted lines --------------------------------------

def _claude_task(request, repo) -> str:
    log = install_claude(repo)
    version = repo.forge("--version").stdout.split()[-1]
    repo.write("forge.toml", f'version = "{version}"\nrepo = "forge-source"\n'
                             'workers = "claude"\ntest = "pytest -q"\n'
                             'models.build = { model = "sonnet", effort = "medium" }\n')
    repo.git("add", "forge.toml")
    repo.git("commit", "-q", "-m", "Pin Forge")
    repo.git("push", "-q", "origin", "main")
    story(repo)
    assert repo.forge("task", "start", "BOARD/PAGE").returncode == 0
    built = repo.forge("work", "BOARD/PAGE")
    assert built.returncode == 0, built.stderr
    return calls(log)[-1]["brief"]


def _codex_fix(request, repo) -> str:
    monkeypatch = request.getfixturevalue("monkeypatch")
    _, log = _codex_repo(repo, monkeypatch, request.getfixturevalue("sdk_data"))
    started = repo.forge("fix", "start", "Fix the login typo", "--done", "It says Log in")
    assert started.returncode == 0, started.stderr
    built = repo.forge("work", "fix-the-login-typo")
    assert built.returncode == 0, built.stdout + built.stderr
    return _sent(log, "turn/start")[-1]["input"][0]["text"]


@pytest.mark.parametrize("brief", [_claude_task, _codex_fix])
def test_2_every_worker_brief_asks_for_spotted_lines(request, repo, gh, brief):
    # Line breaks in the template don't count; the words must be these, in this order.
    assert PARAGRAPH in " ".join(brief(request, repo).split())
