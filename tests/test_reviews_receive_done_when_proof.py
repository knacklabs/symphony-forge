"""Proof-list prompt contracts prove delivery, not whether a model obeys them."""
import shutil
from pathlib import Path

import pytest

from test_close import body, env  # noqa: F401
from test_setup import _fresh_client
from test_worker import calls, install_claude

STORY = "FIX-REVIEWS-FIND-MISSING-CASES-TWO-OR-THREE"
WORKER_RULE = "each Done-when item you cover and every detail next to the test or check that proves it, or marked `missing`"
REVIEW_RULE = "Check every entry against the code and its named proof, including every Done-when detail"


def flat(text):
    return " ".join(text.split())


@pytest.mark.parametrize("adopted", [False, True], ids=["init", "sync-after-earlier-adoption"])
def test_1_clients_receive_proof_list_instructions(repo, gh, tmp_path, monkeypatch, adopted):
    log = install_claude(repo)
    monkeypatch.setenv("STUB_CLAUDE_COMMIT_FROM", "1")
    version = repo.forge("--version").stdout.split()[-1]
    if adopted:
        shutil.copytree(Path(__file__).parent / "fixtures/adopted-v1.2.2/client",
                        repo.path, dirs_exist_ok=True)
        repo.git("add", "-A")
        repo.git("commit", "-q", "-m", "Adopt on an earlier release")
        repo.git("push", "-q", "origin", "main")
        client = repo.path
    else:
        client, made = _fresh_client(repo, gh, tmp_path)
        assert made.returncode == 0, made.stdout + made.stderr
    if not adopted:
        assert WORKER_RULE in flat((client / ".codex/skills/forge/SKILL.md").read_text("utf-8"))
    config = client / "forge.toml"
    text = config.read_text("utf-8").replace('version = "v1.2.2"', f'version = "{version}"')
    text = text.replace('workers = "codex"', 'workers = "claude"').replace(
        'workers = "split"', 'workers = "claude"')
    if adopted:
        config.write_text(text, encoding="utf-8")
        repo.git("add", "-A", cwd=client)
        repo.git("commit", "-q", "-m", "Use the installed Forge", cwd=client)
        repo.git("push", "-q", "origin", "main", cwd=client)
    made = repo.forge("fix", "start", "Check proof guidance", "--done", "Proof is listed", cwd=client)
    assert made.returncode == 0, made.stdout + made.stderr
    where = Path(made.stdout.splitlines()[0].rsplit(" in ", 1)[1])
    if not adopted:
        (where / "forge.toml").write_text(text, encoding="utf-8")
    if adopted:
        synced = repo.forge("sync", cwd=where)
        assert synced.returncode == 0, synced.stdout + synced.stderr
        assert (where / "forge.toml").read_text("utf-8") == text
    for host in (".codex", ".claude"):
        skill = flat((where / host / "skills/forge/SKILL.md").read_text("utf-8"))
        assert WORKER_RULE in skill
        assert REVIEW_RULE in skill
    built = repo.forge("work", "check-proof-guidance", cwd=where)
    assert built.returncode == 0, built.stdout + built.stderr
    brief = flat(calls(log)[-1]["brief"])
    assert "Proof list:" in brief
    assert WORKER_RULE in brief
    assert "pull request" in brief


@pytest.mark.parametrize("kind", ["fix", "task"])
def test_2_close_delivers_the_whole_proof_list_to_pr_and_first_review(env, kind):
    if kind == "fix":
        item, where = env.start_fix()
    else:
        item, where = env.start_approved_task(
            (env.repo.path / "plans/SHOP.md").read_text("utf-8"))
    proof = "Proof list:\n- Greeting, including returning readers: tests/test_greeting.py::test_returning\n- Empty greeting: missing"
    env.repo.git("commit", "--allow-empty", "-q", "-m", "List the proof", "-m", proof, cwd=where)
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert len(env.review_calls()) == 1
    prompt = env.prompt()
    assert proof in prompt
    assert REVIEW_RULE in flat(prompt)
    assert "Report every missing case you find in this round" in flat(prompt)
    assert proof in body(env.gh_calls("pr", "create")[-1])
    # An empty proof-only commit changes the review input even when the code stays identical.
    changed = proof.replace("Empty greeting: missing", "Empty greeting: tests/test_greeting.py::test_empty")
    env.repo.git("commit", "--allow-empty", "-q", "-m", "Complete the proof", "-m", changed, cwd=where)
    assert env.close(item).returncode == 0
    assert len(env.review_calls()) == 2
    assert changed in env.prompt()
    # A later worker commit must not inherit an older round's list.
    env.repo.git("commit", "--allow-empty", "-q", "-m", "Work without proof", cwd=where)
    assert env.close(item).returncode == 0
    assert len(env.review_calls()) == 3
    assert changed not in env.prompt()
    assert "missing list or entry is a P1" in env.prompt()
