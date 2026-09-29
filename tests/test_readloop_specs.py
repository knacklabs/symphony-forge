STORY = "FORGE-READLOOP-1"
"""Specs pass the same way: `spec confirm` and forge-pr-check refuse an unconfirmed spec whose
latest round had findings or which changed after that round; a passing round commits the spec and
its notes, so its pull-request head passes; a confirmed spec keeps today's rules. Everything runs
the real forge command, with the stub `claude` from test_story as the reader.
Each test is named test_<n>_<rule> after the Done-when item of STORY it proves.
"""

from test_readloop_gates import dispose_all, pr_check, read, say
from test_records import SPEC
from test_story import setup, worktree

CONFIRM = ("spec", "confirm", "invoices", "--by", "Ravi")
NOT_PASSED = ("Round {n} of the cold read of docs/specs/invoices.md hasn't passed, so it needs "
              "another round.")
CHANGED = "docs/specs/invoices.md changed after its last round of cold read."
REVIEW_NEXT = "The committed review at the head of fix/{slug} is missing."


def refused(done, problem, next_step="forge read invoices"):
    assert (done.returncode, done.stderr.splitlines()[-2:]) == (1, [problem, f"Next: {next_step}"]), (
        done.stdout + done.stderr)


def test_7_specs_pass_the_same_way(repo):
    setup(repo)
    started = repo.forge("fix", "start", "Invoices get lost", "--done", "The spec is confirmed")
    assert started.returncode == 0, started.stderr
    branch = repo.git("branch", "--list", "fix/*", "--format=%(refname:short)")
    fix = worktree(repo, branch)
    spec, notes = fix / "docs" / "specs" / "invoices.md", fix / "docs" / "specs" / "invoices.read.md"
    spec.parent.mkdir(parents=True)
    spec.write_text(SPEC, encoding="utf-8")
    assert repo.forge("spec", "save", "invoices", cwd=fix).returncode == 0
    # A draft spec with no cold read yet is today's rules: the check goes on to the review.
    assert pr_check(repo, branch).stderr.splitlines()[-2] == REVIEW_NEXT.format(slug=branch[4:])

    # Round 1 has findings: confirm refuses, and so does the pull-request check once it's pushed.
    say(repo, "1. Resending isn't needed by any criterion.\n")
    read(repo, "invoices", cwd=fix)
    refused(repo.forge(*CONFIRM, cwd=fix),
            "Finding 1 in docs/specs/invoices.read.md has no disposition: cut, defer, or keep with a "
            "reason.", 'forge spec confirm invoices --by "Ravi"')
    dispose_all(notes)
    refused(repo.forge(*CONFIRM, cwd=fix), NOT_PASSED.format(n=1))
    repo.git("add", "-A", cwd=fix)
    repo.git("commit", "-q", "-m", "Answer the findings", cwd=fix)
    refused(pr_check(repo, branch), NOT_PASSED.format(n=1))
    # The latest round's text decides, not its passed flag.
    notes.write_text(notes.read_text("utf-8").replace("passed: no", "passed: yes"), encoding="utf-8")
    refused(repo.forge(*CONFIRM, cwd=fix), NOT_PASSED.format(n=1))
    repo.git("commit", "-q", "-am", "Mark the round passed", cwd=fix)
    refused(pr_check(repo, branch), NOT_PASSED.format(n=1))

    # Round 2 passes and is committed, so the pull-request head passes the spec check.
    say(repo, "No findings.\n")
    read(repo, "invoices", cwd=fix)
    assert repo.git("status", "--porcelain", cwd=fix) == ""
    assert pr_check(repo, branch).stderr.splitlines()[-2] == REVIEW_NEXT.format(slug=branch[4:])

    # A spec edited after its passing round is refused by both, uncommitted or committed.
    spec.write_text(spec.read_text("utf-8") + "\nOne more idea.\n", encoding="utf-8")
    refused(repo.forge(*CONFIRM, cwd=fix), CHANGED)
    repo.git("commit", "-q", "-am", "One more idea", cwd=fix)
    refused(pr_check(repo, branch), CHANGED)
    repo.git("revert", "--no-edit", "HEAD", cwd=fix)

    # After the passing round it confirms, and a confirmed spec keeps today's rules.
    confirmed = repo.forge(*CONFIRM, cwd=fix)
    assert confirmed.stdout == ("docs/specs/invoices.md is confirmed by Ravi. "
                                "Next: forge roadmap add invoices\n"), confirmed.stderr
    assert "status: confirmed" in spec.read_text("utf-8")
    notes.write_text(notes.read_text("utf-8").replace("## Round 2\n\nNo findings.",
                                                      "## Round 2\n\n2. A late thought."),
                     encoding="utf-8")
    repo.git("commit", "-q", "-am", "A late thought", cwd=fix)
    assert pr_check(repo, branch).stderr.splitlines()[-2] == REVIEW_NEXT.format(slug=branch[4:])
