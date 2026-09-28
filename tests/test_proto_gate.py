"""Prototype sign-off gates at the Forge command boundary."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

STORY = "FORGE-PROTO-1"
REFUSAL = ("Stories wait for the customer's sign-off. Build and demo the prototype first.\n"
           "Next: forge next\n")


def _client(repo) -> None:
    version = repo.forge("--version").stdout.split()[-1]
    repo.write("forge.toml", f'version = "{version}"\nrepo = "client"\n')
    repo.write("plans/roadmap.json", json.dumps({"items": [{"key": "SHOP"}]}))
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "Set up client")
    repo.git("push", "-q", "origin", "main")


def _signed_off(repo) -> None:
    repo.write("docs/decisions/0001-client-signoff.md", "---\nstatus: accepted\n---\n")
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "Record client sign-off")
    repo.git("push", "-q", "origin", "main")


def _fix_path(repo, why: str) -> Path:
    started = repo.forge("fix", "start", why, "--done", "The prototype works")
    assert started.returncode == 0, started.stderr
    return Path(re.search(r" in (.+)\n", started.stdout)[1])


def test_2_stories_wait_for_client_signoff(repo):
    _client(repo)
    fix = _fix_path(repo, "Prototype discovery")
    body = "# Shop\n\n## Roadmap\n\n- SELL: Shoppers can buy\n"
    digest = hashlib.sha256(body.encode()).hexdigest()
    (fix / "docs/specs").mkdir(parents=True)
    (fix / "docs/specs/shop.md").write_text(
        f"---\nstatus: confirmed\nconfirmed_hash: {digest}\n---\n{body}", encoding="utf-8")
    for command, cwd in ((('roadmap', 'add', 'shop'), fix),
                         (('story', 'new', 'SHOP', 'Shop'), repo.path),
                         (('story', 'new', 'SHOP', '--from-fix', 'prototype-discovery'), repo.path)):
        refused = repo.forge(*command, cwd=cwd)
        assert (refused.returncode, refused.stderr) == (1, REFUSAL)
    assert "SELL" not in (fix / "plans/roadmap.json").read_text()
    assert not (fix.parent / f"{repo.path.name}-story-SHOP").exists()

    _signed_off(repo)
    # The accepted decision is present on the default branch, as after its fix merges.
    added = repo.forge("roadmap", "add", "shop", cwd=fix)
    assert added.returncode == 0, added.stderr
    story = repo.forge("story", "new", "SHOP", "Shop")
    assert story.returncode == 0, story.stderr
    promoted = repo.forge("story", "new", "SELL", "--from-fix", "prototype-discovery")
    assert promoted.returncode == 0, promoted.stderr


def test_3_prototype_fix_keeps_its_allowance(repo):
    _client(repo)
    prototype = _fix_path(repo, "Build prototype")
    state = json.loads((prototype / ".factory/fixes/build-prototype.json").read_text())
    assert state["allow_large"] == "Prototype before sign-off"

    _signed_off(repo)
    later = _fix_path(repo, "Build next feature")
    later_state = json.loads((later / ".factory/fixes/build-next-feature.json").read_text())
    assert not later_state.get("allow_large")
    original = json.loads((prototype / ".factory/fixes/build-prototype.json").read_text())
    assert original["allow_large"] == "Prototype before sign-off"
