"""src/forge/design.py through the read, approval and prototype-fix commands."""
import json
import re
import shutil
from pathlib import Path

import pytest

from test_story import DOC, claude_plan, hook, new_story, setup
from test_setup import _fresh_client
from test_conflicting_pull_requests_stop_check_waits import _publish_default

STORY = "FORGE-PACE-1"
ROOT = Path(__file__).resolve().parents[1]
SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="1440" height="900"><text x="20" y="40">Basket</text></svg>\n'


@pytest.mark.parametrize("adopted", [False, True], ids=["new-client", "earlier-release"])
@pytest.mark.parametrize("user_facing", ["yes", "true"])
def test_1_design_first_binds_the_screens(repo, gh, tmp_path, claude_payload, adopted, user_facing):
    # Previously read and approval accepted missing or changed screens. This command test owns
    # that contract; only the third-party reader is fake, with no new production test seam.
    if adopted:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path, dirs_exist_ok=True)
    else:
        client, made = _fresh_client(repo, gh, tmp_path)
        assert made.returncode == 0, made.stdout + made.stderr
        repo.path = client
    repo.git("switch", "-qc", "fix/design-settings")
    repo.write(".factory/fixes/design-settings.json", json.dumps({"kind": "fix", "branch": "fix/design-settings", "why": "Set design settings", "done_when": "Settings are ready"}))
    setup(repo, kind="client", keys=("SHOP", "BACK"))
    repo.write("forge.toml", (repo.path / "forge.toml").read_text("utf-8") +
               'checks = ["tests", "forge-pr-check"]\n')
    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stdout + synced.stderr
    assert (repo.path / ".forge/design/support.js").is_file()
    repo.git("add", "-A")
    if repo.git("diff", "--cached", "--name-only"):
        repo.git("commit", "-qm", "Install the design renderer")
    _publish_default(repo, repo.git("remote", "get-url", "origin"))
    repo.git("switch", "-q", "main")
    repo.git("merge", "-q", "--ff-only", "fix/design-settings")
    shop = new_story(repo, "SHOP")
    doc = shop / "plans/SHOP.md"
    text = "\n".join(line for line in DOC.split("\n") if not line.startswith("Design:"))
    text = text.replace("| yes |", f"| {user_facing} |")
    doc.write_text(text, encoding="utf-8")
    refused = repo.forge("read", "SHOP")
    assert refused.returncode == 1, refused.stdout + refused.stderr
    assert "design" in refused.stderr.lower() and "Next:" in refused.stderr
    assert not (repo.bin / "claude-calls.jsonl").exists()

    folder = shop / "docs/design/SHOP"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "basket.html").write_text('<h1>Basket</h1>\n', encoding="utf-8")

    def tree_id():
        repo.git("add", "docs/design/SHOP", cwd=shop)
        tree = repo.git("write-tree", cwd=shop)
        return repo.git("rev-parse", f"{tree}:docs/design/SHOP", cwd=shop)

    digest = tree_id()
    named = text.replace("\n## Why", f"\nDesign: docs/design/SHOP/ ({digest})\n\n## Why")
    doc.write_text(named, encoding="utf-8")
    refused = repo.forge("read", "SHOP")
    assert refused.returncode == 1 and "image" in refused.stderr.lower(), refused.stderr
    (folder / "basket.svg").write_text(SVG, encoding="utf-8")
    named = named.replace(digest, tree_id())
    doc.write_text(named, encoding="utf-8")
    read = repo.forge("read", "SHOP")
    assert read.returncode == 0, read.stdout + read.stderr
    approved = hook(repo, claude_plan(claude_payload, named))
    assert approved.returncode == 0, approved.stderr
    assert repo.git("show", "story/SHOP:docs/design/SHOP/basket.svg") == SVG.strip()
    started = repo.forge("task", "start", "SHOP/SAVE")
    assert started.returncode == 0, started.stdout + started.stderr
    task_folder = Path(re.search(r" in (.+)\n", started.stdout)[1])
    assert (task_folder / "docs/design/SHOP/basket.svg").read_text("utf-8") == SVG
    # Approval also binds assets on the build branch, even when its plan did not change.
    screen = task_folder / "docs/design/SHOP/basket.svg"
    screen.write_text(SVG.replace("Basket", "Unapproved screen"), encoding="utf-8")
    repo.git("add", "docs/design/SHOP/basket.svg", cwd=task_folder)
    repo.git("commit", "-qm", "Change a screen on the task branch", cwd=task_folder)
    gh.respond("pr", "list", stdout="[]")
    refused = repo.forge("close", "SHOP/SAVE")
    assert refused.returncode == 1 and "design folder changed" in refused.stderr.lower(), refused.stdout + refused.stderr
    assert "Next:" in refused.stderr
    screen.write_text(SVG, encoding="utf-8")
    repo.git("add", "docs/design/SHOP/basket.svg", cwd=task_folder)
    repo.git("commit", "-qm", "Restore the approved screen", cwd=task_folder)

    # Even unstaged and untracked edits must refuse stale approval, without changing the index.
    (folder / "basket.svg").write_text(SVG.replace("Basket", "Saved baskets"), encoding="utf-8")
    (folder / "empty.html").write_text('<h1>No baskets</h1>\n', encoding="utf-8")
    index_before = repo.git("write-tree", cwd=shop)
    refused = repo.forge("read", "SHOP")
    assert refused.returncode == 1 and "design" in refused.stderr.lower(), refused.stderr
    assert repo.git("write-tree", cwd=shop) == index_before
    shown = repo.forge("next")
    assert "design folder changed" in shown.stdout.lower(), shown.stdout + shown.stderr
    amended = named.replace("can save a basket and", "can save a basket safely and")
    doc.write_text(amended, encoding="utf-8")
    refused = hook(repo, claude_plan(claude_payload, amended))
    assert refused.returncode == 1 and "design" in refused.stderr.lower(), refused.stderr
    started = repo.forge("task", "start", "SHOP/SAVE")
    assert started.returncode == 1 and "design" in started.stderr.lower(), started.stderr
    doc.write_text(named, encoding="utf-8")
    (folder / "empty.html").unlink()
    repo.git("add", "docs/design/SHOP/basket.svg", cwd=shop)
    repo.git("commit", "-qm", "Change a screen without its plan reference", cwd=shop)
    repo.git("worktree", "remove", str(shop))
    refused = repo.forge("task", "start", "SHOP/SHOW")
    assert refused.returncode == 1 and "design" in refused.stderr.lower(), refused.stderr

    backend = new_story(repo, "BACK")
    (backend / "plans/BACK.md").write_text(text.replace(f"| {user_facing} |", "| no |"), encoding="utf-8")
    passed = repo.forge("read", "BACK")
    assert passed.returncode == 0, passed.stdout + passed.stderr

    version = repo.forge("--version").stdout.split()[-1]
    repo.git("switch", "-qc", "fix/prototype-settings")
    repo.write(".factory/fixes/prototype-settings.json", json.dumps({"kind": "fix", "branch": "fix/prototype-settings", "why": "Set prototype stage", "done_when": "The prototype stage is set"}))
    repo.write("forge.toml", f'version = "{version}"\nrepo = "client"\nstage = "prototype"\n')
    repo.git("add", "forge.toml", ".factory/fixes/prototype-settings.json")
    repo.git("commit", "-qm", "Use prototype stage")
    _publish_default(repo, repo.git("remote", "get-url", "origin"))
    repo.git("switch", "-q", "main")
    repo.git("merge", "-q", "--ff-only", "fix/prototype-settings")
    for flags in ([], ["--slug", "screen-change"]):
        refused = repo.forge("fix", "start", "Build screens", "--done", "Screens work", "--kind", "ui", *flags)
        assert refused.returncode == 1 and "prototype-design" in refused.stderr, refused.stdout + refused.stderr
    backend_fix = repo.forge("fix", "start", "Build storage", "--done", "Storage works", "--kind", "backend")
    assert backend_fix.returncode == 0, backend_fix.stdout + backend_fix.stderr
    design_fix = repo.forge("fix", "start", "Draw screens", "--done", "Screens have a design", "--kind", "mechanical")
    assert design_fix.returncode == 0, design_fix.stderr
    fix = Path(re.search(r" in (.+)\n", design_fix.stdout)[1])
    proposed = repo.forge("decision", "new", "prototype-design", cwd=fix)
    assert proposed.returncode == 0, proposed.stderr
    decision = next((fix / "docs/decisions").glob("*-prototype-design.md"))
    body = re.sub(r'(?m)^(## .+)$', r'\1\n\nThe owner approves the screens.', decision.read_text("utf-8"))
    decision.write_text(body, encoding="utf-8")
    missing = repo.forge("decision", "accept", "prototype-design", "--by", "Owner", cwd=fix)
    assert missing.returncode == 1 and "screen images" in missing.stderr, missing.stdout + missing.stderr
    (fix / "docs/design/prototype").mkdir(parents=True, exist_ok=True)
    (fix / "docs/design/prototype/screen.svg").write_text(SVG, encoding="utf-8")
    repo.git("add", "docs/design/prototype", cwd=fix)
    repo.git("commit", "-qm", "Save the prototype design", cwd=fix)
    accepted = repo.forge("decision", "accept", "prototype-design", "--by", "Owner", cwd=fix)
    assert accepted.returncode == 0, accepted.stdout + accepted.stderr
    missing_product = repo.forge("fix", "start", "Build without product init", "--done", "Screens work", "--kind", "ui", cwd=fix)
    assert missing_product.returncode == 1 and "PRODUCT.md" in missing_product.stderr, missing_product.stdout + missing_product.stderr
    assert "init" in missing_product.stderr and "Next:" in missing_product.stderr
    (fix / "PRODUCT.md").write_text("# Basket shop\n\nPeople save baskets and return to them.\n", encoding="utf-8")
    repo.git("add", "PRODUCT.md", cwd=fix)
    repo.git("commit", "-qm", "Record the product from design init", cwd=fix)
    ui = repo.forge("fix", "start", "Build approved screens", "--done", "Screens work", "--kind", "ui", cwd=fix)
    assert ui.returncode == 0, ui.stdout + ui.stderr
    (fix / "docs/design/prototype/screen.svg").write_text(SVG.replace("Basket", "Changed"), encoding="utf-8")
    repo.git("add", "docs/design/prototype/screen.svg", cwd=fix)
    repo.git("commit", "-qm", "Change a screen after its approval", cwd=fix)
    refused = repo.forge("fix", "start", "Build changed screens", "--done", "Screens work", "--kind", "ui", cwd=fix)
    assert refused.returncode == 1 and "approved design" in refused.stderr, refused.stdout + refused.stderr
    accepted = repo.forge("decision", "accept", "prototype-design", "--by", "Owner", cwd=fix)
    assert accepted.returncode == 0, accepted.stdout + accepted.stderr
    ui = repo.forge("fix", "start", "Build the new approved screens", "--done", "Screens work", "--kind", "ui", cwd=fix)
    assert ui.returncode == 0, ui.stdout + ui.stderr
