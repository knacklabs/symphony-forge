"""Command regression for canvas isolation and source-only clients.

Test audit: protect review input isolation, absent-image handling and hold labels.
Whole-tree snapshots and unconditional canvas calls are credible regressions.
Existing transport tests do not check these contracts. Observe only the external
review tool's checkout, reuse client setup, and add no production seam.
The same command case also protects counts at the round limit and on saved stops:
those paths can bypass the first-refusal summary without changing review transport.
"""
import json
import os
import shutil
from pathlib import Path

import pytest

from test_proto_signoff import _client, _adopted_client, _decision

STORY = "in-src-forge-review-py-run-takes-the-sig"
pytestmark = pytest.mark.platform


@pytest.mark.parametrize("adopted,source_only", [(False, False), (True, False), (True, True)],
                         ids=["new", "adopted", "source-only"])
def test_1_signoff_reviews_screens_separately_from_source(repo, tmp_path, monkeypatch, adopted, source_only):
    if adopted:
        repo.write("app.py", "print('earlier prototype')\n")
    fix, answers, queue = (_adopted_client if adopted else _client)(repo, tmp_path, monkeypatch)
    _decision(fix, answers)
    if source_only:
        repo.git("rm", "docs/design/prototype/order-list.svg", cwd=fix)
        repo.git("commit", "-qm", "Keep only source", cwd=fix)
    helper = Path(os.environ["AUTOREVIEW"])
    original = helper.with_name("original")
    shutil.copyfile(helper, original)
    observed = queue.with_suffix(".trees.jsonl")
    helper.write_text('''import json, runpy, subprocess, sys
from pathlib import Path
args = sys.argv[1:]
prompt = Path(args[args.index('--prompt-file') + 1]).read_text('utf-8')
names = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', 'HEAD'], text=True).splitlines()
with Path(OBSERVED).open('a', encoding='utf-8') as out:
    out.write(json.dumps({'canvas': '# Canvas completeness check' in prompt, 'names': names}) + '\\n')
runpy.run_path(ORIGINAL, run_name='__main__')
'''.replace("OBSERVED", json.dumps(str(observed))).replace("ORIGINAL", json.dumps(str(original))), encoding="utf-8")
    if not source_only:
        findings = [{"priority": priority, "title": title,
                     "body": "Gain 4, Work 2, Harm 2\nVisible gap evidence.",
                     "code_location": {"file_path": "docs/design/prototype/SCREENS.md", "line": 1}}
                    for priority, title in [("P1", "Missing status"), ("P2", "Small label")]]
        queue.write_text(json.dumps([{"report": {"review_status": "findings", "findings": findings}}]), encoding="utf-8")
    result = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
    calls = [json.loads(line) for line in observed.read_text("utf-8").splitlines()]
    canvas = [call for call in calls if call["canvas"]]
    if source_only:
        assert result.returncode == 0, result.stdout + result.stderr
        assert not canvas
        assert any("app.py" in call["names"] for call in calls)
    else:
        assert result.returncode == 1, result.stdout + result.stderr
        assert canvas
        assert all(name.startswith("docs/design/") or name == "docs/product/BRIEF.md"
                   for name in canvas[0]["names"]), canvas
        assert "2 open findings" in result.stderr
        assert "1 blocks sign-off" in result.stderr
        assert "Blocks sign-off: Missing status" in result.stderr
        assert "Does not block sign-off: Small label" in result.stderr
        for _ in range(2):
            stopped = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
            assert stopped.returncode == 1, stopped.stdout + stopped.stderr
            assert "One more round, split or accept?" in stopped.stderr
            assert "2 open findings" in stopped.stderr
            assert "1 blocks sign-off" in stopped.stderr
            assert "Blocks sign-off: Missing status" in stopped.stderr
            assert "Does not block sign-off: Small label" in stopped.stderr
        assert len(observed.read_text("utf-8").splitlines()) == 2
        queue.write_text(json.dumps([{"report": {"review_status": "scoped-clean", "findings": []}}]), encoding="utf-8")
        accepted = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi",
                              "--resolve", "more", "--reason", "The owner requests the repair", cwd=fix)
        assert accepted.returncode == 0, accepted.stdout + accepted.stderr
        calls = [json.loads(line) for line in observed.read_text("utf-8").splitlines()]
        assert any(not call["canvas"] and "app.py" in call["names"] for call in calls)
