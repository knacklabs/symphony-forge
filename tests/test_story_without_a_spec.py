"""One story read loop and approval, without prerequisite specs or roadmap fixes.

Test-audit: real commands own creation and spec preservation, which the old tests
never exercise without a roadmap entry. Only the external reader is faked.
"""
import hashlib
import json
import shutil
import sys

import pytest

from conftest import ROOT, _install, patient
from test_setup import _fresh_client, _version
from test_story import DOC, GRILL, READER, claude_plan, hook, new_story, setup, worktree

STORY = "story-from-goal"


def test_3_next_allows_a_new_problem_with_an_existing_roadmap_backlog(repo):
    # A backlog used to restrict planning to its keys, even after discovering another problem.
    repo.write("docs/product/DISCOVERY.md", "# Discovery\n\n## Problems\n\n"
               "### Invoices get lost\n- Job: Send each invoice to the client\n")
    setup(repo, kind="client", keys=("LATER",))
    suggested = repo.forge("next")
    assert suggested.returncode == 0, suggested.stdout + suggested.stderr
    assert 'Next: forge story new <KEY> "<title>"' in suggested.stdout.splitlines()


@pytest.fixture(params=["new-client", "adopted-v1.2.2"])
def client(repo, gh, tmp_path, request):
    if request.param == "new-client":
        folder, initialized = _fresh_client(repo, gh, tmp_path)
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr
        repo.path = folder
    else:
        patient(lambda: shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client",
                                        repo.path, dirs_exist_ok=True))
        repo.git("switch", "-qc", "adoption")
        config = (repo.path / "forge.toml").read_text("utf-8")
        repo.write("forge.toml", config.replace('version = "v1.2.2"',
                                                f'version = "{_version(repo)}"'))
        repo.git("add", "-A")
        repo.git("commit", "-qm", "Adopt earlier Forge")
        repo.git("switch", "-q", "main")
        repo.git("merge", "-q", "--ff-only", "adoption")
        repo.git("push", "-q", "origin", "main")
    started = repo.forge("fix", "start", "Prepare client settings", "--done", "Client is ready")
    assert started.returncode == 0, started.stdout + started.stderr
    folder = worktree(repo, "fix/prepare-client-settings")
    config = (repo.path / "forge.toml").read_text("utf-8")
    config = config.replace('version = "v1.2.2"', f'version = "{_version(repo)}"')
    config = config.replace('stage = "prototype"', 'stage = "live"')
    if "[models.grill.claude]" not in config and "models.grill.claude" not in config:
        config = GRILL + config
    patient(lambda: (folder / "forge.toml").write_text(config, "utf-8"))
    synced = repo.forge("sync", cwd=folder)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    repo.git("add", "-A", cwd=folder)
    repo.git("commit", "-qm", "Upgrade and sync client guidance", cwd=folder)
    _merge_fixture(repo, folder, "fix/prepare-client-settings")
    _install(repo.bin, "claude", READER.format(python=sys.executable))
    return repo


def _merge_fixture(repo, folder, branch):
    # Model GitHub landing the fixture while preserving the real client push hooks.
    repo.git("push", "-q", "origin", "HEAD", cwd=folder)
    remote = repo.git("remote", "get-url", "origin")
    repo.git("update-ref", "refs/heads/main", f"refs/heads/{branch}", cwd=remote)
    repo.git("fetch", "-q", "origin")
    repo.git("merge", "-q", "--ff-only", "origin/main")


def _land(repo, files):
    started = repo.forge("fix", "start", "Prepare planning context", "--done", "Context is ready")
    assert started.returncode == 0, started.stdout + started.stderr
    folder = worktree(repo, "fix/prepare-planning-context")
    for path, text in files.items():
        target = folder / path
        if text is None:
            patient(lambda: target.unlink(missing_ok=True))
        else:
            patient(lambda: target.parent.mkdir(parents=True, exist_ok=True))
            patient(lambda: target.write_text(text, "utf-8"))
    repo.git("add", "-A", cwd=folder)
    repo.git("commit", "-qm", "Prepare client planning context", "--allow-empty", cwd=folder)
    _merge_fixture(repo, folder, "fix/prepare-planning-context")


