"""Workers, fixes, design and the cold reader default to GPT-6.1 Sol; Autoreview owns review defaults.

Sign-off defaults, the light prototype review and the SDK install are proven by their own tests:
test_fix_reviews_run_on_gpt_6_sol_at_xhigh_effort.py, test_aha_review.py and test_codex_setup.py.
"""
import tomllib

from conftest import ROOT
from test_setup import _fresh_client

STORY = "FIX-GPT-6-1-SOL-IS-OUT-AND-ABOUT-40-CHEAPER"
NEW = "gpt-6.1-sol"
REVIEW = {"model": NEW, "effort": "high"}
HELPERS = {"subagents": "gpt-6-luna", "subagent_effort": "max"}


def test_1_forge_init_defaults_work_to_gpt_6_1_sol_and_leaves_reviews_to_autoreview(repo, gh, tmp_path):
    client, result = _fresh_client(repo, gh, tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    models = tomllib.loads((client / "forge.toml").read_text(encoding="utf-8"))["models"]
    assert models["build"] == models["fix"] == {"model": NEW, "effort": "medium"}
    assert models["lite"] == {"model": NEW, "effort": "medium", **HELPERS}
    assert models["grill"]["codex"] == models["design"]["codex"] == {"model": NEW, "effort": "high"}
    assert "review" not in models


def test_2_this_repos_cold_reader_and_design_run_on_gpt_6_1_sol(repo):
    models = tomllib.loads((ROOT / "forge.toml").read_text(encoding="utf-8"))["models"]
    assert models["grill"]["codex"] == models["design"]["codex"] == {"model": NEW, "effort": "high"}
    assert models["review"] == REVIEW
