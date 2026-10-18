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
    other = env.tmp / "peer-clone"
    repo.git("clone", "-q", repo.git("remote", "get-url", "origin"), str(other))
    repo.git("switch", "-qc", peer, cwd=other)
    peer_state = (".factory/fixes/add-orders.json" if peer.startswith("fix/") else
                  ".factory/stories/SHOP/tasks/T2.json" if peer.startswith("task/") else
                  ".factory/stories/ORDERS/story.json")
    env.commit(other, peer_state, json.dumps({"branch": peer, "status": "working"}))
    env.commit(other, "db/migrations/0002_orders.sql", "select 2;\n")
    # Existing migrations, non-migration files and non-numbered files do not clash.
    env.commit(other, "db/migrations/0001_initial.sql", "select 10;\n")
    env.commit(other, "notes/0003_notes.sql", "select 3;\n")
    env.commit(other, "db/migrations/readme.md", "Migration notes\n")
    item, where = env.start_fix({
        "db/migrations/0002_customers.sql": "select 20;\n",
        "db/migrations/0001_initial.sql": "select 11;\n",
        "db/migrations/0003_products.sql": "select 30;\n",
        "db/migrations/0004_stock.sql": "select 40;\n",
        "db/migrations/readme.md": "Other migration notes\n",
    })
    repo.git("push", "-q", "origin", peer, cwd=other)
    assert not repo.git("for-each-ref", f"refs/remotes/origin/{peer}")
    peer_tip = repo.git("rev-parse", "HEAD", cwd=other)
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
                  and any(peer_tip in arg for arg in args)]
    assert len(peer_diffs) == 1, peer_diffs
    assert sum(args[:1] == ["fetch"] for args in calls) == 1, calls
    # The next push leaves this checkout's newly discovered peer ref out of date.
    repo.git("mv", "db/migrations/0002_orders.sql", "db/migrations/0004_orders.sql", cwd=other)
    repo.git("commit", "-qm", "Use a different migration number", cwd=other)
    repo.git("push", "-q", "origin", peer, cwd=other)
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert warning.replace("0002", "0004") in closed.stdout
    assert warning not in closed.stdout
    assert len(env.review_calls()) == 1  # A warning never stops review or checks.
    # Next also warns from the coordinator's default-branch checkout.
    coordinator = repo.forge("next")
    assert coordinator.returncode == 0, coordinator.stderr
    assert "migration number 0004" in coordinator.stdout
    assert item in coordinator.stdout and peer.split("/", 1)[1].split("-T2")[0] in coordinator.stdout
    # Dropped and completed branches remain on origin but are no longer open items.
    status = "dropped" if peer.startswith("fix/") else "done"
    env.commit(other, peer_state, json.dumps({"branch": peer, "status": status}))
    repo.git("push", "-q", "origin", peer, cwd=other)
    quiet = repo.forge("next", cwd=where)
    assert quiet.returncode == 0, quiet.stderr
    assert "add migration number" not in quiet.stdout


@pytest.mark.parametrize("previous, peer, peer_item, peer_state", [
    (False, "fix/add-orders", "add-orders", ".factory/fixes/add-orders.json"),
    (False, "task/SHOP-PAGE", "SHOP/PAGE", ".factory/stories/SHOP/tasks/PAGE.json"),
    (True, "fix/add-orders", "add-orders", ".factory/fixes/add-orders.json"),
], ids=["new-fix", "new-named-task", "adopted-fix"])
def test_2_finished_peers_do_not_warn_even_with_retained_squash_branches(
        env, previous, peer, peer_item, peer_state):
    # Audit: retained squash tips keep additions and pre-merge status. The old
    # test moved the tip to main and could not detect this false warning.
    client(env, previous)
    repo = env.repo
    item, where = env.start_fix({"db/migrations/0002_customers.sql": "select 2;\n"})
    other = env.tmp / "peer-clone"
    repo.git("clone", "-q", repo.git("remote", "get-url", "origin"), str(other))
    repo.git("switch", "-qc", peer, cwd=other)
    env.commit(other, peer_state, json.dumps({"branch": peer, "status": "working"}))
    env.commit(other, "db/migrations/0002_orders.sql", "select 20;\n")
    repo.git("push", "-q", "origin", peer, cwd=other)
    repo.git("fetch", "-q", "origin")  # Isolate identity from refresh behavior.
    warning = f"Warning: {item} and {peer_item} add migration number 0002."
    active = repo.forge("next", cwd=where)
    assert active.returncode == 0, active.stdout + active.stderr
    assert warning in active.stdout
    status = "dropped" if peer.startswith("fix/") else "done"
    env.commit(other, peer_state, json.dumps({"branch": peer, "status": status}))
    repo.git("push", "-q", "origin", peer, cwd=other)
    repo.git("fetch", "-q", "origin")
    finished = repo.forge("next", cwd=where)
    assert finished.returncode == 0, finished.stdout + finished.stderr
    assert "add migration number" not in finished.stdout
    # A squash merge retains the old remote tip and its pre-merge status.
    env.commit(other, peer_state, json.dumps({"branch": peer, "status": "working"}))
    repo.git("push", "-q", "origin", peer, cwd=other)
    repo.git("fetch", "-q", "origin")
    repo.git("merge", "--squash", f"origin/{peer}")
    repo.git("commit", "-qm", "Land the peer through a squash merge")
    repo.git("push", "-q", "origin", "main")
    assert "db/migrations/0002_orders.sql" in repo.git(
        "diff", "--name-only", f"origin/main...origin/{peer}")
    landed = repo.forge("next", cwd=where)
    assert landed.returncode == 0, landed.stdout + landed.stderr
    assert "add migration number" not in landed.stdout
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert "add migration number" not in closed.stdout
