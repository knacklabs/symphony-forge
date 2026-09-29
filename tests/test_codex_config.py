"""A Codex repo keeps its per-role model choices in its forge.toml's [models] table. This repo
moved its own workers to Claude, so the Codex contract lives in a fixture config that
test_fix_first_codex_round_luna_helpers.py also runs Forge against.

Each test is named test_<n>_<rule> after the Done-when item of STORY it proves.
"""
from __future__ import annotations

import tomllib

from conftest import ROOT

STORY = "FORGE-WARM-1"


def test_14_a_codex_repo_builds_on_its_old_per_role_models() -> None:
    config = tomllib.loads((ROOT / "tests/fixtures/codex-forge.toml").read_text(encoding="utf-8"))
    assert config["workers"] == "codex"
    lead = {"model": "gpt-6-sol", "effort": "medium"}
    assert config["models"]["build"] == config["models"]["fix"] == {
        **lead, "subagents": "gpt-6-luna", "subagent_effort": "max"}
    # Lite used to carry only the lead model; first fix rounds now give it the same helpers.
    assert config["models"]["lite"] == config["models"]["build"]
    assert config["models"]["grill"]["codex"] == {"model": "gpt-6-sol", "effort": "high"}
    # The old Astra default had no effort; reviews now use Sol at xhigh effort.
    assert config["models"]["review"] == {"model": "gpt-6-sol", "effort": "xhigh"}
