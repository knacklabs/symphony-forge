"""Close retains readable findings and rejects unreadable Autoreview reports.

Test audit: real close owns retention, priority decisions and diagnostics.
A missing score discarded the report; existing helpers always add scores.
Only Autoreview and GitHub are faked, with no new production seam.
"""
import json
from pathlib import Path

import pytest

from test_close import FAILED, blocked, body, env, finding  # noqa: F401
from test_close_keeps_reviews_for_unchanged_branch_diffs import client

STORY = "review-unscored-findings"


@pytest.mark.parametrize("adopted", [False, True], ids=["new-client", "adopted-v1.2.2"])
def test_1_close_keeps_every_readable_finding_and_uses_unscored_priorities(env, adopted):
    config = (env.repo.path / "forge.toml").read_text("utf-8")
    client(env, adopted)
    env.commit(env.repo.path, "forge.toml", config, "Use the test checks")
    env.repo.git("push", "-q", "origin", "main")
    item, _ = env.start_fix()
    first = finding("P1", "Saving loses the basket")
    second = finding("P1", "Loading loses the basket")
    advice = finding("P2", "Shorten the greeting")
    for entry in (first, second, advice):
        entry["body"] = "The normal path needs a repair."
    scored = finding("P2", "Share the greeting formatter")
    answer = blocked(first, advice, scored)
    # Chunked reviews can place readable findings outside the selected scope.
    answer["report"]["scope_rejected_findings"] = [second]
    env.reviews(answer)

    closed = env.close(item)
    output = closed.stdout + closed.stderr
    assert closed.returncode != 0, output
    assert "Forge cannot read" not in output
    assert len(env.review_calls()) == 1, output
    for entry in (first, second, advice, scored):
        assert entry["title"] in output
    # The published dispositions prove priority fallback without changing the owner's stop choice.
    published = body(env.gh_calls("pr", "edit")[-1])
    for entry in (first, second):
        line = next(line for line in published.splitlines() if entry["title"] in line)
        assert "blocks the merge" in line
    for entry in (advice, scored):
        line = next(line for line in published.splitlines() if entry["title"] in line)
        assert "blocks the merge" not in line
    assert "Gain 2, Work 1, Harm 1" in published


@pytest.mark.parametrize("defect", ["missing-location", "unknown-priority"])
def test_2_unreadable_findings_name_saved_output_even_when_retry_writes_nothing(env, defect):
    item, _ = env.start_fix()
    invalid = finding("P1", "Unreadable finding")
    if defect == "missing-location":
        invalid.pop("code_location")
    else:
        invalid["priority"] = "P9"
    answer = blocked(finding("P1", "Readable finding"), invalid)
    env.reviews(answer, FAILED)

    closed = env.close(item)
    output = closed.stdout + closed.stderr
    assert closed.returncode != 0, output
    assert "it wrote findings Forge cannot read" in output
    assert len(env.review_calls()) == 2
    saved_line = next(line for line in output.splitlines() if line.startswith("Raw Autoreview output: "))
    saved = Path(saved_line.removeprefix("Raw Autoreview output: "))
    assert json.loads(saved.read_text("utf-8")) == answer["report"]
