"""Every owner choice is visible first with its own question and elapsed wait.

Test-audit:
1. The contract is that `forge next` places complete pending choice blocks first and pairs each
   block with the wait that began for that reason, including a current worktree's document state.
2. A regression can omit a cold-read stop, sign-off stop or draft confirmation, use a newer
   unrelated event for its duration, or select an older same-name document from another worktree.
3. Existing next tests cover fix stops and story approval/read resolution. They do not cover
   document cold reads, sign-off, spec confirmation or duplicate document notes across worktrees.
   Sign-off must create its own wait through the decision command and retain it across a clone.
   The task case guards slash-separated item names that the fix cases cannot reach.
4. The test uses the real `forge next` command and needs no production seam.
"""
import json
import pytest

from conftest import Repo
from test_board_status_and_times import _records, _fix, client  # noqa: F401
from test_close import env, STORY_DOC  # noqa: F401
from test_proto_signoff import _client, _decision
from test_story import new_story, setup
from test_start_sorts_ideas import _land_setup

STORY = "FIX-OWNER-CHOICES-ON-TIME"


def _note(read_at, read_hash, round_number, finding=""):
    latest = f"## Round {round_number}\n\n{finding or 'No findings.'}\n"
    return ("---\nreader: codex\nread_at: " + read_at + "\nread_hash: " + read_hash
            + f"\nround: {round_number}\npassed: {'no' if finding else 'yes'}\n---\n\n" + latest)


def _wait(item, reason, at, event_id):
    return {"id": event_id, "item": item, "event": "owner wait start", "reason": reason, "at": at}


@pytest.mark.parametrize("folder,slug", [("specs", "invoices"), ("decisions", "0001-invoices")])
def test_7_next_lists_current_document_stop_and_spec_confirmation_with_matching_waits(repo, gh, monkeypatch, folder, slug):
    client = repo
    setup(client)
    monkeypatch.setenv("FORGE_NOW", "2026-10-09T12:00:00+00:00")
    gh.respond("pr", "list", stdout="[]")
    top = client.path
    # An older same-name spec note exists on main. The current story checkout has a newer,
    # stopped read with different wording, which is the choice the owner must answer.
    spec = top / f"docs/{folder}/{slug}.md"
    spec.parent.mkdir(parents=True, exist_ok=True)
    spec.write_text("# Invoices by email\n\n## Why\nClients lose invoices.\n\n## Behaviour\nInvoices arrive.\n",
                    encoding="utf-8")
    old_hash = client.git("hash-object", "--", str(spec))
    (spec.parent / f"{slug}.read.md").write_text(
        _note("2026-10-09T10:00:00+00:00", old_hash, 1,
              "1. Old read issue: The old review is stale.\n   Gain 4, Work 1, Harm 3"), encoding="utf-8")
    _land_setup(client, top, "save-earlier-read")
    where = new_story(client, "SHOP")
    current_hash = client.git("hash-object", "--", f"docs/{folder}/{slug}.md", cwd=where)
    current_notes = where / f"docs/{folder}/{slug}.read.md"
    current_notes.write_text(
        _note("2026-10-09T11:00:00+00:00", current_hash, 2,
              "1. Current read issue: The current review needs the owner's choice.\n   Gain 4, Work 1, Harm 3"),
        encoding="utf-8")
    # A separate spec is ready for confirmation, another pending owner choice.
    confirm = where / "docs/specs/receipts.md"
    confirm.parent.mkdir(parents=True, exist_ok=True)
    confirm.write_text("---\nstatus: draft\n---\n\n# Receipts by email\n\n## Why\nPeople need receipts.\n",
                       encoding="utf-8")
    confirm_hash = client.git("hash-object", "docs/specs/receipts.md", cwd=where)
    (where / "docs/specs/receipts.read.md").write_text(
        _note("2026-10-09T10:00:00+00:00", confirm_hash, 1), encoding="utf-8")

    _records(client, "events.jsonl", [
        _wait(slug, "read", "2026-10-09T11:05:00+00:00", "read-wait"),
        _wait(slug, "merge conflict", "2026-10-09T11:59:00+00:00", "unrelated-wait"),
        _wait("receipts", "confirmation", "2026-10-09T11:46:00+00:00", "confirm-wait"),
    ])
    result = client.forge("next")
    assert result.returncode == 0, result.stdout + result.stderr
    output = result.stdout
    read_block = (
        f"Waited 55 minutes.\nRound 2 of the cold read of {slug} stopped with open notes, so Forge asks the owner. "
        "Ask the human to choose one more round, split or accept before another read, in these words:\n"
        "Invoices by email: Invoices arrive.\nIt still has these problems:\n"
        "| # | Problem, for whom | Gain | Work | Harm | Proposed |\n"
        "|---|---|---|---|---|---|\n"
        "| 1 | Current read issue: The current review needs the owner's choice. | 4 | 1 | 3 | fix this round |\n"
        "One more round, split or accept?\n"
        "- One more round: repair these cases in its Behaviour and Acceptance criteria and run one more round.\n"
        "- Split: move these cases into a new story or fix of their own; this one goes on without them.\n"
        "- Accept: keep these problems as known and mark the read accepted; approving or confirming the doc is still a separate step.")
    assert read_block in output, output
    assert "Old read issue" not in output
    confirmation = (
        "Waited 14 minutes.\nReceipts by email is ready for confirmation.\nConfirm this spec?\n"
        'Next: cd ')
    assert confirmation in output
    assert where.as_posix() in output.replace("\\", "/")
    assert '&& forge spec confirm receipts --by "<name>"' in output
    assert output.index("Waited 55 minutes.\nRound 2 of the cold read") < output.index("Step ")
    assert output.index("Waited 14 minutes.\nReceipts by email") < output.index("Step ")
    # Without a wait event, the same active checkout's read time is the fallback.
    # The older notes on main say two hours, while the current read says one hour.
    _records(client, "events.jsonl", [_wait("receipts", "confirmation", "2026-10-09T11:46:00+00:00", "confirm-wait")])
    fallback = client.forge("next")
    assert fallback.returncode == 0, fallback.stderr
    assert f"Waited 1 hour.\nRound 2 of the cold read of {slug}" in fallback.stdout


