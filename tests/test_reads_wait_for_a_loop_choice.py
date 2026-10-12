"""Three blocked reads hold the next reader until the human's recorded choice."""
STORY = "three-rounds-ask"

import json
import re
import shlex
import sys

import pytest

from conftest import _install
from test_close import env  # noqa: F401
from test_close_holds_after_three_blocked_reviews import QUESTION_RULE, client_item
from test_readloop_gates import dispose_all, say
from test_records import SPEC
from test_story import DOC, READER, claude_plan, hook, new_story, setup, worktree
from test_worker import calls, install_claude


@pytest.mark.parametrize("previous,target", [(False, "SHOP"), (True, "SHOP"),
                                            (False, "basket"), (True, "basket")])
@pytest.mark.parametrize("choice", ["accept", "narrow", "split"])
def test_1_three_blocked_reads_wait_for_a_recordable_choice_on_new_and_upgraded_clients(
        env, tmp_path, claude_payload, previous, target, choice):
    _, where = client_item(env, tmp_path, previous)
    repo = env.repo
    config = (where / "forge.toml").read_text("utf-8")
    if "models.grill.claude" not in config:
        env.commit(where, "forge.toml", config + 'models.grill.claude = { model = "opus", effort = "high" }\n')
    _install(repo.bin, "claude", READER.format(python=sys.executable))
    env.commit(where, "docs/decisions/0001-client-signoff.md",
               '---\nstatus: accepted\nconfirmed_by: A Client\n---\n# Signed off\n')
    env.commit(where, "plans/roadmap.json", json.dumps({"items": [{"key": "SHOP"}]}))
    # Stories start on the default branch: land the fixture's upgrade and sign-off first.
    repo.git("merge", "--ff-only", repo.git("rev-parse", "HEAD", cwd=where))
    made = repo.forge("story", "new", "SHOP", "Shoppers can save a basket", cwd=where)
    assert made.returncode == 0, made.stderr
    # The spec is planned on the story's branch, where forge spec save accepts it.
    where = worktree(repo, "story/SHOP")
    doc = where / ("plans/SHOP.md" if target == "SHOP" else "docs/specs/basket.md")
    doc.parent.mkdir(parents=True, exist_ok=True)
    # A short bold lead-in keeps the sentence after it.
    # A title with a markdown link and a path reads in plain words in the question.
    original = DOC.replace("# Shoppers can save a basket",
                           "# Shoppers can save a [basket](docs/basket.md) from `src/basket.py`",
                           1) if target == "SHOP" else SPEC.replace(
        "Each invoice is emailed as a PDF.", "**Emailed invoices.** Each invoice is emailed as a PDF.").replace(
        "# Invoices by email", "# Invoices by [email](docs/email.md) at `src/mail.py`", 1)
    doc.write_text(original, "utf-8")
    if target != "SHOP":
        saved = repo.forge("spec", "save", target, cwd=where)
        assert saved.returncode == 0, saved.stderr
    notes = doc.with_name(doc.stem + ".read.md")
    for number in range(1, 4):
        # Settled repeats are clean; each round must still find a distinct blocking gap.
        say(repo, f"1. Blocking: Basket recovery is missing for case {number}.\n"
                  "   Raise: Not done. A shopper who signs out at `src/basket.py:12` loses the saved basket. "
                  "The doc never says when it comes back.\n"
                  # A note already disposed of is not asked about again.
                  + ("2. Blocking: A gap the owner cut.\n   Disposition: cut\n" if number == 3 else ""))
        result = repo.forge("read", target, cwd=where)
        assert result.returncode == (1 if number == 3 else 0), result.stdout + result.stderr
        if number < 3:
            dispose_all(notes)
    resolution = f'forge read {target} --resolve <accept|narrow|split> --reason "<human\'s choice>"'
    # The stop is a ready-to-ask question: the item, each open note in plain words, each choice.
    parts = "Done when" if target == "SHOP" else "Behaviour and Acceptance criteria"
    question = (("Shoppers can save a basket: Shoppers can save a basket and come back to it later."
                 if target == "SHOP" else
                 "Invoices by email: Emailed invoices: each invoice is emailed as a PDF.") + "\n"
                "It still has these problems:\n"
                "- Basket recovery is missing for case 3: a shopper who signs out loses the saved basket. "
                "The doc never says when it comes back.\n"
                "Accept, narrow or split?\n"
                "- Accept: keep these problems as known and mark the read accepted; approving or "
                "confirming the doc is still a separate step.\n"
                f"- Narrow: drop these cases from its {parts}; they become follow-ups.\n"
                "- Split: move these cases into a new story or fix of their own; this one goes on "
                "without them.")
    assert result.stderr == (
        f"Three consecutive cold-read rounds of {target} still have blocking notes. "
        "Ask the human to accept, narrow or split before reading again, in these words:\n"
        f"{question}\nNext: {resolution}\n")
    calls = repo.bin / "claude-calls.jsonl"
    assert len(calls.read_text("utf-8").splitlines()) == 3
    # Even edited documents and missing dispositions cannot spend a fourth reader.
    doc.write_text(doc.read_text("utf-8") + "\nRecovery is now described.\n", "utf-8")
    held = repo.forge("read", target, cwd=where)
    assert held.returncode == 1 and resolution in held.stderr
    said = repo.forge("next", cwd=where).stdout
    assert resolution in said and question in said
    if target != "SHOP":  # from the main checkout, the spec's step runs in its own checkout
        main = repo.forge("next", cwd=repo.path).stdout
        assert f"Next: cd {shlex.quote(str(where))} && {resolution}" in main and question in main
    if previous:  # notes saved before the blocked-round count existed: earlier snapshots count
        notes.write_text(re.sub(r"^blocked_rounds: .*\n", "", notes.read_text("utf-8"), flags=re.M), "utf-8")
        assert "blocked_rounds" not in notes.read_text("utf-8")
        assert question in repo.forge("next", cwd=where).stdout
    assert "A gap the owner cut" not in result.stderr + said
    assert len(calls.read_text("utf-8").splitlines()) == 3
    invalid = repo.forge("read", target, "--resolve", choice, "--reason", " ", cwd=where)
    assert invalid.returncode == 1
    assert invalid.stderr == (
        "Record the human's choice only on a stopped cold-read loop, with a non-empty --reason.\n"
        f"Next: {resolution}\n")
    reason = "The human chose this scope after reading the remaining notes"
    if choice == "accept":
        # The owner's supplied reason must also settle an unfinished latest disposition.
        notes.write_text(notes.read_text("utf-8") + "   Disposition: keep\n", "utf-8")
    chosen = repo.forge("read", target, "--resolve", choice, "--reason", reason, cwd=where)
    assert chosen.returncode == 0, chosen.stdout + chosen.stderr
    assert len(calls.read_text("utf-8").splitlines()) == 3
    committed = repo.git("show", f"HEAD:{notes.relative_to(where).as_posix()}", cwd=where)
    assert reason in committed and "Basket recovery is missing" in committed
    assert repo.forge("read", target, "--resolve", choice, "--reason", reason,
                      cwd=where).returncode == 1
    if choice == "accept" and target == "SHOP":
        approved = hook(repo, claude_plan(claude_payload, doc.read_text("utf-8"), cwd=where))
        assert approved.returncode == 0, approved.stderr
        doc.write_text(doc.read_text("utf-8") + "\nA new requirement.\n", "utf-8")
        # Once approved, task start is the boundary that checks later edits against the read.
        changed = repo.forge("task", "start", "SHOP/SAVE", cwd=where)
        assert changed.returncode == 1 and "changed after" in changed.stderr
    elif choice == "accept":
        confirmed = repo.forge("spec", "confirm", target, "--by", "Ravi", cwd=where)
        assert confirmed.returncode == 0, confirmed.stderr
    else:
        dispose_all(notes)
    say(repo, "No findings.\n")
    resumed = repo.forge("read", target, cwd=where)
    assert resumed.returncode == 0, resumed.stdout + resumed.stderr
    assert len(calls.read_text("utf-8").splitlines()) == 4
    for host in (".codex", ".claude"):
        guide = (where / host / "skills/forge/SKILL.md").read_text("utf-8")
        assert "three consecutive cold-read rounds" in " ".join(guide.split())
        assert '--resolve <accept|narrow|split> --reason "<human\'s choice>"' in guide
        assert QUESTION_RULE in " ".join(guide.split())


