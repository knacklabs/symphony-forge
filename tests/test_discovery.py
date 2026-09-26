"""Discovery: the agent's asking rules, the problem card, and options priced by payback.

The skill and its reference page are what the agent reads, so they are checked as `forge sync`
ships them; the card and the discovery-first line through `forge init` and `forge next`.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

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


def test_1_discovery_asks_by_size_or_runs_office_hours(repo, gh, tmp_path):
    section = _discovery(_client(repo, gh, tmp_path))
    # An everyday ask: one past-event question per turn, each saying why, up to the limit.
    for rule in ("one question per turn", "about something that already happened",
                 "Why I ask:", "until the engineer says they know why",
                 "at most two questions for a fix and eight for a story",
                 "write what is still unanswered as `unknown`",
                 "neutral choices", "recommendation first"):
        assert rule in section, rule
    # A new project, or an ask no confirmed spec covers: office-hours, or the fallback without it.
    for rule in ("a new project, or an ask no confirmed spec covers", "`/office-hours`",
                 "`*-design-*.md`", "unchanged into `docs/context/`",
                 "github.com/garrytan/gstack", "your own interview"):
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
