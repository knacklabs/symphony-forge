"""Each worker round runs its real test command and allows one repair turn on failure."""
import json
import os
import re
import sys

import pytest

from test_worker import calls, install_claude
from test_tools_session_hold import Session
from conftest import ROOT, _install
from test_codex_worker import sdk_data, _sent  # noqa: F401

STORY = "laptop-tests-before-push"


# Observable contract: work executes the configured check against the worker's actual edit.
# Regression: CI-mode work returns without executing that check, or repeatedly repairs a red run.
# Existing prompt tests cannot detect a command that never runs. Only the external model is fake;
# the configured check, git commits, work command and test lane are real. No production seam.
# Repair turns also leave settings edits that Forge must restore before the real recheck.
# Earlier cases always committed the repair and used at most one nudge. A dirty repair must
# not certify HEAD, and a question must survive the next nudge in either order.
# Runtime owners: src/forge/worker.py and src/forge/native.py.
@pytest.mark.platform
@pytest.mark.parametrize("test_place", ["local", "ci"])
@pytest.mark.parametrize("result", ["pass", "repair", "red", "uncommitted", "questions"])
@pytest.mark.parametrize("route", ["external", "native", "codex"])
def test_1_work_runs_related_tests_and_repairs_once(repo, monkeypatch, tmp_path, request,
                                                  test_place, result, route):
    log = install_claude(repo)
    home = tmp_path / "codex-home"
    home.mkdir()
    (home / "config.toml").write_text(
        f'[projects.{json.dumps(str(repo.path))}]\ntrust_level = "trusted"\n', "utf-8")
    monkeypatch.setenv("CODEX_HOME", str(home))
    version = repo.forge("--version").stdout.split()[-1]
    counted = repo.bin / "test-runs.txt"
    repo.write("check.py", "from pathlib import Path\n"
               f"counter = Path({counted.as_posix()!r})\n"
               "with counter.open('a', encoding='utf-8') as out: out.write('run\\n')\n"
               "assert Path('product.txt').read_text('utf-8') == 'good', 'product is broken'\n")
    command = f'"{sys.executable}" check.py'
    family = "codex" if route == "codex" else "claude"
    model = "gpt-6-sol" if route == "codex" else "sonnet"
    repo.write("forge.toml", f'version = "{version}"\nrepo = "forge-source"\n'
               f'workers = "{family}"\n'
               f'test_place = "{test_place}"\nchecks = ["tests"]\n'
               f'test = {json.dumps(command)}\n'
               f'fast_test = {json.dumps(command)}\n'
               f'models.lite = {{ model = "{model}", effort = "medium" }}\n')
    repo.write("product.txt", "good")
    repo.git("add", "-A")
    repo.git("commit", "-qm", "Configure the real product check")
    repo.git("push", "-q", "origin", "main")
    started = repo.forge("fix", "start", "Repair product", "--done", "The product check passes",
                         "--kind", "mechanical")
    assert started.returncode == 0, started.stdout + started.stderr
    expected = 1 if result in {"pass", "uncommitted"} else 2
    expected_turns = 3 if result in {"uncommitted", "questions"} else expected

    def check_result(built):
        assert counted.read_text("utf-8").splitlines() == ["run"] * expected
        red = result in {"red", "uncommitted"}
        assert ("Related tests failed" if red else "Related tests passed.") in built.stdout
        if result == "uncommitted":
            assert "Related tests passed." not in built.stdout
            folder = repo.path.parent / f"{repo.path.name}-fix-repair-product"
            assert repo.git("show", "HEAD:product.txt", cwd=folder) == "broken"
            assert (folder / "product.txt").read_text("utf-8") == "good"
        if result == "questions":
            refused = repo.forge("work", "repair-product")
            assert refused.returncode == 1, refused.stdout + refused.stderr
            if route == "native":
                assert "Question: Commit question?" in refused.stderr
            assert "Question: Repair question?" in refused.stderr
    if route == "codex":
        # The real SDK talks to a fake model service; only that service makes the worker edit.
        monkeypatch.setenv("XDG_DATA_HOME", str(request.getfixturevalue("sdk_data")))
        stub = (ROOT / "tests/stubs/codex-app-server").read_text("utf-8")
        marker = '        elif method == "turn/start":\n'
        edit = ("            import subprocess\n"
                "            repairing = \"The change's related tests failed.\" in params['input'][0]['text']\n"
                "            committing = 'Your turn ended' in params['input'][0]['text']\n"
                f"            good = {result == 'pass'!r} or (repairing and {result in {'repair', 'uncommitted', 'questions'}!r})\n"
                f"            if repairing and {result == 'repair'!r}:\n"
                "                settings = pathlib.Path(cwd) / 'forge.toml'\n"
                f"                settings.write_text(settings.read_text('utf-8').replace({('test = ' + json.dumps(command))!r}, 'test = \"echo bypass\"'), encoding='utf-8')\n"
                "            (pathlib.Path(cwd) / 'product.txt').write_text('good' if good else 'broken', encoding='utf-8')\n"
                f"            leave = ({result == 'uncommitted'!r} and not committing) or ({result == 'questions'!r} and not committing and not repairing)\n"
                "            if not leave:\n"
                "                subprocess.run(['git', 'add', 'product.txt'], cwd=cwd, check=True)\n"
                "                subprocess.run(['git', 'commit', '--allow-empty', '-qm', 'Worker edit'], cwd=cwd, check=True, stdout=sys.stderr)\n"
                f"            if {result == 'questions'!r}:\n"
                "                os.environ['STUB_CODEX_TEXT'] = ('Committed.' if committing else 'Question: Repair question?' if repairing else 'Built.')\n")
        _install(repo.bin, "codex-app-server", stub.replace(marker, marker + edit))
        monkeypatch.setenv("CODEX_BIN", str(repo.bin / (
            "codex-app-server.cmd" if os.name == "nt" else "codex-app-server")))
        built = repo.forge("work", "repair-product")
        assert built.returncode == 0, built.stdout + built.stderr
        codex_log = repo.bin / "codex-app-server.jsonl"
        turns = _sent(codex_log, "turn/start")
        assert len(turns) == expected_turns
        if result != "pass":
            assert any("product is broken" in turn["input"][0]["text"] for turn in turns[1:])
            assert _sent(codex_log, "thread/resume")
        check_result(built)
        return
    if route == "native":
        # A real session owns the native handback and must keep its place for the repair turn.
        monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
        monkeypatch.setenv("CLAUDECODE", "1")
        data = tmp_path / "without-claude-sdk"
        data.mkdir()
        monkeypatch.setenv("XDG_DATA_HOME", str(data))
        host = Session(repo, tmp_path / "host", "claude-session")
        folder = repo.path.parent / f"{repo.path.name}-fix-repair-product"
        try:
            given = host.forge("work", "repair-product")
            assert given.returncode == 0, given.stdout + given.stderr
            match = re.search(r"forge handback repair-product --round (\d+)", given.stdout)
            assert match, given.stdout + given.stderr
            number = match[1]
            actions = [(result == "pass", True, "The edit is committed.")]
            if result in {"repair", "red"}:
                actions.append((result == "repair", True, "The repair is committed."))
            elif result == "uncommitted":
                actions = [(False, False, "Built."), (False, True, "Committed."),
                           (True, False, "Repaired.")]
            elif result == "questions":
                actions = [(False, True, "Question: Commit question?"),
                           (True, False, "Question: Repair question?"), (True, True, "Committed.")]
            for turn, (good, commit, text) in enumerate(actions):
                (folder / "product.txt").write_text("good" if good else "broken", "utf-8")
                if turn == 1 and result == "repair":
                    settings = folder / "forge.toml"
                    settings.write_text(settings.read_text("utf-8").replace(
                        "test = " + json.dumps(command), 'test = "echo bypass"'), "utf-8")
                if commit:
                    repo.git("add", "product.txt", cwd=folder)
                    repo.git("commit", "--allow-empty", "-qm", "Worker edit", cwd=folder)
                built = host.forge("handback", "repair-product", "--round", number,
                                   "--subagent", "worker", "--text", text)
                assert built.returncode == 0, built.stdout + built.stderr
                if turn == 0 and result != "pass":
                    assert "Send this to subagent worker, then hand back again:" in built.stdout
                    if result != "uncommitted":
                        assert "product is broken" in built.stdout
            assert "Send this to subagent" not in built.stdout
        finally:
            host.close()
        check_result(built)
        return
    sdk = repo.bin / "claude_agent_sdk" / "__init__.py"
    source = sdk.read_text("utf-8")
    marker = '    if os.environ.get("STUB_CLAUDE_LEAVE"):'
    assert marker in source
    edit = ("    import subprocess\n"
            f"    repairing = \"The change's related tests failed.\" in prompt\n"
            "    committing = 'Your turn ended' in prompt\n"
            f"    good = {result == 'pass'!r} or (repairing and {result in {'repair', 'uncommitted', 'questions'}!r})\n"
            f"    if repairing and {result == 'repair'!r}:\n"
            "        settings = Path('forge.toml')\n"
            f"        settings.write_text(settings.read_text('utf-8').replace({('test = ' + json.dumps(command))!r}, 'test = \"echo bypass\"'), encoding='utf-8')\n"
            "    Path('product.txt').write_text('good' if good else 'broken', encoding='utf-8')\n"
            f"    leave = ({result == 'uncommitted'!r} and not committing) or ({result == 'questions'!r} and not committing and not repairing)\n"
            "    if not leave:\n"
            "        subprocess.run(['git', 'add', 'product.txt'], check=True)\n"
            "        subprocess.run(['git', 'commit', '--allow-empty', '-qm', 'Worker edit'], check=True)\n"
            f"    if {result == 'questions'!r}:\n"
            "        os.environ['STUB_CLAUDE_RESULT'] = ('Committed.' if committing else 'Question: Repair question?' if repairing else 'Built.')\n")
    sdk.write_text(source.replace(marker, edit + marker), "utf-8")
    built = repo.forge("work", "repair-product")
    assert built.returncode == 0, built.stdout + built.stderr
    assert counted.exists(), built.stdout + built.stderr
    turns = calls(log)
    assert len(turns) == expected_turns
    if result != "pass":
        assert any("product is broken" in turn["brief"] for turn in turns[1:])
        assert turns[1]["options"]["resume"]
    check_result(built)
