"""Test audit: command-level image invalidation is not covered by initial canvas
tests. Hashing all app files credibly repeats checks. Fake only the external
review command; no production seam is needed.
"""
import json
import os
import shutil
from pathlib import Path

import pytest

from test_proto_signoff import _adopted_client, _client, _decision
from test_signoff_design import _calls

STORY = "the-screens-check-runs-again-whenever-an"


@pytest.mark.parametrize("adopted", [False, True], ids=["new-client", "earlier-release"])
def test_1_later_screen_checks_only_review_changed_screens_and_open_findings(repo, tmp_path, monkeypatch, adopted):
    fix, answers, queue = (_adopted_client if adopted else _client)(repo, tmp_path, monkeypatch)
    folder = fix / "docs/design/prototype"
    (folder / "other.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"><text>Other</text></svg>', encoding="utf-8")
    repo.git("add", "docs/design/prototype", cwd=fix)
    repo.git("commit", "-qm", "Add another screen", cwd=fix)
    page = _decision(fix, answers)
    helper = Path(os.environ["AUTOREVIEW"])
    original = helper.with_name("original-autoreview")
    shutil.copyfile(helper, original)
    helper.write_text('''import json, os, runpy, subprocess, sys
from pathlib import Path
args = sys.argv[1:]
prompt = Path(args[args.index('--prompt-file') + 1]).read_text('utf-8')
if '# Canvas completeness check' in prompt:
    names = subprocess.check_output(['git', 'ls-files'], text=True).splitlines()
    with Path(os.environ['AUTOREVIEW_STUB']).with_suffix('.screens.jsonl').open('a', encoding='utf-8') as out:
        out.write(json.dumps([n for n in names if n.endswith('.svg')]) + '\\n')
runpy.run_path(__ORIGINAL__, run_name='__main__')
'''.replace('__ORIGINAL__', repr(str(original))), encoding="utf-8")
    if adopted:
        page.write_text(page.read_text("utf-8").replace("status: proposed", "status: accepted") +
                        "\ndesign_checked: old-product-hash\n", encoding="utf-8")

    def accept():
        result = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
        assert result.returncode == 0, result.stdout + result.stderr

    def canvas_calls():
        return [c for c in _calls(queue) if "# Canvas completeness check" in "\n".join(c["prompt_files"].values())]

    accept()
    assert len(canvas_calls()) == 1
    (fix / "app.py").write_text("print('changed app')\n", encoding="utf-8")
    repo.git("add", "app.py", cwd=fix)
    repo.git("commit", "-qm", "Change app code", cwd=fix)
    accept()
    assert len(canvas_calls()) == 1
    image = folder / "order-list.svg"
    image.write_text(image.read_text("utf-8").replace("Orders", "Updated orders"), encoding="utf-8")
    repo.git("add", "docs/design/prototype", cwd=fix)
    repo.git("commit", "-qm", "Change one screen", cwd=fix)
    accept()
    assert len(canvas_calls()) == 2
    prompt = "\n".join(canvas_calls()[-1]["prompt_files"].values())
    assert "Report only" in prompt and "docs/design/prototype/order-list.svg" in prompt
    batches = [json.loads(line) for line in queue.with_suffix('.screens.jsonl').read_text('utf-8').splitlines()]
    assert set(batches[0]) == {"docs/design/prototype/order-list.svg", "docs/design/prototype/other.svg"}
    assert batches[-1] == ["docs/design/prototype/order-list.svg"]
    # A finding can name an unchanged image in its evidence.
    queue.write_text(json.dumps([{"report": {"review_status": "findings", "findings": [{
        "priority": "P0", "title": "Private customer data", "body":
        "Gain 5, Work 1, Harm 5\nother.svg shows private customer data.",
        "code_location": {"file_path": "docs/design/prototype/SCREENS.md", "line": 1}}]}}]), encoding="utf-8")
    image.write_text(image.read_text('utf-8') + '\n', encoding='utf-8')
    repo.git("add", "docs/design/prototype", cwd=fix)
    repo.git("commit", "-qm", "Revise screen", cwd=fix)
    refused = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
    assert refused.returncode == 1 and "Private customer data" in refused.stderr
    queue.write_text(json.dumps([{"report": {"review_status": "scoped-clean", "findings": []}}]), encoding="utf-8")
    accept()
    batches = [json.loads(line) for line in queue.with_suffix('.screens.jsonl').read_text('utf-8').splitlines()]
    assert batches[-1] == ["docs/design/prototype/other.svg"]
    assert "Private customer data" in "\n".join(canvas_calls()[-1]["prompt_files"].values())
    brief = fix / "docs/product/BRIEF.md"
    brief.write_text(brief.read_text('utf-8').replace('## Summary', '## Summary\nUpdated scope.'), encoding='utf-8')
    repo.git("add", "docs/product/BRIEF.md", cwd=fix)
    repo.git("commit", "-qm", "Update brief", cwd=fix)
    accept()
    assert len(canvas_calls()) == 5
