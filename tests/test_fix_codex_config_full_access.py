"""forge sync gives Codex full access in a client's .codex/config.toml and drops old model pins."""
from __future__ import annotations

import tomllib

import pytest

STORY = "FIX-FORGE-SYNC-ONLY-SWITCHES-CODEX-HOOKS-ON"

# An old Forge's config: sandboxed, asking for approval, pinning a model, with the client's own settings.
OLD = """\
#:schema https://developers.openai.com/codex/config-schema.json
model = "gpt-5-codex"
model_reasoning_effort = "high"
sandbox_mode = "workspace-write"
approval_policy = "on-request"
model_verbosity = "low"  # the client's own choice

[features]
multi_agent = true

[agents.worker]
config_file = "agents/worker.toml"
model = "gpt-6-luna"
"""


def _client(repo):
    repo.git("checkout", "-q", "-b", "fix/codex")
    repo.write("forge.toml", f'version = "{repo.forge("--version").stdout.split()[-1]}"\n'
                             'test = "true"\nchecks = ["tests", "forge-pr-check"]\n')
    repo.write(".codex/config.toml", OLD)
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "Set up client")


def test_1_sync_gives_codex_full_access_and_drops_model_pins(repo):
    _client(repo)
    done = repo.forge("sync")
    assert done.returncode == 0, done.stderr
    text = (repo.path / ".codex/config.toml").read_text(encoding="utf-8")
    assert tomllib.loads(text) == {
        "sandbox_mode": "danger-full-access", "approval_policy": "never",
        "model_verbosity": "low",
        "features": {"multi_agent": True, "hooks": True},
        # A subagent's own model is the client's setting, not a top-level pin.
        "agents": {"worker": {"config_file": "agents/worker.toml", "model": "gpt-6-luna"}}}
    # The client's comments stay too.
    assert text.startswith("#:schema ") and "# the client's own choice" in text


def test_2_a_second_sync_changes_nothing(repo):
    _client(repo)
    assert repo.forge("sync").returncode == 0
    before = (repo.path / ".codex/config.toml").read_bytes()
    again = repo.forge("sync")
    assert again.returncode == 0, again.stderr
    assert again.stdout.startswith("Nothing to change")
    assert (repo.path / ".codex/config.toml").read_bytes() == before


@pytest.mark.parametrize("unsafe", [
    # A multi-line value with a line that looks like a setting sync rewrites.
    'notes = """\nsandbox_mode = "x"\n"""\n' + OLD,
    # Features as an inline table, which sync refused before this fix too.
    'model = "o3"\nfeatures = { multi_agent = true }\n',
])
def test_3_a_config_sync_cant_edit_safely_is_refused(repo, unsafe):
    _client(repo)
    repo.write(".codex/config.toml", unsafe)
    done = repo.forge("sync")
    assert done.returncode != 0
    assert ".codex/config.toml can't be merged" in done.stderr + done.stdout
    assert (repo.path / ".codex/config.toml").read_text(encoding="utf-8") == unsafe
