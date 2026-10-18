"""The whole fix's generated output stays cheap to check at the real commit hook."""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from statistics import median

import pytest

from test_fix_sync_output_skips_fix_limit import git, hand_edit, synced_fix
from test_githooks import NEXT_PROMOTE, hooked

STORY = "FORGE-GITCOST-1"


@pytest.mark.parametrize("kind", ["new-repo", "new-husky", "adopted-v1.2.2"])
def test_2_generated_file_check_is_fast_and_checks_the_whole_fix(repo, kind):
    # Protect the cost and the base-to-index contract together: a later ordinary
    # commit must keep the earlier generated exemption, but a hand edit must count.
    if kind == "adopted-v1.2.2":
        shutil.copytree(Path(__file__).parent / "fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
        repo.git("add", "-A")
        repo.git("commit", "-qm", "Earlier adoption")
    if kind == "new-husky":
        repo.write("nested/.husky/pre-commit", "#!/bin/sh\necho client-check >&2\n")
        repo.git("config", "core.hooksPath", "nested/.husky/_")
    repo.write("package.json", '{"engines": {"node": "24"}}\n')
    repo.write("requirements-dev.txt", "pytest-split\n")
    repo.git("add", "-A")
    repo.git("commit", "-qm", "Client build inputs")
    hooked(repo)
    fix, folder = synced_fix(repo)
    if kind == "new-husky":
        wrappers = folder / "nested/.husky/_"
        wrappers.mkdir(parents=True, exist_ok=True)
        (wrappers / ".gitignore").write_text("*\n", encoding="utf-8")
        wrapper = wrappers / "pre-commit"
        shutil.copyfile(Path(__file__).parent / "fixtures/husky-v9.1.7/husky", wrapper)
        wrapper.chmod(0o755)
    for n in range(5):
        path = folder / f"src/f{n}.py"
        path.parent.mkdir(exist_ok=True)
        path.write_text("x = 1\n", encoding="utf-8")
    log = repo.bin / "generated-check.jsonl"
    shim = repo.bin / "forge"
    shim.write_text(shim.read_text("utf-8").replace("from forge.cli import main", f'''
import ast, json, time
from forge import sync
active = None
parses = 0
commands = []
def observe(event, args):
    if active is not None and event == "subprocess.Popen":
        commands.append(args[1])
sys.addaudithook(observe)
original_parse = ast.parse
def parse(*args, **kwargs):
    global parses
    if active is not None:
        parses += 1
    return original_parse(*args, **kwargs)
ast.parse = parse
original_synced = sync.synced
def timed(*args, **kwargs):
    global active, parses, commands
    parses, commands = 0, []
    active = time.perf_counter()
    try:
        return original_synced(*args, **kwargs)
    finally:
        elapsed = time.perf_counter() - active
        active = None
        with open({json.dumps(str(log))}, "a", encoding="utf-8") as out:
            out.write(json.dumps([elapsed, parses, commands]) + "\\n")
sync.synced = timed
from forge.cli import main'''), encoding="utf-8")

    def measure(status):
        # A shared runner can pause one process. Use the owner-approved 0.2-second budget
        # for the median of five real checks of each unchanged staged snapshot.
        log.write_text("", encoding="utf-8")
        for _ in range(5):
            checked = repo.forge("hook", "pre-commit", cwd=folder)
            assert checked.returncode == status, checked.stdout + checked.stderr
        samples = [json.loads(line) for line in log.read_text("utf-8").splitlines()]
        assert len(samples) == 5, samples
        assert median(elapsed for elapsed, _, _ in samples) < 0.2, samples
        for _, parses, commands in samples:
            assert parses == 0, samples
            assert not any("worktree" in command for command in commands), commands

    def commit(message):
        repo.git("add", "-A", cwd=folder)
        measure(0)
        return git(folder, "commit", "-qm", message)

    first = commit("Sync and change five source files")
    assert first.returncode == 0, first.stderr
    (folder / "src/f0.py").write_text("x = 2\n", encoding="utf-8")
    second = commit("Change only ordinary source")
    assert second.returncode == 0, second.stderr
    hand_edit(folder)
    repo.git("add", "-A", cwd=folder)
    # An unstaged repair cannot hide what is actually being committed.
    (folder / ".claude/settings.json").write_text(
        repo.git("show", "HEAD:.claude/settings.json", cwd=folder) + "\n", encoding="utf-8")
    measure(1)
    refused = git(folder, "commit", "-qm", "Hand edit generated settings")
    assert refused.returncode != 0
    expected = (
        f"Fix {fix} changes 6 code files, over the limit of 5, so it has to become a story, unless "
        "the human allows it with forge fix allow-large.\n" + NEXT_PROMOTE.format(fix=fix))
    # Husky runs the client's check first and adds its own failure notice.
    if kind == "new-husky":
        expected = "client-check\n" + expected + "husky - pre-commit script failed (code 1)\n"
    assert refused.stderr == expected
