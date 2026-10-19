"""Round receipts count both model responses, including a resumed conversation.

Command-boundary coverage of src/forge/codex_turn.py and src/forge/codex.py.
"""
import subprocess
import sys

import pytest

from conftest import ROOT, _install
from test_close import env, report  # noqa: F401
from test_codex_worker import _codex_repo, sdk_data  # noqa: F401
from test_fix_reviews_and_reads_record_their_cost import CODEX, CLAUDE, HELPER, run_end
from test_fix_reviews_always_run_on_codex_so_a_team_wi import _claude_only
from test_read_only_model_selection import _sdk
from test_run_records import configure
from test_story import DOC, new_story, setup, worktree
from test_upgrade_command import (NAME, RELEASE, _repo_adopted_on_the_previous_release,
                                  unsynced_up)  # noqa: F401

STORY = "round-token-totals"


def two_responses(repo):
    # The provider's `last` describes one model response; `total` includes earlier
    # responses and earlier rounds. Repeated snapshots must not count twice.
    source = (ROOT / 'tests/stubs/codex-app-server').read_text('utf-8')
    start = source.index('        last = {"inputTokens"')
    end = source.index('    turn = {', start)
    source = source[:start] + '''        prior = json.loads(os.environ.get("ROUND_PRIOR", "{}"))
        if prior:
            notify("thread/tokenUsage/updated", threadId=THREAD, turnId=TURN,
                   tokenUsage={"last": prior, "total": prior})
        for last, total in (
            ((100, 50, 10, 4), (100, 50, 10, 4)),
            ((200, 80, 30, 6), (300, 130, 40, 10)),
            ((200, 80, 30, 6), (300, 130, 40, 10))):
            keys = ("inputTokens", "cachedInputTokens", "outputTokens", "reasoningOutputTokens")
            last = dict(zip(keys, last))
            total = {key: value + prior.get(key, 0) for key, value in zip(keys, total)}
            last["totalTokens"] = last["inputTokens"] + last["outputTokens"]
            total["totalTokens"] = total["inputTokens"] + total["outputTokens"]
            notify("thread/tokenUsage/updated", threadId=THREAD, turnId=TURN,
                   tokenUsage={"last": last, "total": total})
        os.environ["ROUND_PRIOR"] = json.dumps(total)
''' + source[end:]
    source = source.replace('if method == "thread/resume":',
                            'if method == "thread/resume":\n'
                            '            old = {key: 10000 for key in ("inputTokens", "cachedInputTokens",\n'
                            '                "outputTokens", "reasoningOutputTokens", "totalTokens")}\n'
                            '            os.environ["ROUND_PRIOR"] = json.dumps(old)\n'
                            '            notify("thread/tokenUsage/updated", threadId=THREAD,\n'
                            '                turnId="previous-turn", tokenUsage={"last": old, "total": old})')
    source = source.replace('def main():', 'def main():\n    global TURN').replace(
        'turns += 1', 'turns += 1\n            TURN = "turn-stub-" + str(turns)')
    _install(repo.bin, 'codex-app-server', source)


