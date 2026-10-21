"""The owner decides on review leftovers; workers keep repairing P0s until stuck.

Only Autoreview and the worker's model are faked. Real Forge commands own the
rounds, stops, recorded choices and Known issues on new and upgraded clients.
"""
import json

import pytest

from test_close import CLEAN, STORY_DOC, blocked, env  # noqa: F401
from test_fix_plan_reads_capped import _client as read_client
from test_readloop_gates import dispose_all, say
from test_setup import _fresh_client
from test_tools_session_hold import Session
from test_two_round_limit import client, known, note
from test_upgrade_command import _repo_adopted_on_the_previous_release, unsynced_up
from test_worker import calls, install_claude
from test_story import DOC, new_story
from test_records import SPEC

STORY = "FORGE-ROUNDS-2"


@pytest.mark.parametrize("case", ["part", "fix", "adopted fix", "session"])
def test_1_at_the_round_limit_an_open_finding_below_p0_stops_for_the_owner(env, monkeypatch, case):
    # The former contract silently kept P1s as follow-ups at the limit. Now
    # only the owner's accept can turn these findings into follow-ups.
    client(env, case == "adopted fix")
    log = install_claude(env.repo)
    entry = note("P1", "Saving loses quantities")
    env.reviews(blocked(entry))
    item, where = env.start_approved_task(STORY_DOC) if case == "part" else env.start_fix()
    if case == "part":
        first = env.close(item)
        assert first.returncode == 1, first.stdout + first.stderr
        assert "The review left serious findings open" in first.stderr
        assert "reached the round limit" not in first.stderr
        env.commit(where, "app.py", "print('save quantities')\n", "Repair saving")
    stopped = env.close(item)
    round_number = 2 if case == "part" else 1
    line = (f"Review round {round_number} of {item} reached the round limit with open findings, "
            "so Forge stopped.")
    step = f'forge close {item} --resolve <more|split|accept> --reason "<human\'s choice>"'
    assert stopped.returncode == 1, stopped.stdout + stopped.stderr
    for text in (line, "One more round, split or accept?", entry["title"], step):
        assert text in stopped.stderr
    shown = env.repo.forge("next")
    assert shown.returncode == 0, shown.stdout + shown.stderr
    assert "One more round, split or accept?" in shown.stdout and step in shown.stdout
    if case == "part":
        assert ("Forge asks the owner about each finding below P0 that is still open at the "
                "round limit.") in " ".join(env.prompt().split())
        held = env.repo.forge("work", item)
        assert held.returncode == 1, held.stdout + held.stderr
        assert line in held.stderr and step in held.stderr
        assert calls(log) == []
    elif case == "fix":
        held = env.repo.forge("land", item)
        assert held.returncode == 3, held.stdout + held.stderr
        assert "One more round, split or accept?" in held.stdout + held.stderr
        assert entry["title"] in held.stdout + held.stderr
        assert calls(log) == []
    elif case == "session":
        monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
        monkeypatch.setenv("CLAUDECODE", "1")
        host = Session(env.repo, env.tmp / "host", "claude-session")
        try:
            held = host.forge("work", item)
            assert held.returncode == 1, held.stdout + held.stderr
            assert line in held.stderr and step in held.stderr
            assert "--round" not in held.stdout
            assert calls(log) == []
        finally:
            host.close()
    if case == "adopted fix":
        chosen = env.close(item, "--resolve", "more", "--reason", "Repair the quantity loss")
        assert chosen.returncode == 0, chosen.stdout + chosen.stderr
        assert "Next: forge work tidy-readme" in chosen.stdout
        worked = env.repo.forge("work", item)
        assert worked.returncode == 0, worked.stdout + worked.stderr
        assert "The owner chose more" in calls(log)[-1]["brief"]
        env.commit(where, "app.py", "print('quantities kept')\n", "Keep quantities")
        env.reviews(CLEAN)
        ready = env.close(item)
    else:
        ready = env.close(item, "--resolve", "accept", "--reason", "Keep the current quantity flow")
        issues = known(env, where)
        assert issues[entry["title"]]["kept"] == "follow-up"
        assert issues[entry["title"]]["reason"].startswith("Human accepted the remaining finding:")
    assert ready.returncode == 0 and "Ready" in ready.stdout, ready.stdout + ready.stderr
    assert len(env.review_calls()) == (2 if case in ("part", "adopted fix") else 1)


