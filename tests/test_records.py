"""Planning records (specs, decisions, the roadmap), driven only through the forge command.

The spec's cold read is written here the way `forge read <slug>` leaves it: the notes file
docs/specs/<slug>.read.md, with the read record in its frontmatter and the findings below.
"""
from __future__ import annotations

import json

SPEC = """# Invoices by email

## Why

Clients lose paper invoices.

## Behaviour

Each invoice is emailed as a PDF.

## Acceptance criteria

1. An invoice reaches the client's inbox.

## Roadmap

- INV-1: Invoices go out by email
- INV-2: Clients can resend an invoice
"""

FINDINGS = """1. Cut or defer: resending; no Done-when item needs it.
   Disposition: defer
2. Simpler: an HTML email instead of a PDF.
   Disposition: keep{reason}
"""

MAIN = ("Forge changes nothing on main; work happens on a story, task or fix branch.\n"
        'Next: forge fix start "<why>" --done "<done when>"\n')


def _refused(done, problem: str, next_step: str) -> None:
    assert (done.returncode, done.stderr) == (1, f"{problem}\nNext: {next_step}\n")


def _ok(done) -> str:
    assert done.returncode == 0, done.stderr
    return done.stdout


def _notes(repo, read_hash: str, amended_hash: str = "", reason: str = "") -> None:
    repo.write("docs/specs/invoices.read.md",
               f"---\nreader: codex\nread_at: 2026-09-25T10:00:00+00:00\nread_hash: {read_hash}\n"
               f"amended_hash: {amended_hash}\n---\n\n# Cold read\n\n"
               + FINDINGS.format(reason=reason))


def _text(repo, rel: str) -> str:
    return (repo.path / rel).read_text(encoding="utf-8")


def _committed(repo) -> list[str]:
    return repo.git("show", "--name-only", "--format=", "HEAD").splitlines()


