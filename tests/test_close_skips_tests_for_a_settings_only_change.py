"""forge close skips forge.toml's test command when the change touches only forge.toml (with or
without docs, plans, Markdown or Forge's records), and says so in one line naming the command."""
from __future__ import annotations

from test_close import env, run  # noqa: F401
from test_fix_close_skips_tests_for_docs_only_changes import _with_test_command

STORY = "FIX-A-CHANGE-THAT-ONLY-EDITS-FORGE-TOML-STIL"


def test_1_close_skips_the_test_command_for_a_forge_toml_only_change(env):
    log = _with_test_command(env)
    toml = (env.repo.path / "forge.toml").read_text("utf-8")
    item, _ = env.start_fix({"forge.toml": toml + "# Reviews read this file\n",
                             "docs/settings.md": "Settings\n"})
    closed = env.close(item)
    assert closed.returncode == 0, closed.stderr
    assert not log.exists()
    said = [line for line in closed.stdout.splitlines() if "so close did not run" in line]
    assert len(said) == 1, closed.stdout
    assert "forge.toml" in said[0] and "suite.py" in said[0]
