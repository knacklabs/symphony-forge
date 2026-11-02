"""Sign-off rounds survive a repair squash and a fresh checkout.

Test audit:
1. Protect the decision command's saved sign-off history, owner stop and settled findings.
2. A repair based on the default branch after its parent was merged can drop later sign-off rounds.
3. Existing sign-off tests stay on one checkout and cannot detect history lost by a squash clone.
4. Real Forge commands and git own the boundary; only external services are replaced.

Replay audit: the earlier manual merge bypassed close's reconstruction of the
repair branch. Main now changes the inherited app while the repair adds its own
file. Real close must keep main's app and the sign-off record before the squash
and clone. Only GitHub, CI and Autoreview responses are replaced at their edges.
"""
import json
import shlex
from pathlib import Path

import pytest

from test_close import Forge, GREEN
from test_proto_signoff import _adopted_client, _client, _decision, _green_full_run, _request_build
from test_signoff_design import _calls

STORY = "sign-off-rounds-settled-findings-and-the"
pytestmark = pytest.mark.platform


def _finding(title, path, scores):
    return {
        "priority": "P1",
        "title": title,
        "body": scores + "\nThe order path has this problem.",
        "code_location": {"file_path": path, "line": 1},
    }


def _report(*findings):
    return {"report": {"review_status": "findings", "findings": list(findings)}}


def _clean():
    return {"report": {"review_status": "scoped-clean", "findings": []}}


def _accept(repo, fix, *args):
    return repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", *args, cwd=fix)


def _squash(repo, branch):
    repo.git("merge", "-q", "--squash", branch, cwd=repo.path)
    repo.git("commit", "-q", "-m", f"Merge {branch}", cwd=repo.path)
    repo.git("push", "-q", "origin", "main", cwd=repo.path)
    repo.git("fetch", "-q", "origin", cwd=repo.path)
    _green_full_run(repo)


def _fresh_repair_checkout(repo, tmp_path, repair_branch):
    clone = tmp_path / "fresh client"
    remote = repo.git("remote", "get-url", "origin", cwd=repo.path)
    repo.git("clone", "-q", remote, str(clone), cwd=repo.path)
    repo.git("switch", "-c", repair_branch, cwd=clone)
    return clone


def _signoff_app_edit(repo, fix):
    (fix / "app.py").write_text("SIGNOFF_APP = True\n\nSTABLE_APP = True\n", encoding="utf-8")
    repo.git("add", "app.py", cwd=fix)
    repo.git("commit", "-qm", "Keep the sign-off app change", cwd=fix)


def _default_app_edit(repo, tmp_path):
    writer = tmp_path / "default app writer"
    remote = repo.git("remote", "get-url", "origin", cwd=repo.path)
    repo.git("clone", "-q", remote, str(writer), cwd=repo.path)
    (writer / "app.py").write_text("DEFAULT_APP = True\n\nSTABLE_APP = True\n", encoding="utf-8")
    repo.git("add", "app.py", cwd=writer)
    repo.git("commit", "-qm", "Change the app on main", cwd=writer)
    repo.git("push", "-q", "origin", "main", cwd=writer)
    repo.git("fetch", "-q", "origin", cwd=repo.path)
    _green_full_run(repo)


def _close_and_squash_repair(repo, gh, tmp_path, queue, repair, repair_branch):
    queue.write_text(json.dumps([_clean()]), encoding="utf-8")
    checks = Forge(repo, gh, tmp_path)
    checks.checks(GREEN)
    gh.respond("pr", "list", stdout="[]")
    gh.respond("pr", "create", stdout="https://github.com/acme/shop/pull/7\n")
    gh.respond("pr", "edit")
    gh.respond("pr", "ready")
    default_head = repo.git("rev-parse", "origin/main", cwd=repair)
    item = repair_branch.removeprefix("fix/")
    closed = repo.forge("close", item, cwd=repair)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    repo.git("merge-base", "--is-ancestor", default_head, "HEAD", cwd=repair)
    assert (repair / "app.py").read_text("utf-8") == "DEFAULT_APP = True\n\nSTABLE_APP = True\n"
    repo.git("merge", "--ff-only", "origin/main", cwd=repo.path)
    _squash(repo, repair_branch)


