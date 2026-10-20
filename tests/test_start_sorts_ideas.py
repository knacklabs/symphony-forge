"""Ideas enter through the real start command and session handback on both repo ages.

The session is a real parent process. Only GitHub, models and Autoreview use the
existing third-party stubs; they never choose the lane or create the Forge item.
"""
import json
import re
import shutil
import sys
from pathlib import Path

import pytest

from conftest import GH_STUB, ROOT, _install
from test_close import GREEN, env  # noqa: F401
from test_land import GH, URL, land  # noqa: F401
from test_setup import _fresh_client
from test_tools_session_hold import Session

STORY = "FORGE-INTAKE-1"


def _land_setup(repo, top, branch, paths=("-A",)):
    # Fixture commits represent an adoption/settings/sign-off already merged by
    # the owner, just as Upgrade.on_main does. Commands under test keep hooks.
    no_hooks = top.parent / "fixture-no-hooks"
    no_hooks.mkdir(exist_ok=True)
    repo.git("switch", "-q", "-c", branch, cwd=top)
    repo.git("add", *paths, cwd=top)
    repo.git("-c", f"core.hooksPath={no_hooks}", "commit", "-q", "--allow-empty",
             "-m", "Prepare idea intake", cwd=top)
    repo.git("switch", "-q", "main", cwd=top)
    repo.git("merge", "-q", "--ff-only", branch, cwd=top)
    repo.git("-c", f"core.hooksPath={no_hooks}", "push", "-q", "origin", "main", cwd=top)


@pytest.fixture(params=["new", "adopted"])
def intake(request, land, gh, monkeypatch, tmp_path):
    repo = land.repo
    version = repo.forge("--version").stdout.split()[-1]
    if request.param == "new":
        top, made = _fresh_client(repo, gh, tmp_path)
        assert made.returncode == 0, made.stdout + made.stderr
        remote = tmp_path / "client.git"
        expected = ("claude-haiku-5-5", "high")
    else:
        top = repo.path
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", top,
                        dirs_exist_ok=True)
        toml = top / "forge.toml"
        toml.write_text(toml.read_text("utf-8").replace('"v1.2.2"', json.dumps(version)),
                        "utf-8")
        repo.git("switch", "-q", "-c", "adoption-sync", cwd=top)
        synced = repo.forge("sync", cwd=top)
        assert synced.returncode == 0, synced.stdout + synced.stderr
        repo.git("switch", "-q", "main", cwd=top)
        remote = tmp_path / "remote.git"
        expected = ("claude-sonnet-5-5", "xhigh")
    # A landed adoption and initial scaffold are facts in git before intake starts.
    _land_setup(repo, top, "setup-intake")
    _install(repo.bin, "gh", GH.format(python=sys.executable, remote=str(remote), url=URL)
             + GH_STUB.format(python=sys.executable).split("\n", 1)[1])
    land.checks(GREEN)
    monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.setenv("CLAUDE_SESSION_ID", "intake-session")
    owner = Session(repo, tmp_path / "intake-host", "claude-intake-session")
    try:
        yield repo, top, owner, expected, request.param, land
    finally:
        owner.close()


def _offer(intake, idea):
    _, top, owner, expected, _, _ = intake
    offered = owner.forge("start", idea, cwd=top)
    assert offered.returncode == 0, offered.stdout + offered.stderr
    result = json.loads(offered.stdout)
    assert result["role"] == "explorer" and result["round"] == 1
    assert (result["model"], result["effort"]) == expected
    assert Path(result["checkout"]).resolve() == top.resolve()
    return result


def _back(intake, offered, text):
    _, top, owner, _, _, _ = intake
    return owner.forge("handback", offered["target"], "--round", str(offered["round"]),
                       "--subagent", "idea-explorer", "--text", text, cwd=top)


def _signed_off(intake):
    repo, top, *_ = intake
    path = top / "docs/decisions/0001-client-signoff.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('---\nstatus: accepted\nconfirmed_by: "The owner"\n---\n\n'
                    '# The client signed off\n', "utf-8")
    _land_setup(repo, top, "record-signoff")


def _fix(why="Fix the welcome typo", kind="backend"):
    return (f"Lane: fix\nReason: The change is small and clear.\nWhy: {why}\n"
            f"Done: The welcome page says Welcome.\nKind: {kind}")


def test_1_start_answers_in_one_plain_line_with_its_choice_and_reason(intake):
    # The new boundary did not exist before SORT; malformed answers must never
    # create a partially specified fix, and refusal must permit a fresh attempt.
    repo, top, _, _, _, _ = intake
    _signed_off(intake)
    offer = _offer(intake, "Correct the welcome page")
    prompt = offer["prompt"]
    for instruction in ("five code files", "docs/decisions/", "## Review rules",
                        "Lane:", "Reason:", "Why:", "Done:", "Kind:",
                        "Key:", "Title:", "Change:", "Problem:"):
        assert instruction in prompt
    malformed = _back(intake, offer, "Lane: fix\nReason: Small.\nWhy: Correct the typo\nKind: ui")
    assert malformed.returncode == 0, malformed.stdout + malformed.stderr
    assert "send this to subagent" in malformed.stdout.lower()
    assert not repo.git("branch", "--list", "fix/*", cwd=top)
    good = _back(intake, offer, _fix())
    assert good.returncode == 0, good.stdout + good.stderr
    assert good.stdout.splitlines()[0] == "Forge chose a fix: The change is small and clear."
    for lane, fields, chosen in (
        ("discovery", "Question: Who needs this?", "discovery"),
        ("later", "", "the idea list"),
    ):
        offer = _offer(intake, "Keep this idea for " + lane)
        done = _back(intake, offer, f"Lane: {lane}\nReason: The owner gave no problem.\n{fields}")
        assert done.returncode == 0, done.stdout + done.stderr
        assert done.stdout.splitlines()[0] == f"Forge chose {chosen}: The owner gave no problem."
    for number, first in enumerate(("not a reply", "")):
        idea = f"A refused idea {number}"
        offer = _offer(intake, idea)
        again = _back(intake, offer, first)
        assert again.returncode == 0 and "send this to subagent" in again.stdout.lower()
        refused = _back(intake, offer, "still not a reply")
        assert refused.returncode == 1
        assert "Forge cannot read the explorer's reply after two tries. Nothing started." in (
            refused.stdout + refused.stderr)
        assert f'Next: forge start "{idea}"' in refused.stdout + refused.stderr
        restarted = _offer(intake, idea)
        completed = _back(intake, restarted, "Lane: discovery\nReason: No clear problem.\n"
                          "Question: What should change?")
        assert completed.returncode == 0, completed.stdout + completed.stderr
    assert not repo.git("branch", "--list", "story/*", cwd=top)
    assert repo.git("branch", "--list", "fix/*", cwd=top).count("fix/") == 1


