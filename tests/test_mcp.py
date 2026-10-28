"""Client apps ship an MCP server, with agent accounts and a switch for agent delete and restore.

Python dependency contracts: src/forge/templates/starter-python/apps/api/pyproject.toml
and src/forge/templates/starter-python/apps/api/uv.lock.
"""
import ast
import json
import re
import shlex
import shutil
import tomllib
from pathlib import Path

import pytest

from test_feature_command import (
    _written_paths,
    feature_live_run,
    feature_python_live_run,
    require_feature_cases,
)
from test_setup import _fresh_client
from test_starter_tree import LIVE, STARTER, _junit_cases, _require_cases, live_run

STORY = "FORGE-MCP-1"

pytest_plugins = ("test_python_starter",)

ROOT = Path(__file__).resolve().parents[1]
ADOPTED = ROOT / "tests/fixtures/adopted-v1.2.2/client"
AGENT_CASES = {
    "typescript": ("an admin adds an agent account and creates and revokes its key",
                   "a member cannot add an agent account or change its key or agent access",
                   "an agent account cannot sign in with a password"),
    "python": ("test_an_admin_adds_an_agent_account_and_creates_and_revokes_its_key",
               "test_a_member_cannot_add_an_agent_account_or_change_its_key_or_agent_access",
               "test_an_agent_account_cannot_sign_in_with_a_password"),
}
AGENT_FLOW = "an admin adds an agent account, creates its key once and revokes it"
ACCESS_FLOW = "an admin turns on agent delete and restore for {plural}"
FEATURE_LINE = ("forge task feature jobs --one job --field 'name:text' "
                "--field 'status:status(planned|active|done)'")
CLIENTS_LINE = "forge task feature clients --one client --field 'name:text'"


def _adopted_files_after_sync(repo, *, include_sync_status=False):
    """An app adopted on an earlier release, with the starter's members and projects code, before
    and after it upgrades and syncs."""
    shutil.copytree(ADOPTED, repo.path, dirs_exist_ok=True)
    config = repo.path / "forge.toml"
    version = repo.forge("--version").stdout.split()[-1]
    config.write_text(config.read_text("utf-8").replace('"v1.2.2"', json.dumps(version)),
                      encoding="utf-8")
    for module in ("organisations", "projects"):
        shutil.copytree(STARTER / "libs" / module, repo.path / "libs" / module)
    shutil.copytree(STARTER / "apps/web/e2e", repo.path / "apps/web/e2e")

    def files() -> dict:
        return {path.relative_to(repo.path): path.read_bytes()
                for folder in ("libs", "apps") for path in (repo.path / folder).rglob("*")
                if path.is_file()}

    before = files()
    if include_sync_status:
        repo.git("add", "-A")
        repo.git("commit", "-q", "-m", "Prepare adopted app")
    repo.git("checkout", "-b", "fix/agent-accounts-upgrade")
    status_before = repo.git("status", "--porcelain=v1", "-uall")
    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stdout + synced.stderr
    if include_sync_status:
        status_after = repo.git("status", "--porcelain=v1", "-uall")
        return before, files(), status_before, status_after, synced.stdout
    return before, files()


def _live(starter: str, request) -> dict:
    return (live_run(request.getfixturevalue("tmp_path_factory")) if starter == "typescript"
            else request.getfixturevalue("live_python_starter"))