@pytest.mark.parametrize('family,kind', [
    ('codex', 'worker'), ('codex', 'read'), ('codex', 'review'),
    ('claude', 'worker'), ('claude', 'read'), ('claude', 'review'),
    ('codex', 'adopted'), ('codex', 'worker_retry'),
])
def test_1_round_records_total_input_cached_output_and_reasoning_tokens(
        env, monkeypatch, request, tmp_path, family, kind):
    # Existing receipt tests exercise only one response per provider run. This
    # command-boundary regression supplies provider facts, never Forge receipts.
    repo = env.repo
    if kind == 'review':
        helper = HELPER.format(python=sys.executable, report=report())
        if family == 'codex':
            (tmp_path / 'autoreview/scripts/autoreview').write_text(helper, 'utf-8')
            source = CODEX.format(python=sys.executable).replace(
                'print(json.dumps(event), flush=True)',
                'if event["type"] == "turn.completed":\n'
                '        print(json.dumps({"type": "turn.completed", "usage": {\n'
                '            "input_tokens": 100, "cached_input_tokens": 50,\n'
                '            "output_tokens": 10, "reasoning_output_tokens": 4}}), flush=True)\n'
                '    print(json.dumps(event), flush=True)')
            _install(repo.bin, 'codex', source)
            expected = (1800, 1200, 240, 80)
        else:
            _claude_only(tmp_path, monkeypatch, repo.bin, helper)
            _install(repo.bin, 'claude', CLAUDE.format(python=sys.executable))
            expected = (1800, 1600, 240, None)
        item, _ = env.start_fix()
        result = repo.forge('close', item)
        assert result.returncode == 0, result.stdout + result.stderr
        end = run_end(repo, 'review')
    elif family == 'codex':
        if kind == 'adopted':
            _repo_adopted_on_the_previous_release(request.getfixturevalue('unsynced_up'))
            repo.git('-c', f'core.hooksPath={tmp_path / "no-hooks"}',
                     'merge', '-q', '--ff-only', f'fix/{NAME}')
            repo.git('-c', f'core.hooksPath={tmp_path / "no-hooks"}', 'push', '-q', 'origin', 'main')
        request.getfixturevalue('claude_session')
        if kind.startswith('worker'):
            _codex_repo(repo, monkeypatch, request.getfixturevalue('sdk_data'))
            command = ('work', 'BOARD/PAGE')
            if kind == 'worker_retry':
                monkeypatch.setenv('STUB_CODEX_OVERLOADED', '1')
                monkeypatch.setenv('FORGE_CODEX_RETRY_WAIT', '0')
        else:
            if kind == 'adopted':
                release = [sys.executable, str(tmp_path / 'releases' / RELEASE / 'forge')]
                made = subprocess.run([*release, 'story', 'new', 'SHOP', 'Shoppers can save a basket'],
                                      cwd=repo.path, capture_output=True, text=True, timeout=60)
                assert made.returncode == 0, made.stdout + made.stderr
                where = worktree(repo, 'story/SHOP')
            else:
                setup(repo)
                where = new_story(repo, 'SHOP')
            (where / 'plans/SHOP.md').write_text(DOC, 'utf-8')
            if kind != 'adopted':
                config = where / 'forge.toml'
                config.write_text(config.read_text('utf-8') +
                                  '\n[models.grill.codex]\nmodel = "gpt-6-sol"\neffort = "high"\n',
                                  'utf-8')
            _sdk(repo, monkeypatch, request.getfixturevalue('sdk_data'), repo.path)
            monkeypatch.setenv('STUB_CODEX_TEXT', 'No findings.')
            command = ('read', 'SHOP')
        two_responses(repo)
        # The second round resumes a conversation with earlier token use.
        for _ in range(2):
            result = (subprocess.run([*release, *command], cwd=repo.path, capture_output=True,
                                     text=True, timeout=60) if kind == 'adopted'
                      else repo.forge(*command))
            assert result.returncode == 0, result.stdout + result.stderr
            end = run_end(repo, 'work' if kind.startswith('worker') else 'read')
            assert tuple(end[key] for key in (
                'input_tokens', 'cached_input_tokens', 'output_tokens',
                'reasoning_output_tokens')) == ((600, 260, 80, 20) if kind == 'worker_retry'
                                                else (300, 130, 40, 10))
        return
    else:
        # Claude emits one cumulative ResultMessage after its two model turns.
        sdk = repo.bin / 'claude_agent_sdk/__init__.py'
        source = sdk.read_text('utf-8').replace(
            'yield ResultMessage(session_id=session, result=os.environ.get(',
            'yield AssistantMessage([TextBlock("Second response")], options.model)\n'
            '    yield ResultMessage(num_turns=2, session_id=session, usage={\n'
            '        "input_tokens": 30, "cache_read_input_tokens": 130,\n'
            '        "cache_creation_input_tokens": 140, "output_tokens": 40},\n'
            '        result=os.environ.get(')
        sdk.write_text(source, 'utf-8')
        if kind == 'worker':
            configure(env)
            item, _ = env.start_fix()
            result = repo.forge('work', item)
        else:
            setup(repo)
            where = new_story(repo, 'SHOP')
            (where / 'plans/SHOP.md').write_text(DOC, 'utf-8')
            _install(repo.bin, 'claude', CLAUDE.format(python=sys.executable))
            result = repo.forge('read', 'SHOP')
        assert result.returncode == 0, result.stdout + result.stderr
        end = run_end(repo, 'worker' if kind == 'worker' else 'read')
        expected = (300, 130, 40, None) if kind == 'worker' else (900, 800, 120, None)
    assert tuple(end[key] for key in (
        'input_tokens', 'cached_input_tokens', 'output_tokens',
        'reasoning_output_tokens')) == expected
