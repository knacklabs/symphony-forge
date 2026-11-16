"""A first review's builder-detail Not done note and exact repeats never reach the builder."""
import json

from test_close import blocked, env, finding  # noqa: F401
from test_close_explains_findings_and_requires_done_when import setup_client

STORY = "review-noise"


def test_1_builder_detail_not_done_and_duplicates_are_dropped(env):
    setup_client(env, False)
    detail = "The greeting uses a separate formatter"
    item, where = env.start_task()
    env.commit(where, "docs/implementation.md", f"# Builder details\n\n{detail}.\n")
    real = finding("P1", "Greeting is missing")
    safe = finding("P1", "Not done: Orders are scoped to their owner")
    safe["body"] += "\nRaise: Security"
    env.reviews(blocked(finding("P1", f" Not done: {detail}"), real, dict(real),
                        dict(real, priority="P0"), safe))

    closed = env.close(item)

    assert closed.returncode == 1, closed.stdout + closed.stderr
    state = json.loads((where / ".factory/stories/SHOP/tasks/T1.json").read_text(encoding="utf-8"))
    events = [json.loads(line) for line in (env.repo.path / ".git/forge/events.jsonl").read_text(
        encoding="utf-8").splitlines() if line.strip()]
    sent = [e for e in events if e.get("event") == "review result"][-1]["findings"]
    for titles in ([f["title"] for f in state["review"]["findings"]], [f["title"] for f in sent]):
        assert titles == ["Greeting is missing", safe["title"]]
    assert state["review"]["findings"][0]["priority"] == "P0"