@pytest.mark.platform
@pytest.mark.timeout(1800)
@pytest.mark.parametrize("starter", ["typescript", "python", "plain", "earlier adopted"])
def test_1_a_new_starter_app_serves_its_mcp_server(repo, gh, tmp_path, starter, request):
    # Audit: protects the generated-app boundary: both starters register their API path, while
    # plain init and an earlier-adopted app gain no MCP code. The existing starter-tree checks
    # compare files but do not parse the service that Mainline reads. No production seam is
    # needed; GitHub's init responses use the existing fixture.
    if starter == "earlier adopted":
        before, after, status_before, status_after, sync_output = _adopted_files_after_sync(
            repo, include_sync_status=True)
        assert after == before
        assert not (repo.path / "services.toml").exists()
        assert not (repo.path / "libs/mcp").exists()
        assert not (repo.path / "apps/api/src/mcp").exists()
        assert not (repo.path / "apps/api/app/mcp").exists()
        sync_written = {line.removeprefix("Wrote ") for line in sync_output.splitlines()
                        if line.startswith("Wrote ")}
        paths_after = {entry[3:] if entry[2] == " " else entry[2:]
                       for entry in status_after.splitlines() if len(entry) >= 3}
        assert not status_before
        assert paths_after <= sync_written
        return

    init_args = (
        ("--starter", "react") if starter == "typescript" else
        ("--starter", "python") if starter == "python" else ()
    )
    client, initialized = _fresh_client(repo, gh, tmp_path, *init_args)
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    service = tomllib.loads((client / "services.toml").read_text(encoding="utf-8"))["service"][0]
    if starter in ("typescript", "python"):
        assert service["mcp"] == "/mcp"
        assert "services.toml" in repo.git("ls-files", cwd=client).splitlines()
        if starter == "typescript":
            assert (client / "libs/mcp/server/src/index.ts").is_file()
            assert (client / "apps/api/test/mcp.e2e-spec.ts").is_file()
        else:
            assert (client / "apps/api/app/mcp/server.py").is_file()
            assert (client / "apps/api/tests/test_mcp.py").is_file()
        if LIVE:
            live = _live(starter, request)
            expected = (
                "the MCP server refuses a missing or revoked agent key"
                if starter == "typescript" else
                "test_the_mcp_server_refuses_a_missing_or_revoked_agent_key"
            )
            _require_cases(live["api"], (expected,))
    else:
        assert "mcp" not in service
        assert not (client / "libs/mcp").exists()
        assert not (client / "apps/api/app/mcp").exists()


@pytest.mark.platform
@pytest.mark.timeout(1800)
@pytest.mark.parametrize("starter", ["typescript", "python", "earlier adopted"])
def test_2_an_admin_adds_an_agent_account_and_its_key(repo, gh, tmp_path, starter, request):
    # Audit: an agent account that is missing from the member list, a key that shows twice or
    # still works after a revoke, a member who can add agents or change keys, an agent that can
    # sign in with a password, or a change with no history row fails the app's own cases, which
    # own the behaviour; the browser flow fails when the key stays on the page after Done. Sync
    # must leave an earlier-adopted app's own files as they are.
    if starter == "earlier adopted":
        before, after = _adopted_files_after_sync(repo)
        assert after == before
        return
    client, initialized = _fresh_client(
        repo, gh, tmp_path, "--starter", "react" if starter == "typescript" else "python")
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    tests = "apps/api/test/agents.e2e-spec.ts" if starter == "typescript" else "apps/api/tests/test_agents.py"
    assert (client / tests).is_file()
    if LIVE:
        live = _live(starter, request)
        _require_cases(live["api"], AGENT_CASES[starter])
        _require_cases(live["browser"], (AGENT_FLOW,))


