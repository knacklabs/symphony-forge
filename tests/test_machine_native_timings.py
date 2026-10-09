"""Keep successful native Machine timings visible in CI, not only on failure."""
from test_mod_native import run_native_plugin_checks

STORY = "machine-test-speed"


def test_1_native_machine_timings_reach_the_ci_summary(tmp_path, monkeypatch):
    summary = tmp_path / "step-summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", summary.as_posix())
    run_native_plugin_checks(tmp_path)
    timings = summary.read_text(encoding="utf-8")
    for case in (
        "6: terminal Machine shows lanes, local tree facts, gates, log and narrow list",
        "6: terminal Machine load history keeps the last thirty refresh samples and their colours",
    ):
        line = next(line for line in timings.splitlines() if case in line)
        assert "(pass)" in line and "ms]" in line
