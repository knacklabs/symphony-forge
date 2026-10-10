"""Commands and installed git hooks load only the command they run."""
import json
import shutil
from pathlib import Path

import pytest

from conftest import ROOT
from test_close import env  # noqa: F401
from test_fix_new_repos_get_claude_as_their_worker_by import _new_repo
from test_split_commands import HELP_GOLDEN
from test_upgrade_command import RELEASE, unsynced_up  # noqa: F401

STORY = "FIX-EVERY-FORGE-PROCESS-INCLUDING-EACH-GIT-H"
HELP = {**HELP_GOLDEN,
        "test": "usage: forge test [-h] [--pytest BASE]\n\n"
                "Run related tests in the machine test lane, or pick pytest tests with --pytest\n\n"
                "options:\n  -h, --help     show this help message and exit\n  --pytest BASE\n",
        "land": "usage: forge land [-h] item\n\nBuild, close, fix and merge a task or fix\n\n"
                "positional arguments:\n  item\n\n"
                "options:\n  -h, --help  show this help message and exit\n",
        "hook handoff": "usage: forge hook handoff [-h]\n\n"
                        "Before compaction: save forge next beside the agent's decisions and lessons\n\n"
                        "options:\n  -h, --help  show this help message and exit\n",
        "hook merge-roadmap": "usage: forge hook merge-roadmap [-h] base ours theirs\n\n"
                              "Merge the roadmap or spotted list for git\n\n"
                              "positional arguments:\n  base\n  ours\n  theirs\n\n"
                              "options:\n  -h, --help  show this help message and exit\n"}


def _trace(repo, log):
    # Observe the real entry point; neither parsing nor command results are replaced.
    shim = repo.bin / "forge"
    shim.write_text(shim.read_text("utf-8").replace("from forge.cli import main", f'''
import argparse, ast, atexit, json
parsers, sources = [], []
original_init, original_parse = argparse.ArgumentParser.__init__, ast.parse
def observe_init(self, *args, **kwargs):
    original_init(self, *args, **kwargs)
    parsers.append(self.prog)
def observe_parse(source, filename="<unknown>", *args, **kwargs):
    sources.append(filename)
    return original_parse(source, filename, *args, **kwargs)
argparse.ArgumentParser.__init__ = observe_init
ast.parse = observe_parse
def record():
    with open({json.dumps(str(log))}, "a", encoding="utf-8") as out:
        out.write(json.dumps({{"argv": sys.argv[1:], "parsers": parsers,
                              "sources": sources,
                              "modules": sorted(name for name in sys.modules
                                                if name == "forge" or name.startswith("forge."))}}) + "\\n")
atexit.register(record)
from forge.cli import main
'''), "utf-8")


def _assert_hooks_are_small(repo, client, log):
    started = repo.forge("fix", "start", "Small hook client", "--done", "A small commit", cwd=client)
    assert started.returncode == 0, started.stdout + started.stderr
    work = Path(started.stdout.splitlines()[0].split(" in ", 1)[1].removesuffix("."))
    _trace(repo, log)
    (work / "change.txt").write_text("small change\n", "utf-8")
    repo.git("add", "change.txt", cwd=work)
    repo.git("commit", "-qm", "Small change", cwd=work)
    repo.git("push", "-q", "-u", "origin", "HEAD", cwd=work)
    runs = [json.loads(line) for line in log.read_text("utf-8").splitlines()]
    assert [run["argv"][:2] for run in runs] == [["hook", "pre-commit"], ["hook", "pre-push"]]
    for run in runs:
        assert len(run["modules"]) <= 6, run["modules"]
        assert run["parsers"] == ["forge", "forge hook", "forge " + " ".join(run["argv"][:2])]
        assert len(run["sources"]) == 1, run["sources"]


def test_1_new_clients_git_commit_and_push_build_only_their_hook(repo, gh, tmp_path):
    client = _new_repo(repo, gh, tmp_path)
    initialized = repo.forge("init", cwd=client)
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    _assert_hooks_are_small(repo, client, tmp_path / "starts.jsonl")


def test_2_earlier_adopted_clients_get_small_hooks_after_upgrade(unsynced_up):
    up = unsynced_up
    shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", up.repo.path, dirs_exist_ok=True)
    up.repo.git("switch", "-qc", "adoption")
    up.repo.git("add", "-A")
    up.repo.git("commit", "-qm", "Adopt earlier Forge")
    up.repo.git("switch", "-q", "main")
    up.repo.git("merge", "-q", "--ff-only", "adoption")
    up.repo.git("push", "-q", "origin", "main")
    upgraded = up.run(RELEASE)
    assert upgraded.returncode == 0, upgraded.stdout + upgraded.stderr
    # Use the installed release launcher and its hook shims, not this checkout's launcher.
    up.repo.bin = up.tmp / "uvbin"
    _assert_hooks_are_small(up.repo, up.folder, up.tmp / "starts.jsonl")


@pytest.mark.parametrize("words,expected", HELP.items())
def test_3_root_groups_and_commands_keep_their_help(repo, monkeypatch, words, expected):
    monkeypatch.setenv("COLUMNS", "80")
    result = repo.forge(*words.split(), "--help")
    assert (result.returncode, result.stdout, result.stderr) == (0, expected, "")


@pytest.mark.parametrize("words", [words for words, text in HELP.items()
                                   if words and "\ncommands:\n" not in text])
def test_4_command_help_parses_only_its_owner_and_builds_only_its_command(repo, tmp_path, words):
    log = tmp_path / "starts.jsonl"
    _trace(repo, log)
    result = repo.forge(*words.split(), "--help")
    assert result.returncode == 0, result.stderr
    [run] = [json.loads(line) for line in log.read_text("utf-8").splitlines()]
    assert len(run["sources"]) == 1, run["sources"]
    parts = words.split()
    assert run["parsers"] == ["forge", *["forge " + " ".join(parts[:n])
                                         for n in range(1, len(parts) + 1)]]
    assert len(run["modules"]) <= 4, run["modules"]