def test_2_a_small_clear_idea_starts_a_fix_that_lands_as_the_merge_setting_allows(intake, monkeypatch):
    repo, top, _, _, age, env = intake
    # Build via the real worker/land path, using LAND's SDK and GitHub edges.
    config = top / "forge.toml"
    text = config.read_text("utf-8")
    text = re.sub(r'^workers = .*$', 'workers = "claude"', text, flags=re.M)
    text = re.sub(r'^test = .*$', 'test = "python -c \\\"print(123)\\\""', text, flags=re.M)
    config.write_text(text, "utf-8")
    _land_setup(repo, top, "configure-worker", ("forge.toml",))
    for kind in ("backend", "ui"):
        why = "Fix the welcome typo" if kind == "backend" else "Correct the button label"
        offered = _offer(intake, why)
        done = _back(intake, offered, _fix(why, kind))
        assert done.returncode == 0, done.stdout + done.stderr
        name = done.stdout.splitlines()[-1].removeprefix("Next: forge land ")
        assert done.stdout.splitlines()[-1] == f"Next: forge land {name}"
        state = json.loads(repo.git("show", f"fix/{name}:.factory/fixes/{name}.json", cwd=top))
        assert (state["why"], state["done_when"], state["fix_kind"]) == (
            why, "The welcome page says Welcome.", kind)
        if age == "new":
            assert state["allow_large"] == "Prototype before sign-off"
        if kind == "ui":
            continue
        with monkeypatch.context() as external_worker:
            external_worker.delenv("CLAUDECODE", raising=False)
            external_worker.setenv("CODEX_THREAD_ID", "intake-land-coordinator")
            landed = repo.forge("land", name, cwd=top)
        assert landed.returncode == 0, landed.stdout + landed.stderr
        if age == "new":
            assert (repo.bin / "github-merged").exists()
            assert "Merging " + name in landed.stdout
        else:
            assert f"{name} is ready; a human merges its pull request:" in landed.stdout
            assert not (repo.bin / "github-merged").exists()
    offered = _offer(intake, "Repeat the first fix")
    duplicate = _back(intake, offered, _fix())
    assert duplicate.returncode == 0, duplicate.stdout + duplicate.stderr
    assert duplicate.stdout.splitlines()[-1] == "Next: forge land fix-the-welcome-typo-2"


def test_3_a_big_idea_starts_a_story_with_a_first_plan(intake):
    repo, top, _, _, age, _ = intake
    reply = ("Lane: plan\nReason: People need a new way to save baskets.\nKey: SAVE\n"
             "Title: Keep baskets for later\nChange: Shoppers save their basket.\n"
             "Change: Shoppers open a saved basket.\nProblem: Shoppers lose baskets when they leave.\n"
             "Done: A shopper can save a basket.\nDone: A saved basket returns after sign-in.")
    if age == "new":
        offered = _offer(intake, "Save baskets")
        assert "Lane: plan" not in offered["prompt"]
        rejected = _back(intake, offered, reply)
        assert rejected.returncode == 0 and "send this to subagent" in rejected.stdout.lower()
        finished = _back(intake, offered, _fix("Build the basket prototype"))
        assert finished.returncode == 0, finished.stdout + finished.stderr
    _signed_off(intake)
    offered = _offer(intake, "Let shoppers keep baskets")
    done = _back(intake, offered, reply)
    assert done.returncode == 0, done.stdout + done.stderr
    assert done.stdout.splitlines()[0] == "Forge chose a plan: People need a new way to save baskets."
    assert done.stdout.splitlines()[-1].endswith("then forge read SAVE")
    doc = repo.git("show", "story/SAVE:plans/SAVE.md", cwd=top)
    for expected in ("# Keep baskets for later", "- Shoppers save their basket.",
                     "- Shoppers open a saved basket.", "Shoppers lose baskets when they leave.",
                     "1. **A shopper can save a basket.**", "2. **A saved basket returns after sign-in.**"):
        assert expected in doc
    assert "<What the people who use this will notice" not in doc
    state = json.loads(repo.git("show", "story/SAVE:.factory/stories/SAVE/story.json", cwd=top))
    assert state["status"] == "planning"
    next_step = repo.forge("next", cwd=top)
    assert next_step.returncode == 0, next_step.stdout + next_step.stderr
    assert "forge read SAVE" in next_step.stdout
    occupied = _offer(intake, "Another basket idea")
    refused = _back(intake, occupied, reply)
    assert refused.returncode == 1
    assert "already" in refused.stderr.lower()