@pytest.mark.platform
@pytest.mark.timeout(1800)
@pytest.mark.parametrize("starter", ["typescript", "python", "earlier adopted", "older starter"])
def test_3_each_feature_has_its_tools(repo, gh, tmp_path, starter, request):
    # Audit: a generated feature without its six field-based tools, its linked-name resolver,
    # or its delete/restore switch fails this command-boundary contract; an older starter must
    # not receive MCP code that it cannot run. The generated API cases exercise the copied tools
    # through the agent boundary, while the unit case owns custom-tool registration and timeout.
    if starter == "older starter":
        client, initialized = _fresh_client(repo, gh, tmp_path, "--starter", "react")
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr
        (client / "libs/core/server/src/common/tools.ts").unlink()
        shutil.rmtree(client / "libs/mcp")
        built = repo.forge(*shlex.split(FEATURE_LINE)[1:], cwd=client)
        assert built.returncode == 0, built.stdout + built.stderr
        assert built.stdout.count("This app has no MCP server, so jobs get no agent tools.") == 1
        written = _written_paths(built, client)
        # SQL search indexes also end in _search; only the MCP tool name is forbidden.
        forbidden = ("forge:feature:mcp", "JobsTools", "AgentAccessDialog", "agentClient", "afterCreate", "jobs_search")
        for path in written:
            text = (client / path).read_text("utf-8")
            assert all(value not in text for value in forbidden), path
        assert "libs/jobs/server/src/jobs.tools.ts" not in written

        python_tmp = tmp_path / "python"
        python_tmp.mkdir()
        python_client, initialized = _fresh_client(
            repo, gh, python_tmp, "--starter", "python"
        )
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr
        (python_client / "apps/api/app/core/tools.py").unlink()
        shutil.rmtree(python_client / "apps/api/app/mcp")
        built = repo.forge(*shlex.split(FEATURE_LINE)[1:], cwd=python_client)
        assert built.returncode == 0, built.stdout + built.stderr
        assert built.stdout.count("This app has no MCP server, so jobs get no agent tools.") == 1
        written = _written_paths(built, python_client)
        assert "apps/api/app/jobs/tools.py" not in written
        python_forbidden = (
            "forge:feature:mcp",
            "register_tools",
            "after_create",
            "AgentAccessDialog",
            "MCP_FEATURE",
            "MCP_TOOL_PREFIX",
            "agent_client",
            "jobs_search",
        )
        for path in written:
            text = (python_client / path).read_text("utf-8")
            assert all(value not in text for value in python_forbidden), path
        return
    if starter == "earlier adopted":
        before, after = _adopted_files_after_sync(repo)
        projects = {path: text for path, text in before.items() if "projects" in path.as_posix()}
        assert projects and all(after[path] == text for path, text in projects.items())
        return
    client, initialized = _fresh_client(
        repo, gh, tmp_path, "--starter", "react" if starter == "typescript" else "python")
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    if starter == "typescript":
        for line, plural, words in ((CLIENTS_LINE, "clients", "clients"),
                                    (FEATURE_LINE, "jobs", "jobs"),
                                    ("forge task feature work-orders --one work-order --field 'name:text' "
                                     "--field 'client?:link(clients)'", "work-orders", "work orders")):
            built = repo.forge(*shlex.split(line)[1:], cwd=client)
            assert built.returncode == 0, built.stdout + built.stderr
            if plural != "clients":
                page = (client / f"libs/{plural}/web/src/pages/{plural}-page.tsx").read_text("utf-8")
                assert f'feature="{plural}"' in page and f'label="{words}"' in page, page
            if plural == "jobs":
                tools = (client / "libs/jobs/server/src/jobs.tools.ts").read_text("utf-8")
                assert "feature: 'jobs'" in tools and "JOB_PERMISSIONS" in tools
                concise = re.search(r"\bconcise:\s*(\[[^\]]*\])", tools)
                assert concise and ast.literal_eval(concise[1]) == ["name", "status"]
                assert "links: {}" in tools
            if plural == "work-orders":
                tools = (client / "libs/work-orders/server/src/work-orders.tools.ts").read_text("utf-8")
                assert "import { CLIENTS_API } from '@app/clients-contracts';" in tools
                assert "clientId: CLIENTS_API" in tools
                concise = re.search(r"\bconcise:\s*(\[[^\]]*\])", tools)
                assert concise and ast.literal_eval(concise[1]) == ["name", "clientId"]
    else:
        built = repo.forge(*shlex.split(FEATURE_LINE)[1:], cwd=client)
        assert built.returncode == 0, built.stdout + built.stderr
        tools = (client / "apps/api/app/jobs/tools.py").read_text("utf-8")
        assert 'feature="jobs"' in tools and "JOB_PERMISSIONS" in tools
        concise = re.search(r"\bconcise\s*=\s*(\[[^\]]*\])", tools)
        assert concise and ast.literal_eval(concise[1]) == ["name", "status"]
    if LIVE:
        _require_cases(_live(starter, request)["browser"], (ACCESS_FLOW.format(plural="projects"),))
        if starter == "typescript":
            live = feature_live_run(repo, gh, request.getfixturevalue("tmp_path_factory"))
            require_feature_cases(live["browser"], "jobs.spec.ts", (ACCESS_FLOW.format(plural="jobs"),))
            require_feature_cases(live["api"], "jobs.e2e-spec.ts", (
                "an agent searches, reads, creates and updates jobs through MCP as its account",
                "a member agent cannot delete or restore a job through MCP",
                "job delete and restore tools stay off until an admin turns them on",
                "omitted optional fields stay valid in concise and detailed MCP results",
            ))
            require_feature_cases(live["api"], "tasks.e2e-spec.ts", (
                "omitted optional fields stay valid in concise and detailed MCP results",
                "a deleted linked item does not stop parent reads or bypass the member role",
            ))
            require_feature_cases(live["api"], "notes.e2e-spec.ts", (
                "an agent searches, reads, creates and updates notes through MCP as its account",
                "a member agent cannot delete or restore a note through MCP",
            ))
            require_feature_cases(live["api"], "projects.e2e-spec.ts", (
                "an agent searches, reads, creates and updates projects through MCP as its account",
                "a member agent cannot delete or restore a project through MCP",
                "project delete and restore tools stay off until an admin turns them on",
            ))
            _require_cases(_junit_cases(live["folder"] / "test-results/formats.xml"),
                           ("a tools file can hide a default tool and add its own",))
        else:
            live = feature_python_live_run(
                repo, gh, request.getfixturevalue("tmp_path_factory")
            )
            require_feature_cases(live["api"], "test_projects", (
                "test_an_agent_searches_reads_creates_and_updates_projects_through_mcp_as_its_account",
                "test_a_member_agent_cannot_delete_or_restore_a_project_through_mcp",
                "test_project_delete_and_restore_tools_stay_off_until_an_admin_turns_them_on",
            ))
            require_feature_cases(live["api"], "test_jobs", (
                "test_an_agent_searches_reads_creates_and_updates_jobs_through_mcp_as_its_account",
                "test_a_member_agent_cannot_delete_or_restore_a_job_through_mcp",
                "test_job_delete_and_restore_tools_stay_off_until_an_admin_turns_them_on",
            ))
            require_feature_cases(live["api"], "test_tools", (
                "test_a_tools_file_can_hide_a_default_tool_and_add_its_own",
                "test_a_tool_over_its_time_limit_gets_a_retryable_unavailable_error",
            ))


