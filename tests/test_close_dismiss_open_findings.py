"""Dismissals refer to open findings before a repair review changes its report."""
import json
import sys

import pytest
import conftest
from test_close import CLEAN, blocked, body, env, finding
from test_close_explains_findings_and_requires_done_when import setup_client

STORY = "dismiss-checked-first"


def _reviewed_fix(env, adopted=False):
    setup_client(env, adopted)
    marker = env.tmp / "client-tests-ran"
    conftest._install(env.repo.bin, "client-tests", f'''#!{sys.executable}
from pathlib import Path
Path({json.dumps(marker.as_posix())}).write_text("ran", encoding="utf-8")
''')
    settings = (env.repo.path / "forge.toml").read_text("utf-8")
    env.commit(env.repo.path, "forge.toml", settings + '\ntest = "client-tests"\ntest_place = "local"\n')
    env.commit(env.repo.path, "app.py", "print('base')\n")
    env.repo.git("push", "-q", "origin", "main")
    env.reviews(blocked(finding("P0", "The greeting is missing"),
                        finding("P0", "The greeting loses its punctuation")), CLEAN)
    item, where = env.start_fix()
    first = env.close(item)
    assert first.returncode == 1, first.stdout + first.stderr
    assert marker.exists()
    marker.unlink()
    env.commit(where, "other.py", "value = 1\n")
    return item, marker


@pytest.mark.parametrize("adopted,settled", [(False, False), (False, True), (True, False)],
                         ids=["new-unknown", "new-dismissed", "adopted-unknown"])
def test_1_unknown_dismissal_stops_before_tests_or_review(env, adopted, settled):
    # Contract: bad input costs no test or model run. Previously validation was too late.
    # Existing refusal cases check text, but do not check either expensive side effect.
    # Only external tools are faked; close is the real command, with no production seam.
    item, marker = _reviewed_fix(env, adopted)
    if settled:
        # The first number stays open, but the second is no longer open.
        env.reviews(blocked(finding("P0", "The greeting is missing"),
                            finding("P0", "The greeting loses its punctuation")))
        accepted = env.close(item, "--dismiss", "2", "--because", "app.py:1 punctuation exists")
        assert accepted.returncode == 1 and "Review: blocked." in accepted.stdout, accepted.stdout + accepted.stderr
        marker.unlink()
        env.commit(env.tmp / "fix-tidy-readme", "other.py", "value = 2\n")
    calls = len(env.review_calls())
    result = env.close(item, "--dismiss", "1", "--because", "app.py:1 the greeting exists",
                       "--dismiss", "2" if settled else "9", "--because", "app.py:1 punctuation exists")
    assert result.returncode == 1, result.stdout + result.stderr
    assert "Each --dismiss needs an open finding number" in result.stderr
    assert f'Next: forge close {item} --dismiss <n> --because "<file:line> <reason>"' in result.stderr
    assert not marker.exists()
    assert len(env.review_calls()) == calls


@pytest.mark.parametrize("adopted", [False, True], ids=["new", "earlier-adopted"])
def test_2_dismiss_an_open_finding_from_an_earlier_round(env, adopted):
    # Contract: a repair report with no new findings still accepts the owner's dismissal.
    # Existing dismissal cases reuse or repeat the finding; none omit it in a new report.
    # The real command owns validation and publication; stubs only supply external reports.
    item, marker = _reviewed_fix(env, adopted)
    where = env.tmp / "fix-tidy-readme"
    # The old finding's file leaves the branch diff. Appending it to the repair
    # report used to make the saved review disagree with the required check.
    env.commit(where, "app.py", "print('base')\n")
    result = env.close(item, "--dismiss", "1", "--because", "app.py:1 the greeting exists",
                       "--dismiss", "2", "--because", "app.py:1 punctuation exists")
    assert result.returncode == 0, result.stdout + result.stderr
    assert marker.exists() and len(env.review_calls()) == 2
    checked = env.repo.forge("hook", "pr-check", "--base", env.repo.git("rev-parse", "HEAD"),
                             "--head", env.repo.git("rev-parse", "HEAD", cwd=where),
                             "--branch", "fix/tidy-readme")
    assert checked.returncode == 0, checked.stdout + checked.stderr


@pytest.mark.parametrize("adopted,settled", [(False, False), (False, True), (True, False)],
                         ids=["new-remote-number", "remotely-dismissed", "adopted-remote-number"])
def test_3_dismissal_numbers_use_the_reconciled_remote_review(env, adopted, settled):
    # Contract: another machine's review owns the current numbers and open status.
    # A local-only review fixture cannot expose a stale review after a remote merge.
    # Both machines use the real command, with only GitHub and the reviewer faked.
    item, marker = _reviewed_fix(env, adopted)
    teammate = env.tmp / "teammate"
    env.repo.git("clone", "-q", "-b", "fix/tidy-readme",
                 env.repo.git("remote", "get-url", "origin"), str(teammate))
    env.commit(teammate, "teammate.py", "value = 1\n")
    notes = [finding("P0", "The greeting is missing"), finding("P0", "The greeting loses its punctuation")]
    env.reviews(blocked(*notes, finding("P0", "The greeting drops its suffix")))
    extra = ("--dismiss", "2", "--because", "app.py:1 punctuation exists") if settled else ()
    remote = env.repo.forge("close", item, *extra, cwd=teammate)
    assert remote.returncode == 1 and "Review: blocked." in remote.stdout, remote.stdout + remote.stderr
    marker.unlink()
    calls = len(env.review_calls())
    result = env.close(item, "--dismiss", "2" if settled else "3", "--because", "app.py:1 the greeting exists")
    if settled:
        assert result.returncode == 1 and "Each --dismiss needs an open finding number" in result.stderr
        assert not marker.exists() and len(env.review_calls()) == calls
    else:
        assert result.returncode == 1 and "Review: blocked." in result.stdout, result.stdout + result.stderr
        assert marker.exists() and len(env.review_calls()) == calls + 1
        assert "The greeting drops its suffix (app.py:1): dismissed because app.py:1 the greeting exists" in body(
            env.gh_calls("pr", "edit")[-1])


@pytest.mark.parametrize("adopted", [False, True], ids=["new", "earlier-adopted"])
def test_4_reused_review_checks_evidence_at_its_reviewed_commit(env, adopted):
    # Contract: evidence for a reused review must exist at that review's commit.
    # Existing line checks do not merge a new evidence file while reusing a review.
    # Real Git history and close expose the lifetime mismatch without a new seam.
    item, marker = _reviewed_fix(env, adopted)
    # Keep the branch diff unchanged so close can reuse its earlier review.
    where = env.tmp / "fix-tidy-readme"
    env.reviews(blocked(finding("P0", "The greeting is missing")))
    assert env.close(item).returncode == 1
    marker.unlink()
    env.commit(env.repo.path, "proof.txt", "The greeting exists\n")
    env.repo.git("push", "-q", "origin", "main")
    env.gh.respond("pr", "list", "--head", stdout=json.dumps([
        {"number": 7, "state": "OPEN", "body": "", "isDraft": True, "mergeStateStatus": "BEHIND"}]))
    calls = len(env.review_calls())
    result = env.close(item, "--dismiss", "1", "--because", "proof.txt:1 the greeting exists")
    assert result.returncode == 1 and "proof.txt:1 is not a line of the reviewed commit" in result.stderr, result.stdout + result.stderr
    assert (where / "proof.txt").exists()
    assert not marker.exists() and len(env.review_calls()) == calls
