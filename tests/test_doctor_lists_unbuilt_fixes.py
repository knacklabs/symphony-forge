"""Doctor lists old starts and offers an owner-controlled drop command.

Test-audit: real doctor output owns this contract. Omitting unbuilt worktrees,
counting the start record as build work, or ignoring age makes this fail.
Finished-work cleanup tests cover PRs, not unpublished build work. Only GitHub
is fake; real fix starts, commits and worktrees supply the evidence. No seam.
"""
from test_doctor_fix_files import _land
from test_started_branches_claim_the_work import client  # noqa: F401
from test_story import worktree

STORY = "doctor-lists-old-empty-fixes"


def test_1_doctor_lists_each_started_empty_fix_older_than_seven_days(client, monkeypatch, request):
    repo = client
    monkeypatch.setenv("CODEX_HOME", str(repo.bin / "codex-home"))
    adopted = request.node.callspec.params["client"]
    cases = [("old-start", "2026-10-01T12:00:00+00:00")]
    if not adopted:
        cases += [("another-old-start", "2026-10-03T11:59:59+00:00"),
                  ("built-fix", "2026-10-01T12:00:00+00:00"),
                  ("recent-start", "2026-10-08T12:00:01+00:00"),
                  ("exactly-seven-days", "2026-10-03T12:00:00+00:00")]
    for name, at in cases:
        monkeypatch.setenv("FORGE_NOW", at)
        started = repo.forge("fix", "start", "Repair the greeting", "--done",
                             "Readers see the greeting", "--slug", name)
        assert started.returncode == 0, started.stdout + started.stderr
        if name == "built-fix":
            folder = worktree(repo, "fix/" + name)
            (folder / "greeting.txt").write_text("Hello\n", encoding="utf-8")
            repo.git("add", "greeting.txt", cwd=folder)
            repo.git("commit", "-qm", "Add the greeting", cwd=folder)

    if not adopted:
        # A newer default branch merged into an empty fix does not count as its work.
        _land(repo, repo.path, "Publish the news", lambda folder:
              (folder / "news.txt").write_text("News from another change\n", encoding="utf-8"))
        repo.git("merge", "-q", "--no-edit", "main", cwd=worktree(repo, "fix/old-start"))

    monkeypatch.setenv("FORGE_NOW", "2026-10-10T12:00:00+00:00")
    before = repo.git("worktree", "list", "--porcelain")
    checked = repo.forge("doctor")
    assert checked.returncode == 1, checked.stdout + checked.stderr
    names = ["old-start"] if adopted else ["old-start", "another-old-start"]
    for name in names:
        assert (f"Fix {name} started more than seven days ago and has no work commits.\n"
                f'  Fix: forge fix drop {name} --because "<reason>"') in checked.stdout
    for name in ("built-fix", "recent-start", "exactly-seven-days"):
        assert f"forge fix drop {name} " not in checked.stdout
    assert repo.git("worktree", "list", "--porcelain") == before