def test_41_records_ship_through_the_fix_lane(repo, monkeypatch):
    monkeypatch.setenv("FORGE_NOW", "2026-09-25T10:00:00+00:00")
    repo.write("plans/roadmap.json", json.dumps({"generated_by": "human", "items": [
        {"key": "OLD-1", "title": "Old", "spec": "docs/specs/other.md", "order": 4}]}, indent=2))
    repo.write("docs/decisions/0001-use-mysql.md",
               '---\nstatus: accepted\nconfirmed_by: "Ann"\n---\n\n# Use MySQL\n')
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "Planning so far")
    repo.git("checkout", "-q", "-b", "fix/elsewhere")  # another branch has taken decision 0007
    repo.write("docs/decisions/0007-elsewhere.md", "---\nstatus: proposed\n---\n\n# Elsewhere\n")
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "A decision elsewhere")
    repo.git("checkout", "-q", "main")
    main = repo.git("rev-parse", "main")

    # On the default branch every records command refuses and changes nothing.
    repo.write("docs/specs/invoices.md", SPEC)
    for command in (["spec", "save", "invoices"], ["spec", "confirm", "invoices", "--by", "Ravi"],
                    ["decision", "new", "use-postgres"],
                    ["decision", "accept", "use-mysql", "--by", "Ravi"],
                    ["roadmap", "add", "invoices"]):
        done = repo.forge(*command)
        assert (done.returncode, done.stderr) == (1, MAIN), command
    assert repo.git("rev-parse", "main") == main
    assert repo.git("status", "--porcelain", "--untracked-files=all") == "?? docs/specs/invoices.md"

    # The fix lane: the branch `forge fix start` makes.
    repo.git("checkout", "-q", "-b", "fix/plan-invoices")
    _refused(repo.forge("spec", "save", "Invoices by email"),
             "'Invoices by email' is not a slug; a slug is lowercase words joined by hyphens.",
             "forge spec save invoices-by-email")
    _refused(repo.forge("spec", "save", "missing"),
             "docs/specs/missing.md does not exist; write the spec there first.",
             "forge spec save missing")
    repo.write("docs/specs/thin.md", "## Why\n\nBecause.\n")
    _refused(repo.forge("spec", "save", "thin"),
             "docs/specs/thin.md is missing a # title, ## Behaviour, ## Acceptance criteria.",
             "forge spec save thin")
    _refused(repo.forge("spec", "confirm", "thin", "--by", "Ravi"),
             "docs/specs/thin.md is not a saved draft (status: none).", "forge spec save thin")

    # Save: a draft, committed on the fix branch. Roadmap add refuses a draft spec.
    assert _ok(repo.forge("spec", "save", "invoices")) == (
        "Saved docs/specs/invoices.md as a draft. Next: forge read invoices\n")
    draft = _text(repo, "docs/specs/invoices.md")
    assert draft == ("---\nslug: invoices\ntitle: Invoices by email\nstatus: draft\n"
                     "saved: 2026-09-25T10:00:00+00:00\n---\n\n" + SPEC)
    assert _committed(repo) == ["docs/specs/invoices.md"]
    _refused(repo.forge("roadmap", "add", "invoices"),
             "docs/specs/invoices.md is not confirmed (status: draft); only a confirmed spec adds "
             "roadmap items.", 'forge spec confirm invoices --by "<name>"')

    # Confirm needs the cold read, the amended hash and a disposition under every finding.
    confirm = ("spec", "confirm", "invoices", "--by", "Ravi")
    _refused(repo.forge("spec", "confirm", "invoices", "--by", " "),
             "--by needs the name of the human who confirmed, on one line.",
             'forge spec confirm invoices --by "<name>"')
    _refused(repo.forge(*confirm), "docs/specs/invoices.md has no cold read.", "forge read invoices")
    read_hash = repo.git("hash-object", "docs/specs/invoices.md")
    _notes(repo, read_hash)
    _refused(repo.forge(*confirm),
             "Finding 2 in docs/specs/invoices.read.md has no disposition: cut, defer, or keep "
             "with a reason.", 'forge spec confirm invoices --by "Ravi"')
    _notes(repo, read_hash, reason=" - clients file PDFs")
    amended = draft.replace("- INV-2: Clients can resend an invoice\n", "") + (
        "\n## Out of scope\n\nResending an invoice.\n")
    repo.write("docs/specs/invoices.md", amended)
    _refused(repo.forge(*confirm), "docs/specs/invoices.md changed after its cold read.",
             "forge read invoices --amended")
    _notes(repo, read_hash, repo.git("hash-object", "docs/specs/invoices.md"), " - clients file PDFs")
    repo.write("docs/specs/invoices.md", amended + "One more edit.\n")
    _refused(repo.forge(*confirm), "docs/specs/invoices.md changed after its one recorded amendment.",
             "git diff -- docs/specs/invoices.md")
    repo.write("docs/specs/invoices.md", amended)
    assert _ok(repo.forge(*confirm)) == (
        "docs/specs/invoices.md is confirmed by Ravi. Next: forge roadmap add invoices\n")
    assert _text(repo, "docs/specs/invoices.md").startswith(
        '---\nslug: invoices\ntitle: Invoices by email\nstatus: confirmed\n'
        'saved: 2026-09-25T10:00:00+00:00\nconfirmed_by: "Ravi"\n---\n\n# Invoices by email\n')
    assert _committed(repo) == ["docs/specs/invoices.md", "docs/specs/invoices.read.md"]
    assert _ok(repo.forge(*confirm)) == "docs/specs/invoices.md is already confirmed.\n"
    _refused(repo.forge("spec", "save", "invoices"),
             "docs/specs/invoices.md is already confirmed; saving it again would undo the human's "
             "confirmation.", "forge spec save <new-slug>")

    # Roadmap add: each `- KEY: title` line of the spec's Roadmap section, through the fix lane.
    confirmed = _text(repo, "docs/specs/invoices.md")
    for section, problem in (("", "it has none"),
                             ("- INV-3 resend\n", "'- INV-3 resend' is not one"),
                             ("- INV-1: One\n- INV-1: Two\n", "INV-1 is listed twice"),
                             ("- OLD-1: Old again\n",
                              "OLD-1 is already on the roadmap for docs/specs/other.md")):
        repo.write("docs/specs/invoices.md",
                   confirmed.replace("- INV-1: Invoices go out by email\n", section))
        _refused(repo.forge("roadmap", "add", "invoices"),
                 "The Roadmap section of docs/specs/invoices.md needs one `- KEY: title` line per "
                 f"story: {problem}.", "forge roadmap add invoices")
    repo.git("checkout", "--", "docs/specs/invoices.md")
    assert _ok(repo.forge("roadmap", "add", "invoices")) == (
        "Added INV-1 to plans/roadmap.json from docs/specs/invoices.md.\n")
    assert json.loads(_text(repo, "plans/roadmap.json")) == {"generated_by": "human", "items": [
        {"key": "OLD-1", "title": "Old", "spec": "docs/specs/other.md", "order": 4},
        {"key": "INV-1", "title": "Invoices go out by email", "spec": "docs/specs/invoices.md",
         "status": "pending", "order": 5}]}
    assert _committed(repo) == ["plans/roadmap.json"]
    assert _ok(repo.forge("roadmap", "add", "invoices")) == (
        "plans/roadmap.json already has every item in docs/specs/invoices.md.\n")

    # Decisions: the next number after every branch's, then accepted with who confirmed it.
    accept = ("decision", "accept", "use-postgres", "--by", "Ravi")
    _refused(repo.forge(*accept), "There is no decision docs/decisions/NNNN-use-postgres.md.",
             "forge decision new use-postgres")
    assert _ok(repo.forge("decision", "new", "use-postgres")).startswith(
        "Wrote docs/decisions/0008-use-postgres.md; no branch has a higher decision number.")
    record = "docs/decisions/0008-use-postgres.md"
    proposed = _text(repo, record)
    assert proposed.startswith('---\nstatus: proposed\nconfirmed_by: ""\ndate: 2026-09-25\n'
                               'stories: []\nsupersedes: ""\n---\n\n# Use postgres\n')
    assert _committed(repo) == [record]
    _refused(repo.forge("decision", "new", "use-postgres"), f"{record} already exists.",
             'forge decision accept use-postgres --by "<name>"')
    repo.write(record, proposed.replace('supersedes: ""', "supersedes: use-oracle"))
    _refused(repo.forge(*accept),
             f"{record} supersedes use-oracle, but there is no such decision.",
             'forge decision accept use-postgres --by "Ravi"')
    repo.write(record, proposed.replace('supersedes: ""', "supersedes: 0001-use-mysql"))
    assert _ok(repo.forge(*accept)) == (
        f"Accepted {record}, confirmed by Ravi; docs/decisions/0001-use-mysql.md is now superseded.\n")
    assert _text(repo, record).startswith('---\nstatus: accepted\nconfirmed_by: "Ravi"\n')
    assert _text(repo, "docs/decisions/0001-use-mysql.md") == (
        '---\nstatus: superseded\nconfirmed_by: "Ann"\nsuperseded_by: 0008-use-postgres\n---\n\n'
        "# Use MySQL\n")
    assert _committed(repo) == ["docs/decisions/0001-use-mysql.md", record]
    assert _ok(repo.forge(*accept)) == f"{record} is already accepted.\n"
    _refused(repo.forge("decision", "accept", "use-mysql", "--by", "Ravi"),
             "docs/decisions/0001-use-mysql.md is superseded, so it cannot be accepted.",
             "forge decision new <new-slug>")
    assert repo.git("rev-parse", "main") == main
