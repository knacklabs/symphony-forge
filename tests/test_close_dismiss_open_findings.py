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
    env.repo.git("push", "-q", "origin", "main")
    env.reviews(blocked(finding("P0", "The greeting is missing")), CLEAN)
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
        # A number exists, but is no longer an open finding.
        env.reviews(blocked(finding("P0", "The greeting is missing")))
        accepted = env.close(item, "--dismiss", "1", "--because", "app.py:1 the greeting exists")
        assert accepted.returncode == 0, accepted.stdout + accepted.stderr
        marker.unlink()
        env.commit(env.tmp / "fix-tidy-readme", "other.py", "value = 2\n")
    calls = len(env.review_calls())
    result = env.close(item, "--dismiss", "1" if settled else "9", "--because", "app.py:1 the greeting exists")
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
    result = env.close(item, "--dismiss", "1", "--because", "app.py:1 the greeting exists")
    assert result.returncode == 0, result.stdout + result.stderr
    assert marker.exists() and len(env.review_calls()) == 2
    published = body(env.gh_calls("pr", "edit")[-1])
    assert "The greeting is missing (app.py:1): dismissed because app.py:1 the greeting exists" in published
