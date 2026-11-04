"""The generated review check tolerates GitHub's delayed pull request ref.

Test-audit gate:
1. Protect the workflow delivered by init and by sync on an earlier-adopted repo.
2. A single fetch and silent comparison fail when GitHub still serves the prior commit.
3. Existing workflow tests do not cover this delay or its final diagnostic. The generated
   shell text is the public Actions contract, which the coordinator asked this test to check.
4. Use real Forge commands and existing client fixtures, with no production test seam.
"""
import pytest

from test_groups_pytest import _adopted_client, _new_client
from test_testplace_workflow import _jobs

STORY = "FIX-FORGE-PR-CHECK-FAILS-WITH-NO-MESSAGE-WHE"


@pytest.mark.parametrize("adopted", [False, True], ids=["new", "earlier-adopted"])
def test_1_review_waits_for_pull_request_ref_and_explains_a_safe_rerun(
        repo, gh, tmp_path, adopted):
    client = (_adopted_client(repo, tmp_path, "ref-client") if adopted else
              _new_client(repo, gh, tmp_path, "ref-client"))
    check = _jobs((client / ".github/workflows/forge.yml").read_text(encoding="utf-8"))[
        "forge-pr-check"]
    # Seven fetches with six five-second pauses allow 30 seconds for the ref to catch up.
    assert 'for attempt in 1 2 3 4 5 6 7; do' in check
    assert 'git fetch --no-tags origin "refs/pull/$PR/head"' in check
    assert 'fetched=$(git rev-parse FETCH_HEAD)' in check
    assert '[ "$fetched" = "$HEAD_SHA" ] && break' in check
    assert '[ "$attempt" = 7 ] || sleep 5' in check
    assert 'if [ "$fetched" != "$HEAD_SHA" ]; then' in check
    assert ('echo "GitHub\'s pull request ref has not caught up: fetched $fetched, '
            'expected $HEAD_SHA. A rerun is safe."' in check)
    assert '            exit 1\n' in check
