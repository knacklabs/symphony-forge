"""Overlapping required check names each count their matching check runs."""

from test_close import CLEAN, env, run  # noqa: F401 (env is the fixture)

STORY = "FIX-IN-SRC-FORGE-CHECKS-PY-A-CHECK-RUN-COUNT"


def test_1_every_required_check_name_matches_its_run_independently(env):
    toml = env.repo.path / "forge.toml"
    env.commit(env.repo.path, "forge.toml", toml.read_text("utf-8").replace(
        'checks = ["tests", "forge-pr-check"]',
        'checks = ["tests", "tests (ubuntu-latest)", "forge-pr-check"]'))
    item, _ = env.start_fix()
    env.reviews(CLEAN)
    env.checks([run("tests"), run("tests (ubuntu-latest)"), run("forge-pr-check")])

    done = env.close(item)

    assert done.returncode == 0, done.stderr
    assert f"Ready: {item} has a clean review and green checks." in done.stdout
