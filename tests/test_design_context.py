"""Design context delivered through the real worker and review commands."""
import json
import os
import re
import shutil
from pathlib import Path

import pytest

from test_close import DESIGN_TREE, STORY_DOC, env  # noqa: F401
from test_codex_worker import ROOT, _codex_repo, _sent, sdk_data  # noqa: F401
from test_conflicting_pull_requests_stop_check_waits import _publish_default
from test_prototype_build import _accept_build_decision
from test_task import story as task_story
from test_worker import calls, install_claude

STORY = "FORGE-PACE-1-CONTEXT"
SCREENS = "# Screens\n\n## Basket\nComponents: Card, Button\nFields: basket name\n"
DESIGN = "# Basket look\n\nUse ink blue and warm cream.\n"
PRODUCT = "# Basket shop\n\nShoppers save baskets and return to them.\n"


def prepare(env, monkeypatch, sdk_data, family, *, adopted=False, starter=False, prototype=False):
    repo = env.repo
    if adopted:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path, dirs_exist_ok=True)
    repo.git("switch", "-qc", "fix/context-setup")
    repo.write(".factory/fixes/context-setup.json", json.dumps({
        "kind": "fix", "branch": "fix/context-setup", "why": "Set up design context",
        "done_when": "Design context is ready"}))
    _, log = _codex_repo(repo, monkeypatch, sdk_data, client=True, start_task=False)
    config = repo.path / "forge.toml"
    settings = config.read_text("utf-8").replace('workers = "codex"', 'workers = "claude"')
    settings = settings.replace("[models.build]", "[models.build.codex]")
    head, models = settings.split("\n[", 1)
    settings = head + ('\ntools = "claude"\nchecks = ["tests", "forge-pr-check"]\n') + "\n[" + models
    settings += ('\n[models.design.claude]\nmodel = "opus"\neffort = "high"\n'
                 '\n[models.design.codex]\nmodel = "gpt-6-sol"\neffort = "high"\n'
                 '\n[models.build.claude]\nmodel = "opus"\neffort = "high"\n'
                 '\n[models.grill.claude]\nmodel = "opus"\neffort = "high"\n')
    settings = settings.replace('tools = "claude"', f'tools = "{family}"').replace(
        'workers = "claude"', f'workers = "{family}"')
    if prototype:
        settings = settings.replace('repo = "client"', 'repo = "client"\nstage = "prototype"')
    env.commit(repo.path, "forge.toml", settings)
    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stdout + synced.stderr
    for name, text in {"DESIGN.md": DESIGN, "PRODUCT.md": PRODUCT,
                       "docs/design/baskets/SCREENS.md": SCREENS,
                       "docs/design/prototype/SCREENS.md": SCREENS,
                       "docs/design/prototype/canvas.svg": "<svg>Signed basket</svg>\n"}.items():
        repo.write(name, text)
    if starter:
        repo.write("apps/web/src/index.css", ":root { --background: white; }\n")
    if not prototype:
        repo.write("docs/decisions/0001-client-signoff.md",
                   '---\nstatus: accepted\nconfirmed_by: "Client"\n---\n\n# Signed canvas\n')
    repo.git("add", "-A")
    repo.git("commit", "-qm", "Save the app design")
    _publish_default(repo, repo.git("remote", "get-url", "origin"))
    repo.git("switch", "-q", "main")
    repo.git("merge", "-q", "--ff-only", "fix/context-setup")
    return log


def context(prompt, folder):
    for text in ("## Design context", folder, SCREENS.strip(), DESIGN.strip(), PRODUCT.strip(),
                 "### test-audit", "observable behavior", "credible regression"):
        assert text in prompt, text
    assert f"{folder}SCREENS.md" in prompt


