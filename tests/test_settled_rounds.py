"""Earlier answers stay visible and settled findings cannot reopen a read or review."""
import shutil

import pytest

import conftest
from test_close import CLEAN, GREEN, blocked, body, env, finding  # noqa: F401
from test_codex_worker import sdk_data  # noqa: F401
from test_readloop_rounds import _setup
from test_setup import _fresh_client
from test_steer_question import _resumable_question
from test_upgrade_command import NAME, RELEASE, Upgrade, unsynced_up  # noqa: F401

STORY = "FIX-SETTLED-STAYS-SETTLED"


@pytest.mark.parametrize("app", ["codex", "claude"])
@pytest.mark.parametrize("repeat_first", [False, True])
def test_1_cold_read_keeps_all_answers_and_ignores_settled_repeats(
        repo, monkeypatch, tmp_path, sdk_data, app, repeat_first):
    reader = _setup(repo, monkeypatch, tmp_path, sdk_data, app)
    first, second, third = "Saving needs an account.", "The date format is unclear.", "Tax is unclear."
    reader.ok(f"1. {first}\n2. {second}\n")
    reader.dispose(first, "keep because the owner chose sign-in")
    reader.dispose(second, "cut because the date uses the browser locale")
    reader.ok(f"1. {third}\n")
    reader.dispose(third, "defer because this slice excludes tax")

    # Reworded evidence underneath the same settled note must not start another round.
    clean = reader.ok(f"1. {first}\n   Another shopper also needs an account.\n")
    prompt = reader.prompt()
    for answer in (first, second, third, "the owner chose sign-in",
                   "the date uses the browser locale", "this slice excludes tax"):
        assert answer in prompt, answer
    assert "found nothing" in clean
    assert "Next: forge read SHOP" not in repo.forge("next").stdout

    # Editing after a pass starts a fresh review of the change, retaining every old answer.
    reader.doc.write_text(reader.doc.read_text("utf-8") + "\nThe basket includes delivery.\n",
                          encoding="utf-8")
    notes = ["1. Delivery charges are unclear.\n", f"1. {first}\n"]
    new = reader.ok("".join(reversed(notes) if repeat_first else notes))
    for answer in (first, second, third, "the owner chose sign-in"):
        assert answer in reader.prompt(), answer
    assert "found nothing" not in new
    assert "Delivery charges are unclear." in reader.notes.read_text("utf-8")
    refused = reader.read()
    assert refused.returncode == 1 and "has no disposition" in refused.stderr


def test_2_review_keeps_all_settlements_and_blocks_only_new_findings(env):
    dismissed, fixed = "Saving requires an account", "Saving drops the basket"
    env.reviews(blocked(finding("P1", dismissed), finding("P1", fixed)))
    item, where = env.start_fix()
    assert env.close(item).returncode == 1
    reason = "app.py:1 the owner chose account-only saving"
    assert env.close(item, "--dismiss", "1", "--because", reason).returncode == 1

    env.commit(where, "app.py", "print('saved')\n", "Keep saved baskets\n\n"
               "Coordinator note:\nCan guests save?\nAnswer: Saving requires an account.\n")
    env.reviews(CLEAN)
    assert env.close(item).returncode == 0

    env.commit(where, "app.py", "print('saved again')\n")
    repeated = [finding("P1", dismissed), finding("P1", fixed)]
    for entry in repeated:
        entry["body"] = "Different evidence for the same settled issue."
    env.reviews(blocked(*repeated))
    done = env.close(item)
    assert done.returncode == 0, done.stdout + done.stderr
    assert len(env.review_calls()) == 3
    shown = body(env.gh_calls("pr", "edit")[-1])
    assert dismissed in shown and f"dismissed because {reason}" in shown
    assert fixed not in shown
    for settled in (dismissed, fixed, reason, "Can guests save?", "Saving requires an account."):
        assert settled in env.prompt(), settled

    env.commit(where, "app.py", "print('saved with delivery')\n")
    env.reviews(blocked(finding("P1", "Delivery loses the basket")))
    done = env.close(item)
    assert done.returncode == 1 and "Delivery loses the basket" in done.stderr
    assert len(env.review_calls()) == 4


@pytest.mark.parametrize("adopted", [False, True], ids=["new-client", "adopted-v1.2.2"])
def test_3_init_and_upgrade_sync_deliver_settled_guidance(unsynced_up, adopted):
    up = unsynced_up

    def check(top):
        for host in (".codex", ".claude"):
            skill = (top / host / "skills/forge/SKILL.md").read_text("utf-8")
            assert "Settled findings stay settled" in skill

    if adopted:
        shutil.copytree(conftest.ROOT / "tests/fixtures/adopted-v1.2.2/client",
                        up.repo.path, dirs_exist_ok=True)
        up.repo.git("switch", "-q", "-c", "adoption")
        up.repo.git("add", "-A")
        up.repo.git("commit", "-q", "-m", "Adopt the earlier release")
        up.repo.git("switch", "-q", "main")
        up.repo.git("merge", "-q", "--ff-only", "adoption")
        up.repo.git("push", "-q", "origin", "main")
    else:
        client, initialized = _fresh_client(up.repo, up.env.gh, up.tmp)
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr
        check(client)
        up.repo.path = client
        up = Upgrade(up.env, up.tmp)
        up.env.checks(GREEN)

    upgraded = up.run(RELEASE)
    assert upgraded.returncode == 0, upgraded.stdout + upgraded.stderr
    where = up.tmp / f"{up.repo.path.name}-fix-{NAME}"
    synced = up.repo.forge("sync", cwd=where)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    check(where)


def test_4_work_notes_and_answers_are_kept_for_review(repo, monkeypatch, sdk_data):
    folder, _, _, _, question = _resumable_question(repo, monkeypatch, sdk_data)
    first = repo.forge("work", "BOARD/PAGE", "--note", "Yes, use the existing parser.")
    assert first.returncode == 0, first.stdout + first.stderr
    second = repo.forge("work", "BOARD/PAGE", "--note", "The parser already handles tax.")
    assert second.returncode == 0, second.stdout + second.stderr
    # Machine conversation records disappear between hosts; the committed answers do not.
    history = repo.git("log", "--format=%B", cwd=folder)
    assert f"Coordinator note:\n{question}\nAnswer: Yes, use the existing parser." in history
    assert "Coordinator note:\nAnswer: The parser already handles tax." in history
