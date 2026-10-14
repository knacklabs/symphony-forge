"""Specs keep full-document blocking after round two; only story plans cap unchanged text."""
import json

import pytest

from test_fix_plan_reads_capped import CAP, _client
from test_readloop_gates import dispose_all, say
from test_records import SPEC
from test_story import worktree

STORY = "FIX-PLAN-READS-CAPPED"


@pytest.mark.parametrize("previous", [False, True], ids=["init", "earlier-adoption-upgrade-sync"])
def test_3_specs_keep_full_document_blocking_in_later_rounds(repo, gh, tmp_path, previous):
    _client(repo, gh, tmp_path, previous)
    started = repo.forge("fix", "start", "Invoices get lost", "--done", "The spec is confirmed")
    assert started.returncode == 0, started.stdout + started.stderr
    branch = repo.git("branch", "--list", "fix/invoices-get-lost", "--format=%(refname:short)")
    where = worktree(repo, branch)
    spec = where / "docs/specs/invoices.md"
    spec.parent.mkdir(parents=True, exist_ok=True)
    spec.write_text(SPEC, encoding="utf-8")
    saved = repo.forge("spec", "save", "invoices", cwd=where)
    assert saved.returncode == 0, saved.stdout + saved.stderr
    notes = spec.with_name("invoices.read.md")
    for number, gap in enumerate(("The invoice recipient is unspecified.",
                                  "Failed delivery has no recovery rule.",
                                  "The unchanged PDF rule exposes private invoice data."), 1):
        say(repo, f"{number}. Blocking: {gap}\n")
        result = repo.forge("read", "invoices", cwd=where)
        assert result.returncode == (1 if number == 3 else 0), result.stdout + result.stderr
        if number < 3:
            dispose_all(notes)
    # The third-party reply cannot prove an agent's judgement; inspect Forge's delivered contract.
    calls = repo.bin / "claude-calls.jsonl"
    prompts = [json.loads(line)["prompt"] for line in calls.read_text("utf-8").splitlines()]
    assert "Look for new gaps anywhere in the doc" in prompts[2]
    assert CAP not in prompts[2]
    assert "The unchanged PDF rule exposes private invoice data." in notes.read_text("utf-8")
    resolution = 'forge read invoices --resolve <accept|narrow|split> --reason "<human\'s choice>"'
    lines = result.stderr.splitlines()
    assert [lines[0], lines[-1]] == [
        "Three consecutive cold-read rounds of invoices still have blocking notes. "
        "Ask the human to accept, narrow or split before reading again, in these words:",
        f"Next: {resolution}"]
    assert "- The unchanged PDF rule exposes private invoice data." in lines[1:-1]
    assert lines[1] == "Invoices by email: Each invoice is emailed as a PDF."  # what it delivers
    assert [line.split(":")[0] for line in lines[-4:-1]] == ["- Accept", "- Narrow", "- Split"]
    held = repo.forge("read", "invoices", cwd=where)
    assert held.returncode == 1 and resolution in held.stderr
    assert len(calls.read_text("utf-8").splitlines()) == 3
