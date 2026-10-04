"""Command-boundary proof for stage times and actionable run/question occurrences."""
import json
import sys
from datetime import datetime
from uuid import UUID

import pytest

from test_close import env  # noqa: F401
from test_codex_worker import _codex_repo, sdk_data  # noqa: F401
from test_worker import install_claude
from test_story import DOC, new_story, setup

STORY = "FORGE-MOD-1-RUNS"


def records(repo, name):
    path = repo.path / '.git' / 'forge' / name
    return [json.loads(line) for line in path.read_text('utf-8').splitlines()]


def require_worker_environment(path):
    # Assert at the external process edge, before it can supply a result to Forge.
    source = path.read_text('utf-8')
    lines = source.splitlines(keepends=True)
    lines.insert(1, 'import os\nassert os.environ.get("FORGE_WORKER") == "1"\n')
    path.write_text(''.join(lines), 'utf-8')


def configure(env):
    repo = env.repo
    install_claude(repo)
    config = repo.path / 'forge.toml'
    config.write_text(config.read_text('utf-8') +
                      'models.lite = { model = "sonnet", effort = "medium" }\n'
                      f'test = "{sys.executable} -c \'print(123)\'"\n', 'utf-8')
    repo.git('add', 'forge.toml')
    repo.git('commit', '-q', '-m', 'Configure runs')
    repo.git('push', '-q', 'origin', 'main')
    return repo


@pytest.mark.parametrize('family', ['claude', 'codex', 'docs'])
def test_2_each_round_records_worker_tests_review_and_ci_times(env, monkeypatch, request, family):
    # Older timing tests cover durations, but not the round association or close's test stage.
    if family == 'docs':
        _docs_only_close_records_skipped_tests(env)
        return
    repo = env.repo
    if family == 'claude':
        configure(env)
        require_worker_environment(repo.bin / 'claude')
        item, where = env.start_fix()
    else:
        where, _ = _codex_repo(repo, monkeypatch, request.getfixturevalue('sdk_data'))
        require_worker_environment(repo.bin / 'codex-app-server')
        item = 'BOARD/PAGE'
        config = where / 'forge.toml'
        env.commit(where, 'forge.toml', 'checks = ["tests", "forge-pr-check"]\n'
                   + f'test = "{sys.executable} -c \'print(123)\'"\n'
                   + config.read_text('utf-8'))
    require_worker_environment(env.queue.parent / 'autoreview' / 'scripts' / 'autoreview')
    for number in (1, 2):
        worked = repo.forge('work', item)
        assert worked.returncode == 0, worked.stderr
        env.commit(where, 'app.py', f'print({number})\n')
        closed = repo.forge('close', item)
        assert closed.returncode == 0, closed.stderr
    timings = records(repo, 'timings.jsonl')
    assert [(row['round'], row['step'], row['outcome']) for row in timings] == [
        (number, step, outcome) for number in (1, 2) for step, outcome in
        [('worker round', 'completed'), ('test run', 'passed'), ('review', 'clean'),
         ('CI wait', 'passed')]]
    for row in timings:
        assert row['item'] == item
        assert row['seconds'] > 0
        datetime.fromisoformat(row['start'])
    events = records(repo, 'events.jsonl')
    assert len({row['id'] for row in events}) == len(events)
    assert [row['round'] for row in events if row['event'] == 'review result'] == [1, 2]
    for row in events:
        UUID(row['id'])
    starts = [row for row in events if row['event'] == 'run start']
    ends = [row for row in events if row['event'] == 'run end']
    assert starts and {row['id'] for row in starts} == {row['run_id'] for row in ends}


def _docs_only_close_records_skipped_tests(env):
    repo = configure(env)
    item, _ = env.start_fix({'README.md': '# Hello\n'})
    closed = repo.forge('close', item)
    assert closed.returncode == 0, closed.stderr
    tests = [row for row in records(repo, 'timings.jsonl') if row['step'] == 'test run']
    assert len(tests) == 1 and tests[0]['outcome'] == 'skipped'


@pytest.mark.parametrize('case', [
    'questions_claude', 'questions_codex', 'readers_claude', 'readers_codex',
    'reviewers_claude', 'reviewers_codex', 'failed_test', 'failed_review', 'failed_worker',
    'control_codex',
])
def test_3_run_and_question_occurrences(env, repo, monkeypatch, request, tmp_path, case):
    action, family = case.split('_')
    if action == 'questions':
        _repeated_worker_questions(env, monkeypatch, request, family)
    elif action == 'readers':
        _readers_inherit_worker_environment(repo, monkeypatch, request, family)
    elif action == 'reviewers':
        _review_processes_inherit_worker_environment(env, tmp_path, monkeypatch, family)
    elif action == 'control':
        _control_requests_do_not_start_agent_runs(env, monkeypatch, request)
    else:
        _failures_keep_run_end_occurrences(env, monkeypatch, family)


def _repeated_worker_questions(env, monkeypatch, request, family):
    # The external agent supplies text only; Forge must detect, persist and pause on it itself.
    repo = env.repo
    question = 'Question: May I use the existing parser?'
    if family == 'codex':
        _codex_repo(repo, monkeypatch, request.getfixturevalue('sdk_data'))
        require_worker_environment(repo.bin / 'codex-app-server')
        item = 'BOARD/PAGE'
        monkeypatch.setenv('STUB_SAY', '\n\n' + question)
    else:
        configure(env)
        stub = repo.bin / 'claude'
        require_worker_environment(stub)
        stub.write_text(stub.read_text('utf-8').replace(
            'print("stub claude: built it")', f'print("\\n\\n" + {question!r})'), 'utf-8')
        item, _ = env.start_fix()
    for args in [(), ('--note', 'Yes, use it.')]:
        worked = repo.forge('work', item, *args)
        assert worked.returncode == 0, worked.stderr
        assert question in worked.stdout
        blocked = repo.forge('work', item)
        assert blocked.returncode != 0 and 'waiting for an answer' in blocked.stderr
    events = records(repo, 'events.jsonl')
    questions = [row for row in events if row['event'] == 'worker question']
    assert [row['question'] for row in questions] == [question, question]
    assert [row['round'] for row in questions] == [1, 2]
    assert questions[0]['id'] != questions[1]['id']
    ends = [row for row in events if row['event'] == 'run end' and row['item'] == item]
    assert len(ends) >= 2 and len({row['id'] for row in ends}) == len(ends)


