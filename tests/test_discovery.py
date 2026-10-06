"""Discovery: the agent's asking rules, the problem card, and options priced by payback.

The skill and its reference page are what the agent reads, so they are checked as `forge sync`
ships them; the card and the discovery-first line through `forge init` and `forge next`.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from conftest import ROOT
from test_measure import DUE, SPEC, _confirm, _fix
from test_setup import _version

STORY = "FORGE-FDE-1"

HOSTS = (".claude", ".codex")
FIELDS = ("Job", "Workaround", "Cost", "Who feels it", "How often", "Evidence")
DISCOVER = ["No story or fix is in progress and the roadmap is empty, so start with discovery, as "
            "the Forge skill's Discovery section says.",
            'Next: forge fix start "Find the problem to solve" --done "The discovery notes hold a '
            'filled problem card and the brief names it"']
WRITE_SPEC = ["No story or fix is in progress and the roadmap is empty; the discovery notes hold a "
              "problem card, so write its spec.",
              'Next: forge fix start "Write the spec for the chosen problem" --done "A confirmed '
              'spec whose Why names the problem card"',
              "Next: forge spec save <slug>"]


def _ok(done) -> str:
    assert done.returncode == 0, done.stderr
    return done.stdout


def _client(repo, gh, tmp_path: Path) -> Path:
    """A new project set up with forge init."""
    client, remote = tmp_path / "client", tmp_path / "client.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(client)], check=True)
    repo.git("remote", "add", "origin", str(remote), cwd=client)
    gh.respond("api", stdout="{}")
    gh.respond("api", "repos/{owner}/{repo}/branches/main/protection", exit=1,
               stdout='{"message":"Branch not protected","status":"404"}')
    _ok(repo.forge("init", cwd=client))
    return client


def _discovery(client: Path) -> str:
    """The skill's Discovery section as synced for both hosts, which must match."""
    skills = {(client / host / "skills/forge/SKILL.md").read_text(encoding="utf-8") for host in HOSTS}
    assert len(skills) == 1
    [skill] = skills
    return " ".join(skill.split("\n## Discovery\n")[1].split("\n## ")[0].split())


def test_1_discovery_asks_by_size(repo, gh, tmp_path):
    section = _discovery(_client(repo, gh, tmp_path))
    # An everyday ask: one past-event question per turn, each saying why, up to the limit.
    for rule in ("one question per turn", "about something that already happened",
                 "Why I ask:", "until the engineer says they know why",
                 "at most two questions for a fix and eight for a story",
                 "write what is still unanswered as `unknown`",
                 "neutral choices", "recommendation first"):
        assert rule in section, rule


def test_2_a_new_project_starts_with_an_empty_card_and_discovery_first(repo, gh, tmp_path):
    client = _client(repo, gh, tmp_path)
    notes = (client / "docs/product/DISCOVERY.md").read_text(encoding="utf-8")
    problems = notes.split("\n## Problems\n")[1].split("\n## ")[0]
    assert re.findall(r"^### .+$", problems, re.M) == ["### <short problem title>"]
    assert re.findall(r"^- (.+?): (.*)$", problems, re.M) == [(field, "unknown") for field in FIELDS]
    assert _ok(repo.forge("next", cwd=client)).splitlines()[:2] == DISCOVER

    # The card lands in the discovery notes, named in the brief and the spec's Why.
    section = _discovery(client)
    for rule in ("`docs/product/DISCOVERY.md`", "`## Problems`", *(f"{field}" for field in FIELDS),
                 "the brief's Summary", "the spec's Why"):
        assert rule in section, rule

    # Once a card is filled, the next planning step is its spec.
    repo.write("docs/product/DISCOVERY.md", notes.replace(
        "### <short problem title>\n- Job: unknown",
        "### Invoices get lost\n- Job: Send each invoice to the client"))
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "Discover the problem")
    repo.git("push", "-q", "origin", "main")
    assert _ok(repo.forge("next")).splitlines()[:3] == WRITE_SPEC

    # Anything on the roadmap means planning is under way: the usual idle lines.
    repo.write("plans/roadmap.json", '{"items": [{"key": "INV-1", "spec": "docs/specs/inv.md"}]}\n')
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "Plan invoices")
    repo.git("push", "-q", "origin", "main")
    assert _ok(repo.forge("next")).splitlines()[0] == "No story or fix is in progress."


def test_3_options_are_priced_by_payback_and_the_choice_goes_into_the_spec(repo, gh, tmp_path):
    client = _client(repo, gh, tmp_path)
    section = _discovery(client)
    for rule in ("two to four options", "Don't build", "Smallest slice", "`forge spec payback`",
                 "fewest months", "the spec's Behaviour", "one line of why", "rounded rates"):
        assert rule in section, rule

    # The reference page ships beside the skill for both hosts, and each payback it shows is
    # what the command answers.
    pages = {(client / host / "skills/forge/fde.md").read_text(encoding="utf-8") for host in HOSTS}
    assert len(pages) == 1
    [page] = pages
    examples = re.findall(r"^(forge spec payback .+)\n(.+)$", page, re.M)
    assert len(examples) >= 3
    for command, answer in examples:
        assert _ok(repo.forge(*command.split()[1:], cwd=tmp_path)) == answer + "\n", command
    assert "(SKILL.md" in page and "./forge" not in page


@pytest.mark.parametrize("adoption", ["new", "previous release"])
def test_due_success_check_precedes_discovery_when_every_roadmap_story_is_done(
        repo, gh, tmp_path, monkeypatch, adoption):
    # Empty means no unfinished stories; keep their roadmap links for check-back.
    monkeypatch.setenv("FORGE_NOW", "2026-10-01T09:00:00+00:00")
    if adoption == "new":
        repo.path = _client(repo, gh, tmp_path)
    else:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
        config = (repo.path / "forge.toml").read_text(encoding="utf-8")
        repo.write("forge.toml", config.replace('version = "v1.2.2"',
                                               f'version = "{_version(repo)}"'))
        repo.git("add", "-A")
        repo.git("commit", "-q", "-m", "Upgrade the earlier adoption")
        repo.git("push", "-q", "origin", "main")

    plan = _fix(repo, "Plan invoices by email")
    if adoption == "previous release":
        _ok(repo.forge("sync", cwd=plan))
    (plan / "docs/specs/invoices.md").write_text(SPEC, encoding="utf-8")
    _confirm(repo, plan, "invoices")
    (plan / "plans").mkdir(exist_ok=True)
    (plan / "plans/roadmap.json").write_text(json.dumps({"items": [
        {"key": key, "spec": "docs/specs/invoices.md"} for key in ("INV-1", "INV-2")
    ]}) + "\n", encoding="utf-8")
    for key in ("INV-1", "INV-2"):
        state = plan / f".factory/stories/{key}/story.json"
        state.parent.mkdir(parents=True, exist_ok=True)
        state.write_text(json.dumps({"title": key, "status": "done"}) + "\n",
                         encoding="utf-8")
    repo.git("add", "-A", cwd=plan)
    repo.git("commit", "-q", "-m", "Finish the invoice stories", cwd=plan)
    repo.git("merge", "-q", "--ff-only", "fix/plan-invoices-by-email")
    # The remote receives the landed fixture, as GitHub would after merging its PR.
    remote = Path(repo.git("remote", "get-url", "origin"))
    repo.git("fetch", "-q", str(repo.path), "main:main", cwd=remote)
    repo.git("fetch", "-q", "origin")
    repo.git("worktree", "remove", str(plan))

    assert _ok(repo.forge("next")).splitlines()[:5] == DUE + DISCOVER