@pytest.mark.parametrize("family,adopted,starter,none", [
    ("codex", False, True, False), ("claude", False, False, False),
    ("claude", True, False, False), ("claude", False, False, True),
])
def test_1_workers_and_reviewers_receive_the_apps_design(env, monkeypatch, sdk_data,
                                                        family, adopted, starter, none):
    # Only the third-party model/reviewer is fake; it does not assemble the asserted context.
    repo = env.repo
    codex_log = prepare(env, monkeypatch, sdk_data, family, adopted=adopted, starter=starter)
    if none:
        # HANDOFF owns admission of user-facing Design:none stories. A backend task already
        # reaches this context path, without adding an unrelated gate change to CONTEXT.
        doc = re.sub(r"Design: .*", "Design: none (only a label changes)", STORY_DOC)
        doc = doc.replace("| yes |", "| no |")
        folder = "docs/design/prototype/"
    else:
        folder = "docs/design/baskets/"
        task_story(repo, key="SHOP", doc=STORY_DOC, approved=STORY_DOC)
        repo.git("switch", "-q", "story/SHOP")
        # A generated canvas added on the story branch must stay readable in the review's
        # checkout even though generated contents stay out of the reviewed diff.
        repo.write(folder + "flow.svg", "<svg>Flow</svg>\n")
        repo.write(".gitattributes", "docs/design/** linguist-generated\n")
        repo.git("add", "docs/design", ".gitattributes")
        tree = repo.git("write-tree")
        digest = repo.git("rev-parse", f"{tree}:docs/design/baskets")
        doc = STORY_DOC.replace(DESIGN_TREE, digest).replace("| — | no |", "| — | yes |")
    task_story(repo, key="SHOP", doc=doc, approved=doc)
    started = repo.forge("task", "start", "SHOP/T1")
    assert started.returncode == 0, started.stdout + started.stderr
    item = "SHOP/T1"
    where = Path(started.stdout.splitlines()[0].rsplit(" in ", 1)[1])
    env.commit(where, "app.py", "print('saved basket')\n")
    monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
    monkeypatch.delenv("CLAUDECODE", raising=False)
    monkeypatch.setenv("CLAUDECODE" if family == "codex" else "CODEX_THREAD_ID", "1")
    claude_log = install_claude(repo)
    for _ in range(2):
        built = repo.forge("work", item)
        assert built.returncode == 0, built.stdout + built.stderr
        prompt = (_sent(codex_log, "turn/start")[-1]["input"][0]["text"] if family == "codex"
                  else calls(claude_log)[-1]["brief"])
        context(prompt, folder)
        assert f"{folder}{'canvas' if none else 'screen'}.svg" in prompt
        if not none:
            # Both briefs now scope fields to Build now / named Done-when screens.
            assert "that your Done-when items name" in prompt
            assert "Build nothing for any other screen or field" in prompt
            # Full and continued briefs phrase the same theme requirement differently.
            for text in ("### frontend", "impeccable", "emil-design-eng",
                         "theme tokens, type and colours", "app's theme file"):
                assert text in prompt, text
            assert ("apps/web/src/index.css" in prompt) == starter
        else:
            assert "context only" in prompt.lower()
    if not none:
        helper = Path(os.environ["AUTOREVIEW"])
        helper.write_text("from pathlib import Path\n"
                          "assert Path('docs/design/baskets/flow.svg').read_text('utf-8') == '<svg>Flow</svg>\\n'\n"
                          + helper.read_text("utf-8"), encoding="utf-8")
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    prompt = env.prompt()
    context(prompt, folder)
    assert ("Report as P1 a built screen" in prompt) == (not none)
    if not none:
        assert "starter's neutral tokens" in prompt
        assert "component or field" in prompt
        assert "Do not report a field missing from any other screen" in prompt


def test_2_unsigned_prototype_fix_receives_its_own_screen_requirements(env, monkeypatch, sdk_data):
    repo = env.repo
    prepare(env, monkeypatch, sdk_data, "claude", prototype=True)
    _accept_build_decision(repo)
    item, _ = env.start_fix(fix_kind="ui", allow_large="Prototype before sign-off")
    log = install_claude(repo)
    worked = repo.forge("work", item)
    assert worked.returncode == 0, worked.stdout + worked.stderr
    context(calls(log)[-1]["brief"], "docs/design/prototype/")
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    prompt = env.prompt()
    context(prompt, "docs/design/prototype/")
    # Working prototype rounds use design references to find demo breakage. The strict
    # design-completeness requirement remains at sign-off rather than every demo round.
    assert "Use the screen list to assess demo breakage" in prompt
    assert "docs/design/prototype/SCREENS.md" in prompt
