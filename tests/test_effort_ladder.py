"""A failed Forge work round raises effort on the next turn.

Test-audit answers:
1. Protects effort choice, session reuse, SDK routing and native requested labels after failures,
   plus fixed read/review/design effort and a repo's explicit effort choice.
2. A retry may keep the first effort, start a new session, skip the SDK route or omit the requested
   label from a native handout, raise fixed effort, or reject a repo's explicit none.
3. Existing worker and native tests own normal routing and handbacks, but not failure-driven effort
   or this installed-versus-missing SDK choice. This file owns those contracts through Forge
   commands; each parameter changes one failure or host condition.
4. The tests use Forge commands and existing SDK, GitHub and host-session stubs; they add no
   production seam.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

from conftest import ROOT, _install, _install_claude_sdk
from test_close import blocked, env as close_env, finding, run
from test_task import story
from test_worker import calls, install_claude
from test_codex_worker import sdk_data  # noqa: F401
from test_setup import _fresh_client
from test_tools_session_hold import Session

STORY = "FORGE-EFFORT-1"
pytestmark = pytest.mark.platform


def _round_client(repo, gh, tmp_path, monkeypatch, mode, effort="low", task="HELP",
                  history="new", sdk_data=None, fixed=False, test_place="local"):
    """A new or earlier-adopted client with one started task and a configured worker."""
    env = close_env.__wrapped__(repo, gh, tmp_path, monkeypatch)
    version = repo.forge("--version").stdout.split()[-1]
    family = "claude" if mode == "claude" else "codex"
    model = "claude-sonnet-5-5" if family == "claude" else "gpt-6.1-sol"
    helpers = ', subagents = "gpt-6-luna", subagent_effort = "max"' if family == "codex" else ""
    settings = (f'version = "{version}"\nrepo = "client"\nworkers = "{mode}"\n'
                f'test_place = "{test_place}"\nchecks = ["tests", "forge-pr-check"]\n'
                'test = "python fail_test.py"\nfast_test = "python fail_test.py"\n' +
                "".join(f'models.{kind} = {{ model = "{model}", effort = "{effort}"{helpers} }}\n'
                        for kind in ("build", "fix", "lite")))
    if fixed:
        settings += ('models.review.codex = { model = "gpt-6.1-sol", effort = "medium" }\n'
                     'models.grill.claude = { model = "claude-sonnet-5-5", effort = "medium" }\n'
                     'models.design.codex = { model = "gpt-6.1-sol", effort = "medium" }\n'
                     'models.design.claude = { model = "claude-sonnet-5-5", effort = "medium" }\n')
    if history == "new":
        client = tmp_path / "client"
        client.mkdir()
        (client / "forge.toml").write_text(settings, encoding="utf-8")
        client, initialized = _fresh_client(repo, gh, tmp_path)
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr
        repo.path = client
    elif history == "adopted":
        import shutil

        fixture = Path(__file__).parent / "fixtures/adopted-v1.2.2/client"
        shutil.copytree(fixture, repo.path, dirs_exist_ok=True)
        repo.write("forge.toml", settings)
        repo.git("add", "-A")
        repo.git("commit", "-q", "-m", "Use an adopted client repo")
        repo.git("push", "-q", "origin", "main")
    else:
        raise AssertionError(f"Unknown client history: {history}")

    assert sdk_data is not None
    _install_claude_sdk(repo.bin, sdk_data)
    monkeypatch.setenv("XDG_DATA_HOME", str(sdk_data))
    monkeypatch.setenv("PYTHONPATH", str(repo.bin) + os.pathsep + os.environ.get("PYTHONPATH", ""))
    log = repo.bin / "claude-sdk-calls.jsonl"
    if family == "codex":
        _install(repo.bin, "codex-app-server", (ROOT / "tests/stubs/codex-app-server").read_text("utf-8"))
        program = repo.bin / ("codex-app-server.cmd" if os.name == "nt" else "codex-app-server")
        monkeypatch.setenv("CODEX_BIN", str(program))
        home = tmp_path / "worker-codex-home"
        home.mkdir()
        (home / "config.toml").write_text(
            f'[projects.{json.dumps(str(repo.path))}]\ntrust_level = "trusted"\n', encoding="utf-8")
        monkeypatch.setenv("CODEX_HOME", str(home))
        log = repo.bin / "codex-app-server.jsonl"
    install_claude(repo)
    story(repo)
    started = repo.forge("task", "start", f"BOARD/{task}")
    assert started.returncode == 0, started.stdout + started.stderr
    folder = Path(started.stdout.splitlines()[0].rsplit(" in ", 1)[1])
    return env, folder, log


@pytest.mark.parametrize(
    "mode,failure",
    [(mode, failure) for mode in ("codex", "claude", "split")
     for failure in ("test", "finding", "required-check", "optional-check", "required-matrix-check",
                     "optional-matrix-check", "similar-matrix-check", "note")]
    + [("codex", "test-medium"), ("claude", "test-xhigh"), ("codex", "required-matrix-check-medium")],
    ids=[f"{mode}-{failure}" for mode in ("codex", "claude", "split")
         for failure in ("test", "finding", "required-check", "optional-check", "required-matrix-check",
                         "optional-matrix-check", "similar-matrix-check", "note")]
    + ["adopted-codex-medium", "adopted-claude-xhigh", "adopted-required-matrix-check"])
def test_1_a_failed_round_runs_at_top_effort_in_the_same_thread(
        repo, gh, tmp_path, monkeypatch, sdk_data, claude_session, mode, failure):
    history = "adopted" if failure.startswith("test-") else "new"
    if failure == "test-medium":
        history, effort, failure = "adopted", "medium", "test"
    elif failure == "test-xhigh":
        history, effort, failure = "adopted", "xhigh", "test"
    elif failure == "required-matrix-check-medium":
        history, effort, failure = "adopted", "medium", "required-matrix-check"
    else:
        effort = "low"
    expected_effort = ("xhigh" if mode == "claude" else "high") if failure in (
        "test", "finding", "required-check", "required-matrix-check") else effort
    env, folder, log = _round_client(repo, gh, tmp_path, monkeypatch, mode, effort,
                                     history=history, sdk_data=sdk_data,
                                     test_place="ci" if failure.endswith("check") else "local")
    family = "claude" if mode == "claude" else "codex"
    if family == "claude":
        monkeypatch.setenv("CODEX_THREAD_ID", "coordinator")
        monkeypatch.delenv("CLAUDECODE", raising=False)
    settings_before = (folder / "forge.toml").read_bytes()
    model = "claude-sonnet-5-5" if family == "claude" else "gpt-6.1-sol"
    commit_env = "STUB_CLAUDE_COMMIT_FROM" if family == "claude" else "STUB_CODEX_COMMIT_FROM"
    monkeypatch.setenv(commit_env, "1")
    (folder / "web/help.py").parent.mkdir(parents=True, exist_ok=True)
    (folder / "web/help.py").write_text("HELP = 'first round'\n", encoding="utf-8")
    test_text = ("print('intentional failed close test')\nraise SystemExit(1)\n"
                 if failure == "test" else "print('close test passed')\n")
    (folder / "fail_test.py").write_text(test_text, encoding="utf-8")
    if failure == "note":
        question = "Question: Should I keep the existing parser?"
        monkeypatch.setenv("STUB_CLAUDE_RESULT" if family == "claude" else "STUB_CODEX_TEXT",
                           "\n\n" + question)
    elif failure == "finding":
        env.reviews(blocked(finding("P1", "The help file is incomplete", "web/help.py")))
    elif failure.endswith("check"):
        # Matrix jobs count as their required check; optional jobs and similar prefixes do not.
        check = {"required-check": "tests", "optional-check": "lint",
                 "required-matrix-check": "tests (ubuntu-latest)",
                 "optional-matrix-check": "lint (ubuntu-latest)",
                 "similar-matrix-check": "tests-extra (ubuntu-latest)"}[failure]
        rows = [run(check, "failure"), run("forge-pr-check")]
        if failure == "required-matrix-check":
            rows.append(run("tests (windows-latest)"))
        elif failure != "required-check":
            rows.append(run("tests"))
        env.checks(rows)
        gh.respond("pr", "checks", stdout=json.dumps([
            {"name": row["name"], "bucket": "fail" if row["conclusion"] == "failure" else "pass",
             "link": "https://github.com/acme/shop/actions/runs/1/job/42"} for row in rows]))
        gh.respond("run", "view", stdout="failed check output\n")

    first = repo.forge("work", "BOARD/HELP")
    assert first.returncode == 0, first.stdout + first.stderr
    if family == "claude":
        assert f"Building BOARD/HELP with Claude ({model}, {effort})" in first.stdout
    if failure == "note":
        monkeypatch.delenv("STUB_CLAUDE_RESULT" if family == "claude" else "STUB_CODEX_TEXT",
                           raising=False)
    else:
        closed = env.close("BOARD/HELP")
        if failure in ("test", "finding", "required-check", "required-matrix-check"):
            assert closed.returncode == 1, closed.stdout + closed.stderr
        if failure == "test":
            assert "intentional failed close test" in closed.stdout
        elif failure == "finding":
            assert "The review left serious findings open" in closed.stderr
        elif failure in ("required-check", "required-matrix-check"):
            assert "tests" in closed.stdout + closed.stderr

    monkeypatch.delenv(commit_env, raising=False)
    retried = repo.forge("work", "BOARD/HELP", *( ["--note", "Keep the existing parser."]
                                                  if failure == "note" else []))
    assert retried.returncode == 0, retried.stdout + retried.stderr
    if family == "claude":
        [initial, retry] = calls(log)
        assert initial["session_id"] == retry["session_id"]
        assert (initial["options"]["model"], initial["options"]["effort"]) == (model, effort)
        assert (retry["options"]["model"], retry["options"]["effort"]) == (model, expected_effort)
    else:
        from test_codex_worker import _sent

        [initial] = _sent(log, "thread/start")
        [retry] = _sent(log, "thread/resume")
        conversation = re.search(r'Codex conversation "BOARD · The help": (.+)', first.stdout)[1]
        assert retry["threadId"] == conversation
        assert (initial["config"]["model"], initial["config"]["model_reasoning_effort"]) == (
            model, effort)
        assert (retry["config"]["model"], retry["config"]["model_reasoning_effort"]) == (
            model, expected_effort)
        for key in ("agents.default_subagent_model", "agents.default_subagent_reasoning_effort"):
            assert initial["config"][key] == retry["config"][key]
        assert (retry["config"]["agents.default_subagent_model"],
                retry["config"]["agents.default_subagent_reasoning_effort"]) == (
                    "gpt-6-luna", "max")
    events = [json.loads(line) for line in
              (repo.path / ".git/forge/events.jsonl").read_text("utf-8").splitlines()]
    starts = [event for event in events if event.get("item") == "BOARD/HELP"
              and event.get("event") == "run start" and event.get("kind") in ("work", "worker")]
    assert [(event["round"], event["effort"]) for event in starts] == [
        (1, effort), (2, expected_effort)]
    assert (folder / "forge.toml").read_bytes() == settings_before


def _failed_test_record(env, folder, task="HELP"):
    path = f".factory/stories/BOARD/tasks/{task}.json"
    state = json.loads((folder / path).read_text("utf-8"))
    env.commit(folder, path, json.dumps({**state, "tests": "FAILED tests/test_help.py"}),
               "Keep the previous failed test result")


@pytest.mark.parametrize("phase", ["design", "design-codex", "design-split", "read", "review", "signoff"])
def test_3_reviews_reads_and_design_keep_their_effort(
        repo, gh, tmp_path, monkeypatch, sdk_data, phase):
    # These paths have fixed settings. A worker's failure must not raise them.
    # Existing selection tests cover normal calls, without a failed worker round.
    if phase == "signoff":
        from test_proto_signoff import _client, _decision

        folder, answers, queue = _client(repo, tmp_path, monkeypatch)
        page = _decision(folder, answers)
        settings = (folder / "forge.toml").read_text("utf-8")
        (folder / "forge.toml").write_text(settings +
            '\n[models.review.codex]\nmodel = "gpt-6.1-sol"\neffort = "medium"\n',
            encoding="utf-8")
        record = folder / ".factory/fixes/record-client-approval.json"
        state = json.loads(record.read_text("utf-8"))
        record.write_text(json.dumps({**state, "tests": "FAILED tests/test_help.py"}),
                          encoding="utf-8")
        repo.git("add", "-A", cwd=folder)
        repo.git("commit", "-qm", "Keep the fixed sign-off settings", cwd=folder)
        queue.write_text(json.dumps([{"say": "model: gpt-6.1-sol\nthinking: medium\nautoreview done",
                                      "report": {"review_status": "scoped-clean", "findings": []}}]),
                         encoding="utf-8")
        accepted = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=folder)
        assert accepted.returncode == 0, accepted.stdout + accepted.stderr
        assert "status: accepted" in page.read_text("utf-8")
        call = [json.loads(line) for line in
                queue.with_suffix(".calls.jsonl").read_text("utf-8").splitlines()][-1]
        args = call["args"]
        assert args[args.index("--thinking") + 1] == "codex=medium"
        return

    design = phase.startswith("design")
    task = "PAGE" if design else "HELP"
    mode = phase.removeprefix("design-") if "design-" in phase else "claude"
    env, folder, log = _round_client(repo, gh, tmp_path, monkeypatch, mode,
                                     task=task, sdk_data=sdk_data, fixed=True)
    _failed_test_record(env, folder, task)
    if design:
        if mode == "codex":
            monkeypatch.setenv("CLAUDECODE", "1")
            monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
        worked = repo.forge("work", "BOARD/PAGE")
        assert worked.returncode == 0, worked.stdout + worked.stderr
        if mode == "codex":
            from test_codex_worker import _sent

            [call] = _sent(log, "thread/start")
            assert call["config"]["model_reasoning_effort"] == "medium"
        else:
            [call] = calls(repo.bin / "claude-sdk-calls.jsonl")
            assert call["options"]["effort"] == "medium"
    elif phase == "review":
        env.commit(folder, "fail_test.py", "raise SystemExit(0)\n", "Repair the failed test")
        closed = env.close("BOARD/HELP")
        assert closed.returncode == 0, closed.stdout + closed.stderr
        [call] = env.review_calls()
        args = call["args"]
        assert args[args.index("--thinking") + 1] == "codex=medium"
    else:
        import sys

        from conftest import _install
        from test_story import READER

        # Read the actual story worktree with its own settings, after its part failed.
        tree = tmp_path / "read-story"
        repo.git("worktree", "add", "-q", str(tree), "story/BOARD")
        failed_part = ".factory/stories/BOARD/tasks/HELP.json"
        env.commit(tree, failed_part, (folder / failed_part).read_text("utf-8"),
                   "Keep the failed part result for the cold read")
        _install(repo.bin, "claude", READER.format(python=sys.executable))
        read = repo.forge("read", "BOARD", cwd=tree)
        assert read.returncode == 0, read.stdout + read.stderr
        [call] = calls(repo.bin / "claude-calls.jsonl")
        args = call["args"]
        assert args[args.index("--effort") + 1] == "medium"


@pytest.mark.parametrize("family", ["claude", "codex"])
def test_5_effort_none_is_never_sent(
        repo, gh, tmp_path, monkeypatch, sdk_data, claude_session, family):
    # A repo's explicit none remains legal for a normal round. Forge itself must
    # replace it on a failure round, without changing the file or the model.
    from test_codex_worker import _sent

    env, folder, log = _round_client(repo, gh, tmp_path, monkeypatch, family,
                                     effort="none", sdk_data=sdk_data)
    if family == "claude":
        monkeypatch.setenv("CODEX_THREAD_ID", "coordinator")
        monkeypatch.delenv("CLAUDECODE", raising=False)
    # A standalone mechanical fix uses Lite rather than the task's Build/Fix entries.
    started = repo.forge("fix", "start", "Raise effort after failure", "--done",
                         "A failed round raises effort", "--kind", "mechanical")
    assert started.returncode == 0, started.stdout + started.stderr
    folder = Path(started.stdout.splitlines()[0].rsplit(" in ", 1)[1])
    item = "raise-effort-after-failure"
    before = (folder / "forge.toml").read_bytes()
    first = repo.forge("work", item)
    assert first.returncode == 0, first.stdout + first.stderr
    path = f".factory/fixes/{item}.json"
    state = json.loads((folder / path).read_text("utf-8"))
    env.commit(folder, path, json.dumps({**state, "tests": "FAILED tests/test_help.py"}),
               "Keep the standalone fix test failure")
    retry = repo.forge("work", item)
    assert retry.returncode == 0, retry.stdout + retry.stderr
    if family == "claude":
        initial, failed = calls(log)
        efforts = [call["options"]["effort"] for call in (initial, failed)]
        assert initial["session_id"] == failed["session_id"]
    else:
        [initial] = _sent(log, "thread/start")
        failed = _sent(log, "thread/resume")[-1]
        efforts = [call["config"]["model_reasoning_effort"] for call in (initial, failed)]
    assert efforts == ["none", "xhigh" if family == "claude" else "high"]
    assert (folder / "forge.toml").read_bytes() == before


@pytest.mark.parametrize("history,sdk_installed", [("new", True), ("new", False), ("adopted", True)],
                         ids=["installed", "missing", "adopted-installed"])
def test_7_claude_rounds_use_the_sdk_in_a_claude_session(
        repo, gh, tmp_path, monkeypatch, sdk_data, history, sdk_installed):
    _, _, log = _round_client(repo, gh, tmp_path, monkeypatch, "claude",
                              sdk_data=sdk_data, history=history)
    monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
    monkeypatch.setenv("CLAUDECODE", "1")
    if not sdk_installed:
        missing_data = tmp_path / "without-sdk"
        missing_data.mkdir()
        monkeypatch.setenv("XDG_DATA_HOME", str(missing_data))
    host = Session(repo, tmp_path / "claude-host", "claude-session")
    try:
        worked = host.forge("work", "BOARD/HELP")
        assert worked.returncode == 0, worked.stdout + worked.stderr
        if sdk_installed:
            [call] = calls(log)
            assert call["options"]["model"] == "claude-sonnet-5-5"
            assert "Run this round as a background worker subagent" not in worked.stdout
            assert "Start it on claude-sonnet-5-5" not in worked.stdout
        else:
            assert calls(log) == []
            assert "Run this round as a background worker subagent" in worked.stdout
            number = re.search(r"forge handback BOARD/HELP --round (\d+)", worked.stdout)[1]
            handed_back = host.forge("handback", "BOARD/HELP", "--round", number,
                                     "--subagent", "worker-session", "--text", "Built it.")
            assert handed_back.returncode == 0, handed_back.stdout + handed_back.stderr
    finally:
        host.close()


@pytest.mark.parametrize("family", ["codex", "claude"])
def test_8_native_round_names_the_requested_effort(
        repo, gh, tmp_path, monkeypatch, sdk_data, family):
    env, folder, log = _round_client(repo, gh, tmp_path, monkeypatch, family,
                                     sdk_data=sdk_data)
    if family == "claude":
        monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
        monkeypatch.setenv("CLAUDECODE", "1")
        missing_data = tmp_path / "without-sdk"
        missing_data.mkdir()
        monkeypatch.setenv("XDG_DATA_HOME", str(missing_data))
        model, raised = "claude-sonnet-5-5", "xhigh"
        host_name = "claude-session"
    else:
        monkeypatch.delenv("CLAUDECODE", raising=False)
        monkeypatch.setenv("CODEX_THREAD_ID", "codex-thread")
        model, raised = "gpt-6.1-sol", "high"
        host_name = "codex-session"

    (folder / "web").mkdir(exist_ok=True)
    (folder / "web/help.py").write_text("HELP = 'native worker result'\n", encoding="utf-8")
    (folder / "fail_test.py").write_text("print('intentional native close failure')\n"
                                         "raise SystemExit(1)\n", encoding="utf-8")
    repo.git("add", "-A", cwd=folder)
    repo.git("commit", "-q", "-m", "Prepare a native worker round", cwd=folder)

    host = Session(repo, tmp_path / f"{family}-host", host_name)
    try:
        before = calls(log)
        first = host.forge("work", "BOARD/HELP")
        assert first.returncode == 0, first.stdout + first.stderr
        assert f"Building BOARD/HELP with {family.title()} ({model}, low requested)" in first.stdout
        assert f"Start it on {model} at low effort" in first.stdout
        first_round = re.search(r"forge handback BOARD/HELP --round (\d+)", first.stdout)[1]
        handed_back = host.forge("handback", "BOARD/HELP", "--round", first_round,
                                 "--subagent", "worker-session", "--text", "Built it.",
                                 cwd=folder)
        assert handed_back.returncode == 0, handed_back.stdout + handed_back.stderr
        assert calls(log) == before

        closed = env.close("BOARD/HELP")
        assert closed.returncode == 1, closed.stdout + closed.stderr
        assert "intentional native close failure" in closed.stdout

        # Close may invoke the external reviewer; only the worker turns must stay native.
        before = calls(log)
        retry = host.forge("work", "BOARD/HELP")
        assert retry.returncode == 0, retry.stdout + retry.stderr
        assert f"Building BOARD/HELP with {family.title()} ({model}, {raised} requested)" in retry.stdout
        assert "Continue subagent worker-session with:" in retry.stdout
        assert f"Start it on {model} at {raised} effort" in retry.stdout
        assert "This effort is requested." in retry.stdout
        second_round = re.search(r"forge handback BOARD/HELP --round (\d+)", retry.stdout)[1]
        handed_back = host.forge("handback", "BOARD/HELP", "--round", second_round,
                                 "--subagent", "worker-session", "--text", "Still working.",
                                 cwd=folder)
        assert handed_back.returncode == 0, handed_back.stdout + handed_back.stderr

        events = [json.loads(line) for line in
                  (repo.path / ".git/forge/events.jsonl").read_text("utf-8").splitlines()]
        starts = [event for event in events if event.get("item") == "BOARD/HELP"
                  and event.get("event") == "run start" and event.get("kind") == "work"]
        assert [(event["round"], event["effort"], event["requested"]) for event in starts] == [
            (1, "low", True), (2, raised, True)]
        assert calls(log) == before
    finally:
        host.close()
