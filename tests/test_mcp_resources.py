"""The starter exposes feature data as MCP resources and permits explicit prompts."""
import subprocess

import pytest

from test_feature_command import feature_live_run, require_feature_cases
from test_mcp import _adopted_files_after_sync
from test_setup import _fresh_client
from test_starter_tree import LIVE, _junit_cases, _require_cases, live_run


RESOURCE_ITEM_CASE = "an agent reads a project, the project fields and the status values as resources"
RESOURCE_CONTRACT_CASE = "every feature has its resources, each with a description and the JSON type"
RESOURCE_PERMISSION_CASE = "a resource read without the view permission is refused"
JOBS_SEARCH_CASE = "an agent searches, reads, creates and updates jobs through MCP as its account"
NO_PROMPTS_CASE = "the MCP server has no prompts by default"
CUSTOM_PROMPT_CASE = "a tools file can add a prompt with its inputs"
SOURCE_EXCLUDES = (
    ":(exclude,glob)**/*.test.ts",
    ":(exclude,glob)**/*.spec.ts",
    ":(exclude,glob)apps/api/tests/**",
)


def _git_grep(client, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "grep", "-n", *args, "--", "libs", "apps", *SOURCE_EXCLUDES],
        cwd=client, capture_output=True, text=True, encoding="utf-8", timeout=30,
    )


@pytest.mark.platform
@pytest.mark.timeout(1800)
@pytest.mark.parametrize("starter", ["typescript", "earlier adopted"])
def test_1_each_feature_offers_its_resources(repo, gh, tmp_path, tmp_path_factory, starter):
    # Audit: this protects the installed and upgraded app boundary. It fails if a starter feature
    # loses its item, field-guide or choice-value resources, if a feature built by the command is
    # omitted, or if sync adds resource code to an earlier app. Existing MCP cases cover tools only.
    # The app's API report owns resource reads; the format report owns the permission refusal.
    # No production seam is needed.
    if starter == "earlier adopted":
        before, after, status_before, status_after, sync_output = _adopted_files_after_sync(
            repo, include_sync_status=True
        )
        assert after == before
        assert not (repo.path / "libs/core/server/src/common/resources.ts").exists()
        assert not (repo.path / "apps/api/app/core/resources.py").exists()
        sync_written = {
            line.removeprefix("Wrote ") for line in sync_output.splitlines()
            if line.startswith("Wrote ")
        }
        paths_after = {
            entry[3:] if entry[2] == " " else entry[2:]
            for entry in status_after.splitlines() if len(entry) >= 3
        }
        assert not status_before
        assert paths_after <= sync_written
        return

    client, initialized = _fresh_client(repo, gh, tmp_path, "--starter", "react")
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    assert (client / "apps/api/test/mcp.e2e-spec.ts").is_file()

    if LIVE:
        live = live_run(tmp_path_factory)
        _require_cases(live["api"], (RESOURCE_ITEM_CASE, RESOURCE_CONTRACT_CASE))
        _require_cases(
            _junit_cases(live["folder"] / "test-results/formats.xml"),
            (RESOURCE_PERMISSION_CASE,),
        )
        feature = feature_live_run(repo, gh, tmp_path_factory)
        require_feature_cases(
            feature["api"], "mcp.e2e-spec.ts", (RESOURCE_CONTRACT_CASE,)
        )
        require_feature_cases(
            feature["api"], "jobs.e2e-spec.ts", (JOBS_SEARCH_CASE,)
        )


@pytest.mark.platform
@pytest.mark.timeout(1800)
@pytest.mark.parametrize("starter", ["typescript", "earlier adopted"])
def test_2_a_new_app_has_no_prompts_until_a_tools_file_adds_one(
    repo, gh, tmp_path, tmp_path_factory, starter
):
    # Audit: this protects the default prompt list, custom prompt inputs, and the no-elicitation
    # and no-sampling contract. It fails if defaults appear, custom prompts stop reaching agents,
    # or the server starts asking either side for generated input. Existing tests cover tools only.
    # The API and format reports own prompt delivery and argument behavior; no production seam is
    # needed.
    if starter == "earlier adopted":
        before, after = _adopted_files_after_sync(repo)
        assert after == before
        assert not (repo.path / "libs/core/server/src/common/prompts.ts").exists()
        assert not (repo.path / "apps/api/app/core/prompts.py").exists()
        return

    client, initialized = _fresh_client(repo, gh, tmp_path, "--starter", "react")
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    prompts = client / "libs/core/server/src/common/prompts.ts"
    assert prompts.is_file()

    forbidden = _git_grep(
        client, "-E", "elicitation/create|elicitInput|createMessage|create_message"
    )
    assert forbidden.returncode == 1, forbidden.stdout + forbidden.stderr

    definitions = _git_grep(client, "-E", r"definePrompt\(")
    assert definitions.returncode == 0, definitions.stdout + definitions.stderr
    assert {line.split(":", 1)[0] for line in definitions.stdout.splitlines()} == {
        "libs/core/server/src/common/prompts.ts"
    }

    if LIVE:
        live = live_run(tmp_path_factory)
        _require_cases(live["api"], (NO_PROMPTS_CASE,))
        _require_cases(
            _junit_cases(live["folder"] / "test-results/formats.xml"),
            (CUSTOM_PROMPT_CASE,),
        )