def test_8_next_lists_signoff_question_with_its_reason_wait(repo, tmp_path, monkeypatch, gh):
    monkeypatch.setenv("FORGE_NOW", "2026-10-09T11:00:00+00:00")
    fix, answers, queue = _client(repo, tmp_path, monkeypatch)
    proposal = _decision(fix, answers)
    repo.git("add", proposal.relative_to(fix).as_posix(), cwd=fix)
    repo.git("commit", "-qm", "Record proposed sign-off", cwd=fix)
    report = {"report": {"review_status": "findings", "findings": [{
        "title": "Sign-off leaves a gap", "priority": "P1",
        "body": "Gain 5, Work 2, Harm 4\nCase: normal use - The prototype misses an answer.",
        "code_location": {"file_path": "app.py", "line": 1}}]}}
    for at in ("11:00:00", "11:46:00", "11:59:00"):
        monkeypatch.setenv("FORGE_NOW", f"2026-10-09T{at}+00:00")
        queue.write_text(json.dumps([report]), encoding="utf-8")
        stopped = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
        assert stopped.returncode == 1, stopped.stdout + stopped.stderr
    assert "One more round, split or accept?" in stopped.stderr
    # Only committed data crosses to this machine. No event history or fabricated wait does.
    peer = tmp_path / "second-machine"
    branch = repo.git("branch", "--show-current", cwd=fix)
    repo.git("push", "-q", "origin", "HEAD", cwd=fix)
    repo.git("clone", "--no-local", "-q", "-b", branch,
             repo.git("remote", "get-url", "origin", cwd=fix), str(peer))
    client = Repo(peer, repo.bin)
    gh.respond("pr", "list", stdout="[]")
    gh.respond("api", "graphql", stdout=json.dumps({"data": {"repository": {"pullRequests": {"nodes": []}}}}))
    monkeypatch.setenv("FORGE_NOW", "2026-10-09T12:00:00+00:00")
    result = client.forge("next")
    assert result.returncode == 0, result.stdout + result.stderr
    block = (
        "Waited 14 minutes.\nClient sign-off needs your choice.\n"
        "Ask the human to choose one more round, split or accept the remaining findings, in these words:\n"
        "Client sign-off: The prototype matches the client's answers\nIt still has these problems:\n"
        "| # | Problem, for whom | Gain | Work | Harm | Proposed |\n|---|---|---|---|---|---|\n"
        "| 1 | Sign-off leaves a gap: case: normal use - The prototype misses an answer. | 5 | 2 | 4 | fix now |\n"
        "One more round, split or accept?\n"
        "- One more round: repair these cases in its Done when and run one more round.\n"
        "- Split: move these cases into a new story or fix of their own; this one goes on without them.\n"
        "- Accept: the findings stay in the item's Known issues with your reason, and sign-off continues.")
    assert block in result.stdout, result.stdout
    assert result.stdout.index("Waited 14 minutes.\nClient sign-off needs your choice.") < result.stdout.index("Step ")
    resolved = client.forge("decision", "accept", "client-signoff", "--by", "Ravi",
                            "--resolve", "accept", "--reason", "The owner accepts this limitation")
    assert resolved.returncode == 0, resolved.stdout + resolved.stderr
    shown = client.forge("next")
    assert shown.returncode == 0, shown.stderr
    assert "Client sign-off needs your choice." not in shown.stdout


