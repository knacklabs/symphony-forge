"""Agent Must findings hold close; Should advice and unsigned prototypes do not."""
import pytest

from test_agents_skill import BRIEF
from test_close import GREEN, STORY_DOC, blocked, env  # noqa: F401 (fixture)
from test_score_notes import _client_repo as setup_client, _scored
from test_worker import calls, install_claude

STORY = "FORGE-AGENTS-1"

REVIEW_RULE = (
    "Report agent, chat or assistant code that this change adds or changes, and that breaks "
    "a Must rule of the agents skill (.codex/skills/agents/SKILL.md), as a P1 finding titled "
    "`Agents: <the rule's heading>`. Report a broken Should rule as a P2 finding titled "
    "`Agents advice: <the rule's heading>` scored Gain 1 or 2, so it stays advice. Agent code, "
    "including its system prompts, tool descriptions and prompt versions, is agent code, so "
    "a change that only edits a prompt is checked. Agent code that the default branch "
    "already has is not a finding."
)


@pytest.mark.parametrize("adopted", [False, True], ids=["new-client", "adopted-v1.2.2"])
def test_3_reviews_hold_agent_work_that_breaks_a_must_rule(env, tmp_path, monkeypatch, adopted):
    # Audit: real work delivers the rule and real close distinguishes Must, Should and demo.
    # A Markdown prompt read by production code must receive normal review even when no
    # application code changes. The old docs classifier silently made its Must finding advice.
    # Existing docs tests cover only test consumers, not runtime prompts. Extend this owner
    # rather than repeat the inline-prompt scenario. Missing/overbroad floors also break it.
    # Database coverage cannot detect agent titles or prompt-only edits. Only external tools are faked;
    # no production seam is needed. Prompt text is the reviewer's independent contract.
    setup_client(env, tmp_path, adopted)
    env.checks(GREEN)
    repo = env.repo
    no_hooks = tmp_path / "fixture-no-hooks"
    no_hooks.mkdir(exist_ok=True)
    git = repo.git

    def fixture_git(*args, cwd=None):
        if args and args[0] in {"commit", "push"}:
            args = ("-c", f"core.hooksPath={no_hooks}", *args)
        return git(*args, cwd=cwd)

    with monkeypatch.context() as patch:
        patch.setattr(repo, "git", fixture_git)
        env.commit(repo.path, "app.py", "from pathlib import Path\n"
                   "SYSTEM_PROMPT = Path('docs/booking.md').read_text(encoding='utf-8')\n",
                   "Load the booking prompt")
        env.commit(repo.path, "docs/booking.md", "Use the existing booking workflow.\n",
                   "Keep the current booking prompt")
        repo.git("push", "-q", "origin", "main")
        item, where = env.start_approved_task(
            STORY_DOC, changes={"docs/booking.md": "Use an open-ended loop for every request.\n"})
    log = install_claude(repo)
    worked = repo.forge("work", item)
    assert worked.returncode == 0, worked.stdout + worked.stderr
    assert BRIEF in " ".join(calls(log)[-1]["brief"].split())
    title = "Agents: Start with the simplest thing that works"
    env.reviews(blocked(_scored("P1", title,
                               "Gain 2, Work 3, Harm 1\nKnown steps use a free agent loop.",
                               "docs/booking.md")))
    closed = env.close(item)
    output = closed.stdout + closed.stderr
    assert closed.returncode == 1, output
    assert "The review left serious findings open" in output
    assert title in output
    assert "Gain 4, Work 2, Harm 1 (floor: agents)" in output
    assert REVIEW_RULE in " ".join(env.prompt().split())

    env.commit(where, "docs/booking.md", "Follow the fixed booking workflow.\n",
               "Use the booking workflow")
    advice = "Agents advice: Route by difficulty"
    env.reviews(blocked(_scored("P2", advice,
                               "Gain 2, Work 2, Harm 2\nEasy turns use the larger model.",
                               "docs/booking.md")))
    released = env.close(item)
    output = released.stdout + released.stderr
    assert released.returncode == 0, output
    assert advice in output
    assert "Gain 2, Work 2, Harm 2" in output
    assert "(floor: agents)" not in output

    if adopted:
        # The earlier-adopted client's unsigned demo keeps the existing P0-only contract.
        (repo.path / "docs/decisions/0001-client-signoff.md").unlink()
        config = (repo.path / "forge.toml").read_text("utf-8")
        with monkeypatch.context() as patch:
            patch.setattr(repo, "git", fixture_git)
            env.commit(repo.path, "forge.toml", config + 'repo = "client"\nstage = "prototype"\n',
                       "Return to the unsigned demo")
            repo.git("push", "-q", "origin", "main")
        demo, _ = env.start_fix(
            {"docs/booking.md": "Use an open-ended loop for every request.\n"},
            allow_large="Prototype before sign-off")
        env.reviews(blocked(_scored("P1", title,
                                   "Gain 2, Work 3, Harm 1\nKnown steps use a free agent loop.",
                                   "docs/booking.md")))
        closed = env.close(demo)
        output = closed.stdout + closed.stderr
        assert closed.returncode == 0, output
        assert title in output
        assert "Gain 4, Work 2, Harm 1 (floor: agents)" in output
        prompt = " ".join(env.prompt().split())
        assert "Check only these three things:" in prompt
        assert "agents skill" not in prompt
        assert "Agents advice:" not in prompt
