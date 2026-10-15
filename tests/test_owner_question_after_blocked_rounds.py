"""Two blocked rounds prompt an owner question before more work, after init or upgrade."""
STORY = "fix-grill-when-rounds-grow"

import sys

import pytest

from conftest import _install, patient
from test_close import CLEAN, blocked, env, finding  # noqa: F401
from test_close_holds_after_three_blocked_reviews import client_item
from test_readloop_gates import dispose_all, say
from test_records import SPEC
from test_story import DOC, READER, new_story


ASK = "Stop sending rounds and ask the owner to settle the missing rule."
TITLES = ("Saving loses the basket", "Delivery loses the address")


def assert_owner_question(text):
    assert ASK in text
    assert "| Round | Finding titles |" in text
    for number, title in enumerate(TITLES, 1):
        assert f"| {number} | {title} |" in text
    assert "one question at a time" in text
    assert "options and a recommendation" in text
    assert "builder details" in text
    assert "one focused round" in text


def review_round(env, item, where, number):
    # Distinct areas and findings reproduce a missing rule without the existing same-file hold.
    env.commit(where, "app.py", f"print('round {number}')\n")
    env.reviews(blocked(finding("P1", TITLES[number - 1], f"docs/round-{number}.md")))
    result = env.close(item)
    assert result.returncode == 1, result.stdout + result.stderr
    assert len(env.review_calls()) == number
    return result


@pytest.mark.parametrize("previous", [False, True], ids=["init", "earlier-adoption-upgraded"])
@pytest.mark.parametrize("phase", ["review", "remote-review", "story-read", "spec-read"])
def test_1_next_asks_the_owner_after_two_blocked_rounds(env, tmp_path, previous, phase):
    item, where = client_item(env, tmp_path, previous)
    client_where = where
    if phase in ("review", "remote-review"):
        review_round(env, item, where, 1)
        first = env.repo.forge("next")
        assert first.returncode == 0, first.stderr
        assert ASK not in first.stdout
        review_round(env, item, where, 2)
    else:
        _install(env.repo.bin, "claude", READER.format(python=sys.executable))
        if phase == "story-read":
            target = "OWNER"
            env.commit(where, "docs/decisions/0001-client-signoff.md",
                       '---\nstatus: accepted\nconfirmed_by: A Client\n---\n# Signed off\n')
            # Story planning starts from main, which needs the client's upgrade and sign-off.
            env.repo.git("merge", "--ff-only", env.repo.git("rev-parse", "HEAD", cwd=where))
            where = new_story(env.repo, target)
            doc = where / "plans/OWNER.md"
            patient(lambda: doc.write_text(DOC, encoding="utf-8"))
        else:
            target = "invoices"
            doc = where / "docs/specs/invoices.md"
            doc.parent.mkdir(parents=True, exist_ok=True)
            patient(lambda: doc.write_text(SPEC, encoding="utf-8"))
            saved = env.repo.forge("spec", "save", target, cwd=where)
            assert saved.returncode == 0, saved.stderr
        notes = doc.with_suffix(".read.md")
        for number, title in enumerate(TITLES, 1):
            say(env.repo, f"1. {title}\n   Gain 4, Work 2, Harm 1\n")
            read = env.repo.forge("read", target, cwd=where)
            assert read.returncode == 0, read.stdout + read.stderr
            if number == 1:
                first = env.repo.forge("next", cwd=where)
                assert first.returncode == 0, first.stderr
                assert ASK not in first.stdout
                patient(lambda: dispose_all(notes))
    result = env.repo.forge("next", cwd=where)
    assert result.returncode == 0, result.stderr
    assert_owner_question(result.stdout)
    # The commands ship the coordinator's complete instruction to both hosts at init and upgrade.
    for host in (".codex", ".claude"):
        guide = " ".join((client_where / host / "skills/forge/SKILL.md").read_text("utf-8").split())
        for instruction in ("second blocked", "list the findings", "name the pattern",
                            "one question at a time", "options and a recommendation",
                            "builder details", "one focused round"):
            assert instruction in guide
    if phase == "remote-review":
        # Keep only the published fix branch under its original name, as on another machine.
        env.repo.git("worktree", "remove", str(where))
        env.repo.git("branch", "-m", f"fix/{item}", f"worker/{item}")
        remote = env.repo.forge("next")
        assert remote.returncode == 0, remote.stderr
        assert_owner_question(remote.stdout)
        assert "runs on their machine" not in remote.stdout


@pytest.mark.parametrize("previous", [False, True], ids=["init", "earlier-adoption-upgraded"])
def test_2_close_asks_the_owner_after_two_blocked_reviews(env, tmp_path, previous):
    item, where = client_item(env, tmp_path, previous)
    first = review_round(env, item, where, 1)
    assert ASK not in first.stderr
    second = review_round(env, item, where, 2)
    assert_owner_question(second.stderr)
    # The second-round advice does not replace the existing third-round hard stop with a gate.
    env.commit(where, "app.py", "print('owner rule applied')\n")
    env.reviews(CLEAN)
    focused = env.close(item)
    assert focused.returncode == 0, focused.stdout + focused.stderr
    assert "Ready:" in focused.stdout
    assert len(env.review_calls()) == 3


@pytest.mark.parametrize("previous", [False, True], ids=["init", "earlier-adoption-upgraded"])
@pytest.mark.parametrize("remote", [False, True], ids=["local", "remote"])
def test_3_hard_stop_keeps_the_owner_question_and_resolution_step(env, tmp_path, previous, remote):
    item, where = client_item(env, tmp_path, previous)
    titles = (*TITLES, "Checkout loses the total")
    for number, title in enumerate(titles, 1):
        env.commit(where, "app.py", f"print('round {number}')\n")
        # Three distinct low-Harm findings in one area still need the owner's choice.
        env.reviews(blocked(finding("P1", title, "README.md")))
        stopped = env.close(item)
        assert stopped.returncode == 1, stopped.stdout + stopped.stderr
    resolution = f'forge close {item} --resolve <narrow|split|accept>'
    assert resolution in stopped.stderr
    assert ASK in stopped.stderr
    assert "The coordinator asks. The owner decides. The coordinator records the choice." in stopped.stderr
    assert "settle it yourself" not in stopped.stderr
    assert "then send one focused round" not in stopped.stderr
    if remote:
        env.repo.git("worktree", "remove", str(where))
        env.repo.git("branch", "-m", f"fix/{item}", f"worker/{item}")
    shown = env.repo.forge("next")
    assert shown.returncode == 0, shown.stderr
    assert resolution in shown.stdout
    assert "Accept, narrow or split?" in shown.stdout
    assert "The coordinator asks. The owner decides. The coordinator records the choice." in shown.stdout
    assert "settle it yourself" not in shown.stdout
    assert "then send one focused round" not in shown.stdout
    for number, title in enumerate(titles, 1):
        assert f"| {number} | {title} |" in stopped.stderr
        assert f"| {number} | {title} |" in shown.stdout
    assert len(env.review_calls()) == 3
