"""Planned prerequisites get the machine's next agent place before ordinary work."""
import json
import shutil
import sys

import pytest

from conftest import ROOT, _install, machine_cores
from test_board import DOC
from test_board_dependency_timelines import _client, _land_fixture
from test_close import env  # noqa: F401
from test_fix_agent_runs_wait_in_line import _until
from test_lanes_agents import finish, hold_agents, make_work, start
from test_story import GRILL, READER, claude_plan, hook, ready, worktree
from test_upgrade_command import unsynced_up  # noqa: F401

STORY = "unblockers-first"


@pytest.mark.parametrize("history", ["new", "adopted-v1.2.2"])
@pytest.mark.parametrize("dependency", ["after", "scope-only-draft"])
def test_1_waiting_prerequisites_start_first_and_explain_their_place(
        env, gh, tmp_path, claude_payload, history, unsynced_up, dependency):
    repo = env.repo
    if history == "new":
        _client(repo, gh, tmp_path, history)
    else:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
        repo.git("add", "-A")
        repo.git("commit", "-qm", "Adopt earlier Forge")
        _land_fixture(repo)
        version = repo.forge("--version").stdout.split()[-1]
        upgraded = repo.forge("upgrade", version)
        assert upgraded.returncode == 0, upgraded.stdout + upgraded.stderr
        branch = f"fix/upgrade-forge-to-{version.replace('.', '-')}"
        repo.git("merge", "-q", "--ff-only", branch)
        _land_fixture(repo)
    for host in (".codex", ".claude"):
        guide = " ".join((repo.path / host / "skills/forge/SKILL.md").read_text("utf-8").split())
        assert "Waiting items that other planned work waits on go first, first-come within each group" in guide
    machine_cores(repo, 2)
    configured = repo.forge("fix", "start", "Configure the client", "--done", "Workers use Claude",
                            "--slug", "configure-client")
    assert configured.returncode == 0, configured.stderr
    main = repo.path
    repo.path = worktree(repo, "fix/configure-client")
    version = repo.forge("--version").stdout.split()[-1]
    repo.write("forge.toml", f'version = "{version}"\nrepo = "client"\nworkers = "claude"\n'
               'models.build = { model = "opus", effort = "high" }\n'
               'models.fix = { model = "opus", effort = "high" }\n' + GRILL)
    repo.write("plans/roadmap.json", '{"items": [{"key": "SHOP"}, {"key": "WISH"}]}')
    repo.git("add", "-A")
    repo.git("commit", "-qm", "Configure the client")
    repo.path = main
    repo.git("merge", "-q", "--ff-only", "fix/configure-client")
    _land_fixture(repo)
    _install(repo.bin, "claude", READER.format(python=sys.executable))
    doc = DOC.replace("`tests/test_page.py` | SAVE | yes |",
                      "`tests/test_page.py` | none | yes |").replace(
                          "`tests/test_share.py` | SAVE | yes |",
                          "`tests/test_share.py` | SAVE, SHOW | yes |" if dependency == "after"
                          else "`tests/test_share.py` | none | yes |")
    story_tree = ready(repo, "SHOP", doc)
    approved = hook(repo, claude_plan(claude_payload, doc, cwd=story_tree))
    assert approved.returncode == 0, approved.stderr
    prerequisites = []
    for part in ("SAVE", "SHOW"):
        started = repo.forge("task", "start", f"SHOP/{part}")
        assert started.returncode == 0, started.stderr
        prerequisites.append((f"SHOP/{part}", worktree(repo, f"task/SHOP-{part}").name))
    if dependency == "scope-only-draft":
        # Unapproved work has no After entries; its scopes alone wait on SHOP's started parts.
        ready(repo, "WISH", doc)
    occupied = make_work(repo, "Already running")
    ordinary = [make_work(repo, title) for title in ("Earlier typo", "Later typo")]
    hold_agents(env)
    seen = lambda name: (repo.bin / f"started-{name}").exists()
    processes, outputs = {}, {}
    expected = [*prerequisites, *ordinary]
    try:
        process, output = start(repo.path, tmp_path / "occupied", repo, "work", occupied[0])
        processes[occupied[0]], outputs[occupied[0]] = process, output
        _until(lambda: seen(occupied[1]), "occupied agent place")
        gh.log.write_text("", encoding="utf-8")
        for index, (item, marker) in enumerate([ordinary[0], *prerequisites, ordinary[1]]):
            process, output = start(repo.path, tmp_path / f"waiting-{index}", repo, "work", item)
            processes[item], outputs[item] = process, output
            _until(lambda: "in line." in output.read_text("utf-8"), "waiting agent place")
            assert not seen(marker)
        assert not gh.calls(), "Agent admission must not read GitHub's board history"
        lanes = repo.forge("lanes", "--json")
        assert lanes.returncode == 0, lanes.stderr
        rows = json.loads(lanes.stdout)["agents"]["entries"]
        order = [occupied[0], *(item for item, _ in expected)]
        assert [row["item"] for row in rows] == order
        assert [row["place"] for row in rows] == [0, 1, 2, 3, 4]
        board = repo.forge("board", "--json")
        assert board.returncode == 0, board.stderr
        assert [row["item"] for row in json.loads(board.stdout)["lanes"]["agents"]["entries"]] == order
        reason = "Other planned work waits on this item, so it goes before runs nothing waits on."
        for item, _ in prerequisites:
            _until(lambda: reason in outputs[item].read_text("utf-8"), "prerequisite explanation")
        for item, _ in ordinary:
            _until(lambda: "Nothing waits on this item" in outputs[item].read_text("utf-8"),
                   "ordinary work explanation")
        for index, (item, marker) in enumerate([occupied, *expected]):
            _until(lambda: seen(marker), "the next admitted agent")
            assert all(not seen(later) for _, later in expected[max(0, index):])
            (repo.bin / f"go-{marker}").touch()
            assert processes[item].wait(timeout=30) == 0, outputs[item].read_text("utf-8")
    finally:
        finish(repo, list(processes.values()))


