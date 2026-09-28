"""A new Forge repo starts reviews on Sol at xhigh effort."""
import tomllib

from test_setup import _fresh_client

STORY = "FIX-AUTOREVIEW-AND-OTHER-ASTRA-PASSES-BURN-T"


def test_1_forge_init_sets_review_to_sol_xhigh(repo, gh, tmp_path):
    client, result = _fresh_client(repo, gh, tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    config = tomllib.loads((client / "forge.toml").read_text(encoding="utf-8"))
    assert config["models"]["review"] == {"model": "gpt-6-sol", "effort": "xhigh"}