def test_9_next_shows_a_worker_question_from_the_shared_pull_request(client, gh):
    tree = _fix(client, slug="remote-question")
    client.git("add", ".factory/fixes/remote-question.json", cwd=tree)
    client.git("commit", "-qm", "Record the remote worker", cwd=tree)
    head = client.git("rev-parse", "HEAD", cwd=tree)
    client.git("worktree", "remove", str(tree))
    question = "Question: Can this repair change all six source files?"
    event = {"id": "remote-question-wait", "item": "remote-question", "event": "worker question",
             "at": "2026-10-09T11:05:00+00:00", "question": question}
    opened = {"headRefName": "fix/remote-question", "headRefOid": head, "state": "OPEN", "number": 1,
              "url": "https://github.com/example/client/pull/1", "title": "Repair labels", "isDraft": False,
              "body": "<!-- forge:begin -->\n<!-- forge:time-record " + json.dumps({"events": [event]})
                      + " -->\n<!-- forge:end -->"}
    gh.respond("pr", "list", stdout=json.dumps([opened]))
    gh.respond("pr", "list", "--state", "merged", stdout="[]")
    gh.respond("api", "graphql", stdout=json.dumps({"data": {"repository": {"pullRequests": {"nodes": [opened]}}}}))
    shown = client.forge("next")
    assert shown.returncode == 0, shown.stdout + shown.stderr
    block = ("Waited 55 minutes.\nThe worker on The fix remote-question asked a question. Ask the human:\n"
             + question + '\nNext: forge work remote-question --note "<answer>"')
    assert block in shown.stdout
    assert shown.stdout.index(block) < shown.stdout.index("Step ")


def test_10_next_lists_task_round_limit_with_its_owner_wait(env, monkeypatch):
    item, tree = env.start_approved_task(STORY_DOC)
    path = tree / ".factory/stories/SHOP/tasks/T1.json"
    state = json.loads(path.read_text(encoding="utf-8"))
    state["stop"] = {"round": 2, "at": "2026-10-01T11:00:00+00:00", "wait_id": "task-choice"}
    path.write_text(json.dumps(state), encoding="utf-8")
    _records(env.repo, "events.jsonl", [
        _wait(item, "review loop", "2026-10-09T11:05:00+00:00", "task-choice"),
        _wait(item, "merge conflict", "2026-10-09T11:59:00+00:00", "unrelated"),
    ])
    monkeypatch.setenv("FORGE_NOW", "2026-10-09T12:00:00+00:00")
    shown = env.repo.forge("next")
    assert shown.returncode == 0, shown.stdout + shown.stderr
    block = (
        "Waited 55 minutes.\nClose stopped SHOP/T1: its review reached the round limit with open findings.\n"
        "Ask the human to choose one more round, split or accept the remaining findings, in these words:\n"
        "Save a basket (part of Shoppers can save a basket): Shoppers can save their basket with one click\n"
        "One more round, split or accept?\n"
        "- One more round: repair these cases in its Done when and run one more round.\n"
        "- Split: move these cases into a new story or fix of their own; this one goes on without them.\n"
        "- Accept: the 0 findings listed become follow-ups in Known issues with your reason; close then goes on "
        "to the checks, and merging is still a separate step.")
    assert block in shown.stdout, shown.stdout
    assert shown.stdout.index(block) < shown.stdout.index("Step ")
    assert f'Next: forge close {item} --resolve <more|split|accept> --reason "<human\'s choice>"' in shown.stdout
