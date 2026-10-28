"""Init, sync and work deliver the approved agent-ready guidance."""
import re
import shutil
from pathlib import Path

import pytest

from conftest import ROOT
from test_setup import LISTED, _fresh_client, _version
from test_worker import calls, install_claude


BUILT_IN = (
    "- Built in: every action goes through its feature's service and permission, from the "
    "screens, the API and agents; each feature's create takes a retry key; an agent that a "
    "person signs in acts as that person, and the change history records both; reports are "
    "named, typed reads in their feature's report service."
)
PLANNING = (
    "When a part adds a create or a send, pay or notify action, it says that the action takes "
    "a retry key. When it adds a report, it names the report, its result fields and their "
    "units. When it lets a person sign an agent in, the agent acts as that person, and the "
    "part names the agent's `viaAgent` text."
)
STANDARDS = (
    "- Every create, and every action with a side effect (send, pay, notify), accepts an "
    "`Idempotency-Key`. A repeat with the same key from the same account makes no second "
    "record and gives back the first result. An update that sets values takes no key. A "
    "webhook stores the sender's event id, so a replay is refused.",
    "- Screens, the API, agent tools and any later in-app agent use the same module service "
    "for each action, with the same permission check. No route, tool or job changes a "
    "module's data around its service.",
    "- An agent account, for a team agent, acts as itself with its role. An agent that a "
    "person signs in acts as that person, with that person's permissions, and its principal "
    "names the agent, so the change history records both.",
    "- A report is a named, typed read in its module's report service. Each result field "
    "has a plain name with its unit (`revenueInr`, `durationSeconds`). Start with a live "
    "query, and move it to a summary table only when the database skill's measure shows "
    "it slow, with no change for its callers.",
)
BRIEF = (
    "In an app with `libs/core/server/src/common/retry-keys.ts` (Python "
    "`app/core/retry_keys.py`), a create or a send, pay or notify action that you add takes "
    "the `Idempotency-Key` header through `RetryKeys.once` (Python `create_once`), as the "
    "projects create does. An update takes no key. Put a report in its module's report "
    "service, with named, typed results that carry their units. Never change a module's "
    "data around its service, from a route, a tool or a job."
)


@pytest.mark.platform
@pytest.mark.parametrize("setup", ["new init", "previous release"])
def test_4_the_guides_state_the_agent_ready_rules(repo, gh, tmp_path, setup):
    log = install_claude(repo)
    if setup == "new init":
        client, made = _fresh_client(repo, gh, tmp_path)
        assert made.returncode == 0, made.stdout + made.stderr
    else:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
        client = repo.path
        config = client / "forge.toml"
        config.write_text(config.read_text("utf-8").replace(
            'version = "v1.2.2"', f'version = "{_version(repo)}"'), "utf-8")
        repo.git("add", "-A", cwd=client)
        repo.git("commit", "-q", "-m", "Upgrade the earlier client", cwd=client)
        repo.git("push", "-q", "origin", "main", cwd=client)

    started = repo.forge("fix", "start", "Check agent ready guidance", "--done",
                         "The agent ready guidance is delivered", "--kind", "mechanical",
                         cwd=client)
    assert started.returncode == 0, started.stdout + started.stderr
    client = client.parent / f"{client.name}-fix-check-agent-ready-guidance"
    if setup == "previous release":
        synced = repo.forge("sync", cwd=client)
        assert synced.returncode == 0, synced.stdout + synced.stderr
        changed = {line.split(None, 1)[1] for line in
                   repo.git("status", "--porcelain", "-uall", cwd=client).splitlines()}
        assert changed <= LISTED  # Existing app code stays untouched.

    for host in (".claude", ".codex"):
        guide = " ".join((client / host / "skills/forge/SKILL.md").read_text("utf-8").split())
        assert guide.count(BUILT_IN) == 2, host
        assert PLANNING in guide, host
        standards = " ".join((client / host / "skills/forge/standards.md")
                             .read_text("utf-8").split())
        for instruction in STANDARDS:
            assert instruction in standards, (host, instruction)

    config = client / "forge.toml"
    config.write_text(config.read_text("utf-8").replace(
        'workers = "split"', 'workers = "claude"').replace(
        'workers = "codex"', 'workers = "claude"'), "utf-8")
    repo.git("add", "-A", cwd=client)
    repo.git("commit", "-q", "-m", "Use the current agent ready guidance", cwd=client)
    worked = repo.forge("work", "check-agent-ready-guidance", cwd=client)
    assert worked.returncode == 0, worked.stdout + worked.stderr
    brief = " ".join(calls(log)[-1]["brief"].split())
    assert BRIEF in brief
    for instruction in STANDARDS:
        assert instruction in brief
    conventions = re.search(r"how-to for each concern .*? in `([^`]+)`", brief)
    assert conventions, brief
    for name in ("backend.md", "python.md"):
        text = (Path(conventions[1]) / name).read_text("utf-8")
        assert "## Ready for agents" in text, name
