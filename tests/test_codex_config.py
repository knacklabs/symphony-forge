"""This repository builds its work with Codex workers, and its old per-role model choices live in
its forge.toml's [models] table.

Each test is named test_<n>_<rule> after the Done-when item of STORY it proves.
"""
from __future__ import annotations

import tomllib

from conftest import ROOT

STORY = "FORGE-WARM-1"


def test_14_this_repo_builds_with_codex_on_its_old_per_role_models() -> None:
    config = tomllib.loads((ROOT / "forge.toml").read_text(encoding="utf-8"))
    assert config["workers"] == "codex"
    lead = {"model": "gpt-6-sol", "effort": "medium"}
    assert config["models"]["build"] == config["models"]["fix"] == {
        **lead, "subagents": "gpt-6-luna", "subagent_effort": "max"}
    assert config["models"]["lite"] == lead
    assert config["models"]["grill"]["codex"] == {"model": "gpt-6-sol", "effort": "high"}
    # The old Astra default had no effort; reviews now use Sol at xhigh effort.
    assert config["models"]["review"] == {"model": "gpt-6-sol", "effort": "xhigh"}
