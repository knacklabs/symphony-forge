"""Command regressions for current confirmation and required roadmap lines."""
from test_records import SPEC, ITEMS, _ok
from test_spec_rules import client, _write  # noqa: F401

STORY = "fix-spec-confirm-edited-and-roadmap"
CONFIRM = ("spec", "confirm", "invoices", "--by", "Ravi")


def notes(repo, top):
    digest = repo.git("hash-object", "docs/specs/invoices.md", cwd=top)
    _write(top, "docs/specs/invoices.read.md",
           f"---\nread_hash: {digest}\nround: 1\npassed: yes\n---\n\n"
           "## Round 1\n\nNo findings.\n")


def test_1_edited_spec_needs_current_text_confirmation(repo, client):
    top, _, _ = client
    _write(top, "docs/specs/invoices.md", SPEC)
    _ok(repo.forge("spec", "save", "invoices", cwd=top))
    notes(repo, top)
    _ok(repo.forge(*CONFIRM, cwd=top))
    spec = top / "docs/specs/invoices.md"
    spec.write_text(spec.read_text("utf-8").replace("emailed as a PDF", "sent as HTML"), "utf-8")
    result = repo.forge(*CONFIRM, cwd=top)
    assert (result.returncode, result.stderr) == (1,
        "docs/specs/invoices.md is not the text that was confirmed; it needs a new "
        "cold read and confirmation.\nNext: forge spec save invoices\n")
    _ok(repo.forge("spec", "save", "invoices", cwd=top))
    notes(repo, top)
    assert _ok(repo.forge(*CONFIRM, cwd=top)) == (
        "docs/specs/invoices.md is confirmed by Ravi. Next: forge roadmap add invoices\n")
    assert "Added" in _ok(repo.forge("roadmap", "add", "invoices", cwd=top))
    assert _ok(repo.forge(*CONFIRM, cwd=top)) == "docs/specs/invoices.md is already confirmed.\n"


def test_2_no_roadmap_lines_refused_before_confirmation(repo, client):
    top, _, _ = client
    for body in (SPEC.replace(ITEMS, ""), SPEC.split("## Roadmap")[0]):
        _write(top, "docs/specs/invoices.md", "---\nstatus: draft\n---\n\n" + body)
        notes(repo, top)
        before = repo.git("rev-parse", "HEAD", cwd=top)
        for command in (CONFIRM, ("spec", "save", "invoices")):
            result = repo.forge(*command, cwd=top)
            assert (result.returncode, result.stderr) == (1,
                "The Roadmap section of docs/specs/invoices.md needs one `- KEY: title` "
                "line per story: it has none.\nNext: forge spec save invoices\n")
            assert repo.git("rev-parse", "HEAD", cwd=top) == before
