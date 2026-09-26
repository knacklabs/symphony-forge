"""A spec's success measure: refused when incomplete, then checked back once its stories ship.

Driven only through the forge command; a merge to main pushed to origin is how work lands.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

STORY = "FORGE-FDE-1"

MEASURE = """## Success measure

- Metric: share of invoices paid within
  30 days.
- Baseline: 40% today.
- Target: 70%.
- Check date: 2026-10-01
"""
SPEC = f"""# Invoices by email

## Why

Clients lose paper invoices.

## Behaviour

Each invoice is emailed as a PDF.

## Acceptance criteria

1. An invoice reaches the client's inbox.

{MEASURE}
## Roadmap

- INV-1: Invoices go out by email
- INV-2: Clients can resend an invoice
"""
NEEDS = "docs/specs/{slug}.md needs a ## Success measure section with {missing} filled in."
ALL = "- Metric:, - Baseline:, - Target:, - Check date: YYYY-MM-DD"
DUE = ["Every story from the Invoices by email spec is done and its check date has passed; "
       "measure share of invoices paid within 30 days.",
       'Next: forge fix start "Record the invoices success result" --done "The invoices spec '
       'records its result"',
       'Next: forge spec measure invoices --result "<measured result>"']


def _refused(done, problem: str, next_step: str) -> None:
    assert (done.returncode, done.stderr) == (1, f"{problem}\nNext: {next_step}\n")


def _ok(done) -> str:
    assert done.returncode == 0, done.stderr
    return done.stdout


def _fix(repo, why: str):
    """Start a real fix and return its worktree."""
    started = _ok(repo.forge("fix", "start", why, "--done", "It is recorded"))
    path = Path(started.splitlines()[0].rsplit(" in ", 1)[1])
    (path / "docs/specs").mkdir(parents=True, exist_ok=True)
    return path


def _confirm(repo, fix, slug: str) -> None:
    """Save, read (as `forge read` leaves its notes) and confirm a spec in the fix's worktree."""
    _ok(repo.forge("spec", "save", slug, cwd=fix))
    read_hash = repo.git("hash-object", f"docs/specs/{slug}.md", cwd=fix)
    (fix / f"docs/specs/{slug}.read.md").write_text(
        f"---\nreader: codex\nread_at: 2026-09-25T10:00:00+00:00\nread_hash: {read_hash}\n---\n",
        encoding="utf-8")
    _ok(repo.forge("spec", "confirm", slug, "--by", "Ravi", cwd=fix))


def _land(repo, branch: str) -> None:
    repo.git("merge", "-q", "--ff-only", branch)
    repo.git("push", "-q", "origin", "main")


def _done(repo, *keys: str) -> None:
    """Stories whose outcome `forge story done` has recorded on main."""
    for key in keys:
        repo.write(f".factory/stories/{key}/story.json",
                   f'{{"title": "{key}", "status": "done"}}\n')
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", f"Finish {', '.join(keys)}")
    repo.git("push", "-q", "origin", "main")


def _next(repo, monkeypatch, today: str) -> list[str]:
    monkeypatch.setenv("FORGE_NOW", f"{today}T09:00:00+00:00")
    return _ok(repo.forge("next")).splitlines()


def test_5_a_spec_without_a_complete_success_measure_is_refused(repo, monkeypatch):
    monkeypatch.setenv("FORGE_NOW", "2026-09-25T10:00:00+00:00")
    fix = _fix(repo, "Plan invoices by email")
    save = ("spec", "save", "invoices")
    for measure, missing in (
            ("", ALL),
            ("## Success measure\n\nWe'll know it when we see it.\n", ALL),
            (MEASURE.replace("70%.", "").replace("2026-10-01", "next month"),
             "- Target:, - Check date: YYYY-MM-DD"),
            (MEASURE.replace("2026-10-01", "2026-02-30"), "- Check date: YYYY-MM-DD"),
            (MEASURE.replace("2026-10-01", "2026-10-01\n  or later"),
             "- Check date: YYYY-MM-DD")):
        (fix / "docs/specs/invoices.md").write_text(SPEC.replace(MEASURE, measure), encoding="utf-8")
        _refused(repo.forge(*save, cwd=fix), NEEDS.format(slug="invoices", missing=missing),
                 "forge spec save invoices")
    assert repo.git("status", "--porcelain", "--untracked-files=all", cwd=fix) == "?? docs/specs/invoices.md"

    # A draft whose measure was emptied after it was saved is refused at confirm, before the read.
    (fix / "docs/specs/invoices.md").write_text(SPEC, encoding="utf-8")
    _ok(repo.forge(*save, cwd=fix))
    draft = (fix / "docs/specs/invoices.md").read_text(encoding="utf-8")
    (fix / "docs/specs/invoices.md").write_text(draft.replace("- Baseline: 40% today.", "- Baseline:"),
                                                encoding="utf-8")
    _refused(repo.forge("spec", "confirm", "invoices", "--by", "Ravi", cwd=fix),
             NEEDS.format(slug="invoices", missing="- Baseline:"), "forge spec save invoices")

    # A spec confirmed before the measure was required isn't checked again until it is saved,
    # but it can't record a result without one.
    body = "\n" + SPEC.replace(MEASURE, "")
    old = (f"---\nslug: old\nstatus: confirmed\n"
           f"confirmed_hash: {hashlib.sha256(body.encode()).hexdigest()}\n---\n{body}")
    (fix / "docs/specs/old.md").write_text(old, encoding="utf-8")
    assert _ok(repo.forge("spec", "confirm", "old", "--by", "Ravi", cwd=fix)) == (
        "docs/specs/old.md is already confirmed.\n")
    _refused(repo.forge("spec", "measure", "old", "--result", "72%", cwd=fix),
             NEEDS.format(slug="old", missing=ALL), "forge spec save old")
    assert (fix / "docs/specs/old.md").read_text(encoding="utf-8") == old