def _readers_inherit_worker_environment(repo, monkeypatch, request, family):
    setup(repo)
    where = new_story(repo, 'SHOP')
    (where / 'plans' / 'SHOP.md').write_text(DOC, 'utf-8')
    if family == 'claude':
        require_worker_environment(repo.bin / 'claude')
    else:
        from conftest import ROOT, _install
        sdk = request.getfixturevalue('sdk_data')
        monkeypatch.setenv('XDG_DATA_HOME', str(sdk))
        # Every Codex turn now requires project trust so Forge's hooks run, including cold reads.
        home = repo.path.parent / 'reader-codex-home'
        home.mkdir()
        (home / 'config.toml').write_text(
            f'[projects.{json.dumps(str(repo.path))}]\ntrust_level = "trusted"\n', 'utf-8')
        monkeypatch.setenv('CODEX_HOME', str(home))
        _install(repo.bin, 'codex-app-server',
                 (ROOT / 'tests' / 'stubs' / 'codex-app-server').read_text('utf-8'))
        require_worker_environment(repo.bin / 'codex-app-server')
        monkeypatch.setenv('CODEX_BIN', str(repo.bin / 'codex-app-server'))
        monkeypatch.delenv('CODEX_THREAD_ID')
        monkeypatch.setenv('CLAUDECODE', '1')
        config = where / 'forge.toml'
        config.write_text(config.read_text('utf-8') +
                          'models.grill.codex = { model = "gpt-6-sol", effort = "high" }\n',
                          'utf-8')
    read = repo.forge('read', 'SHOP')
    assert read.returncode == 0, read.stderr
    events = [row for row in records(repo, 'events.jsonl') if row['kind'] == 'read']
    assert [row['event'] for row in events] == ['run start', 'run end']
    assert events[1]['run_id'] == events[0]['id']


def _failures_keep_run_end_occurrences(env, monkeypatch, failure):
    repo = configure(env)
    item, where = env.start_fix()
    if failure == 'worker':
        monkeypatch.setenv('STUB_CLAUDE_EXIT', '3')
        failed = repo.forge('work', item)
        step = 'worker round'
    else:
        if failure == 'test':
            config = where / 'forge.toml'
            env.commit(where, 'forge.toml', config.read_text('utf-8').replace(
                'print(123)', 'raise SystemExit(1)'))
            step = 'test run'
        else:
            from test_close import FAILED
            env.reviews(FAILED)
            step = 'review'
        failed = repo.forge('close', item)
    assert failed.returncode != 0
    assert any(row['step'] == step and row['outcome'] == 'failed'
               for row in records(repo, 'timings.jsonl'))
    events = records(repo, 'events.jsonl')
    assert any(row['event'] == 'run end' and row['outcome'] == 'failed' for row in events)
    if failure == 'review':
        assert any(row['event'] == 'review result' and row['outcome'] == 'failed'
                   for row in events)


def _review_processes_inherit_worker_environment(env, tmp_path, monkeypatch, family):
    from conftest import _install
    from test_claude_review_reads_the_checkout import HELPER
    from test_close import report
    repo = env.repo
    helper = HELPER.format(python=sys.executable, report=report())
    if family == 'claude':
        from test_fix_reviews_always_run_on_codex_so_a_team_wi import _claude_only
        _claude_only(tmp_path, monkeypatch, repo.bin, helper)
        _install(repo.bin, 'claude', f'#!{sys.executable}\nimport sys\nsys.stdin.read()\n')
        require_worker_environment(repo.bin / 'claude')
    else:
        require_worker_environment(repo.bin / 'codex')
    item, _ = env.start_fix()
    closed = repo.forge('close', item)
    assert closed.returncode == 0, closed.stderr


def _control_requests_do_not_start_agent_runs(env, monkeypatch, request):
    from test_chatview_start import _ready
    from test_codex_worker import _sent
    repo = env.repo
    where, calls = _ready(repo, monkeypatch, request.getfixturevalue('sdk_data'))
    config = where / 'forge.toml'
    env.commit(where, 'forge.toml', 'checks = ["tests", "forge-pr-check"]\n'
               + config.read_text('utf-8'))
    worked = repo.forge('work', 'BOARD/PAGE')
    assert worked.returncode == 0, worked.stderr
    env.gh.respond('pr', 'view', stdout=json.dumps({
        'number': 7, 'url': 'https://github.com/acme/board/pull/7',
        'headRefName': 'task/BOARD-PAGE'}))
    closed = repo.forge('close', 'BOARD/PAGE')
    assert closed.returncode == 0, closed.stderr
    assert _sent(calls, 'thread/attachment/add')
    # Attaching the PR uses the SDK but starts no turn; it must not wake the session as a run end.
    runs = [row for row in records(repo, 'events.jsonl')
            if row.get('kind') == 'work']
    assert [row['event'] for row in runs] == ['run start', 'run end']
    assert runs[-1]['outcome'] == 'completed'
