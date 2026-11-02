"""Sign-off rounds survive a repair squash and a fresh checkout.

Test audit:
1. Protect the decision command's saved sign-off history, owner stop and settled findings.
2. A repair based on the default branch after its parent was merged can drop later sign-off rounds.
3. Existing sign-off tests stay on one checkout and cannot detect history lost by a squash clone.
4. The real Forge commands and git merges exercise the boundary; only Autoreview is replaced.
"""
import json
import shlex
from pathlib import Path

import pytest

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


@pytest.mark.parametrize(
    "setup,canvas",
    [
        pytest.param(_client, False, id="new-working-build"),
        pytest.param(_client, True, id="new-canvas"),
        pytest.param(_adopted_client, False, id="adopted-working-build"),
        pytest.param(_adopted_client, True, id="adopted-canvas"),
    ],
)
def test_1_repair_checkout_keeps_rounds_settlements_and_owner_stop(
        repo, tmp_path, monkeypatch, setup, canvas):
    if setup is _client:
        fix, answers, queue = _client(repo, tmp_path, monkeypatch, working_build=not canvas)
    else:
        fix, answers, queue = _adopted_client(repo, tmp_path, monkeypatch)
        if not canvas:
            _request_build(repo, fix)
            (fix / "app.py").write_text("print('prototype')\n", encoding="utf-8")
            repo.git("add", "app.py", cwd=fix)
            repo.git("commit", "-qm", "Build the adopted order path", cwd=fix)

    checked_file = "docs/design/prototype/SCREENS.md" if canvas else "app.py"
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
    reports = ([first_round, second_round, third_round] if canvas else
               [_clean(), first_round, second_round])
    queue.write_text(json.dumps(reports), encoding="utf-8")

    parent_branch = repo.git("branch", "--show-current", cwd=fix)
    _squash(repo, parent_branch)
    first = _accept(repo, fix)
    assert first.returncode == 1, first.stdout + first.stderr
    assert "Order submission loses the order" in first.stderr

    second = _accept(repo, fix)
    assert second.returncode == 1, second.stdout + second.stderr
    assert "One more round, split or accept?" in second.stderr

    repair_args = shlex.split(next(line.removeprefix("Next: ") for line in first.stderr.splitlines()
                                    if line.startswith("Next: forge fix start ")))
    started = repo.forge(*repair_args[1:], cwd=fix)
    assert started.returncode == 0, started.stdout + started.stderr
    repair = Path(started.stdout.split(" in ", 1)[1].splitlines()[0])
    repair_branch = repo.git("branch", "--show-current", cwd=repair)
    changed = repair / checked_file
    changed.write_text(changed.read_text("utf-8") + "\nThe order remains available after submission.\n",
                       encoding="utf-8")
    repo.git("add", checked_file, cwd=repair)
    repo.git("commit", "-qm", "Repair order submission", cwd=repair)
    # Work merges the default branch before repair. Keep the repair's newer
    # sign-off record and app edits when the earlier squash added the same file.
    repo.git("merge", "-q", "--no-edit", "-X", "ours", "origin/main", cwd=repair)
    _squash(repo, repair_branch)

    clone = _fresh_repair_checkout(repo, tmp_path, repair_branch)
    before = len(_calls(queue))
    if not canvas:
        queue.write_text(json.dumps([_clean(), third_round]), encoding="utf-8")
    still_stopped = _accept(repo, clone)
    assert still_stopped.returncode == 1, still_stopped.stdout + still_stopped.stderr
    assert "One more round, split or accept?" in still_stopped.stderr
    assert len(_calls(queue)) == before + (not canvas)

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
        repo, tmp_path, monkeypatch):
    fix, answers, queue = _adopted_client(repo, tmp_path, monkeypatch)
    _request_build(repo, fix)
    (fix / "app.py").write_text("print('prototype')\n", encoding="utf-8")
    repo.git("add", "app.py", cwd=fix)
    repo.git("commit", "-qm", "Build the adopted order path", cwd=fix)
    page = _decision(fix, answers)
    rel = page.relative_to(fix).as_posix()
    repo.git("add", rel, cwd=fix)
    repo.git("commit", "-qm", "Save the customer's sign-off request", cwd=fix)
    finding = _finding("Order submission loses the order", "app.py", "Gain 5, Work 2, Harm 4")
    queue.write_text(json.dumps([_clean(), _report(finding)]), encoding="utf-8")

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
    repair_args = shlex.split(next(line.removeprefix("Next: ") for line in first.stderr.splitlines()
                                    if line.startswith("Next: forge fix start ")))
    started = repo.forge(*repair_args[1:], cwd=fix)
    assert started.returncode == 0, started.stdout + started.stderr
    repair = Path(started.stdout.split(" in ", 1)[1].splitlines()[0])
    repair_branch = repo.git("branch", "--show-current", cwd=repair)
    changed = repair / "app.py"
    changed.write_text(changed.read_text("utf-8") + "\nprint('order retained')\n", encoding="utf-8")
    repo.git("add", "app.py", cwd=repair)
    repo.git("commit", "-qm", "Repair order submission", cwd=repair)
    repo.git("merge", "-q", "--no-edit", "-X", "ours", "origin/main", cwd=repair)
    _squash(repo, repair_branch)

    clone = _fresh_repair_checkout(repo, tmp_path, repair_branch)
    queue.write_text(json.dumps([_clean(), _report(finding)]), encoding="utf-8")
    second = _accept(repo, clone)
    assert second.returncode == 1, second.stdout + second.stderr
    assert "One more round, split or accept?" in second.stderr
    assert len(_calls(queue)) == 4
    prompt = "\n".join(_calls(queue)[-1]["prompt_files"].values())
    assert "Order submission loses the order" in prompt
    assert f"sign-off checkout: {fix}" in first.stderr
