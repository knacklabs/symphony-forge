"""Compaction keeps Forge's current state beside the agent's own notes."""
import json
import subprocess

STORY = "FIX-CLIENT-REPOS-LOSE-THE-AGENT-S-STATE-THE"


def test_1_sync_ships_precompact_handoff_and_hook_preserves_decisions(repo, monkeypatch):
    monkeypatch.setenv("FORGE_NOW", "2026-09-28T12:00:00+00:00")
    version = repo.forge("--version").stdout.split()[-1]
    repo.write("forge.toml", f'version = "{version}"\nrepo = "client"\ntest = "true"\n')
    repo.git("add", "forge.toml")
    repo.git("commit", "-q", "-m", "Pin Forge")
    repo.git("push", "-q", "origin", "main")
    repo.git("checkout", "-q", "-b", "fix/handoff")

    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stderr
    shipped_commands = []
    for path in (".claude/settings.json", ".codex/hooks.json"):
        hooks = json.loads((repo.path / path).read_text(encoding="utf-8"))["hooks"]
        commands = [hook["command"] for group in hooks["PreCompact"]
                    for hook in group["hooks"]]
        assert len(commands) == 1 and "forge hook handoff" in commands[0]
        shipped_commands.append(commands[0])

    def compact(command):
        return subprocess.run(["sh", "-c", command], cwd=repo.path,
                              input='{"hook_event_name":"PreCompact","trigger":"auto"}',
                              capture_output=True, text=True)

    before = repo.forge("next")
    assert before.returncode == 0, before.stderr
    first = compact(shipped_commands[0])
    assert first.returncode == 0, first.stderr
    handoff = repo.path / ".git" / "forge" / "handoff.md"
    content = handoff.read_text(encoding="utf-8")
    assert "## Current state (2026-09-28)" in content
    assert before.stdout.strip() in content
    assert "## Decisions and lessons\n" in content

    notes = "## Decisions and lessons\n- The owner chose the simpler path.\n- Keep the release small.\n"
    handoff.write_text(content.split("## Decisions and lessons\n")[0] + notes, encoding="utf-8")
    started = repo.forge("fix", "start", "Refresh handoff state", "--done", "The new fix is listed")
    assert started.returncode == 0, started.stderr
    after = repo.forge("next")
    assert after.returncode == 0, after.stderr
    assert after.stdout != before.stdout
    assert "The fix refresh-handoff-state is started" in after.stdout
    second = compact(shipped_commands[1])
    assert second.returncode == 0, second.stderr
    updated = handoff.read_text(encoding="utf-8")
    assert after.stdout.strip() in updated
    assert before.stdout.strip() not in updated
    assert updated.endswith(notes)
    assert updated.count("## Current state (") == 1
    assert "handoff.md" not in repo.git("ls-files", "--others", "--exclude-standard")

    for path in (".claude/skills/forge/SKILL.md", ".codex/skills/forge/SKILL.md"):
        skill = " ".join((repo.path / path).read_text(encoding="utf-8").split())
        for phrase in ("`.git/forge/handoff.md`", "at each milestone", "read it first",
                       "never committed"):
            assert phrase in skill
