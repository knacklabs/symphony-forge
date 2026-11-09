"""Close waits out temporary review rate limits without spending its failure allowance.

Test audit: the real close command must finish after repeated provider throttling.
The old two-attempt loop stops instead. Existing failure tests cover unreadable
reports, not throttling. Only third-party answers and the backoff clock are faked;
there is no production test seam. New and earlier-adopted clients share this rule.
"""
import json

import pytest

from test_close import CLEAN, FAILED, env  # noqa: F401
from test_close_keeps_reviews_for_unchanged_branch_diffs import client

STORY = "review-retries-rate-limit"


@pytest.mark.parametrize("adopted", [False, True], ids=["new", "earlier-adopted"])
def test_1_close_waits_and_retries_rate_limits_before_counting_failures(env, adopted):
    config = (env.repo.path / "forge.toml").read_text("utf-8")
    client(env, adopted)
    env.commit(env.repo.path, "forge.toml", config, "Use the test checks")
    env.repo.git("push", "-q", "origin", "main")
    item, _ = env.start_fix()
    waits = env.tmp / "review-waits.jsonl"
    shim = env.repo.bin / "forge"
    source = shim.read_text("utf-8")
    shim.write_text(source.replace("from forge.cli import main", f'''
from forge import review
def backoff(seconds):
    with open({json.dumps(waits.as_posix())}, "a", encoding="utf-8") as log:
        log.write(str(seconds) + "\\n")
review.time = type("Clock", (), {{"sleep": staticmethod(backoff),
                                  "time": staticmethod(review.time.time)}})
from forge.cli import main
'''), "utf-8")
    errors = ["429", "rate limit", "Too Many Requests", "HTTP 429", "RATE LIMIT"]
    env.reviews(FAILED, *({"exit": 3, "report": None, "say": error}
                          for error in errors), CLEAN)

    closed = env.close(item)

    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert len(env.review_calls()) == 7
    assert waits.read_text("utf-8").splitlines() == ["30", "60", "120", "120", "120"]
    assert "Review service rate limit. Waiting" in closed.stderr
