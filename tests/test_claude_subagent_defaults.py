"""Claude role defaults reach the host files through init and sync."""
from __future__ import annotations

import pytest

from test_setup import _fresh_client
from test_subagent_roles import _settings

STORY = "FIX-CLAUDE-SONNET-DEFAULT"

CODEX_MODELS = """
[models.build.codex]
model = "gpt-6.1-sol"
effort = "medium"
[models.lite.codex]
model = "gpt-6-luna"
effort = "max"
[models.design.codex]
model = "gpt-6-sol"
effort = "xhigh"
[models.review.codex]
model = "gpt-6.1-sol"
effort = "high"
"""
CLAUDE_MODELS = """
[models.build.claude]
model = "claude-sonnet-5-5"
effort = "xhigh"
[models.lite.claude]
model = "claude-sonnet-5-5"
effort = "xhigh"
[models.design.claude]
model = "claude-sonnet-5-5"
effort = "xhigh"
[models.grill.claude]
model = "custom-opus"
effort = "medium"
[models.review.claude]
model = "claude-opus-4-6"
effort = "low"
"""


@pytest.mark.parametrize("models,planning", [
    (None, ("claude-opus-5-5", "high")),
    (CODEX_MODELS, ("claude-opus-5-5", "high")),
    (CODEX_MODELS + CLAUDE_MODELS, ("custom-opus", "medium")),
], ids=["new-repo", "missing-claude-entries", "configured-grill-and-old-review"])
def test_5_init_and_sync_write_claude_role_defaults_and_preserve_codex_settings(
        repo, gh, tmp_path, models, planning):
    # Building stays on Sonnet. Planning follows grill rather than design, while diagnostic
    # roles use Opus independently of obsolete review pins owned by the external reviewer.
    top = repo.path
    if models is None:
        top, initialized = _fresh_client(repo, gh, tmp_path)
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr
        settings = top / "forge.toml"
        settings.write_text(settings.read_text(encoding="utf-8").replace(
            'workers = "codex"', 'workers = "claude"').replace(
            'workers = "split"', 'workers = "claude"'), encoding="utf-8")
        result = repo.forge("sync", cwd=top)
    else:
        repo.git("checkout", "-q", "-b", "fix/role-defaults")
        version = repo.forge("--version").stdout.split()[-1]
        repo.write("forge.toml", f'version = "{version}"\nworkers = "claude"\n'
                                f'test = "make check"\n{models}')
        result = repo.forge("sync")
    assert result.returncode == 0, result.stdout + result.stderr

    for name in ("worker", "coder", "frontend", "tester", "refactorer"):
        assert _settings(top, name)[1] == ("claude-sonnet-5-5", "xhigh"), name
    # Fresh init separates read-only explore; configs without explore retain lite.
    assert _settings(top, "explorer")[1] == (
        ("claude-haiku-5-5", "high") if models is None else ("claude-sonnet-5-5", "xhigh"))
    for name in ("planner", "architect"):
        assert _settings(top, name)[1] == planning, name
    for name in ("debugger", "security", "performance"):
        assert _settings(top, name)[1] == ("claude-opus-5-5", "high"), name

    if models is None:
        for name in ("debugger", "security", "performance"):
            assert _settings(top, name)[0] == ("gpt-6.1-sol", "high"), name

    if models is not None:
        for name in ("worker", "coder", "frontend", "tester", "refactorer"):
            assert _settings(repo.path, name)[0] == ("gpt-6.1-sol", "medium"), name
        assert _settings(repo.path, "explorer")[0] == ("gpt-6-luna", "max")
        for name in ("planner", "architect"):
            assert _settings(repo.path, name)[0] == ("gpt-6-sol", "xhigh"), name
        for name in ("debugger", "security", "performance"):
            assert _settings(repo.path, name)[0] == ("gpt-6.1-sol", "high"), name
