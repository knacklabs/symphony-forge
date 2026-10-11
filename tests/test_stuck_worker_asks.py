"""When a worker can't get past the same failing test or finding, Forge stops the item and prints
a ready-to-ask question; the owner's choice, such as switching the item to the other tool, is
recorded and the next round follows it. Both client hosts get the guide paragraph."""
from __future__ import annotations

import json
import sys

import pytest

from conftest import _install
from test_close import ROOT, blocked, env, finding  # noqa: F401
from test_codex_worker import sdk_data  # noqa: F401
from test_land import _workers, land  # noqa: F401
from test_setup import _fresh_client
from test_upgrade_command import _repo_adopted_on_the_previous_release, unsynced_up  # noqa: F401

STORY = "stuck-worker-asks"

# The repo's test commands: pytest naming the same test every run, pytest failing test_a once
# then test_b, Jest with the same failure but a different duration, and Jest failing a different
# test on each run.
SUITES = {
    "pytest same": 'print("FAILED test_readme.py::test_greeting - AssertionError")\nraise SystemExit(1)\n',
    "a then b": ('import pathlib\nrun = pathlib.Path("{runs}")\nfirst = not run.exists()\n'
                 'run.write_text("x")\n'
                 'print("FAILED test_readme.py::test_" + ("a" if first else "b"))\nraise SystemExit(1)\n'),
    "jest same": ('import random\nprint(f"  ✕ greets the reader ({{random.randint(2, 99)}} ms)")\n'
                  'raise SystemExit(1)\n'),
    "jest different": ('import pathlib\nrun = pathlib.Path("{runs}")\n'
                       'run.write_text(run.read_text() + "x" if run.exists() else "x")\n'
                       'print(f"  ✕ greeting case {{len(run.read_text())}} (3 ms)")\nraise SystemExit(1)\n'),
}
STUCK = {"pytest same": "the failing test test_readme.py::test_greeting",
         "a then b": "the failing test test_readme.py::test_b",
         "jest same": 'the failing check Tests on the close run ("✕ greets the reader")',
         "finding": 'the review finding "Saving drops the greeting" in app.py'}
NEXT = 'Next: forge close tidy-readme --resolve <switch|same|narrow|split> --reason "<human\'s choice>"'


def question(stuck):
    return ["Readme greets new readers is stuck. It should deliver: The readme opens with a greeting",
            f"Two rounds in a row left {stuck}.", "The worker tried: Worker round.",
            "Choose one: switch this item to Codex; keep Claude for one more round; or narrow or split it.",
            NEXT]


def _rounds(env, case):
    """Start the fix whose every close fails, then run work and close once (twice for a then b)."""
    if case == "finding":
        env.reviews(blocked(finding("P1", "Saving drops the greeting")))
    else:
        script = env.tmp / "suite.py"
        script.write_text(SUITES[case].format(runs=(env.tmp / "runs").as_posix()), "utf-8")
        toml = env.repo.path / "forge.toml"
        env.commit(env.repo.path, "forge.toml", toml.read_text("utf-8")
                   + "test = " + json.dumps(f"{sys.executable} {script}") + "\n")
        env.repo.git("push", "-q", "origin", "main")
    item, _ = env.start_fix()
    for _ in range(2 if case == "a then b" else 1):
        assert env.close(item).returncode == 1
        worked = env.repo.forge("work", item)
        assert worked.returncode == 0, worked.stdout + worked.stderr
    assert env.close(item).returncode == 1
    return item


@pytest.mark.parametrize("case", ["pytest same", "a then b", "jest same", "jest different", "finding"])
def test_1_two_rounds_leaving_the_same_failure_stop_with_a_question(land, case):
    env = land
    item = _rounds(env, case)
    stuck = env.repo.forge("work", item)
    if case == "jest different":  # different failing tests are progress, not a stuck worker
        assert stuck.returncode == 0, stuck.stdout + stuck.stderr
        return
    assert stuck.returncode == 1, stuck.stdout + stuck.stderr
    assert stuck.stderr.splitlines()[-5:] == question(STUCK[case])
    assert env.close(item).stderr.splitlines()[-5:] == question(STUCK[case])
    shown = env.repo.forge("next").stdout
    assert question(STUCK[case])[0] in shown and NEXT in shown
    assert env.close(item, "--resolve", "accept", "--reason", "Accept it").returncode == 1


@pytest.mark.parametrize("choice", ["same", "narrow", "split"])
def test_2_a_choice_buys_one_more_round_then_forge_asks_again(land, choice):
    env = land
    item = _rounds(env, "pytest same")
    assert env.repo.forge("work", item).returncode == 1
    chosen = env.close(item, "--resolve", choice, "--reason", "One more try")
    assert chosen.returncode == 0, chosen.stdout + chosen.stderr
    before = len(_workers(env))
    again = env.repo.forge("work", item)
    assert again.returncode == 0, again.stdout + again.stderr
    assert len(_workers(env)) == before + 1
    assert env.close(item).returncode == 1
    asked = env.repo.forge("work", item)
    assert asked.returncode == 1 and asked.stderr.splitlines()[-1] == NEXT


def test_3_switch_runs_the_next_round_on_the_other_tool(land, sdk_data, monkeypatch):
    env = land
    item = _rounds(env, "pytest same")
    assert env.repo.forge("work", item).returncode == 1
    chosen = env.close(item, "--resolve", "switch", "--reason", "Try the other tool")
    assert chosen.returncode == 0, chosen.stdout + chosen.stderr
    assert "Codex builds it" in env.repo.forge("next").stdout
    # A Codex this project trusts, as test_codex_worker sets it up.
    _install(env.repo.bin, "codex-app-server", (ROOT / "tests/stubs/codex-app-server").read_text("utf-8"))
    monkeypatch.setenv("CODEX_BIN", str(env.repo.bin / "codex-app-server"))
    monkeypatch.setenv("XDG_DATA_HOME", str(sdk_data))
    home = env.tmp / "codex-home"
    home.mkdir()
    (home / "config.toml").write_text(
        f'[projects.{json.dumps(str(env.repo.path))}]\ntrust_level = "trusted"\n', "utf-8")
    monkeypatch.setenv("CODEX_HOME", str(home))
    before = len(_workers(env))
    switched = env.repo.forge("work", item)
    assert switched.returncode == 0, switched.stdout + switched.stderr
    assert f"Building {item} with Codex" in switched.stdout
    assert (env.repo.bin / "codex-app-server.jsonl").exists()
    assert len(_workers(env)) == before  # Claude ran no round


@pytest.mark.parametrize("adoption", ["new init", "previous release upgrade and sync"])
def test_4_clients_receive_the_stuck_worker_guidance(unsynced_up, adoption):
    up = unsynced_up
    if adoption == "new init":
        client, made = _fresh_client(up.repo, up.env.gh, up.tmp)
        assert made.returncode == 0, made.stdout + made.stderr
    else:
        _repo_adopted_on_the_previous_release(up)
        client = up.folder
    for host in (".codex", ".claude"):
        guide = " ".join((client / host / "skills/forge/SKILL.md").read_text("utf-8").split())
        assert "When two rounds in a row leave the same failing test or finding" in guide
        assert ('`forge close <item> --resolve <switch|same|narrow|split> --reason '
                '"<human\'s choice>"`') in guide
