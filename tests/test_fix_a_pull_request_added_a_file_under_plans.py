"""A test that scans a folder tree is picked for a change anywhere inside it."""
import os
import subprocess
import sys
from pathlib import Path

STORY = "FIX-A-PULL-REQUEST-ADDED-A-FILE-UNDER-PLANS"
ROOT = Path(__file__).resolve().parents[1]


def test_1_recursive_scan_is_picked_for_a_deeper_file_and_direct_listing_is_not(repo):
    repo.write("forge.toml", 'test = "python -m pytest checks"\n')
    repo.write("plans/a.md", "a\n")
    repo.write("checks/test_deep.py", "from pathlib import Path\nROOT = Path(__file__).resolve().parents[1]\n"
               "def test_deep():\n    assert list((ROOT / 'plans').rglob('*.md'))\n")
    repo.write("checks/test_shallow.py", "from pathlib import Path\nROOT = Path(__file__).resolve().parents[1]\n"
               "def test_shallow():\n    assert list((ROOT / 'plans').iterdir())\n")
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "Set up")
    base = repo.git("rev-parse", "HEAD").strip()
    repo.write("plans/notes/n.md", "n\n")
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "Add a deeper note")
    environment = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    run = subprocess.run([sys.executable, str(repo.bin / "forge"), "test", "--pytest", base],
                         cwd=repo.path, env=environment, capture_output=True, text=True, timeout=120)
    assert run.returncode == 0, run.stdout + run.stderr
    assert "1 passed" in run.stdout, run.stdout
