"""Build rounds for the coordinating app's tool run as that session's own subagents."""
import json
import os
import re
from pathlib import Path

import pytest

from conftest import ROOT, _install
from test_task import story
from test_tools_session_hold import Session
from test_worker import calls, install_claude

STORY = "FORGE-TOOLS-1"
MODELS = {"claude": ('[models.build]\nmodel = "sonnet"\neffort = "medium"\n'
                     '[models.fix]\nmodel = "haiku"\neffort = "low"\n'
                     '[models.lite]\nmodel = "opus"\neffort = "high"\n'),
          "codex": ('[models.build]\nmodel = "gpt-6-sol"\neffort = "high"\n'
                    '[models.fix]\nmodel = "gpt-6-luna"\neffort = "low"\n'
                    '[models.lite]\nmodel = "gpt-6-mini"\neffort = "medium"\n')}


@pytest.mark.parametrize("tool", ["claude", "codex"])
def test_3_build_rounds_run_as_session_subagents(repo, gh, monkeypatch, tmp_path, tool):
    claude_log = install_claude(repo)
    _install(repo.bin, "codex-app-server", (ROOT / "tests/stubs/codex-app-server").read_text("utf-8"))
    monkeypatch.setenv("CODEX_BIN", str(repo.bin / (
        "codex-app-server.cmd" if os.name == "nt" else "codex-app-server")))
    data = tmp_path / "data"  # no Codex SDK installed: a native round needs none
    data.mkdir()
    monkeypatch.setenv("XDG_DATA_HOME", str(data))
    if tool == "claude":
        monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
        monkeypatch.setenv("CLAUDECODE", "1")
    version = repo.forge("--version").stdout.split()[-1]
    setting = 'workers = "claude"' if tool == "claude" else 'tools = "codex"\nworkers = "claude"'
    repo.write("forge.toml", f'version = "{version}"\nrepo = "forge-source"\n{setting}\n'
                             f'test = "pytest -q"\n{MODELS[tool]}')
    repo.write("plans/roadmap.json", json.dumps({"items": [{"key": "BOARD"}]}))
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "Pin Forge")
    repo.git("push", "-q", "origin", "main")
    story(repo)
    repo.git("worktree", "add", "-q", str(tmp_path / "story"), "story/BOARD")  # next reads it
    folder = repo.path.parent / f"{repo.path.name}-BOARD-HELP"
    home = tmp_path / "codex-home"
    home.mkdir()
    (home / "config.toml").write_text("".join(
        f'[projects.{json.dumps(str(path))}]\ntrust_level = "trusted"\n'
        for path in (folder, repo.path.parent / f"{repo.path.name}-BOARD-PAGE")), "utf-8")
    monkeypatch.setenv("CODEX_HOME", str(home))
    assert repo.forge("task", "start", "BOARD/HELP").returncode == 0
    host = Session(repo, tmp_path / "host", tool + "-session")
    try:
        def lane(item):
            shown = repo.forge("lanes", "--json")
            return [entry for entry in json.loads(shown.stdout)["agents"]["entries"]
                    if entry["item"] == item]

        def handout(item, role, cwd=None):
            given = host.forge("work", item, cwd=cwd)
            assert given.returncode == 0, given.stdout + given.stderr
            out = given.stdout
            checkout = re.search(rf"background {role} subagent of this session, working in (.+)\.\n",
                                 out)[1]
            whole = Path(re.search(r"(?i)start a new \w+ subagent with: Read (.+\.fresh\.md) and follow it",
                                   out)[1])
            assert checkout in whole.read_text("utf-8")
            number = int(re.search(rf"forge handback {re.escape(item)} --round (\d+) --subagent", out)[1])
            [entry] = lane(item)
            assert entry["native"] is True and entry["kind"] == "work"
            return given, Path(checkout), number

        def handback(item, number, text, cwd=None):
            return host.forge("handback", item, "--round", str(number), "--subagent", "w1",
                              input=text, cwd=cwd)

        # The first round starts no program and hands out the whole brief for the task's checkout.
        given, checkout, number = handout("BOARD/HELP", "worker")
        assert checkout.resolve() == folder.resolve()
        assert "Start a new worker subagent with" in given.stdout
        assert calls(claude_log) == [] and not (repo.bin / "codex-app-server.jsonl").exists()
        assert "subagent" in repo.forge("next").stdout
        head = repo.git("rev-parse", "HEAD", cwd=folder)
        busy = host.forge("work", "BOARD/HELP")
        assert busy.returncode == 1 and repo.git("rev-parse", "HEAD", cwd=folder) == head

        # Uncommitted work gets the commit nudge and keeps the place; the second hand-back frees it.
        (folder / "web").mkdir()
        (folder / "web/help.py").write_text("WORDS = {}\n", "utf-8")
        nudged = handback("BOARD/HELP", number, "Built it.")
        assert nudged.returncode == 0, nudged.stdout + nudged.stderr
        assert "Send this to subagent w1, then hand back again:" in nudged.stdout
        assert "Commit your work on this branch first." in nudged.stdout
        assert lane("BOARD/HELP")
        repo.git("add", "-A", cwd=folder)
        repo.git("commit", "-q", "-m", "Add the words", cwd=folder)
        done = handback("BOARD/HELP", number, "Committed.")
        assert done.returncode == 0, done.stdout + done.stderr
        assert lane("BOARD/HELP") == []
        timings = (repo.path / ".git/forge/timings.jsonl").read_text("utf-8")
        assert '"item": "BOARD/HELP", "round": 1, "step": "worker round"' in timings

        # The next round continues the subagent on the role's model; a changed forge.toml, the
        # pin included, is put back, and a closing question is recorded.
        given, _, number = handout("BOARD/HELP", "worker")
        model = "sonnet, medium" if tool == "claude" else "gpt-6-sol, high"
        assert f"({model})" in given.stdout
        assert "Continue subagent w1 with: Read " in given.stdout
        assert "If this session can't reach it, start a new worker subagent with" in given.stdout
        settings = (folder / "forge.toml").read_text("utf-8")
        (folder / "forge.toml").write_text(settings.replace(version, "v9.9.9"), "utf-8")
        repo.git("commit", "-q", "-am", "Try another release", cwd=folder)
        (folder / "forge.toml").write_text(settings + "# scratch\n", "utf-8")
        asked = handback("BOARD/HELP", number, "Done.\n\nQuestion: Which colour?", cwd=folder)
        assert asked.returncode == 0, asked.stdout + asked.stderr
        assert (folder / "forge.toml").read_text("utf-8") == settings
        assert repo.git("status", "--porcelain", cwd=folder) == ""
        assert "Question: Which colour?" in asked.stdout
        waiting = host.forge("work", "BOARD/HELP")
        assert waiting.returncode == 1 and "Which colour?" in waiting.stderr

        if tool == "codex":
            # With one tool and no session open, nothing runs.
            monkeypatch.delenv("CODEX_THREAD_ID")
            head = repo.git("rev-parse", "HEAD", cwd=folder)
            refused = repo.forge("work", "BOARD/HELP", "--note", "Blue.")
            assert refused.returncode == 1
            assert "none is open here, so nothing ran" in refused.stderr
            assert repo.git("rev-parse", "HEAD", cwd=folder) == head
            return

        # A fix uses the fixer role; land stops at the handout and closes after the hand-back.
        made = repo.forge("fix", "start", "Tidy the words", "--done", "The words read well",
                          "--slug", "tidy-words")
        assert made.returncode == 0, made.stdout + made.stderr
        gh.respond("pr", "list", stdout="[]")
        landed = host.forge("land", "tidy-words")
        assert landed.returncode == 0, landed.stdout + landed.stderr
        assert "background fixer subagent" in landed.stdout
        assert "Next: run the subagent, forge handback tidy-words, then forge land tidy-words" in landed.stdout
        assert "Closing" not in landed.stdout
        fix = Path(re.search(r"working in (.+)\.\n", landed.stdout)[1])
        (fix / "notes.txt").write_text("tidy\n", "utf-8")
        repo.git("add", "-A", cwd=fix)
        repo.git("commit", "-q", "-m", "Tidy", cwd=fix)
        number = int(re.search(r"--round (\d+)", landed.stdout)[1])
        assert handback("tidy-words", number, "Tidied.").returncode == 0
        assert "Closing tidy-words." in host.forge("land", "tidy-words").stdout

        # Under split, a user-facing part coordinated from Claude Code is a frontend subagent.
        assert repo.forge("task", "start", "BOARD/PAGE").returncode == 0
        page = repo.path.parent / f"{repo.path.name}-BOARD-PAGE"
        (page / "forge.toml").write_text((page / "forge.toml").read_text("utf-8").replace(
            'workers = "claude"', 'workers = "split"'), "utf-8")
        repo.git("commit", "-q", "-am", "Split workers", cwd=page)
        handout("BOARD/PAGE", "frontend")
        assert calls(claude_log) == []
    finally:
        host.close()
