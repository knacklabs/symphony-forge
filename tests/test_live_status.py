"""Live machine status through Forge commands; only agent/GitHub edges are replaced.

The existing machine-view tests cover readiness and timings, not live tool streams,
idle transitions, runner progress or severity. These cases protect that transport
and lifecycle contract without importing Forge or supplying its derived fields.
"""
import json
import os
import socket
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from test_close import env  # noqa: F401
from test_codex_worker import _codex_repo, sdk_data  # noqa: F401
from test_machine_views import github, pull, state, view
from test_run_records import configure, records

# Review selection is reported by Autoreview; legacy pins do not set live defaults.
STORY = "FORGE-MOD-1"


def row(repo, item):
    boards = [view(repo, command) for command in ("board", "next")]
    assert boards[0]["items"] == boards[1]["items"]
    assert boards[0]["events"] == boards[1]["events"]
    rows = [r for parent in boards[0]["items"] for r in [parent, *parent["children"]]]
    return next(r for r in rows if r["id"] == item), boards[0]


@pytest.mark.parametrize("case", ["idle", "remote fix", "remote task", "checks", "claude", "claude error", "codex", "read claude", "read codex", "read default claude", "read default codex", "review claude", "review codex", "review default claude", "review default codex", "review fallback claude", "review fallback codex", "progress", "progress parallel", "progress error", "progress teardown", "progress single", "progress selected", "restart", "plan", "plan detached", "ci", "ci red", "ci green"])
def test_7_live_status_in_both_machine_views(env, monkeypatch, request, case):
    # Both commands read at different instants; freeze their clock for timer equality.
    monkeypatch.setenv("FORGE_NOW", "2026-10-06T12:00:00+00:00")
    repo = env.repo
    if case.startswith("remote"):
        if case == "remote task":
            folder, _ = _codex_repo(repo, monkeypatch, request.getfixturevalue("sdk_data"))
            item, branch = "BOARD/PAGE", "task/BOARD-PAGE"
        else:
            configure(env)
            item, folder = env.start_fix()
            branch = f"fix/{item}"
        committed = repo.git("log", "-1", "--format=%cI", cwd=folder)
        repo.git("push", "-q", "origin", branch)
        repo.git("worktree", "remove", "--force", str(folder))
        repo.git("branch", "-D", branch)
        monkeypatch.setenv("FORGE_NOW", (datetime.fromisoformat(committed) + timedelta(hours=25)).isoformat())
        result, _ = row(repo, item)
        assert result["idle_since"] == committed and result["stalled"] is True
        return
    if case.startswith("plan"):
        from test_story import setup, new_story, DOC
        setup(repo)
        folder = new_story(repo, "SHOP")
        (folder / "plans/SHOP.md").write_text(DOC, "utf-8")
        assert row(repo, "SHOP")[0]["gates"]["plan_read"] == {"status": "none"}
        assert repo.forge("read", "SHOP").returncode == 0
        assert row(repo, "SHOP")[0]["gates"]["plan_read"] == {"status": "passed"}
        if case == "plan detached":
            stale = repo.path.parent / "stale-task"
            repo.git("worktree", "add", "-b", "task/SHOP-PAGE", str(stale), "story/SHOP")
            env.commit(stale, ".factory/stories/SHOP/tasks/PAGE.json", json.dumps({"branch": "task/SHOP-PAGE", "status": "working"}))
        (folder / "plans/SHOP.md").write_text(DOC.replace("come back", "return"), "utf-8")
        if case == "plan detached":
            repo.git("add", "plans/SHOP.md", cwd=folder)
            repo.git("commit", "-m", "Change the plan", cwd=folder)
            repo.git("push", "origin", "story/SHOP", cwd=folder)
            repo.git("worktree", "remove", "--force", str(folder))
        assert row(repo, "SHOP")[0]["gates"]["plan_read"] == {"status": "blocked"}
        if case == "plan detached":
            repo.git("worktree", "add", str(folder), "story/SHOP")
            assert repo.forge("read", "SHOP").returncode == 0
            repo.git("worktree", "remove", "--force", str(folder))
            assert row(repo, "SHOP")[0]["gates"]["plan_read"] == {"status": "passed"}
        return
    if case.startswith("read"):
        from test_story import setup, new_story, DOC
        from conftest import ROOT, _install
        setup(repo)
        if "default" in case:
            config = repo.path / "forge.toml"
            config.write_text(config.read_text("utf-8").replace('models.grill.claude = { model = "opus", effort = "high" }\n', ''), "utf-8")
            repo.git("add", "forge.toml")
            repo.git("commit", "-m", "Use provider defaults")
        folder = new_story(repo, "SHOP")
        (folder / "plans/SHOP.md").write_text(DOC, "utf-8")
        item, model, effort = "SHOP", "opus", "high"
        if case.endswith("codex"):
            monkeypatch.setenv("XDG_DATA_HOME", str(request.getfixturevalue("sdk_data")))
            home = repo.path.parent / "reader-home"
            home.mkdir()
            (home / "config.toml").write_text(f'[projects.{json.dumps(str(repo.path))}]\ntrust_level = "trusted"\n', "utf-8")
            monkeypatch.setenv("CODEX_HOME", str(home))
            _install(repo.bin, "codex-app-server", (ROOT / "tests/stubs/codex-app-server").read_text("utf-8"))
            stub = repo.bin / "codex-app-server"
            stub.write_text(stub.read_text("utf-8").replace('"stub codex: built it with "\n            + json.dumps(config, sort_keys=True) + os.environ.get("STUB_SAY", "")', '"No findings."'), "utf-8")
            monkeypatch.setenv("CODEX_BIN", str(repo.bin / ("codex-app-server.cmd" if os.name == "nt" else "codex-app-server")))
            monkeypatch.delenv("CODEX_THREAD_ID")
            monkeypatch.setenv("CLAUDECODE", "1")
            config = folder / "forge.toml"
            if "default" not in case:
                config.write_text(config.read_text("utf-8") + 'models.grill.codex = { model = "gpt-6-sol", effort = "high" }\n', "utf-8")
            else:
                # Codex reports a null configured effort. Its matching model's default
                # is on the second catalog page, after a different model's high default.
                stub.write_text(stub.read_text("utf-8").replace('"stub-model"', '"gpt-6.1-sol"'), "utf-8")
            monkeypatch.setenv("STUB_SAY", "No findings.")
            model = "gpt-6-sol"
        if "default" in case:
            model, effort = ("gpt-6.1-sol", "medium") if case.endswith("codex") else ("claude-opus-5-5", "high")
        assert repo.forge("read", item).returncode == 0
        (folder / "plans/SHOP.md").write_text(DOC.replace("come back", "return"), "utf-8")
    elif case == "codex":
        request.getfixturevalue("claude_session")
        folder, _ = _codex_repo(repo, monkeypatch, request.getfixturevalue("sdk_data"))
        item = "BOARD/PAGE"
        model, effort = "gpt-6-sol", "medium"
    else:
        configure(env)
        if case.startswith("review"):
            config = repo.path / "forge.toml"
            family = case.split()[-1]
            settings = config.read_text("utf-8").replace('workers = "claude"', f'workers = "{family}"')
            if "default" not in case:
                settings += ('models.review.codex = { model = "gpt-6-sol", effort = "xhigh" }\n'
                             'models.review.claude = { model = "opus", effort = "high" }\n')
            if settings != config.read_text("utf-8"):
                env.commit(repo.path, "forge.toml", settings)
        item, folder = env.start_fix()
        model, effort = "sonnet", "medium"
    number = 1
    if case.startswith("read"):
        number = 2
    if case.startswith("review"):
        if case.endswith("claude"):
            from test_fix_reviews_always_run_on_codex_so_a_team_wi import _claude_only
            _claude_only(env.tmp, monkeypatch, repo.bin, (env.tmp / "autoreview/scripts/autoreview").read_text("utf-8"))
        # Legacy pins no longer seed status; Autoreview's live reports supply selection.
        model, effort = None, None
    if case == "restart":
        assert repo.forge("work", item).returncode == 0
        assert row(repo, item)[0]["idle_since"] is not None
        number, case = 2, "claude"
    if case == "idle":
        initial, _ = row(repo, item)
        assert initial["activity"] == {"status": "idle"}
        assert initial["idle_since"] == repo.git("log", "-1", "--format=%cI", cwd=folder)
        monkeypatch.setenv("FORGE_NOW", (datetime.fromisoformat(initial["idle_since"]) +
                                         timedelta(hours=25)).isoformat())
        assert row(repo, item)[0]["stalled"] is True
        for _ in range(11):
            assert repo.forge("work", item).returncode == 0
        ended, board = row(repo, item)
        assert ended["idle_since"] == board["events"][-1]["time"]
        assert ended["stalled"] is False
        assert board["events"][-1]["item"] == item
        assert board["events"][-1]["line"] == "Worker finished"
        assert len(board["events"]) == 20
        return
    if case == "checks":
        from test_close import finding
        review = {"status": "blocked", "findings": [finding("P1", "Input lost"),
                  finding("P2", "Copy unclear"), finding("P1", "Already handled")],
                  "dismissals": [{"finding": 3, "because": "Already handled"}]}
        state(folder / f".factory/fixes/{item}.json", review=review)
        prs = [pull(7, f"fix/{item}", "CANCELLED")]
        checks = prs[0]["commits"]["nodes"][0]["commit"]["statusCheckRollup"]["contexts"]["nodes"]
        checks.append({**checks[0], "databaseId": 123, "name": "tests", "conclusion": "FAILURE"})
        checks.append({**checks[0], "databaseId": 124, "name": "manually cancelled"})
        # GitHub cancels both jobs; only its timeout annotation distinguishes them.
        env.gh.respond("api", "--paginate", "--slurp", f'repos/{{owner}}/{{repo}}/check-runs/{checks[0]["databaseId"]}/annotations?per_page=100', stdout=json.dumps([[{"message": "The operation was canceled."}], [{"message": "The job running on runner Hosted Agent has exceeded the maximum execution time of 1 minute."}]]))
        env.gh.respond("api", "--paginate", "--slurp", "repos/{owner}/{repo}/check-runs/124/annotations?per_page=100", stdout=json.dumps([[{"message": "The operation was canceled."}]]))
        github(env.gh, prs)
        result, _ = row(repo, item)
        assert result["pr"]["failures"] == [{"job": "forge-pr-check", "cause": "timeout"},
                                            {"job": "tests", "cause": "failed"},
                                            {"job": "manually cancelled", "cause": "failed"}]
        assert result["findings"]["items"] == [{"title": "Input lost", "priority": "P1"},
                                              {"title": "Copy unclear", "priority": "P2"}]
        assert result["findings"]["dismissed"] == 1
        assert result["gates"] == {"plan_read": {"status": "none"},
                                   "review": {"status": "blocked", "count": 2},
                                   "ci": {"status": "red"}}
        return
        # Raw tool/progress events arrive without a timer sleep. The socket only holds the
    # external process, so Forge must consume and expose both events itself.
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        listener.settimeout(30)
        gate = (f'import socket\nwith socket.create_connection({listener.getsockname()!r}, '
                'timeout=30) as gate:\n    gate.settimeout(None)\n    gate.recv(1)\n')
        expected_steps = ["editing src/forge/close.py", "committing"]
        selections = {}
        if case == "codex" or case.startswith("read") and case.endswith("codex"):
            stub = repo.bin / "codex-app-server"
            source = stub.read_text("utf-8")
            events = ""
            tools = [("commandExecution", {"command": "pytest tests/test_live_status.py", "cwd": str(folder), "status": "inProgress", "processId": "1"}),
                     ("fileChange", {"changes": [{"path": "app.py", "kind": {"type": "update"}, "diff": "+x"}], "status": "inProgress"}),
                     ("webSearch", {"query": "Forge docs", "action": {"type": "search", "query": "Forge docs"}}),
                     ("mcpToolCall", {"server": "docs", "tool": "lookup", "arguments": {}, "status": "inProgress"}),
                     ("dynamicToolCall", {"tool": "lookup", "arguments": {}, "status": "inProgress"}),
                     ("collabAgentToolCall", {"tool": "spawnAgent", "status": "inProgress", "senderThreadId": "parent", "receiverThreadIds": []}),
                     ("imageView", {"path": "screen.png"}), ("imageGeneration", {"status": "inProgress"}), ("sleep", {}),
                     ("subAgentActivity", {"kind": "progress", "agentThreadId": "helper", "agentPath": "helper"}),
                     ("enteredReviewMode", {"review": "Review the change"}), ("exitedReviewMode", {"review": "Done"}), ("contextCompaction", {})]
            expected_steps = ["running pytest tests/test_live_status.py", "editing app.py", "searching the web", "using docs.lookup", "using lookup", "using spawnAgent", "reading screen.png", "generating an image", "waiting", "working with a helper", "reviewing", "finishing the review", "compacting context"]
            for index, (kind, inputs) in enumerate(tools):
                event = {"type": kind, "id": f"live-{index}", **inputs}
                events += f'notify("item/started", threadId=THREAD, turnId=TURN, item={event!r})\n' + gate
            stub.write_text(source.replace('asked = {"stub-ask-1"',
                events.replace("\n", "\n            ") + 'asked = {"stub-ask-1"'), "utf-8")
        elif case in ("claude", "claude error") or case.startswith("read") and case.endswith("claude"):
            stub = repo.bin / "claude"
            events = ""
            if "default" in case:
                event = {"type": "system", "subtype": "init", "model": model}
                events += f'print({json.dumps(event)!r}, flush=True)\n'
                event = {"type": "control_response", "response": {"subtype": "success", "request_id": "forge-live-settings", "response": {"applied": {"model": model, "effort": effort}}}}
                events += 'assert any(e.get("request", {}).get("subtype") == "get_settings" for e in input_events)\n'
                events += f'print({json.dumps(event)!r}, flush=True)\n'
            for tool, inputs in (("Edit", {"file_path": "src/forge/close.py"}),
                                 ("Bash", {"command": "git commit -m Done"})):
                event = {"type": "assistant", "message": {"content": [
                    {"type": "tool_use", "name": tool, "input": inputs}]}}
                events += f'print({json.dumps(event)!r}, flush=True)\n' + gate
            source = stub.read_text("utf-8")
            question = "Question: May I reuse the parser?"
            marker = 'said = here / "claude-says.md"' if case.startswith("read") else 'print("stub claude: built it")'
            replacement = events + ('print(json.dumps({"type": "result", "result": "No findings."}), flush=True)\nraise SystemExit(0)\n' if case.startswith("read") else
                f'print(json.dumps({{"type": "assistant", "message": {{"content": [{{"type": "text", "text": {question!r}}}]}}}}), flush=True)\n'
                f'print(json.dumps({{"type": "result", "result": {question!r}}}), flush=True)')
            if case == "claude error":
                replacement = events + 'print(json.dumps({"type": "result", "subtype": "error_during_execution", "errors": ["Provider connection closed"]}), flush=True)\nraise SystemExit(3)\n'
            stub.write_text(source.replace(marker, replacement), "utf-8")
        elif case.startswith("review"):
            stub = (Path(os.environ["HOME"]) / ".claude/skills/autoreview/scripts/autoreview"
                    if case.endswith("claude") else env.queue.parent / "autoreview/scripts/autoreview")
            source = stub.read_text("utf-8")
            expected_steps = ["preparation: initial source snapshot", "preparation: pre-review verification"]
            if "default" in case or "fallback" in case:
                reported = "gpt-6-sol" if case.endswith("codex") else "opus"
                # The provider edge supplies reports, never machine-view metadata.
                # Hold after partial selection, effort, a change, and later ordinary progress.
                selections = {f"model: {reported}": (reported, effort),
                              "thinking: medium": (reported, "medium")}
                if "fallback" in case:
                    changed = ("codex model gpt-6-sol is unavailable for this account; retrying with gpt-6.1-sol"
                               if case.endswith("codex") else "model: sonnet")
                    reported = "gpt-6.1-sol" if case.endswith("codex") else "sonnet"
                    selections[changed] = (reported, "medium")
                    selections["thinking: high"] = (reported, "high")
                expected_steps = [*selections, *expected_steps]
            events = "".join(f'print({step!r}, flush=True)\n' + gate for step in expected_steps)
            stub.write_text(source.replace('if "--codex-bin" in args:', events + 'if "--codex-bin" in args:'), "utf-8")
        elif case.startswith("ci"):
            stub = repo.bin / "gh"
            source = stub.read_text("utf-8")
            stub.write_text(source.replace('responses = here / "gh-responses.json"',
                'if args and "check-runs?" in args[-1] and not (here / "ci-held").exists():\n'
                '    (here / "ci-held").touch()\n    ' + gate.replace("\n", "\n    ") +
                '\nresponses = here / "gh-responses.json"'), "utf-8")
            pr = pull(7, f"fix/{item}", None)
            check = pr["commits"]["nodes"][0]["commit"]["statusCheckRollup"]["contexts"]["nodes"][0]
            check["startedAt"] = "2026-10-06T11:59:00Z"
            if case != "ci":
                check.update(status="COMPLETED", conclusion="FAILURE" if case == "ci red" else "SUCCESS")
            else:
                pr["commits"]["nodes"][0]["commit"]["statusCheckRollup"]["contexts"]["nodes"].append({"__typename": "StatusContext", "state": "SUCCESS", "context": "old success", "createdAt": "2026-10-05T00:00:00Z"})
            pr["commits"]["nodes"][0]["commit"]["statusCheckRollup"]["contexts"]["nodes"].append({**check, "databaseId": 123, "name": "tests", "status": "COMPLETED", "conclusion": "SUCCESS"})
            github(env.gh, [pr])
        else:
            # Run actual pytest cases. Its second test holds at the external runner
            # boundary after its first real pass; Forge receives pytest's own progress.
            script = folder / "test_progress.py"
            teardown = ('import pytest\n@pytest.fixture\ndef teardown():\n' +
                        ('    yield\n    raise RuntimeError("teardown failed")\n\n'
                         if case == "progress teardown" else
                         '    raise RuntimeError("setup failed")\n    yield\n\n')
                        if case in ("progress error", "progress teardown") else '')
            script.write_text(teardown + f'def test_one({"teardown" if teardown else ""}):\n    assert 2 + 2 == 4\n\n'
                              'def test_two():\n    ' + gate.replace("\n", "\n    ") +
                              '\ndef test_three():\n    assert True\n\n'
                              'def test_four():\n    assert True\n', "utf-8")
            if case == "progress single":
                script.write_text(script.read_text("utf-8").replace('def test_one():', 'def other_one():').replace('def test_three():', 'def other_three():').replace('def test_four():', 'def other_four():'), "utf-8")
            config = folder / "forge.toml"
            parallel = " -n 2 --dist loadfile" if case == "progress parallel" else ""
            parallel += " -k test_two" if case == "progress selected" else ""
            env.commit(folder, "forge.toml", config.read_text("utf-8").replace(
                json.dumps(f'"{sys.executable}" -c "print(123)"'),
                json.dumps(f'"{sys.executable}" -m pytest -vv{parallel} test_progress.py')))
        process = subprocess.Popen([sys.executable, str(repo.bin / "forge"),
                                   "read" if case.startswith("read") else "close" if case.startswith(("progress", "ci", "review")) else "work", item], cwd=repo.path,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        connections, activities = [], []
        try:
            for expected in ([None] if case.startswith(("progress", "ci")) else expected_steps):
                connection, _ = listener.accept()
                connections.append(connection)
                # A connection acknowledges emission, not Forge consuming the event.
                # Hold the producer until the real board exposes this step; only then
                # compare snapshots. The test and parent cleanup bound the held run.
                if expected is not None:
                    deadline = time.monotonic() + 30
                    while True:
                        snapshot = view(repo, "board")
                        current = next(r for parent in snapshot["items"]
                                       for r in [parent, *parent["children"]] if r["id"] == item)
                        if (current["worker"] or {}).get("step") == expected:
                            break
                        assert time.monotonic() < deadline, f"Forge did not report {expected}"
                result, _ = row(repo, item)
                activities.append(result["activity"])
                assert result["idle_since"] is None and result["stalled"] is False
                if case.startswith("progress"):
                    assert result["tests"]["done"] == (0 if case in ("progress single", "progress selected") else 1)
                    assert result["tests"]["total"] == (1 if case in ("progress single", "progress selected") else 4)
                elif case.startswith("ci"):
                    assert result["gates"]["ci"] == ({"status": "red" if case == "ci red" else "green"} if case != "ci" else {"status": "running", "elapsed": 60})
                    stage = next(s for s in result["stages"] if s["name"] == "CI")
                    assert stage["status"] == "running" and stage["elapsed"] == 0
                else:
                    worker = result["worker"]
                    model, effort = selections.get(expected, (model, effort))
                    assert (worker["tool"], worker["model"], worker["effort"], worker["round"]) == (
                        "claude" if case == "claude error" else case.split()[-1], model, effort, number if not case.startswith("review") else 0)
                    assert worker["step"] == expected
                    datetime.fromisoformat(worker["started_at"])
                    # The clock stays in one ten-second window throughout this burst.
                    # Keep the latest action visible without retaining every notification.
                    events = records(repo, "events.jsonl")
                    run = next(e for e in reversed(events) if e["item"] == item and e["event"] == "run start")
                    progress = [e for e in events if e.get("run_id") == run["id"] and e["event"] == "progress"]
                    assert len(progress) == 1
                    assert progress[0]["step"] == expected
                connection.sendall(b"1")
        finally:
            for connection in connections:
                connection.close()
            try:
                output, error = process.communicate(timeout=60)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate()
                raise
        assert (process.returncode == 0) == (case not in ("progress error", "progress teardown", "claude error")), output + error
        action = ("test" if case.startswith("progress") else "ci" if case.startswith("ci")
                  else "review" if case.startswith("review") else "read" if case.startswith("read")
                  else "worker" if case.startswith("claude") else "work")
        assert all(activity == {"status": "running", "action": action}
                   for activity in activities), activities
        if case == "claude error":
            log = repo.path / ".git/forge" / f"work-{item}.log"
            assert "error_during_execution" in log.read_text("utf-8")
            assert "Provider connection closed" in log.read_text("utf-8")
    ended, board = row(repo, item)
    assert ended["activity"] == {"status": "idle"}
    assert ended["idle_since"] is not None
    assert all(set(e) == {"time", "item", "line"} for e in board["events"])
    assert len(board["events"]) <= 20
    if case.startswith("review"):
        assert {"time": "2026-10-06T12:00:00+00:00", "item": item,
                "line": "Review clean"} in board["events"]
    if case == "claude":
        assert board["events"][-1]["line"] == question
