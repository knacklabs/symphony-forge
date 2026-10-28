"""Production stories inherit accepted sign-off evidence.

Test audit:
1. Protect the sign-off hand-off and cold reader's settled-evidence contract.
2. Story creation could omit proof or use the wrong canvas; the reader could re-open settled work.
3. Existing sign-off tests stop at acceptance, and story tests do not start after sign-off.
4. Use Forge commands and the reader's real prompt boundary; add no production seam.
"""
from __future__ import annotations

import json
import os
import re
import sys

import pytest

from test_proto_signoff import _adopted_client, _client, _decision
from test_story import DESIGN_TREE, DOC, READER, approved_constitution, worktree

pytestmark = pytest.mark.platform

STORY = "FORGE-PACE-1/HANDOFF"

PROOF = "The approved canvas proves the order list flow."
DESIGN_CHOICE = "The approved canvas is the source for production stories."


def _install_reader(repo):
    reader = repo.bin / "claude"
    reader.write_text(READER.format(python=sys.executable), encoding="utf-8")
    reader.chmod(0o755)
    if os.name == "nt":
        (repo.bin / "claude.cmd").write_text(f'@"{sys.executable}" "%~dp0claude" %*\n', encoding="utf-8")


def _start_story(repo, key):
    started = repo.forge("story", "new", key, f"Plan {key}")
    assert started.returncode == 0, started.stdout + started.stderr
    return worktree(repo, f"story/{key}") / "plans" / f"{key}.md"


def _assert_evidence(plan, tree, working_build):
    for text in ("## Proven by the prototype", "### Signed design",
                 f"docs/design/prototype/ ({tree})", "### Decisions", DESIGN_CHOICE,
                 f"Design: docs/design/prototype/ ({tree})"):
        assert text in plan
    if working_build:
        assert f"### Proof\n\n{PROOF}" in plan
    else:
        assert "### Proof" not in plan


@pytest.mark.parametrize("working_build", [False, True], ids=["canvas", "working-build"])
def test_1_first_and_second_stories_keep_signed_off_evidence(
        repo, tmp_path, monkeypatch, working_build):
    fix, answers, _ = _client(repo, tmp_path, monkeypatch, working_build=working_build)
    page = _decision(fix, answers, proof=PROOF if working_build else "")
    # A coordinator can keep the sign-off template's comment beside the signed folder.
    page.write_text(page.read_text("utf-8").replace(
        "## Signed design\n", "## Signed design\n<!-- The approved canvas follows. -->\n"), encoding="utf-8")
    accepted = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
    assert accepted.returncode == 0, accepted.stdout + accepted.stderr
    tree = repo.git("rev-parse", "HEAD:docs/design/prototype", cwd=fix)
    branch = repo.git("branch", "--show-current", cwd=fix)
    repo.git("merge", "--no-ff", "-m", "Merge accepted sign-off", branch, cwd=repo.path)
    approved_constitution(repo)

    first = _start_story(repo, "PROD-1")
    generated = first.read_text("utf-8")
    _assert_evidence(generated, tree, working_build)
    evidence = re.search(r"(?ms)^## Proven by the prototype\n.*?(?=^## |\Z)", generated)[0].rstrip()
    reader_doc = DOC.replace(f"Design: docs/design/baskets/ ({DESIGN_TREE})",
                             f"Design: docs/design/prototype/ ({tree})")
    reader_doc = reader_doc.replace("## Why\n", f"{evidence}\n\n## Why\n")
    first.write_text(reader_doc, encoding="utf-8")
    _install_reader(repo)
    read = repo.forge("read", "PROD-1")
    assert read.returncode == 0, read.stdout + read.stderr
    prompt = json.loads((repo.bin / "claude-calls.jsonl").read_text("utf-8").splitlines()[0])["prompt"]
    prompt = " ".join(prompt.split())
    prompt_items = ["Treat `## Proven by the prototype` as settled evidence from the accepted sign-off.",
                    "Read only the rest for new work and production risks.",
                    "Do not ask the plan to prove those outcomes again."]
    if working_build:
        prompt_items.append(PROOF)
    for text in prompt_items:
        assert " ".join(text.split()) in prompt

    second = _start_story(repo, "PROD-2").read_text("utf-8")
    _assert_evidence(second, tree, working_build)
    assert "status: accepted" in page.read_text("utf-8")


def test_2_adopted_legacy_signoff_starts_without_fabricated_evidence(
        repo, tmp_path, monkeypatch):
    _adopted_client(repo, tmp_path, monkeypatch, old_signoff=True)
    approved_constitution(repo)
    plan = _start_story(repo, "OLD-1").read_text("utf-8")
    assert "## Proven by the prototype" not in plan
    assert "### Signed design" not in plan
