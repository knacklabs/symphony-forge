"""forge close hands the reviewer the standards page the worker brief carries, as rules to check."""
from __future__ import annotations

from pathlib import Path

from test_close import env  # noqa: F401

STORY = "FIX-WORKERS-BUILD-CLIENT-APPS-WITH-FORGE-S-S"
STANDARDS = (Path(__file__).parents[1] / "src/forge/standards.md").read_text(encoding="utf-8").strip()


def _rules(env) -> str:
    """Every prompt text the reviewer got on the last run: --prompt, then each --prompt-file."""
    call = env.review_calls()[-1]
    prompt = "\n\n".join([env.prompt(), *call["prompt_files"].values()])
    assert "## Standards" in prompt
    return prompt.split("## Standards", 1)[1]


def test_1_a_fix_review_checks_the_change_against_the_standards_page(env):
    item, _ = env.start_fix()
    assert env.close(item).returncode == 0
    rules = _rules(env)
    assert STANDARDS in rules
    intro = " ".join(rules.split(STANDARDS, 1)[0].split())
    assert "Report every rule the change breaks as a P1 finding" in intro
    assert "titled `Standard: <the rule it breaks>`" in intro


def test_2_a_task_review_carries_the_same_standards_page(env):
    item, _ = env.start_task()
    assert env.close(item).returncode == 0
    assert STANDARDS in _rules(env)


def test_3_a_branch_s_forge_standards_link_never_redirects_the_prompt_file(env):
    outside = env.tmp / "outside.txt"
    outside.write_text("keep me\n", "utf-8")
    item, where = env.start_fix()
    # A tracked symlink, committed as git stores one, so it checks out as a link where links work.
    target = env.tmp / "link-target"
    target.write_bytes(str(outside).encode("utf-8"))
    blob = env.repo.git("hash-object", "-w", str(target), cwd=where)
    env.repo.git("update-index", "--add", "--cacheinfo", f"120000,{blob},forge-standards.md",
                 cwd=where)
    env.repo.git("commit", "-q", "-m", "Link the standards page", cwd=where)
    env.repo.git("checkout", "-q", "--", "forge-standards.md", cwd=where)
    assert env.close(item).returncode == 0
    assert outside.read_text("utf-8") == "keep me\n"
    assert STANDARDS in _rules(env)