MCP_API_CASES = (
    "every tool has a description, annotations, schemas and the error shape",
    "project search pages with a cursor and says how many match",
    "a retried project create with the same idempotency key makes one project",
    "a repeated project update changes nothing",
    "an invalid project input gets a non-retryable error with an example",
    "an agent key over its rate limit gets a retryable error",
)


@pytest.mark.platform
@pytest.mark.timeout(1800)
@pytest.mark.parametrize("starter", ["typescript", "python", "earlier adopted"])
def test_4_tools_page_answer_and_fail_in_the_agent_form(repo, gh, tmp_path, starter, request):
    # Audit: verifies the running API's MCP contract and behavior report; the REST tests cannot
    # catch a broken MCP transport, tool schema, paging response, or retry result. The adopted
    # app gets no MCP tool implementation during sync.
    if starter == "earlier adopted":
        _adopted_files_after_sync(repo)
        assert not (repo.path / "libs/core/server/src/common/tools.ts").exists()
        assert not (repo.path / "apps/api/app/core/tools.py").exists()
        return

    client, initialized = _fresh_client(
        repo, gh, tmp_path, "--starter", "react" if starter == "typescript" else "python"
    )
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    api_test = (
        client / "apps/api/test/mcp.e2e-spec.ts"
        if starter == "typescript"
        else client / "apps/api/tests/test_mcp.py"
    )
    assert api_test.is_file()
    if LIVE:
        if starter == "typescript":
            live = live_run(request.getfixturevalue("tmp_path_factory"))
            _require_cases(live["api"], MCP_API_CASES)
            _require_cases(_junit_cases(live["folder"] / "test-results/formats.xml"),
                           ("a tool over its time limit gets a retryable unavailable error",))
        else:
            live = request.getfixturevalue("live_python_starter")
            require_feature_cases(live["api"], "test_mcp", (
                "test_every_tool_has_a_description_annotations_schemas_and_the_error_shape",
                "test_project_search_pages_with_a_cursor_and_says_how_many_match",
                "test_a_retried_project_create_with_the_same_idempotency_key_makes_one_project",
                "test_a_repeated_project_update_changes_nothing",
                "test_an_invalid_project_input_gets_a_non_retryable_error_with_an_example",
                "test_an_agent_key_over_its_rate_limit_gets_a_retryable_error",
            ))
            require_feature_cases(live["api"], "test_tools", (
                "test_a_tool_over_its_time_limit_gets_a_retryable_unavailable_error",
            ))