@pytest.mark.parametrize(
    "setup",
    [
        pytest.param(_client, id="new-working-build"),
        pytest.param(_adopted_client, id="adopted-working-build"),
    ],
)
def test_1_repair_checkout_keeps_rounds_settlements_and_owner_stop(
        repo, gh, tmp_path, monkeypatch, setup):
    if setup is _client:
        fix, answers, queue = _client(repo, tmp_path / "signoff", monkeypatch)
    else:
        fix, answers, queue = _adopted_client(repo, tmp_path / "signoff", monkeypatch)
        _request_build(repo, fix)
        (fix / "app.py").write_text("print('prototype')\n", encoding="utf-8")
        repo.git("add", "app.py", cwd=fix)
        repo.git("commit", "-qm", "Build the adopted order path", cwd=fix)

    checked_file = "app.py"
    page = _decision(fix, answers)
    rel = page.relative_to(fix).as_posix()
    repo.git("add", rel, cwd=fix)
    repo.git("commit", "-qm", "Save the customer's sign-off request", cwd=fix)
    settled = _finding("The optional label is unclear", checked_file, "Gain 5, Work 2, Harm 4")
    open_finding = _finding("Order submission loses the order", checked_file,
                            "Gain 5, Work 2, Harm 4")
    first_round = _report(settled, open_finding)
    second_round = _report(open_finding)
    third_round = _report(settled, open_finding)
    # Canvas-only reviews are gone; only product-review rounds remain.
    reports = [first_round, second_round]
    queue.write_text(json.dumps(reports), encoding="utf-8")

    parent_branch = repo.git("branch", "--show-current", cwd=fix)
    _squash(repo, parent_branch)
    first = _accept(repo, fix)
    assert first.returncode == 1, first.stdout + first.stderr
    assert "Order submission loses the order" in first.stderr

    second = _accept(repo, fix)
    assert second.returncode == 1, second.stdout + second.stderr
    assert "One more round, split or accept?" in second.stderr

    _signoff_app_edit(repo, fix)
    repair_args = shlex.split(next(line.removeprefix("Next: ") for line in first.stderr.splitlines()
                                    if line.startswith("Next: forge fix start ")))
    started = repo.forge(*repair_args[1:], cwd=fix)
    assert started.returncode == 0, started.stdout + started.stderr
    repair = Path(started.stdout.split(" in ", 1)[1].splitlines()[0])
    repair_branch = repo.git("branch", "--show-current", cwd=repair)
    (repair / "docs/order-repair.md").write_text("The order remains available after submission.\n",
                                                  encoding="utf-8")
    repo.git("add", "docs/order-repair.md", cwd=repair)
    repo.git("commit", "-qm", "Repair order submission", cwd=repair)
    _default_app_edit(repo, tmp_path)
    _close_and_squash_repair(repo, gh, tmp_path, queue, repair, repair_branch)

    clone = _fresh_repair_checkout(repo, tmp_path, repair_branch)
    before = len(_calls(queue))
    # Close consumes its own clean report. The product review must receive the
    # third-round findings so Forge filters the settled repeat.
    queue.write_text(json.dumps([third_round]), encoding="utf-8")
    still_stopped = _accept(repo, clone)
    assert still_stopped.returncode == 1, still_stopped.stdout + still_stopped.stderr
    assert "One more round, split or accept?" in still_stopped.stderr
    assert len(_calls(queue)) == before

    more = _accept(repo, clone, "--resolve", "more", "--reason", "The owner wants one more round")
    assert more.returncode == 1, more.stdout + more.stderr
    assert "Order submission loses the order" in more.stderr
    assert "The optional label is unclear" not in more.stderr
    calls = _calls(queue)
    prompt = "\n".join(calls[-1]["prompt_files"].values())
    assert "The optional label is unclear" in prompt
    assert "fixed: absent from a later review" in prompt
    assert f"sign-off checkout: {fix}" in first.stderr


def test_2_adopted_client_with_one_legacy_review_reaches_the_round_two_stop(
        repo, gh, tmp_path, monkeypatch):
    fix, answers, queue = _adopted_client(repo, tmp_path / "signoff", monkeypatch)
    _request_build(repo, fix)
    (fix / "app.py").write_text("print('prototype')\n", encoding="utf-8")
    repo.git("add", "app.py", cwd=fix)
    repo.git("commit", "-qm", "Build the adopted order path", cwd=fix)
    page = _decision(fix, answers)
    rel = page.relative_to(fix).as_posix()
    repo.git("add", rel, cwd=fix)
    repo.git("commit", "-qm", "Save the customer's sign-off request", cwd=fix)
    finding = _finding("Order submission loses the order", "app.py", "Gain 5, Work 2, Harm 4")
    queue.write_text(json.dumps([_report(finding)]), encoding="utf-8")

    first = _accept(repo, fix)
    assert first.returncode == 1, first.stdout + first.stderr
    legacy = fix / ".factory/client-signoff.json"
    record = json.loads(legacy.read_text("utf-8"))
    if "rounds" in record:
        record.pop("rounds")
        legacy.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        repo.git("add", ".factory/client-signoff.json", cwd=fix)
        repo.git("commit", "-qm", "Keep the earlier sign-off record", cwd=fix)

    parent_branch = repo.git("branch", "--show-current", cwd=fix)
    _squash(repo, parent_branch)
    _signoff_app_edit(repo, fix)
    repair_args = shlex.split(next(line.removeprefix("Next: ") for line in first.stderr.splitlines()
                                    if line.startswith("Next: forge fix start ")))
    started = repo.forge(*repair_args[1:], cwd=fix)
    assert started.returncode == 0, started.stdout + started.stderr
    repair = Path(started.stdout.split(" in ", 1)[1].splitlines()[0])
    repair_branch = repo.git("branch", "--show-current", cwd=repair)
    (repair / "docs/order-repair.md").write_text("The order remains available after submission.\n",
                                                  encoding="utf-8")
    repo.git("add", "docs/order-repair.md", cwd=repair)
    repo.git("commit", "-qm", "Repair order submission", cwd=repair)
    _default_app_edit(repo, tmp_path)
    _close_and_squash_repair(repo, gh, tmp_path, queue, repair, repair_branch)

    clone = _fresh_repair_checkout(repo, tmp_path, repair_branch)
    queue.write_text(json.dumps([_report(finding)]), encoding="utf-8")
    second = _accept(repo, clone)
    assert second.returncode == 1, second.stdout + second.stderr
    assert "One more round, split or accept?" in second.stderr
    assert len(_calls(queue)) == 3
    prompt = "\n".join(_calls(queue)[-1]["prompt_files"].values())
    assert "Order submission loses the order" in prompt
    assert f"sign-off checkout: {fix}" in first.stderr