@pytest.mark.parametrize("roadmap_exists", [True, False], ids=["existing-roadmap", "no-roadmap"])
def test_1_story_without_a_spec_adds_its_roadmap_and_needs_only_its_read_loop_and_approval(
        client, claude_payload, roadmap_exists):
    repo = client
    roadmap = {"owner_note": "Keep the backlog in this order", "items": [
        {"key": "LATER", "title": "Later work", "order": 7, "status": "pending"}]}
    _land(repo, {"plans/roadmap.json": json.dumps(roadmap) if roadmap_exists else None})
    default = repo.git("rev-parse", "main")
    branches = repo.git("branch", "--list", "fix/*")
    title = "Shoppers lose their baskets when they leave"
    story = new_story(repo, "BASKET", title)
    doc, notes = story / "plans/BASKET.md", story / "plans/BASKET.read.md"
    assert f"## Why\n\n{title}\n" in doc.read_text("utf-8")
    written = json.loads((story / "plans/roadmap.json").read_text("utf-8"))
    if roadmap_exists:
        assert written["owner_note"] == roadmap["owner_note"]
        assert written["items"][:-1] == roadmap["items"]
        assert written["items"][-1]["order"] == 8
        assert json.loads(repo.git("show", "main:plans/roadmap.json")) == roadmap
    else:
        assert len(written["items"]) == 1
        assert not (repo.path / "plans/roadmap.json").exists()
    assert written["items"][-1]["key"] == "BASKET"
    assert written["items"][-1]["title"] == title
    assert "spec" not in written["items"][-1]
    assert repo.git("rev-parse", "main") == default
    assert "plans/roadmap.json" in repo.git("show", "--name-only", "--format=", "story/BASKET")
    assert repo.git("branch", "--list", "fix/*") == branches
    for host in (".codex", ".claude"):
        skill = (story / host / "skills/forge/SKILL.md").read_text("utf-8")
        assert "A spec is optional" in skill

    plan = DOC.replace("People lose their basket when they leave.",
                       "Shoppers rebuild baskets after leaving, wasting ten minutes each time.")
    patient(lambda: doc.write_text(plan, "utf-8"))
    (repo.bin / "claude-says.md").write_text(
        "1. The saved time is outside this problem.\n", "utf-8")
    read = repo.forge("read", "BASKET")
    assert read.returncode == 0, read.stdout + read.stderr
    refused = hook(repo, claude_plan(claude_payload, plan, cwd=story))
    assert refused.returncode == 1
    assert "Finding 1" in refused.stderr and "has no disposition" in refused.stderr
    patient(lambda: notes.write_text(notes.read_text("utf-8")
                                      + "   Disposition: keep because shoppers need to identify their basket\n",
                                      "utf-8"))
    refused = hook(repo, claude_plan(claude_payload, plan, cwd=story))
    assert refused.returncode == 1 and "needs another round" in refused.stderr
    patient(lambda: (repo.bin / "claude-says.md").unlink())
    passed = repo.forge("read", "BASKET")
    assert passed.returncode == 0, passed.stdout + passed.stderr
    approved = hook(repo, claude_plan(claude_payload, plan, cwd=story))
    assert approved.returncode == 0, approved.stdout + approved.stderr
    assert "Next: forge task start BASKET/SAVE" in repo.forge("next").stdout
    assert len((repo.bin / "claude-calls.jsonl").read_text("utf-8").splitlines()) == 2
    replay = hook(repo, claude_plan(claude_payload, plan, cwd=story))
    assert replay.returncode == 1 and "matches no story doc waiting for approval" in replay.stderr
    assert repo.git("rev-parse", "main") == default
    assert repo.git("ls-tree", "-r", "--name-only", "story/BASKET", "--", "docs/specs") == (
        repo.git("ls-tree", "-r", "--name-only", "main", "--", "docs/specs"))


def test_2_a_story_from_a_confirmed_spec_preserves_its_roadmap_and_read_context(
        client, claude_payload):
    repo = client
    body = "\n# Saved baskets\n\n## Why\n\nRebuilding baskets wastes ten minutes.\n"
    spec = ("---\nstatus: confirmed\nconfirmed_hash: "
            + hashlib.sha256(body.encode()).hexdigest() + "\n---\n" + body)
    roadmap = {"items": [{"key": "SHOP", "title": "Saved baskets", "order": 4,
                          "spec": "docs/specs/baskets.md", "status": "pending"}]}
    _land(repo, {"plans/roadmap.json": json.dumps(roadmap), "docs/specs/baskets.md": spec})
    default = repo.git("rev-parse", "main")
    story = new_story(repo, "SHOP")
    assert json.loads((story / "plans/roadmap.json").read_text("utf-8")) == roadmap
    patient(lambda: (story / "plans/SHOP.md").write_text(DOC, "utf-8"))
    read = repo.forge("read", "SHOP")
    assert read.returncode == 0, read.stdout + read.stderr
    prompt = json.loads((repo.bin / "claude-calls.jsonl").read_text("utf-8").splitlines()[-1])["prompt"]
    assert "Confirmed spec at `docs/specs/baskets.md`" in prompt
    assert "Rebuilding baskets wastes ten minutes." in prompt
    approval = hook(repo, claude_plan(claude_payload, DOC, cwd=story))
    assert approval.returncode == 0, approval.stdout + approval.stderr
    assert "Next: forge task start SHOP/SAVE" in repo.forge("next").stdout
    assert (story / "docs/specs/baskets.md").read_text("utf-8") == spec
    assert repo.git("rev-parse", "main") == default
