"""Agent shells tell the owner exactly where to enable agent merges."""
import pytest

from test_close import env  # noqa: F401
from test_merge_enable import branches, enable, unchanged
from test_windows_stdin_bytes import adopt_earlier_release, start_new_client

STORY = "merge-enable-wording"


@pytest.mark.platform
@pytest.mark.parametrize("history,identities", [
    ("new", ("CODEX_THREAD_ID",)),
    ("new", ("CLAUDECODE",)),
    ("new", ("CODEX_THREAD_ID", "CLAUDECODE")),
    ("adopted", ("CODEX_THREAD_ID",)),
])
def test_1_agent_refusal_names_a_terminal_outside_claude_code_or_codex(
        env, monkeypatch, history, identities):
    if history == "adopted":
        adopt_earlier_release(env)
    else:
        start_new_client(env)
    monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
    monkeypatch.delenv("CLAUDECODE", raising=False)
    for name in identities:
        monkeypatch.setenv(name, "1")
    before = branches(env)

    refused = enable(env)

    assert refused.returncode != 0
    # "Own terminal" also described an in-session ! command. Name the external terminal.
    assert refused.stderr == (
        "Only the repo owner switches on agent merges, on main, "
        "from a terminal outside Claude Code or Codex.\n"
        "Next: the repo owner runs forge merge enable on main "
        "in a terminal outside Claude Code or Codex\n")
    unchanged(env, before)
