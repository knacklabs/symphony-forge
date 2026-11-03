"""A fixture change keeps the CI group's passing files out of a retry.

Test audit: This protects retry scope through the real grouped --change picker.
Xdist can rebuild the original group instead of the failed-file selection.
The full-run regression bypasses this nested picker and serial picker cases do
not exercise xdist. Real pytest, split and xdist run here; no production seam.
The existing full-run test retains the earlier-adopted client witness.
"""
import json
import sys
from pathlib import Path

STORY = "tests-copy-seed-repo"


def test_2_grouped_change_run_retries_only_failed_files_after_fixture_change(
        repo, tmp_path, monkeypatch):
    command = (f'"{Path(sys.executable).as_posix()}" -m pytest "client tests" -q '
               '-n 2 --dist loadfile --splits {groups} --group {group}')
    version = repo.forge("--version").stdout.split()[-1]
    repo.write("forge.toml", f'version = "{version}"\nrepo = "forge-source"\n'
               'checks = ["tests"]\nfast_test = "forge test --pytest {base}"\n'
               f'test = {json.dumps(command)}\n')
    repo.write(".gitignore", "__pycache__/\n.pytest_cache/\n")
    for name, tests in {"a": ["pass"], "b": ["failed", "sibling"],
                        "c": ["excluded"], "d": ["excluded_one", "excluded_two"]}.items():
        receipt = tmp_path / (name + ".log")
        source = "from pathlib import Path\n" + f"receipt = Path({json.dumps(receipt.as_posix())})\n"
        for test in tests:
            source += (f"def test_{test}():\n"
                       "    earlier = receipt.exists()\n"
                       "    with receipt.open('a', encoding='utf-8') as log:\n"
                       f"        log.write({json.dumps(test + chr(10))})\n")
            if test == "failed":
                source += "    assert earlier, 'transient failure on the first attempt'\n"
        repo.write(f"client tests/test_{name}.py", source)
    repo.git("add", "-A")
    repo.git("commit", "-qm", "Configure grouped change tests")
    repo.git("push", "-q", "origin", "main")
    repo.git("switch", "-qc", "fixture-copy")
    # Like this fix, changing a shared fixture selects every test in its folder.
    repo.write("client tests/conftest.py", "# Shared fixture setup changed.\n")
    repo.git("add", "-A")
    repo.git("commit", "-qm", "Change shared fixture setup")
    monkeypatch.delenv("PYTEST_ADDOPTS", raising=False)
    monkeypatch.setenv("FORGE_GROUP", "1")
    monkeypatch.setenv("FORGE_GROUPS", "2")

    changed = repo.forge("test", "--change")

    assert changed.returncode == 0, changed.stdout + changed.stderr
    assert (tmp_path / "a.log").read_text("utf-8").splitlines() == ["pass"]
    assert (tmp_path / "b.log").read_text("utf-8").splitlines() == ["failed", "sibling"] * 2
    assert not (tmp_path / "c.log").exists()
    assert not (tmp_path / "d.log").exists()
    assert "Flaky test files:" in changed.stdout