def test_6_forge_next_lists_a_due_check_until_forge_spec_measure_records_it(repo, monkeypatch):
    monkeypatch.setenv("FORGE_NOW", "2026-09-25T10:00:00+00:00")
    plan = _fix(repo, "Plan invoices by email")
    (plan / "docs/specs/invoices.md").write_text(SPEC, encoding="utf-8")
    _confirm(repo, plan, "invoices")
    _ok(repo.forge("roadmap", "add", "invoices", cwd=plan))
    measure = ("spec", "measure", "invoices", "--result", "65% paid within 30 days")

    # Measuring before the spec lands still needs the fix lane, a confirmed spec and one line.
    _refused(repo.forge(*measure),
             "Forge changes nothing on main; work happens on a story, task or fix branch.",
             'forge fix start "<why>" --done "<done when>"')
    for result in ("", "65%\nand more"):
        _refused(repo.forge("spec", "measure", "invoices", "--result", result, cwd=plan),
                 "--result needs the measured result, on one line.",
                 'forge spec measure invoices --result "<measured result>"')
    _land(repo, "fix/plan-invoices-by-email")
    repo.git("worktree", "remove", str(plan))  # nothing is in progress once the plan lands

    # Not due while any of its stories is unfinished, nor before its check date.
    _done(repo, "INV-1")
    assert not set(DUE) & set(_next(repo, monkeypatch, "2026-10-01"))
    _done(repo, "INV-2")
    assert not set(DUE) & set(_next(repo, monkeypatch, "2026-09-30"))
    # A due check comes before the idle lines, where discovery and the next planning step go.
    assert _next(repo, monkeypatch, "2026-10-01") == DUE + [
        "No story or fix is in progress.",
        'Next: forge story new <KEY> "<title>" for an item on plans/roadmap.json',
        'Next: forge fix start "<why>" --done "<done when>"']

    # Recording the result: only in a fix, only on the confirmed text, and the spec stays confirmed.
    record = _fix(repo, "Record the invoices success result")
    spec = record / "docs/specs/invoices.md"
    confirmed = spec.read_text(encoding="utf-8")
    spec.write_text(confirmed.replace("70%.", "80%."), encoding="utf-8")
    _refused(repo.forge(*measure, cwd=record), "docs/specs/invoices.md is not the text that was "
             "confirmed; it needs a new cold read and confirmation.", "forge spec save invoices")
    spec.write_text(confirmed, encoding="utf-8")
    assert _ok(repo.forge(*measure, cwd=record)) == (
        "Added the result to the Success measure of docs/specs/invoices.md; it stays confirmed.\n")
    measured = spec.read_text(encoding="utf-8")
    unhashed = re.compile(r"^confirmed_hash: .*\n", re.M)
    assert unhashed.sub("", measured) == unhashed.sub("", confirmed).replace(
        "- Check date: 2026-10-01\n",
        "- Check date: 2026-10-01\n- Result: 65% paid within 30 days (2026-10-01)\n")
    assert "\nstatus: confirmed\n" in measured
    assert repo.git("show", "--name-only", "--format=", "HEAD", cwd=record) == (
        "docs/specs/invoices.md")
    assert _ok(repo.forge("roadmap", "add", "invoices", cwd=record)) == (
        "plans/roadmap.json already has every item in docs/specs/invoices.md.\n")

    # Once it lands the check is gone; a later result just adds another line.
    _land(repo, "fix/record-the-invoices-success-result")
    assert not set(DUE) & set(_next(repo, monkeypatch, "2026-10-02"))
    _ok(repo.forge("spec", "measure", "invoices", "--result", "72%", cwd=record))
    assert spec.read_text(encoding="utf-8").endswith(
        "- Result: 65% paid within 30 days (2026-10-01)\n- Result: 72% (2026-10-02)\n\n"
        "## Roadmap\n\n- INV-1: Invoices go out by email\n- INV-2: Clients can resend an invoice\n")

    # A spec that isn't confirmed records nothing.
    (record / "docs/specs/draft.md").write_text(SPEC, encoding="utf-8")
    _ok(repo.forge("spec", "save", "draft", cwd=record))
    _refused(repo.forge("spec", "measure", "draft", "--result", "72%", cwd=record),
             "docs/specs/draft.md is not confirmed (status: draft); only a confirmed spec records "
             "a result.", 'forge spec confirm draft --by "<name>"')
