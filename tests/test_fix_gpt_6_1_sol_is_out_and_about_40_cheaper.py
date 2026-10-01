"""Workers, fixes, design and the cold reader move to GPT-6.1 Sol. Reviews first stayed on GPT-6 Sol;
the owner later moved them to GPT-6.1 Sol at high effort too.

The sign-off pin, the light prototype review and the SDK install are proven by their own tests:
test_fix_reviews_run_on_gpt_6_sol_at_xhigh_effort.py, test_aha_review.py and test_codex_setup.py.
"""
import tomllib

from conftest import ROOT
from test_setup import _fresh_client

STORY = "FIX-GPT-6-1-SOL-IS-OUT-AND-ABOUT-40-CHEAPER"
NEW = "gpt-6.1-sol"
REVIEW = {"model": NEW, "effort": "high"}
HELPERS = {"subagents": "gpt-6-luna", "subagent_effort": "max"}


def test_1_forge_init_defaults_work_to_gpt_6_1_sol_and_reviews_to_gpt_6_sol(repo, gh, tmp_path):
    client, result = _fresh_client(repo, gh, tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    models = tomllib.loads((client / "forge.toml").read_text(encoding="utf-8"))["models"]
    assert models["build"] == models["fix"] == {"model": NEW, "effort": "medium"}
    assert models["lite"] == {"model": NEW, "effort": "medium", **HELPERS}
    assert models["grill"]["codex"] == models["design"]["codex"] == {"model": NEW, "effort": "high"}
    assert models["review"] == REVIEW


def test_2_this_repos_cold_reader_and_design_run_on_gpt_6_1_sol(repo):
    models = tomllib.loads((ROOT / "forge.toml").read_text(encoding="utf-8"))["models"]
    assert models["grill"]["codex"] == models["design"]["codex"] == {"model": NEW, "effort": "high"}
    assert models["review"] == REVIEW