def test_2_finished_story_history_does_not_add_git_processes_to_agent_admission(
        env, tmp_path, monkeypatch, claude_payload):
    repo = env.repo
    config = (repo.path / "forge.toml").read_text("utf-8")
    repo.write("forge.toml", config + GRILL +
               'models.fix = { model = "opus", effort = "high" }\n')
    repo.write("plans/roadmap.json", '{"items": [{"key": "SHOP"}]}')
    repo.git("add", "-A")
    repo.git("commit", "-qm", "Plan the unfinished story")
    _land_fixture(repo)
    _install(repo.bin, "claude", READER.format(python=sys.executable))
    # Neither of these runs unblocks a part, so admission must finish inspecting the plans.
    doc = DOC.replace("| SAVE | yes |", "| none | yes |")
    tree = ready(repo, "SHOP", doc)
    approved = hook(repo, claude_plan(claude_payload, doc, cwd=tree))
    assert approved.returncode == 0, approved.stderr
    for part in ("SHOW", "SHARE"):
        made = repo.forge("task", "start", f"SHOP/{part}")
        assert made.returncode == 0, made.stderr
    machine_cores(repo, 2)
    occupied = make_work(repo, "Already running")
    hold_agents(env)
    processes = []
    try:
        process, _ = start(repo.path, tmp_path / "occupied-history", repo, "work", occupied[0])
        processes.append(process)
        _until(lambda: (repo.bin / f"started-{occupied[1]}").exists(), "occupied agent place")
        counts = []
        for index, part in enumerate(("SHOW", "SHARE")):
            if index:
                # Text fixtures represent landed history; stale story refs must not reopen it.
                for number in range(40):
                    key = f"FINISHED-{number}"
                    repo.write(f".factory/stories/{key}/story.json",
                               json.dumps({"status": "done", "branch": f"story/{key}"}))
                    repo.write(f"plans/{key}.md", doc)
                repo.git("add", "-A")
                repo.git("commit", "-qm", "Earlier stories are finished")
                _land_fixture(repo)
                for number in range(40):
                    repo.git("branch", f"story/FINISHED-{number}")
            trace = tmp_path / f"admission-{index}.jsonl"
            with monkeypatch.context() as tracing:
                tracing.setenv("GIT_TRACE2_EVENT", trace.as_posix())
                process, output = start(repo.path, tmp_path / f"history-{index}",
                                        repo, "work", f"SHOP/{part}")
            processes.append(process)
            _until(lambda: "in line." in output.read_text("utf-8"), "waiting agent admission")
            events = [json.loads(line) for line in trace.read_text("utf-8").splitlines()]
            counts.append(sum(event.get("event") == "start" for event in events))
        assert counts[1] <= counts[0] + 2, counts
    finally:
        finish(repo, processes)
