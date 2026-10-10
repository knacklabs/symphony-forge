"""GitHub accepts bounded PR bodies without losing the current review contract.

Audit: the GitHub boundary rejects the submitted body, not a helper's result.
Real closes, a second clone's board and a squash merge own the lifecycle proof.
"""
import json
import re

import pytest

from test_close import CLEAN, STORY_DOC, blocked, env, finding  # noqa: F401
from test_item_time_history import row
from test_last_task_records_story_outcome import github_merge

STORY = "FIX-PULL-REQUEST-BODY-LIMIT"
LIMIT = 65_536


def reject_oversized_bodies(env):
    """GitHub's transport contract applies to create, edit and final merge bodies."""
    gh = env.repo.bin / "gh"
    header, source = gh.read_text("utf-8").split("\n", 1)
    boundary = '''import io, json, pathlib, sys
args = sys.argv[1:]
if args[:1] == ["pr"] and len(args) > 1 and args[1] in ("create", "edit", "merge"):
    text = None
    if "--body-file" in args:
        target = args[args.index("--body-file") + 1]
        text = sys.stdin.read() if target == "-" else pathlib.Path(target).read_text(encoding="utf-8")
        if target == "-":
            sys.stdin = io.StringIO(text)
    elif "--body" in args:
        text = args[args.index("--body") + 1]
    if text is not None:
        with (pathlib.Path(__file__).resolve().parent / "submitted-bodies.jsonl").open("a", encoding="utf-8") as log:
            log.write(json.dumps({"operation": args[1], "body": text}) + "\\n")
        if len(text.encode("utf-8")) > 65536:
            sys.stderr.write("GitHub refused the pull request body: maximum 65536 bytes.\\n")
            sys.exit(1)
'''
    gh.write_text(header + "\n" + boundary + source, "utf-8")


def latest_body(env):
    return json.loads((env.repo.bin / "submitted-bodies.jsonl").read_text("utf-8").splitlines()[-1])["body"]


def publish_snapshot(env, item, text):
    branch = f"task/{item.replace('/', '-')}" if "/" in item else f"fix/{item}"
    head = env.repo.git("ls-remote", "origin", f"refs/heads/{branch}").split()[0]
    env.gh.respond("pr", "list", stdout=json.dumps([{
        "number": 7, "state": "OPEN", "isDraft": True, "body": text,
        "headRefName": branch, "headRefOid": head,
        "title": "Keep the basket", "url": "https://github.com/acme/shop/pull/7"}]))


@pytest.mark.parametrize("oversized", ["contract-and-proof", "diagnostics-and-history", "unicode-owner-text",
                                       "last-part-outcome"])
def test_1_every_pull_request_write_fits_github_and_keeps_current_review_facts(env, oversized):
    config = env.repo.path / "forge.toml"
    env.commit(env.repo.path, "forge.toml", config.read_text("utf-8") + 'merge = "agent"\n')
    env.repo.git("push", "-q", "origin", "main")
    state = {}
    if oversized == "contract-and-proof":
        state["done_when"] = "Basket quantities survive. " + "Detailed basket requirement. " * 4_000
    elif oversized == "unicode-owner-text":
        state["notes"] = "Owner's explanation:\n" + "篮子保持完整。\n" * 12_000
    if oversized == "last-part-outcome":
        doc = "\n".join(line for line in STORY_DOC.splitlines() if not line.startswith("| T2 |"))
        item, where = env.start_approved_task(doc)
    else:
        item, where = env.start_fix(round=1, **state)
    message = "Improve the basket"
    if oversized == "contract-and-proof":
        message += "\n\nProof list:\n- Basket quantities: " + "checked the basket. " * 4_000
        message += "\n\nFunctional check: " + "opened and saved the basket. " * 4_000
    env.commit(where, "app.py", "print('keep basket quantities')\n")
    if oversized == "contract-and-proof":
        # Keep large multiline evidence out of argv, including on Windows.
        message_file = env.tmp / "proof-message.txt"
        message_file.write_text(message, "utf-8")
        env.repo.git("commit", "-q", "--amend", "--file", str(message_file), cwd=where)
    blocker = finding("P1", "Basket quantities disappear")
    diagnostics = []
    if oversized == "diagnostics-and-history":
        diagnostics = [finding("P2", f"Basket diagnostic {n}: " + "Recorded quantity detail. " * 80)
                       for n in range(80)]
        for diagnostic in diagnostics:
            diagnostic["body"] = "Recorded basket diagnostic detail. " * 80
    env.reviews(blocked(blocker, *diagnostics))
    reject_oversized_bodies(env)
    first = env.close(item)
    assert first.returncode == 1, first.stdout + first.stderr
    assert "The review left serious findings open" in first.stderr, first.stderr
    text = latest_body(env)
    assert "Basket quantities disappear" in text
    assert "Done when:" in text
    if oversized != "last-part-outcome":
        assert re.search(r"shorten|omit|trim", re.sub(r"<!--.*?-->", "", text, flags=re.S), re.I)
    if oversized == "contract-and-proof":
        assert "Basket quantities survive" in text
    owner_note = "\n\n## Owner notes\n\nAna will check the basket on Tuesday.\n"
    publish_snapshot(env, item, text + owner_note)
    env.commit(where, "app.py", "print('basket quantities survive')\n")
    env.reviews(CLEAN)
    second = env.close(item)
    assert second.returncode == 0, second.stdout + second.stderr
    text = latest_body(env)
    assert "Ana will check the basket on Tuesday." in text
    publish_snapshot(env, item, text)
    # The retained shared record must remain useful on a machine with no original logs.
    first_machine = env.repo.path
    peer = env.tmp / "body-peer"
    env.repo.git("clone", "-q", env.repo.git("remote", "get-url", "origin"), str(peer))
    env.repo.path = peer
    shared = row(env.repo, item)
    assert shared["stage"] == "ready"
    assert shared["rounds"] and shared["rounds"][-1]["new_findings"] == 0
    env.repo.path = first_machine
    branch = f"task/{item.replace('/', '-')}" if "/" in item else f"fix/{item}"
    github_merge(env, branch)
    gh = env.repo.bin / "gh"
    source = gh.read_text("utf-8")
    gh.write_text(source.replace('"isDraft": False', f'"isDraft": False, "body": {text!r}'), "utf-8")
    reject_oversized_bodies(env)
    # Unicode exceeds the body limit while remaining below Windows' argv limit.
    outcome = "Basket quantities survive. " + "篮" * 23_000
    extra = ("--outcome", outcome) if oversized == "last-part-outcome" else ()
    merged = env.repo.forge("merge", item, *extra)
    assert merged.returncode == 0, merged.stdout + merged.stderr
    submitted = [json.loads(line) for line in
                 (env.repo.bin / "submitted-bodies.jsonl").read_text("utf-8").splitlines()]
    assert {entry["operation"] for entry in submitted} == {"create", "edit", "merge"}
    assert all(len(entry["body"].encode("utf-8")) <= LIMIT for entry in submitted)
    final = env.repo.git("log", "-1", "--format=%B", "origin/main")
    assert "Ana will check the basket on Tuesday." in final
    assert "Done when:" in final
    if oversized == "last-part-outcome":
        completion = json.loads(next(line.removeprefix("Forge-story-done: ")
                                     for line in final.splitlines() if line.startswith("Forge-story-done: ")))
        assert completion["key"] == "SHOP"
        assert completion["outcome"].startswith("Basket quantities survive.")
        assert re.search(r"shorten|omit|trim", re.sub(r"<!--.*?-->", "", final, flags=re.S), re.I)
