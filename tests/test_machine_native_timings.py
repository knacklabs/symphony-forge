"""Keep successful native pane timings visible in CI, not only on failure."""
from test_mod_native import run_native_plugin_checks

STORY = "machine-test-speed"


def test_1_native_machine_timings_reach_the_ci_summary(tmp_path, monkeypatch):
    summary = tmp_path / "step-summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", summary.as_posix())
    run_native_plugin_checks(tmp_path)
    timings = summary.read_text(encoding="utf-8")
    for case in (
        "3: buttons: a row is selected by its title; Open output and Stop run work",
        "2: terminal: the pane keeps its last rows when Forge does not answer, and never shows Loading after content",
    ):
        line = next(line for line in timings.splitlines() if case in line)
        assert "(pass)" in line and "ms]" in line
