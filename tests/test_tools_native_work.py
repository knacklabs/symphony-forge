"""Build rounds for the coordinating app's tool run as that session's own subagents."""
import json
import os
import re
import shutil
from pathlib import Path

import pytest

from conftest import ROOT, _install
from test_conflicting_pull_requests_stop_check_waits import _publish_default
from test_setup import _fresh_client
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


@pytest.mark.parametrize("history", ["new", "adopted"])
@pytest.mark.parametrize("tool", ["claude", "codex"])
def test_3_build_rounds_run_as_session_subagents(repo, gh, monkeypatch, tmp_path, tool, history):
    if history == "new":  # a client repo made by forge init
        made = _fresh_client(repo, gh, tmp_path)
        assert made[1].returncode == 0, made[1].stdout + made[1].stderr
        repo.path = made[0]
    else:  # a client adopted on an earlier release, moved to this one
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path, dirs_exist_ok=True)
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
    repo.git("switch", "-qc", "fix/settings")
    # An earlier-adopted repo may have no [models] table: built-in models apply.
    models = MODELS[tool] if history == "new" else ""
    repo.write("forge.toml", f'version = "{version}"\nrepo = "client"\n{setting}\n'
                             f'test = "pytest -q"\n{models}')
    repo.write("plans/roadmap.json", json.dumps({"items": [{"key": "BOARD"}]}))
    repo.write(".factory/fixes/settings.json", json.dumps({
        "kind": "fix", "branch": "fix/settings", "status": "working",
        "why": "Choose the tools", "done_when": "forge.toml names the tools"}))
    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stdout + synced.stderr
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "Pin Forge")
    repo.git("switch", "-q", "main")
    repo.git("merge", "-q", "--ff-only", "fix/settings")
    _publish_default(repo, Path(repo.git("remote", "get-url", "origin")).as_posix())
    story(repo)
    repo.git("worktree", "add", "-q", str(tmp_path / "story"), "story/BOARD")  # next reads it
    folder = repo.path.parent / f"{repo.path.name}-BOARD-HELP"
    home = tmp_path / "codex-home"
    home.mkdir()
    monkeypatch.setenv("CODEX_HOME", str(home))
    assert repo.forge("task", "start", "BOARD/HELP").returncode == 0
    host = Session(repo, tmp_path / "host", tool + "-session")
    try:
        if tool == "codex":
            # A native Codex round still needs Codex to trust the project, for the session's hooks.
            head = repo.git("rev-parse", "HEAD", cwd=folder)
            untrusted = host.forge("work", "BOARD/HELP")
            assert untrusted.returncode == 1 and "Codex doesn't trust this project" in untrusted.stderr
            assert repo.git("rev-parse", "HEAD", cwd=folder) == head
        (home / "config.toml").write_text("".join(
            f'[projects.{json.dumps(str(path))}]\ntrust_level = "trusted"\n'
            for path in (folder, repo.path.parent / f"{repo.path.name}-BOARD-PAGE")), "utf-8")

        def lane(item):
            shown = repo.forge("lanes", "--json")
            return [entry for entry in json.loads(shown.stdout)["agents"]["entries"]
                    if entry["item"] == item]

        def handout(item, role, *note, cwd=None):
            given = host.forge("work", item, *note, cwd=cwd)
            assert given.returncode == 0, given.stdout + given.stderr
            out = given.stdout
            checkout = re.search(rf"background {role} subagent of this session, working in (.+)\.\r?\n",
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
        # The worker role file names the model forge work prints, built-in ones included.
        printed = re.search(r"Building BOARD/HELP with \w+ \(([^,]+),", given.stdout)[1]
        role = folder / (".codex/agents/worker.toml" if tool == "codex" else ".claude/agents/worker.md")
        assert re.search(rf'^model(:| =) "{re.escape(printed)}"', role.read_text("utf-8"), re.M), printed
        assert checkout.resolve() == folder.resolve()
        assert "Start a new worker subagent with" in given.stdout
        assert calls(claude_log) == [] and not (repo.bin / "codex-app-server.jsonl").exists()
        assert "subagent" in repo.forge("next").stdout
        board = repo.forge("board", "--json")
        assert board.returncode == 0, board.stdout + board.stderr
        [part] = [child for entry in json.loads(board.stdout)["items"]
                  for child in entry.get("children", []) if "BOARD/HELP" in (child.get("key"), child.get("id"))]
        assert part["activity"] == {"status": "running", "action": "work"}
        head = repo.git("rev-parse", "HEAD", cwd=folder)
        busy = host.forge("work", "BOARD/HELP")
        assert busy.returncode == 1 and repo.git("rev-parse", "HEAD", cwd=folder) == head

        # Uncommitted work gets the commit nudge and keeps the place; a second hand-back with the
        # work still uncommitted warns and frees it.
        (folder / "web").mkdir(exist_ok=True)
        (folder / "web/help.py").write_text("WORDS = {}\n", "utf-8")
        nudged = handback("BOARD/HELP", number, "Built it.")
        assert nudged.returncode == 0, nudged.stdout + nudged.stderr
        assert "Send this to subagent w1, then hand back again:" in nudged.stdout
        assert "Commit your work on this branch first." in nudged.stdout
        assert lane("BOARD/HELP")
        done = handback("BOARD/HELP", number, "Still not committed.")
        assert done.returncode == 0, done.stdout + done.stderr
        assert "Warning: the worker ended its round with changes left uncommitted" in done.stdout
        assert "web/help.py" in done.stdout
        assert lane("BOARD/HELP") == []
        repo.git("add", "-A", cwd=folder)
        repo.git("commit", "-q", "-m", "Add the words", cwd=folder)
        assert "Next: forge close BOARD/HELP" in repo.forge("next").stdout  # the round is finished
        timings = (repo.path / ".git/forge/timings.jsonl").read_text("utf-8")
        assert '"item": "BOARD/HELP", "round": 1, "step": "worker round"' in timings
        events = [json.loads(line) for line in
                  (repo.path / ".git/forge/events.jsonl").read_text("utf-8").splitlines()]
        [begun] = [e for e in events if e["event"] == "run start" and e["item"] == "BOARD/HELP"]
        [ended] = [e for e in events if e["event"] == "run end" and e["item"] == "BOARD/HELP"]
        assert (begun["kind"], begun["round"], begun["family"]) == ("work", 1, tool)
        assert (ended["run_id"], ended["outcome"]) == (begun["id"], "completed")

        # The next round continues the subagent on the role's model; an uncommitted forge.toml
        # edit, even a broken one, is put back, and a closing question is recorded.
        given, _, number = handout("BOARD/HELP", "worker")
        model = {("claude", "new"): "sonnet, medium", ("codex", "new"): "gpt-6-sol, high",
                 ("claude", "adopted"): "claude-sonnet-5-5, xhigh",
                 ("codex", "adopted"): "gpt-6.1-sol, medium"}[tool, history]
        assert f"({model})" in given.stdout
        short = Path(re.search(r"Continue subagent w1 with: Read (.+) and follow it", given.stdout)[1])
        assert "The earlier brief in this conversation still applies." in short.read_text("utf-8")
        assert str(folder.resolve().as_posix()) in short.read_text("utf-8")
        assert "If this session can't reach it, start a new worker subagent with" in given.stdout
        settings = (folder / "forge.toml").read_text("utf-8")
        before = repo.git("rev-parse", "HEAD", cwd=folder)
        (folder / "forge.toml").write_text(settings + "[[[ not settings\n", "utf-8")
        # The item's pull request is published, so its record is refreshed with the question.
        with (repo.path / ".git/forge/events.jsonl").open("a", encoding="utf-8") as events:
            events.write(json.dumps({"id": "published", "item": "BOARD/HELP", "round": 1,
                                     "event": "pull request published", "at": "2026-10-01T00:00:00+00:00"}) + "\n")
        gh.respond("pr", "list", stdout=json.dumps([{"number": 7, "state": "OPEN", "body": "<!-- forge:begin -->\nOld record\n<!-- forge:end -->",
                                                     "isDraft": False}]))
        gh.respond("pr", "edit")
        asked = handback("BOARD/HELP", number, "Done.\n\nQuestion: Which colour?", cwd=folder)
        assert any(call[:3] == ["pr", "edit", "7"] for call in gh.calls())
        assert asked.returncode == 0, asked.stdout + asked.stderr
        assert (folder / "forge.toml").read_text("utf-8") == settings
        assert repo.git("status", "--porcelain", cwd=folder) == ""
        assert repo.git("rev-parse", "HEAD", cwd=folder) == before
        assert "Question: Which colour?" in asked.stdout
        waiting = host.forge("work", "BOARD/HELP")
        assert waiting.returncode == 1 and "Which colour?" in waiting.stderr

        # A subagent that ends with no message fails its round and frees the place.
        _, _, number = handout("BOARD/HELP", "worker", "--note", "Blue.")
        empty = handback("BOARD/HELP", number, "")
        assert empty.returncode == 1
        assert "ended with no message, so Forge recorded the round as failed" in empty.stderr
        assert lane("BOARD/HELP") == []
        ends = [json.loads(line) for line in
                (repo.path / ".git/forge/events.jsonl").read_text("utf-8").splitlines()]
        assert [e["outcome"] for e in ends if e["event"] == "run end"
                and e["item"] == "BOARD/HELP"][-1] == "failed"

        # A round that commits its work and a forge.toml change, pin included, hands back from
        # the item's checkout: no nudge, and the settings change is reversed in a new commit.
        # forge.local.toml's model reaches the hand-out, which the role files can't carry.
        local = "gpt-6-local" if tool == "codex" else "claude-local"
        (repo.path / "forge.local.toml").write_text(
            f'[models.build]\nmodel = "{local}"\neffort = "low"\n', "utf-8")
        given, _, number = handout("BOARD/HELP", "worker")
        (repo.path / "forge.local.toml").unlink()
        assert f"Start it on {local} at low effort, over the role's own model." in given.stdout
        handed = repo.git("rev-parse", "HEAD", cwd=folder)
        (folder / "web/help.py").write_text("WORDS = {'done': 'Done'}\n", "utf-8")
        (folder / "forge.toml").write_text(settings.replace(version, "v9.9.9"), "utf-8")
        repo.git("commit", "-q", "-am", "Finish the words and try another release", cwd=folder)
        finished = handback("BOARD/HELP", number, "Committed everything.", cwd=folder)
        assert finished.returncode == 0, finished.stdout + finished.stderr
        assert "Send this to subagent" not in finished.stdout and "Warning" not in finished.stdout
        assert lane("BOARD/HELP") == []
        assert (folder / "forge.toml").read_text("utf-8") == settings
        assert repo.git("status", "--porcelain", cwd=folder) == ""
        assert repo.git("log", "-1", "--format=%s", cwd=folder) == (
            "Restore forge.toml; settings change in their own fix")
        assert repo.git("rev-list", "--count", f"{handed}..HEAD", cwd=folder) == "2"

        # A fix uses the fixer role; land stops at the handout and closes after the hand-back.
        made = repo.forge("fix", "start", "Tidy the words", "--done", "The words read well",
                          "--slug", "tidy-words")
        assert made.returncode == 0, made.stdout + made.stderr
        fix = next(Path(line[9:]) for line in repo.git("worktree", "list", "--porcelain").splitlines()
                   if line.startswith("worktree ") and line.endswith("tidy-words"))
        with (home / "config.toml").open("a", encoding="utf-8") as trusted:
            trusted.write(f'[projects.{json.dumps(str(fix))}]\ntrust_level = "trusted"\n')
        # Close's failed test run makes this round a fix round.
        record = fix / ".factory/fixes/tidy-words.json"
        record.write_text(json.dumps({**json.loads(record.read_text("utf-8")),
                                      "tests": "FAILED tests/test_words.py"}), "utf-8")
        gh.respond("pr", "list", stdout="[]")
        landed = host.forge("land", "tidy-words")
        assert landed.returncode == 0, landed.stdout + landed.stderr
        assert "background fixer subagent" in landed.stdout
        assert "Next: run the subagent, forge handback tidy-words, then forge land tidy-words" in landed.stdout
        assert "Closing" not in landed.stdout
        assert json.loads(record.read_text("utf-8"))["status"] == "fixing"
        again = host.forge("land", "tidy-words")
        assert again.returncode == 0, again.stdout + again.stderr
        assert "Next: run the subagent, forge handback tidy-words" in again.stdout
        assert "Closing" not in again.stdout
        # A round that commits nothing still closes after its hand-back.
        number = int(re.search(r"--round (\d+)", landed.stdout)[1])
        assert handback("tidy-words", number, "Tidied.").returncode == 0
        assert "Closing tidy-words." in host.forge("land", "tidy-words").stdout

        if tool == "codex":
            # Under both tools and split, a failed Claude design run falls back to this Codex
            # session's own frontend subagent, with no Codex SDK.
            assert repo.forge("task", "start", "BOARD/PAGE").returncode == 0
            page = repo.path.parent / f"{repo.path.name}-BOARD-PAGE"
            (page / "forge.toml").write_text((page / "forge.toml").read_text("utf-8").replace(
                'tools = "codex"\nworkers = "claude"', 'tools = "both"\nworkers = "split"'), "utf-8")
            repo.git("commit", "-q", "-am", "Both tools, split workers", cwd=page)
            monkeypatch.setenv("STUB_CLAUDE_EXIT", "3")
            fell = handout("BOARD/PAGE", "frontend")[0]
            monkeypatch.delenv("STUB_CLAUDE_EXIT")
            assert "fell back to Codex" in fell.stdout
            assert "because Claude failed this design round" in fell.stdout
            assert len(calls(claude_log)) == 1 and not (repo.bin / "codex-app-server.jsonl").exists()

            # With one tool and no session open, nothing runs.
            monkeypatch.delenv("CODEX_THREAD_ID")
            head = repo.git("rev-parse", "HEAD", cwd=folder)
            refused = repo.forge("work", "BOARD/HELP")
            assert refused.returncode == 1
            assert "none is open here, so nothing ran" in refused.stderr
            assert repo.git("rev-parse", "HEAD", cwd=folder) == head
            return

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
