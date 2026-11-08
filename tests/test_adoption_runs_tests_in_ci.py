"""Adoption enables CI tests and doctor explains the earlier-adoption repair.

Test-audit: protect generated check settings and the doctor's repair message.
Missing tests in adoption and missing advice for old settings are the regressions.
Existing adoption coverage supplies build/lint checks; it misses review-only input.
Both cases use real Forge commands and existing client fixtures, with no new seam.
"""
import tomllib

from test_close import env  # noqa: F401
from test_live_adopt import _live_app
from test_testplace_upgrade import prepare_adopted_client

STORY = "FIX-ADOPTION-ADDS-TESTS-CHECK"


def test_1_adoption_with_actions_enables_tests(repo, gh):
    _live_app(repo)
    adopted = repo.forge("init", "--actions", "yes", "--test", "npm test",
                         "--checks", "forge-pr-check", "--interfaces", "api/routes/**",
                         "--approver", "Priya", "--merger", "Sam")
    assert adopted.returncode == 0, adopted.stdout + adopted.stderr
    settings = tomllib.loads(repo.git("show", "fix/adopt-forge:forge.toml"))
    assert settings["checks"] == ["forge-pr-check", "tests"]
    workflow = repo.git("show", "fix/adopt-forge:.github/workflows/forge.yml")
    assert "  tests:\n" in workflow
    assert 'forge test --change' in workflow


def test_2_doctor_explains_how_an_earlier_adoption_moves_tests_to_ci(env):
    prepare_adopted_client(env, ["forge-pr-check"])
    path = env.repo.path / "forge.toml"
    before = path.read_bytes()
    warning = ('- Warning: Close runs tests on this machine because checks names only '
               'forge-pr-check, which runs no app tests. Ask the agent to set '
               'checks = ["forge-pr-check", "tests"] in a fix whose Done-when names '
               'forge.toml, then run forge sync.')
    checked = env.repo.forge("doctor")
    assert checked.stdout.count(warning) == 1, checked.stdout + checked.stderr
    assert path.read_bytes() == before
    # An explicit local choice must not prompt a move to CI. Put it before the
    # model tables and require doctor to reach its checks, not reject the fixture.
    env.repo.write("forge.toml", 'test_place = "local"\n' + before.decode("utf-8"))
    checked = env.repo.forge("doctor")
    assert "doctor compared the synced files" in checked.stdout, checked.stdout + checked.stderr
    assert warning not in checked.stdout
