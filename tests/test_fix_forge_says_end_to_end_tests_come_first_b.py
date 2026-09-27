"""Client test jobs have enough time for browser flows."""
from pathlib import Path

STORY = "FIX-FORGE-SAYS-END-TO-END-TESTS-COME-FIRST-B"
GUIDANCE = Path(__file__).resolve().parents[1] / "src" / "forge"


def guidance(path: str) -> str:
    return " ".join((GUIDANCE / path).read_text(encoding="utf-8").split())


def test_1_sync_gives_package_client_tests_ten_minutes(repo):
    repo.git("checkout", "-q", "-b", "fix/client-browser-tests")
    version = repo.forge("--version").stdout.split()[-1]
    repo.write("forge.toml", f'version = "{version}"\nrepo = "client"\ntest = "npm test"\n')
    repo.write("package.json", '{"scripts":{"test":"playwright test"}}\n')

    result = repo.forge("sync")
    assert result.returncode == 0, result.stderr
    workflow = (repo.path / ".github/workflows/forge.yml").read_text(encoding="utf-8")
    tests_job = workflow.split("\n  tests:\n")[1].split("\n  forge-pr-check:\n")[0]
    assert "    timeout-minutes: 10\n" in tests_job
    assert '- run: "npm test"' in tests_job


def test_2_browser_scope_guidance():
    testing = guidance("templates/conventions/testing.md")
    stack = guidance("templates/conventions/stack.md")
    standards = guidance("standards.md")
    assert "Every user-facing Done-when item gets one Playwright test" in testing
    assert "An item with no UI gets a Supertest test through HTTP" in testing
    assert "Playwright" in stack.split("| Tests |", 1)[1].split("| Workspace |", 1)[0]
    assert "Each user-facing Done-when item gets one Playwright browser test" in standards


def test_3_one_check_starts_app_and_runs_all_tests():
    testing = guidance("templates/conventions/testing.md")
    assert "the one `tests` check" in testing
    assert "playwright install --with-deps chromium" in testing
    assert "compose.test.yml up -d --build --wait && npm test" in testing
    assert "npm run test --workspaces --if-present && playwright test" in testing


def test_4_test_data_comes_through_running_api():
    testing = guidance("templates/conventions/testing.md")
    standards = guidance("standards.md")
    assert "Each test creates what it needs through the running app's API" in testing
    assert "Do not use a shared seed or insert rows directly into the database" in testing
    assert "Client tests create their data through the app's API" in standards


def test_5_flaky_browser_tests_fail_without_retry():
    testing = guidance("templates/conventions/testing.md")
    standards = guidance("standards.md")
    assert "fullyParallel: true" in testing
    assert "retries: 0" in testing
    assert "waiting for real app state" in testing
    assert "Playwright retries are zero" in standards


def test_6_browser_test_time_budget_and_groups():
    testing = guidance("templates/conventions/testing.md")
    assert "10-minute cap" in testing
    assert "split a suite that outgrows it into groups within the same check" in testing


def test_7_changed_old_flows_get_browser_tests():
    testing = guidance("templates/conventions/testing.md")
    standards = guidance("standards.md")
    brief = guidance("templates/brief.md")
    assert "An untouched old flow gets its test when a story first changes it" in testing
    assert "with no backfill" in standards
    assert "including an old flow a story touches for the first time" in brief
