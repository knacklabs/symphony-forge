"""Builders lend their agent place during tests and reclaim it before returning."""
import json
import sys

import pytest

from conftest import machine_cores
from test_close import env  # noqa: F401
from test_fix_agent_runs_wait_in_line import _until
from test_lanes_agents import finish, hold_agents, start
from test_agent_admission_priorities import make_work
from test_lanes_tests import shell
from test_runs_wait_for_machine_load import client
from test_story import worktree

STORY = "FIX-BUILD-TEST-BALANCE"


# Audit: the observable contract is admission of another worker while a builder
# tests, and admission before that builder returns. Existing tests start tests
# outside workers. A retained reservation breaks this case. No production seam:
# only the external model provider is replaced; both Forge commands are real.
@pytest.mark.parametrize("adopted", [False, True], ids=["new", "earlier-adoption"])
def test_1_builder_lends_its_place_and_reclaims_it_before_continuing(env, tmp_path, adopted):
    repo = client(env, tmp_path, adopted)
    machine_cores(repo, 2)
    cfg = (repo.path / "forge.toml").read_text("utf-8")
    cfg = '\n'.join(line for line in cfg.splitlines()
                    if line.partition('=')[0].strip() not in ('workers', 'test', 'fast_test'))
    command = shell([sys.executable, '-c', 'print("client tests passed")'])
    env.commit(repo.path, "forge.toml", 'workers = "claude"\ntest = ' + json.dumps(command) + '\n' + cfg)
    repo.git('push', '-q', 'origin', 'main')
    first, first_name = make_work(repo, 'Builder testing')
    second, second_name = make_work(repo, 'Other builder')
    hold_agents(env)
    sdk = repo.bin / 'claude_agent_sdk/__init__.py'
    source = sdk.read_text('utf-8')
    source = source.replace('    name = Path.cwd().name',
        '    name = Path.cwd().name\n'
        f'    if name == {first_name!r}:\n'
        f'        subprocess.run([sys.executable, {(repo.bin / "forge").as_posix()!r}, "test"], check=True)\n'
        '        (here / "test-returned").touch()')
    sdk.write_text(source, 'utf-8')
    gate = tmp_path / 'release-tests'
    script = tmp_path / 'hold.py'
    script.write_text('import pathlib, time\n'
        f'gate = pathlib.Path({gate.as_posix()!r})\n'
        f'pathlib.Path({(tmp_path / "tests-held").as_posix()!r}).touch()\n'
        'while not gate.exists(): time.sleep(0.05)\n', 'utf-8')
    holder, _ = env.start('test-holder', 'fix/test-holder', '.factory/fixes/test-holder.json',
        {'kind': 'fix', 'why': 'Hold tests', 'done_when': 'Tests finish'}, {'app.py': 'x=1\n'})
    holder_where = worktree(repo, 'fix/' + holder)
    settings = holder_where / 'forge.toml'
    settings.write_text('fast_test = ' + json.dumps(shell([sys.executable, str(script)])) + '\n' + settings.read_text('utf-8'), 'utf-8')
    processes = []
    try:
        process, _ = start(holder_where, tmp_path / 'test-holder-run', repo, 'test')
        processes.append(process)
        _until((tmp_path / 'tests-held').exists, 'tests to hold the lane')
        first_run, output = start(repo.path, tmp_path / 'first', repo, 'work', first)
        processes.append(first_run)
        _until(lambda: 'Forge test processes' in output.read_text('utf-8') or first_run.poll() is not None,
               'builder tests to queue')
        assert first_run.poll() is None, output.read_text('utf-8')
        second_run, second_output = start(repo.path, tmp_path / 'second', repo, 'work', second)
        processes.append(second_run)
        _until(lambda: (repo.bin / f'started-{second_name}').exists() or 'Forge agents' in second_output.read_text('utf-8'),
               'the other builder to receive the lent place')
        assert (repo.bin / f'started-{second_name}').exists(), second_output.read_text('utf-8')
        gate.touch()
        _until(lambda: 'Forge agents' in output.read_text('utf-8') or (repo.bin / 'test-returned').exists(),
               'the testing builder to reclaim a place')
        assert not (repo.bin / 'test-returned').exists()
        (repo.bin / f'go-{second_name}').touch()
        assert second_run.wait(timeout=30) == 0, second_output.read_text('utf-8')
        _until((repo.bin / 'test-returned').exists, 'the builder to resume')
    finally:
        gate.touch()
        finish(repo, processes)
