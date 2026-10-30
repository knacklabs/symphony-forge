"""New and earlier-adopted clients receive the notes-first guide through Forge."""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import pytest

from conftest import ROOT
from test_app_constitution import _fixture_git
from test_setup import _fresh_client

STORY = "FORGE-MODULAR-1"


@pytest.fixture
def client(repo, gh, tmp_path, adoption):
    if adoption == "new init":
        top, initialized = _fresh_client(repo, gh, tmp_path)
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr
        return top

    shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                    dirs_exist_ok=True)
    version = repo.forge("--version").stdout.split()[-1]
    config = repo.path / "forge.toml"
    config.write_text(config.read_text("utf-8").replace('"v1.2.2"', json.dumps(version)),
                      encoding="utf-8")
    repo.git("add", "-A")
    _fixture_git(repo, tmp_path, "commit", "-q", "-m", "Adopt the earlier client")
    _fixture_git(repo, tmp_path, "push", "-q", "origin", "main")
    started = repo.forge("fix", "start", "Sync the discovery guide", "--done",
                         "The guide is current", "--kind", "mechanical")
    assert started.returncode == 0, started.stdout + started.stderr
    top = Path(re.search(r" in (.+)\n", started.stdout)[1])
    synced = repo.forge("sync", cwd=top)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    return top


@pytest.mark.parametrize("adoption", ["new init", "previous release upgrade and sync"])
def test_4_a_new_app_starts_from_the_client_notes(client, adoption):
    # The everyday interview keeps its limit; a new app starts with notes instead.
    sentences = (
        "On a new app, the FDE puts every client note in docs/context/. Read all of them before "
        "you ask anything.",
        "Fill docs/product/BRIEF.md and the problem cards in docs/product/DISCOVERY.md from the "
        "notes, and list each contradiction and gap for the FDE.",
        "Ask the FDE one question at a time, and only about a point that changes a screen, a "
        "field or a flow. A new app has no fixed number of questions.",
        "Give every other open point a default, mark it (assumed) where you write it, and list "
        "these assumptions in one message for the FDE to change.",
        "Put each question the FDE cannot answer on the recap's Still to find out list, and "
        "build the prototype without waiting for the answer.",
    )
    for host in (".claude", ".codex"):
        guide = (client / host / "skills/forge/SKILL.md").read_text("utf-8")
        discovery = " ".join(guide.split("\n## Discovery\n")[1].split("\n## ")[0].split())
        for sentence in sentences:
            assert sentence in discovery
        assert "with the story limit" not in discovery


@pytest.mark.parametrize("adoption", ["new init", "previous release upgrade and sync"])
def test_5_the_constitution_starts_with_the_defaults_and_fixed_rules(client, adoption):
    # Defaults now start before the prototype; approval still happens once after sign-off.
    sentences = (
        "Before the prototype, take the product answers from the client notes: what the app is "
        "for, who uses it, the records and fields it needs, the options of each choice list, and "
        "the key flows.",
        "After the customer's sign-off and before the first story, finish the app's "
        "constitution in docs/product/CONSTITUTION.md.",
        "At the start, write docs/product/CONSTITUTION.md with every default from Constitution "
        "defaults filled in, and raise a default with the FDE only when the notes contradict it.",
        "In an app whose tests run Nx's module-boundary lint, copy the fixed rules into the "
        "constitution's ## Fixed rules section, and ask nothing about them.",
        "In any other app, record the stack, package manager and folder layout that the app "
        "already uses, and leave out ## Fixed rules.",
    )
    fixed_rules = (
        "## Fixed rules\n"
        "- One app on pnpm and Prisma, split into modules.\n"
        "- Each module owns its tables, in its own schema file.\n"
        "- Built in: each module keeps its tables in its own Postgres schema, with core tables in "
        "core; links between business modules store an indexed id without a foreign key, and "
        "links to core keep their foreign key.\n"
        "- A module uses another module only through its public service, never through its tables.\n"
        "- The tests run Nx's module-boundary lint, so an import across modules fails them."
    )
    for host in (".claude", ".codex"):
        skills = client / host / "skills/forge"
        guide = (skills / "SKILL.md").read_text("utf-8")
        constitution = guide.split("\n## App constitution\n")[1].split("\n## Adopt a live app\n")[0]
        joined = " ".join(constitution.split())
        for sentence in sentences:
            assert sentence in joined
        outline = constitution.split("```markdown\n")[1].split("```", 1)[0]
        assert fixed_rules in outline
        assert outline.index("## Defaults") < outline.index("## Fixed rules")
        assert outline.index("## Fixed rules") < outline.index("## Architecture choices")
        assert "## Constitution defaults" in (skills / "fde.md").read_text("utf-8")
