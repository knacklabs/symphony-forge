"""Every review and plan read records its model, effort, chat and token use when it ends."""
import json
import sys

import pytest

import conftest
from test_close import report, env  # noqa: F401  (env is a fixture)
from test_codex_worker import sdk_data  # noqa: F401
from test_fix_reviews_always_run_on_codex_so_a_team_wi import _claude_only
from test_run_records import (_previously_adopted_client_records_runs_after_upgrade,
                              _readers_inherit_worker_environment, records)
from test_story import DOC, new_story, setup
from test_upgrade_command import unsynced_up  # noqa: F401

# The pinned helper names its model and thinking, then runs the engine and keeps its output.
HELPER = '''#!{python}
import json, subprocess, sys, tempfile
args = sys.argv[1:]
engine = args[args.index("--engine") + 1]
print("model: review-model", flush=True)
print("thinking: high", flush=True)
if engine == "codex":
    command = [args[args.index("--codex-bin") + 1], "exec", "--json", "-C", tempfile.mkdtemp(), "-"]
else:
    command = [args[args.index("--claude-bin") + 1], "--print", "--output-format", "json"]
subprocess.run(command, input="Review the change.", capture_output=True, text=True, check=True)
with open(args[args.index("--json-output") + 1], "w", encoding="utf-8") as out:
    json.dump({report!r}, out)
'''
# What `codex exec --json` and `claude --output-format json|stream-json` print.
CODEX = '''#!{python}
import json, sys
sys.stdin.read()
for event in ({{"type": "thread.started", "thread_id": "thread-review"}}, {{"type": "turn.started"}},
              {{"type": "turn.completed", "usage": {{"input_tokens": 900, "cached_input_tokens": 600,
                                                   "output_tokens": 120, "reasoning_output_tokens": 40}}}}):
    print(json.dumps(event), flush=True)
'''
CLAUDE = '''#!{python}
import json, sys
sys.stdin.read()
print(json.dumps({{"type": "result", "subtype": "success", "result": "No blocking notes.",
                  "session_id": "session-claude",
                  "usage": {{"input_tokens": 10, "cache_read_input_tokens": 800,
                            "cache_creation_input_tokens": 90, "output_tokens": 120}}}}), flush=True)
'''
CLAUDE_SPENT = {"chat": "session-claude", "input_tokens": 900, "cached_input_tokens": 800,
                "output_tokens": 120, "reasoning_output_tokens": None}
CODEX_SERVER_SPENT = {"input_tokens": 1200, "cached_input_tokens": 1000, "output_tokens": 300,
                      "reasoning_output_tokens": 0}


def run_end(repo, kind):
    return [row for row in records(repo, 'events.jsonl')
            if row['event'] == 'run end' and row['kind'] == kind][-1]


@pytest.mark.parametrize('case', ['review_codex', 'review_claude', 'read_codex', 'read_claude',
                                  'existing_repo'])
def test_1_reviews_and_reads_record_model_effort_chat_and_tokens(env, monkeypatch, request,
                                                                 tmp_path, case):
    repo = env.repo
    if case.startswith('review'):
        helper = HELPER.format(python=sys.executable, report=report())
        if case == 'review_codex':
            (tmp_path / 'autoreview' / 'scripts' / 'autoreview').write_text(helper, 'utf-8')
            conftest._install(repo.bin, 'codex', CODEX.format(python=sys.executable))
            spent = {"chat": "thread-review", "input_tokens": 900, "cached_input_tokens": 600,
                     "output_tokens": 120, "reasoning_output_tokens": 40}
        else:
            _claude_only(tmp_path, monkeypatch, repo.bin, helper)
            conftest._install(repo.bin, 'claude', CLAUDE.format(python=sys.executable))
            spent = CLAUDE_SPENT
        item, _ = env.start_fix()
        closed = repo.forge('close', item)
        assert closed.returncode == 0, closed.stderr
        assert run_end(repo, 'review') | spent == run_end(repo, 'review')
        assert (run_end(repo, 'review')['model'], run_end(repo, 'review')['effort']) == (
            'review-model', 'high')
    elif case == 'read_codex':
        _readers_inherit_worker_environment(repo, monkeypatch, request, 'codex')
        end = run_end(repo, 'read')
        assert end | CODEX_SERVER_SPENT == end and end['chat']
        assert (end['model'], end['effort']) == ('gpt-6-sol', 'high')
    elif case == 'read_claude':
        setup(repo)
        where = new_story(repo, 'SHOP')
        (where / 'plans' / 'SHOP.md').write_text(DOC, 'utf-8')
        conftest._install(repo.bin, 'claude', CLAUDE.format(python=sys.executable))
        read = repo.forge('read', 'SHOP')
        assert read.returncode == 0, read.stderr
        end = run_end(repo, 'read')
        assert end | CLAUDE_SPENT == end
        assert (end['model'], end['effort']) == ('opus', 'high')
    else:
        # A repo adopted on an earlier release gets it on upgrade, with no setting: its Codex
        # rounds go through the same recording as a Codex read.
        _previously_adopted_client_records_runs_after_upgrade(
            request.getfixturevalue('unsynced_up'), monkeypatch, request.getfixturevalue('sdk_data'))
        end = run_end(env.repo, 'work')
        assert end | CODEX_SERVER_SPENT == end and end['chat'] and end['model']
