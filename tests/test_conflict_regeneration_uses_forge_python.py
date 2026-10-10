"""A client's Python pin must not select Forge's conflict-regeneration interpreter.

Real uv selects and launches Python; only release acquisition uses this checkout.
The existing direct-exec package stub could not detect interpreter discovery bugs.
"""
import pytest

import test_running_commands_follow_changed_forge_pin as repin
from test_close import env  # noqa: F401
from test_land import land  # noqa: F401

STORY = "skipped-close"


@pytest.mark.parametrize("adoption", ["fresh", "earlier-adopted"])
@pytest.mark.parametrize("stage", ["close-guide-conflict", "land-guide-conflict"])
def test_6_conflict_regeneration_uses_forge_python_despite_client_pin(
        land, adoption, stage, monkeypatch):
    earlier = repin._earlier_release

    def pinned_client(env):
        env.commit(env.tmp / "repo-fix-tidy-readme", ".python-version", "3.10\n",
                   "Keep the client's Python pin")
        earlier(env, real_uv=True)

    monkeypatch.delenv("UV_PYTHON", raising=False)
    monkeypatch.setattr(repin, "_earlier_release", pinned_client)
    # Reuse the complete command proof: Ready, selected release, guide regeneration,
    # main ancestry, clean merge, real tests/review/checks and unchanged local hooks.
    repin.test_1_running_command_continues_under_the_pin_merged_from_upgraded_default(
        land, adoption, stage, monkeypatch)
    assert land.repo.git("status", "--porcelain", cwd=land.tmp / "repo-fix-tidy-readme") == ""