def test_2_a_clean_read_restarts_the_three_blocked_round_count(repo):
    setup(repo)
    where = new_story(repo, "SHOP")
    (where / "plans/SHOP.md").write_text(DOC, "utf-8")
    notes = where / "plans/SHOP.read.md"
    for reply in ("1. A missing recovery rule.", "No findings.",
                  "1. A new recovery gap.", "1. Another recovery gap."):
        say(repo, reply + "\n")
        result = repo.forge("read", "SHOP")
        assert result.returncode == 0, result.stdout + result.stderr
        dispose_all(notes)
    say(repo, "1. Recovery is still missing.\n")
    result = repo.forge("read", "SHOP")
    assert result.returncode == 1 and "Ask the human to accept, narrow or split" in result.stderr
    assert len((repo.bin / "claude-calls.jsonl").read_text("utf-8").splitlines()) == 5


def test_4_fresh_and_resumed_workers_wait_for_both_read_and_review_choices(env):
    item, _ = env.start_fix()
    log = install_claude(env.repo)
    for _ in range(2):
        result = env.repo.forge("work", item)
        assert result.returncode == 0, result.stdout + result.stderr
        assert "three consecutive cold-read rounds" in " ".join(calls(log)[-1]["brief"].split())
    assert "--resume" in calls(log)[-1]["args"]
