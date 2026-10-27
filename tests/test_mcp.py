"""Client apps ship an MCP server, with agent accounts and a switch for agent delete and restore."""
import json
import shlex
import shutil
from pathlib import Path

import pytest

from test_feature_command import feature_live_run, require_feature_cases
from test_setup import _fresh_client
from test_starter_tree import LIVE, STARTER, _require_cases, live_run

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


def _adopted_files_after_sync(repo) -> tuple[dict, dict]:
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
    repo.git("checkout", "-b", "fix/agent-accounts-upgrade")
    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stdout + synced.stderr
    return before, files()


def _live(starter: str, request) -> dict:
    return (live_run(request.getfixturevalue("tmp_path_factory")) if starter == "typescript"
            else request.getfixturevalue("live_python_starter"))


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
@pytest.mark.parametrize("starter", ["typescript", "python", "earlier adopted"])
def test_3_each_feature_has_its_tools(repo, gh, tmp_path, starter, request):
    # Audit: a list screen without the Agent access dialog, a switch that does not save or does
    # not stay on after a reload, or a member who sees it fails the flow; a feature the command
    # builds must carry the dialog under its own name, or its switch saves for the wrong feature.
    if starter == "earlier adopted":
        before, after = _adopted_files_after_sync(repo)
        projects = {path: text for path, text in before.items() if "projects" in path.as_posix()}
        assert projects and all(after[path] == text for path, text in projects.items())
        return
    client, initialized = _fresh_client(
        repo, gh, tmp_path, "--starter", "react" if starter == "typescript" else "python")
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    if starter == "typescript":
        for line, plural, words in ((FEATURE_LINE, "jobs", "jobs"),
                                    ("forge task feature work-orders --one work-order --field 'name:text'",
                                     "work-orders", "work orders")):
            built = repo.forge(*shlex.split(line)[1:], cwd=client)
            assert built.returncode == 0, built.stdout + built.stderr
            page = (client / f"libs/{plural}/web/src/pages/{plural}-page.tsx").read_text("utf-8")
            assert f'feature="{plural}"' in page and f'label="{words}"' in page, page
    if LIVE:
        _require_cases(_live(starter, request)["browser"], (ACCESS_FLOW.format(plural="projects"),))
        if starter == "typescript":
            live = feature_live_run(repo, gh, request.getfixturevalue("tmp_path_factory"))
            require_feature_cases(live["browser"], "jobs.spec.ts", (ACCESS_FLOW.format(plural="jobs"),))
