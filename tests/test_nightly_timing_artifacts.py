"""Scheduled Forge runs retain complete timings instead of shortened console output.

Test-audit gate: the generated Actions configuration is the independent contract.
A missing store option or artifact loses timings; existing budget tests do not cover it.
The real sync command owns this contract and needs no production seam.
"""
from test_testplace_workflow import _jobs

STORY = "FIX-NIGHTLY-TIMING-ARTIFACTS"


def test_1_nightly_groups_save_complete_timing_artifacts(repo):
    repo.git("checkout", "-qb", "fix/nightly-timings")
    version = repo.forge("--version").stdout.split()[-1]
    repo.write("forge.toml", f'version = "{version}"\nrepo = "forge-source"\n'
               'test = "python -m pytest tests -q"\nchecks = ["tests"]\ngroups = 6\n')
    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stdout + synced.stderr
    jobs = _jobs((repo.path / ".github/workflows/forge.yml").read_text(encoding="utf-8"))
    full = jobs["full-suite"]
    assert "github.event_name == 'schedule' && '--durations=0 --store-durations --clean-durations'" in full
    assert "uses: actions/upload-artifact@v4" in full
    assert "if: always() && github.event_name == 'schedule'" in full
    assert "name: linux-test-durations-${{ matrix.group }}" in full
    assert "path: .test_durations" in full
    assert "include-hidden-files: true" in full
    assert "retention-days: 7" in full
    assert "--store-durations" not in jobs["tests"]
    assert "upload-artifact" not in jobs["tests"]
