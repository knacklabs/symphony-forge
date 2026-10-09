"""Synced clients get review and cold-read instructions that block only on likely, real problems."""
import shutil
import sys
from pathlib import Path

import pytest

import conftest
from test_close import env  # noqa: F401
from test_story import READER
from test_worker import calls, install_claude

STORY = "FIX-LEAN-REVIEW-PROMPTS"


def flat(text):
    return " ".join(text.split())


@pytest.mark.parametrize("adopted", [False, True], ids=["new-client", "adopted-on-v1.2.2"])
def test_1_review_and_cold_read_weigh_likelihood(env, adopted):
    repo = env.repo
    version = repo.forge("--version").stdout.split()[-1]
    if adopted:
        shutil.copytree(Path(__file__).parent / "fixtures/adopted-v1.2.2/client",
                        repo.path, dirs_exist_ok=True)
        repo.git("add", "-A")
        repo.git("commit", "-q", "-m", "Adopt on the earlier release")
        config = (repo.path / "forge.toml").read_text("utf-8")
        config = config.replace('version = "v1.2.2"', f'version = "{version}"')
        config = config.replace('workers = "codex"', 'workers = "claude"')
        config = config.replace('[models.lite]\nmodel = "gpt-6.1-sol"',
                                '[models.lite]\nmodel = "sonnet"')
        config = config.replace('subagents = "gpt-6-luna"\nsubagent_effort = "max"\n', "")
    else:
        config = ((repo.path / "forge.toml").read_text("utf-8")
                  + 'repo = "client"\nstage = "live"\n'
                  + 'models.lite = { model = "sonnet", effort = "medium" }\n'
                  + 'models.grill.claude = { model = "opus", effort = "high" }\n')
    env.commit(repo.path, "forge.toml", config, "Use the installed Forge")
    repo.git("push", "-q", "origin", "main")
    item, where = env.start_fix()
    synced = repo.forge("sync", cwd=where)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    repo.git("add", "-A", cwd=where)
    repo.git("commit", "-q", "-m", "Sync the client instructions", cwd=where)

    log = install_claude(repo)
    conftest._install(repo.bin, "claude", READER.format(python=sys.executable))
    env.commit(where, "docs/specs/basket.md", "# Basket\n\n## Why\n\nKeep a basket.\n")
    read = repo.forge("read", "basket", cwd=where)
    assert read.returncode == 0, read.stdout + read.stderr
    cold_read = flat(calls(log)[-1]["prompt"])
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    review = flat(env.prompt())

    # Compare the whole boundary, including both review gates and cold-read plan gaps.
    boundary = [prompt.split("## What counts", 1)[1].split("at the start of its evidence.")[0]
                for prompt in (cold_read, review)]
    assert boundary[0] == boundary[1]
    for rule in ("Report exactly what falls inside this boundary: nothing outside it, and nothing "
                 "inside it left out.",
                 "- Functional: a defect on a path people or agents normally hit",
                 "- Security: a security gap", "- Data loss: data lost, corrupted or exposed.",
                 "- Scale: a scale or performance problem at a realistic size the finding names, a "
                 "cost repeated on every normal run, or growth with no bound.",
                 "- Not done: an unmet Done-when item, or a doc the change delivers that "
                 "contradicts itself or a recorded decision.",
                 "- Test: a missing or hollow test for a Done-when item's own behaviour.",
                 "it falls under Security or Data loss or the finding names a "
                 "realistic scenario that makes it likely in normal use: - a rare combination "
                 "that needs an unusual sequence",
                 "a platform, shell or tool version the repo doesn't support or the change is "
                 "unlikely to meet",
                 "- hardening beyond what the item promises; - style, wording and preferences; "
                 "- a duplicate of another finding in this round.",
                 "An edge case is inside the boundary only when a Done-when item names it, when "
                 "the finding names a realistic scenario that makes it likely in normal use",
                 "Every finding you raise names its line as `Raise: <line>`"):
        assert rule in boundary[0], rule
    assert "- Moving part: a new dependency" in boundary[0]
    assert "- Plan gap: something that would make the build wrong or stall it" in boundary[0]
    assert "- Gate: a P1 this page names elsewhere" in boundary[0]

    # Review: only Raise lines block; advice is limited to the named forms; one-line findings.
    assert ("Every finding under a Raise line is P0 or P1 and blocks the merge. P2 and P3 are only "
            "the advice forms this page names") in review
    for rule in ("Write each finding as one line naming the defect and its impact, then brief "
                 "evidence", "No speculative suggestions",
                 "Sweep the sibling cases normal use reaches",
                 # Kept: the proof-list check and the previous findings carry over.
                 "Check every entry against the code and its named proof",
                 "recheck them against this branch"):
        assert rule in review, rule
    # Cold read: likely cases and traps only.
    for rule in ("Report a likely case no rule or test covers as `Unproven: item <n>: <case>`",
                 "Raise a platform or shell trap only when that platform is likely for the change."):
        assert rule in cold_read, rule
    notes = flat((where / "docs/specs/basket.read.md").read_text("utf-8"))
    assert "A finding inside What counts is cut or deferred." in notes

    # The coordinator guide synced into the repo holds the orchestrator to the same boundary.
    for guide in (where / ".claude/skills/forge/SKILL.md", where / ".codex/skills/forge/SKILL.md"):
        text = flat(guide.read_text("utf-8"))
        assert ("every P0 or P1 finding inside it gets a fix round with `forge work <item>`, never "
                "a dismissal for being unnecessary, rare or low value") in text, guide
        assert "Dismiss only a finding outside the boundary or factually wrong" in text, guide
        assert "never kept as unnecessary" in text, guide
