"""Shared client templates must trigger both starters' live checks."""
from fnmatch import fnmatchcase
from pathlib import Path
import re

STORY = "FIX-REVIEW-FINDINGS-SPLIT-FROM-SUPPORT-JS-PA"
ROOT = Path(__file__).resolve().parents[1]


def test_1_client_templates_select_starter_proofs():
    # Config contract: every shipped template triggers the existing live workflow.
    # Regression: design scripts bypass both starters' lint jobs. Canvas tests run
    # Node, not starter lint; nightly coverage does not prove PR dispatch. No seam.
    workflow = (ROOT / ".github/workflows/starter-smoke.yml").read_text("utf-8")
    paths = re.search(r"  pull_request:\n    paths:\n(.*?)(?=\n\S)",
                      workflow, re.S)[1]
    patterns = re.findall(r"^      - (.+)$", paths, re.M)
    assert any(fnmatchcase(".github/workflows/starter-smoke.yml", pattern)
               for pattern in patterns)
    templates = ROOT / "src/forge/templates"
    for file in sorted(templates.rglob("*")):
        if file.is_file():
            path = file.relative_to(ROOT).as_posix()
            assert any(fnmatchcase(path, pattern) for pattern in patterns), path
