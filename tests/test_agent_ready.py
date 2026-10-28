"""New starter creates share retry keys; upgrades preserve existing app code."""
import shlex
import shutil

import pytest

from test_feature_command import _written_paths, feature_live_run, require_feature_cases
from test_mcp import FEATURE_LINE, _adopted_files_after_sync
from test_setup import _fresh_client
from test_starter_tree import LIVE, _junit_cases, _require_cases, live_run

STORY = "FORGE-AGENTREADY-1/RETRY"


def _new_client(repo, gh, tmp_path):
    client, initialized = _fresh_client(repo, gh, tmp_path, "--starter", "react")
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    return client


@pytest.mark.platform
@pytest.mark.timeout(1800)
@pytest.mark.parametrize("starter", ["typescript", "earlier adopted"])
def test_1_a_create_sent_again_with_its_retry_key_makes_one_item(repo, gh, tmp_path, starter, request):
    # Audit: HTTP/MCP own storage and email delivery; hooks own key lifetime after transport
    # failure. Existing cases never retry REST creates or invites. Init/sync is the public
    # packaging boundary. No production seam is needed.
    if starter == "earlier adopted":
        before, after = _adopted_files_after_sync(repo)
        assert after == before
        assert not list(repo.path.rglob("retry-keys.ts"))
        assert not list(repo.path.rglob("retry_keys.py"))
        return
    client = _new_client(repo, gh, tmp_path)
    assert (client / "libs/core/server/src/common/retry-keys.ts").is_file()
    if LIVE:
        live = live_run(request.getfixturevalue("tmp_path_factory"))
        _require_cases(live["api"], (
            "a project create sent again with the same Idempotency-Key makes one project",
            "an invite sent again with the same Idempotency-Key sends one email and makes one invitation",
            "a retried project create with the same idempotency key makes one project",
        ))
        _require_cases(_junit_cases(live["folder"] / "test-results/formats.xml"), (
            "the create hook keeps one Idempotency-Key until a create succeeds",
            "the invite hook keeps one Idempotency-Key until an invite succeeds",
        ))
        _require_cases(live["browser"], (
            "a project form retries with its key after the create response is lost",
            "an invite form retries with its key after the response is lost",
        ))


@pytest.mark.platform
@pytest.mark.timeout(1800)
@pytest.mark.parametrize("starter", ["typescript", "earlier adopted"])
def test_2_history_keeps_the_agent_that_acts_for_a_person(repo, gh, tmp_path, starter, request):
    # Audit: the transaction contract owns the optional principal value; existing history
    # HTTP cases detect migration failures. Sync must not migrate earlier apps. No new seam.
    if starter == "earlier adopted":
        before, after = _adopted_files_after_sync(repo)
        assert after == before
        assert not (repo.path / "apps/api/prisma/migrations").exists()
        assert not (repo.path / "apps/api/migrations/versions").exists()
        return
    client = _new_client(repo, gh, tmp_path)
    assert (client / "libs/history/server/src/history.service.test.ts").is_file()
    if LIVE:
        live = live_run(request.getfixturevalue("tmp_path_factory"))
        _require_cases(_junit_cases(live["folder"] / "test-results/formats.xml"), (
            "history records the agent that acts for a person",
        ))
        _require_cases(live["api"], ("an invite and a role change write change history",))


@pytest.mark.platform
@pytest.mark.timeout(1800)
@pytest.mark.parametrize("starter", ["typescript", "older starter"])
def test_3_a_new_feature_takes_a_retry_key_on_create(repo, gh, tmp_path, starter, request):
    # Audit: generated action names must agree across REST and MCP, including hyphenated
    # features. Older apps cannot compile references to the helper they lack. Existing
    # feature cases miss this compatibility boundary. No production seam is needed.
    client = _new_client(repo, gh, tmp_path)
    if starter == "older starter":
        (client / "libs/core/server/src/common/tools.ts").unlink()
        (client / "libs/core/server/src/common/retry-keys.ts").unlink(missing_ok=True)
        shutil.rmtree(client / "libs/mcp")
    built = repo.forge(*shlex.split(FEATURE_LINE)[1:], cwd=client)
    assert built.returncode == 0, built.stdout + built.stderr
    written = _written_paths(built, client)
    if starter == "older starter":
        assert built.stdout.count("This app has no MCP server or retry keys, so jobs get no agent tools, resources or retry keys.") == 1
        for path in written:
            text = (client / path).read_text("utf-8")
            assert all(word not in text for word in ("retry-key", "RetryKeys", "retryKeys")), path
        assert "Idempotency-Key" not in (client / "apps/api/test/jobs.e2e-spec.ts").read_text("utf-8")
        return
    controller = (client / "libs/jobs/server/src/jobs.controller.ts").read_text("utf-8")
    assert "Idempotency-Key" in controller and "'jobs_create'" in controller
    assert "forge:feature:retry-key" not in controller
    spec = (client / "apps/api/test/jobs.e2e-spec.ts").read_text("utf-8")
    assert "Idempotency-Key" in spec and "forge:feature:retry-key" not in spec
    assert "Idempotency-Key" in (client / "libs/jobs/web/src/hooks/jobs-hooks.ts").read_text("utf-8")
    built = repo.forge("task", "feature", "work-orders", "--one", "work-order", "--field", "name:text", cwd=client)
    assert built.returncode == 0, built.stdout + built.stderr
    controller = (client / "libs/work-orders/server/src/work-orders.controller.ts").read_text("utf-8")
    assert "'work_orders_create'" in controller and "workOrders_create" not in controller
    assert "feature: 'work-orders'" in (client / "libs/work-orders/server/src/work-orders.tools.ts").read_text("utf-8")
    if LIVE:
        live = feature_live_run(repo, gh, request.getfixturevalue("tmp_path_factory"))
        require_feature_cases(live["api"], "jobs.e2e-spec.ts", (
            "a job create sent again with the same Idempotency-Key makes one job",
        ))
