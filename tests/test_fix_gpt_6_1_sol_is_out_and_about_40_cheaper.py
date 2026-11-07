"""Workers, fixes and design use GPT-6.1 Sol; Codex reads and reviews use Terra max.
New Claude review settings use Sonnet high; existing repository settings remain unchanged.

Sign-off defaults, the light prototype review and the SDK install are proven by their own tests:
test_reviews_use_repository_tool.py, test_aha_review.py and test_codex_setup.py.
"""
import tomllib

from conftest import ROOT
from test_setup import _fresh_client

STORY = "FIX-GPT-6-1-SOL-IS-OUT-AND-ABOUT-40-CHEAPER"
NEW = "gpt-6.1-sol"
REVIEW = {"model": "gpt-6.1-terra", "effort": "max"}
HELPERS = {"subagents": "gpt-6-luna", "subagent_effort": "max"}


def test_1_forge_init_defaults_work_to_gpt_6_1_sol_and_pins_claude_reviews(repo, gh, tmp_path):
    client, result = _fresh_client(repo, gh, tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    models = tomllib.loads((client / "forge.toml").read_text(encoding="utf-8"))["models"]
    assert models["build"]["codex"] == models["fix"]["codex"] == {"model": NEW, "effort": "low"}
    assert models["lite"]["codex"] == {"model": NEW, "effort": "low", **HELPERS}
    assert models["grill"]["codex"] == REVIEW
    assert models["design"]["codex"] == {"model": NEW, "effort": "high"}
    assert models["review"] == {"codex": REVIEW,
                                "claude": {"model": "claude-sonnet-5-5", "effort": "high"}}


def test_2_this_repos_cold_reader_and_review_use_terra_and_design_keeps_sol(repo):
    models = tomllib.loads((ROOT / "forge.toml").read_text(encoding="utf-8"))["models"]
    assert models["grill"]["codex"] == REVIEW
    assert models["design"]["codex"] == {"model": NEW, "effort": "high"}
    assert models["review"] == REVIEW
