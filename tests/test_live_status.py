"""Live machine status through Forge commands; only agent/GitHub edges are replaced.

The existing machine-view tests cover readiness and timings, not live tool streams,
idle transitions, runner progress or severity. These cases protect that transport
and lifecycle contract without importing Forge or supplying its derived fields.
"""
import json
import socket
import subprocess
import sys
from datetime import datetime, timedelta

import pytest

from test_close import env  # noqa: F401
from test_codex_worker import _codex_repo, sdk_data  # noqa: F401
from test_machine_views import github, pull, state, view
from test_run_records import configure

STORY = "FORGE-MOD-1"


def row(repo, item):
    boards = [view(repo, command) for command in ("board", "next")]
    assert boards[0]["items"] == boards[1]["items"]
    assert boards[0]["events"] == boards[1]["events"]
    rows = [r for parent in boards[0]["items"] for r in [parent, *parent["children"]]]
    return next(r for r in rows if r["id"] == item), boards[0]


@pytest.mark.parametrize("case", ["idle", "checks", "claude", "codex", "progress", "progress parallel", "progress error", "progress teardown", "restart", "plan", "ci"])
def test_7_live_status_in_both_machine_views(env, monkeypatch, request, case):
    # Both commands read at different instants; freeze their clock for timer equality.
    monkeypatch.setenv("FORGE_NOW", "2026-10-06T12:00:00+00:00")
    repo = env.repo
    if case == "plan":
        from test_story import setup, new_story, DOC
        setup(repo)
        folder = new_story(repo, "SHOP")
        (folder / "plans/SHOP.md").write_text(DOC, "utf-8")
        assert row(repo, "SHOP")[0]["gates"]["plan_read"] == {"status": "none"}
        assert repo.forge("read", "SHOP").returncode == 0
        assert row(repo, "SHOP")[0]["gates"]["plan_read"] == {"status": "passed"}
        (folder / "plans/SHOP.md").write_text(DOC.replace("come back", "return"), "utf-8")
        assert row(repo, "SHOP")[0]["gates"]["plan_read"] == {"status": "blocked"}
        return
    if case == "codex":
        folder, _ = _codex_repo(repo, monkeypatch, request.getfixturevalue("sdk_data"))
        item = "BOARD/PAGE"
        model, effort = "gpt-6-sol", "medium"
    else:
        configure(env)
        item, folder = env.start_fix()
        model, effort = "sonnet", "medium"
    number = 1
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
        prs = [pull(7, f"fix/{item}", "TIMED_OUT")]
        checks = prs[0]["commits"]["nodes"][0]["commit"]["statusCheckRollup"]["contexts"]["nodes"]
        checks.append({**checks[0], "databaseId": 123, "name": "tests", "conclusion": "FAILURE"})
        github(env.gh, prs)
        result, _ = row(repo, item)
        assert result["pr"]["failures"] == [{"job": "forge-pr-check", "cause": "timeout"},
                                            {"job": "tests", "cause": "failed"}]
        assert result["findings"]["items"] == [{"title": "Input lost", "priority": "P1"},
                                              {"title": "Copy unclear", "priority": "P2"}]
        assert result["findings"]["dismissed"] == 1
        assert result["gates"] == {"plan_read": {"status": "none"},
                                   "review": {"status": "blocked", "count": 2},
                                   "ci": {"status": "red"}}
        return
    # Two raw tool events arrive without a timer sleep. The socket only holds the
    # external process, so Forge must consume and expose both events itself.
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        listener.settimeout(30)
        gate = (f'import socket\nwith socket.create_connection({listener.getsockname()!r}, '
                'timeout=30) as gate:\n    gate.recv(1)\n')
        if case == "codex":
            stub = repo.bin / "codex-app-server"
            source = stub.read_text("utf-8")
            events = ""
            for command in ("pytest tests/test_live_status.py", "git commit -m Done"):
                events += (f'notify("item/started", threadId=THREAD, turnId=TURN, item={{'
                           f'"type": "commandExecution", "id": "live", "command": {command!r}, '
                           '"cwd": cwd, "status": "inProgress", "processId": "1"})\n' + gate)
            stub.write_text(source.replace('asked = {"stub-ask-1"',
                events.replace("\n", "\n            ") + 'asked = {"stub-ask-1"'), "utf-8")
        elif case == "claude":
            stub = repo.bin / "claude"
            events = ""
            for tool, inputs in (("Edit", {"file_path": "src/forge/close.py"}),
                                 ("Bash", {"command": "git commit -m Done"})):
                event = {"type": "assistant", "message": {"content": [
                    {"type": "tool_use", "name": tool, "input": inputs}]}}
                events += f'print({json.dumps(event)!r}, flush=True)\n' + gate
            source = stub.read_text("utf-8")
            question = "Question: May I reuse the parser?"
            stub.write_text(source.replace('print("stub claude: built it")', events +
                f'print(json.dumps({{"type": "assistant", "message": {{"content": [{{"type": "text", "text": {question!r}}}]}}}}), flush=True)\n'
                f'print(json.dumps({{"type": "result", "result": {question!r}}}), flush=True)'), "utf-8")
        elif case == "ci":
            stub = repo.bin / "gh"
            source = stub.read_text("utf-8")
            stub.write_text(source.replace('responses = here / "gh-responses.json"',
                'if args and "check-runs?" in args[-1] and not (here / "ci-held").exists():\n'
                '    (here / "ci-held").touch()\n    ' + gate.replace("\n", "\n    ") +
                '\nresponses = here / "gh-responses.json"'), "utf-8")
            pr = pull(7, f"fix/{item}", None)
            check = pr["commits"]["nodes"][0]["commit"]["statusCheckRollup"]["contexts"]["nodes"][0]
            check["startedAt"] = "2026-10-06T11:59:00Z"
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
            config = folder / "forge.toml"
            parallel = " -n 2 --dist loadfile" if case == "progress parallel" else ""
            env.commit(folder, "forge.toml", config.read_text("utf-8").replace(
                json.dumps(f'"{sys.executable}" -c "print(123)"'),
                json.dumps(f'"{sys.executable}" -m pytest -vv{parallel} test_progress.py')))
        process = subprocess.Popen([sys.executable, str(repo.bin / "forge"),
                                   "close" if case.startswith("progress") or case == "ci" else "work", item], cwd=repo.path,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        connections = []
        try:
            first = "editing src/forge/close.py" if case == "claude" else "running pytest tests/test_live_status.py"
            for expected in ([None] if case.startswith("progress") or case == "ci" else [first,
                                                                   "committing"]):
                connection, _ = listener.accept()
                connections.append(connection)
                result, _ = row(repo, item)
                assert result["activity"]["status"] == "running"
                assert result["idle_since"] is None and result["stalled"] is False
                if case.startswith("progress"):
                    assert result["tests"]["done"] == 1 and result["tests"]["total"] == 4
                elif case == "ci":
                    assert result["gates"]["ci"] == {"status": "running", "elapsed": 60}
                    stage = next(s for s in result["stages"] if s["name"] == "CI")
                    assert stage["status"] == "running" and stage["elapsed"] == 0
                else:
                    worker = result["worker"]
                    assert (worker["tool"], worker["model"], worker["effort"], worker["round"]) == (
                        case, model, effort, number)
                    assert worker["step"] == expected
                    datetime.fromisoformat(worker["started_at"])
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
        assert (process.returncode == 0) == (case not in ("progress error", "progress teardown")), output + error
    ended, board = row(repo, item)
    assert ended["activity"] == {"status": "idle"}
    assert ended["idle_since"] is not None
    assert all(set(e) == {"time", "item", "line"} for e in board["events"])
    assert len(board["events"]) <= 20
    if case == "claude":
        assert board["events"][-1]["line"] == question