@pytest.mark.parametrize("case", ["fix", "part", "adopted fix", "other p0"])
def test_2_an_open_p0_goes_back_to_the_worker_until_it_is_stuck_two_rounds(env, case):
    # A P0 used to stop at the review limit. It now goes back to the worker,
    # and only leaving the same P0 in two worker rounds asks for a choice.
    client(env, case == "adopted fix")
    log = install_claude(env.repo)
    item, where = env.start_approved_task(STORY_DOC) if case == "part" else env.start_fix()
    first_work = env.repo.forge("work", item)
    assert first_work.returncode == 0, first_work.stdout + first_work.stderr
    first_p0 = note("P0", "Saving deletes the basket")
    env.reviews(blocked(first_p0))
    first = env.close(item)
    assert first.returncode == 1, first.stdout + first.stderr
    assert "The review left serious findings open" in first.stderr
    assert "Forge stopped" not in first.stderr and "--resolve <more" not in first.stderr
    second_work = env.repo.forge("work", item)
    assert second_work.returncode == 0, second_work.stdout + second_work.stderr
    assert "An open P0 never stops for the owner: fix it in this round." in calls(log)[-1]["brief"]
    env.commit(where, "app.py", "print('repair saving')\n", "Repair saving")
    second_p0 = note("P0", "Reopening deletes the basket") if case == "other p0" else first_p0
    env.reviews(blocked(second_p0))
    second = env.close(item)
    assert second.returncode == 1, second.stdout + second.stderr
    assert "The review left serious findings open" in second.stderr
    assert "Forge stopped" not in second.stderr and "--resolve <more" not in second.stderr
    shown = env.repo.forge("next")
    assert shown.returncode == 0, shown.stdout + shown.stderr
    assert "One more round, split or accept?" not in shown.stdout
    third_work = env.repo.forge("work", item)
    if case == "other p0":
        assert third_work.returncode == 0, third_work.stdout + third_work.stderr
        assert len(calls(log)) == 3
    else:
        assert third_work.returncode == 1, third_work.stdout + third_work.stderr
        assert "The worker can't get past the same problem" in third_work.stderr
        assert ("Two rounds in a row left the open P0 saving deletes the basket in app.py."
                in third_work.stderr)
        assert third_work.stderr.splitlines()[-1] == (
            f'Next: forge close {item} --resolve <switch|same|narrow|split> '
            '--reason "<human\'s choice>"')
        assert len(calls(log)) == 2
        if case == "fix":
            chosen = env.close(item, "--resolve", "same", "--reason", "One more try")
            assert chosen.returncode == 0, chosen.stdout + chosen.stderr
            resumed = env.repo.forge("work", item)
            assert resumed.returncode == 0, resumed.stdout + resumed.stderr
            assert "The owner chose same: One more try" in calls(log)[-1]["brief"]
            assert len(calls(log)) == 3
    assert len(env.review_calls()) == 2


