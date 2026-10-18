"""Open branches warn about added migration numbers through next and close."""
import json

import pytest

from test_close import env  # noqa: F401
from test_close_keeps_reviews_for_unchanged_branch_diffs import client

STORY = "migration-number-warning"


@pytest.mark.parametrize("previous, peer", [
    (False, "fix/add-orders"), (False, "task/SHOP-T2"),
    (False, "story/ORDERS"), (True, "fix/add-orders"),
], ids=["new-fix", "new-task", "new-story", "adopted-fix"])
def test_1_next_and_close_warn_without_refusing_duplicate_migration_numbers(env, monkeypatch, previous, peer):
    # Audit: real git branches and real commands own detection and continuation.
    # Existing close tests never create competing migration additions.
    client(env, previous)
    repo = env.repo
    env.commit(repo.path, "db/migrations/0001_initial.sql", "select 1;\n")
    repo.git("push", "-q", "origin", "main")
    repo.git("switch", "-qc", peer)
    peer_state = (".factory/fixes/add-orders.json" if peer.startswith("fix/") else
                  ".factory/stories/SHOP/tasks/T2.json" if peer.startswith("task/") else
                  ".factory/stories/ORDERS/story.json")
    env.commit(repo.path, peer_state, json.dumps({"branch": peer, "status": "working"}))
    env.commit(repo.path, "db/migrations/0002_orders.sql", "select 2;\n")
    # Existing migrations, non-migration files and non-numbered files do not clash.
    env.commit(repo.path, "db/migrations/0001_initial.sql", "select 10;\n")
    env.commit(repo.path, "notes/0003_notes.sql", "select 3;\n")
    env.commit(repo.path, "db/migrations/readme.md", "Migration notes\n")
    repo.git("push", "-q", "origin", peer)
    repo.git("switch", "-q", "main")
    repo.git("branch", "-D", peer)  # The other item exists only on origin.
    item, where = env.start_fix({
        "db/migrations/0002_customers.sql": "select 20;\n",
        "db/migrations/0001_initial.sql": "select 11;\n",
        "db/migrations/0003_products.sql": "select 30;\n",
        "db/migrations/readme.md": "Other migration notes\n",
    })
    warning = f"Warning: {item} and {peer.split('/', 1)[1].replace('-T2', '/T2')} add migration number 0002."
    trace = env.tmp / "migration-git.jsonl"
    # Native Git tracing observes the cost without replacing branch discovery.
    with monkeypatch.context() as tracing:
        tracing.setenv("GIT_TRACE2_EVENT", trace.as_posix())
        next_result = repo.forge("next", cwd=where)
    assert next_result.returncode == 0, next_result.stdout + next_result.stderr
    warnings = [line for line in next_result.stdout.splitlines() if "add migration number" in line]
    assert warnings == [warning + " Change one number before merge."]
    calls = [json.loads(line)["argv"][1:] for line in trace.read_text("utf-8").splitlines()
             if json.loads(line)["event"] == "start"]
    peer_diffs = [args for args in calls if args[:1] == ["diff"]
                  and any(peer in arg for arg in args)]
    assert len(peer_diffs) == 1, peer_diffs
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert warning in closed.stdout
    assert len(env.review_calls()) == 1  # A warning never stops review or checks.
    # Next also warns from the coordinator's default-branch checkout.
    coordinator = repo.forge("next")
    assert coordinator.returncode == 0, coordinator.stderr
    assert "migration number 0002" in coordinator.stdout
    assert item in coordinator.stdout and peer.split("/", 1)[1].split("-T2")[0] in coordinator.stdout
    # Dropped and completed branches remain on origin but are no longer open items.
    repo.git("switch", "-qc", peer, f"origin/{peer}")
    status = "dropped" if peer.startswith("fix/") else "done"
    env.commit(repo.path, peer_state, json.dumps({"branch": peer, "status": status}))
    repo.git("push", "-q", "origin", peer)
    repo.git("switch", "-q", "main")
    quiet = repo.forge("next", cwd=where)
    assert quiet.returncode == 0, quiet.stderr
    assert "add migration number" not in quiet.stdout
    # An already merged branch must not produce a warning either.
    repo.git("push", "-q", "origin", "--delete", peer)
    repo.git("update-ref", f"refs/remotes/origin/{peer}", "origin/main")
    quiet = repo.forge("next", cwd=where)
    assert quiet.returncode == 0, quiet.stderr
    assert "add migration number" not in quiet.stdout