@pytest.mark.parametrize("adopted,target,case", [
    (adopted, target, case)
    for adopted in (False, True)
    for target in ("SHOP", "invoices")
    for case in ("below p0", "p0 once")
] + [(False, target, "p0 twice") for target in ("SHOP", "invoices")])
def test_3_from_round_two_a_cold_read_with_an_open_note_below_p0_stops_for_the_owner(
        repo, gh, tmp_path, adopted, target, case):
    read_client(repo, gh, tmp_path, adopted)
    where = new_story(repo, "SHOP")
    if target == "SHOP":
        doc = where / "plans/SHOP.md"
        doc.write_text(DOC, encoding="utf-8")
    else:
        doc = where / "docs/specs/invoices.md"
        doc.parent.mkdir(parents=True, exist_ok=True)
        doc.write_text(SPEC, encoding="utf-8")
        saved = repo.forge("spec", "save", target, cwd=where)
        assert saved.returncode == 0, saved.stdout + saved.stderr
    notes = doc.with_suffix(".read.md")
    first_harm = 5 if case == "p0 twice" else 2
    first_title = "Saving deletes the basket" if case == "p0 twice" else "Recovery loses saved quantities"
    say(repo, f"1. Blocking: {first_title}.\n"
        "   Case: normal use - A shopper reopens a saved basket and its contents are lost.\n"
        f"   Gain 4, Work 1, Harm {first_harm}\n")
    first = repo.forge("read", target, cwd=where)
    assert first.returncode == 0, first.stdout + first.stderr
    dispose_all(notes)

    second_harm = 2 if case == "below p0" else 5
    title = ("Recovery loses saved quantities again" if case == "below p0" else
             "Saving deletes a different basket" if case == "p0 twice" else
             "Saving deletes the basket")
    say(repo, f"1. Blocking: {title}.\n"
        "   Case: normal use - A shopper reopens a saved basket and its contents are lost.\n"
        f"   Gain 4, Work 1, Harm {second_harm}\n")
    second = repo.forge("read", target, cwd=where)
    calls_log = repo.bin / "claude-calls.jsonl"
    prompt = json.loads(calls_log.read_text("utf-8").splitlines()[-1])["prompt"]
    assert "Forge asks the owner about every other open note after round two." in " ".join(prompt.split())
    if case == "p0 once":
        assert second.returncode == 0, second.stdout + second.stderr
        assert "Wrote round 2" in second.stdout
        assert "One more round, split or accept?" not in second.stdout + second.stderr
        next_step = repo.forge("next", cwd=where)
        assert next_step.returncode == 0, next_step.stdout + next_step.stderr
        assert "One more round, split or accept?" not in next_step.stdout
        assert len(calls_log.read_text("utf-8").splitlines()) == 2
        dispose_all(notes)
        say(repo, "No findings.\n")
        third = repo.forge("read", target, cwd=where)
        assert third.returncode == 0, third.stdout + third.stderr
        assert "Round 3" in third.stdout
        assert len(calls_log.read_text("utf-8").splitlines()) == 3
        return

    question = "One more round, split or accept?"
    resolution = f'forge read {target} --resolve <accept|more|split> --reason "<human\'s choice>"'
    stop = f"Round 2 of the cold read of {target} stopped with open notes, so Forge asks the owner."
    assert second.returncode == 1, second.stdout + second.stderr
    assert stop in second.stderr
    assert question in second.stderr and title in second.stderr and resolution in second.stderr
    assert "Left open after round two" not in notes.read_text("utf-8")
    shown = repo.forge("next", cwd=where)
    assert shown.returncode == 0, shown.stdout + shown.stderr
    assert question in shown.stdout and resolution in shown.stdout and title in shown.stdout
    held = repo.forge("read", target, cwd=where)
    assert held.returncode == 1, held.stdout + held.stderr
    assert resolution in held.stderr
    assert len(calls_log.read_text("utf-8").splitlines()) == 2

    if case == "below p0":
        reason = "The owner accepts the remaining recovery note"
        chosen = repo.forge("read", target, "--resolve", "accept", "--reason", reason, cwd=where)
        assert chosen.returncode == 0, chosen.stdout + chosen.stderr
        assert f"Disposition: keep - {reason}" in notes.read_text("utf-8")
        next_step = repo.forge("next", cwd=where)
        assert next_step.returncode == 0, next_step.stdout + next_step.stderr
        assert ("Plan Mode" if target == "SHOP" else "forge spec confirm invoices") in next_step.stdout
    else:
        chosen = repo.forge("read", target, "--resolve", "more", "--reason",
                            "The owner wants one more read", cwd=where)
        assert chosen.returncode == 0, chosen.stdout + chosen.stderr
        assert f"Next: forge read {target}" in chosen.stdout
        dispose_all(notes)
        say(repo, "No findings.\n")
        third = repo.forge("read", target, cwd=where)
        assert third.returncode == 0, third.stdout + third.stderr
        assert "Round 3" in third.stdout
        assert len(calls_log.read_text("utf-8").splitlines()) == 3


@pytest.mark.parametrize("adoption", ["new init", "previous release upgrade and sync"])
def test_4_clients_get_the_owner_decides_at_the_round_limit_guide(unsynced_up, adoption):
    up = unsynced_up
    if adoption == "new init":
        client, initialized = _fresh_client(up.repo, up.env.gh, up.tmp)
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    else:
        _repo_adopted_on_the_previous_release(up)
        client = up.folder

    sentences = (
        "At the round limit, open findings below P0 stop the item and ask the owner: one more round, split or accept.",
        "An open P0 never stops for the owner; the worker keeps fixing it.",
        "When two rounds in a row leave close's tests failing or the same P0 open, `forge work` stops the item.",
        "Accept makes the open findings follow-ups in Known issues with the owner's reason.",
        "A cold read stops after round two when notes below P0 are still open, or when P0 notes are open in two rounds in a row.",
    )
    for host in (".claude", ".codex"):
        guide = " ".join((client / host / "skills/forge/SKILL.md").read_text("utf-8").split())
        for sentence in sentences:
            assert sentence in guide, (host, sentence)
        assert "Left open after round" not in guide
        assert "Other open notes become follow-ups" not in guide
