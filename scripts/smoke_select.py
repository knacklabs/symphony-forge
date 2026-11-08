"""Select Forge's live smoke jobs. stdout is the GitHub Actions output protocol."""
import argparse
from fnmatch import fnmatchcase
import os
import subprocess

# One home for the full arguments used by --all, nightly and manual runs.
FULL = {
    "starter_smoke": 'tests/test_starter_tree.py tests/test_libs_layout.py tests/test_one_company.py tests/test_defaults_*.py tests/test_database_*.py tests/test_module_schemas.py tests/test_feature_projects.py tests/test_feature_command.py tests/test_feature_access.py tests/test_mcp.py tests/test_agent_ready.py tests/test_request_log.py tests/test_mcp_resources.py tests/test_proxy_error_pages.py tests/test_noscreens_rules.py tests/test_notifications.py tests/test_assistant_*.py -k "not python and not test_2_admins_invite_by_email_and_members_cannot_change_roles_or_invite" -q -x -n 0 --timeout=1800',
    "organisation_invites_smoke": 'tests/test_defaults_organisations.py::test_2_admins_invite_by_email_and_members_cannot_change_roles_or_invite -q -x -n 0 --timeout=3300',
    "member_removal_smoke": 'tests/test_member_removal.py -q -x -n 0 --timeout=1800',
    "python_starter_smoke": 'tests/test_python_starter.py tests/test_libs_layout.py tests/test_database_*.py tests/test_feature_projects.py tests/test_mcp.py tests/test_mcp_resources.py tests/test_noscreens_rules.py tests/test_assistant_*.py -k "python and not test_5_feature_columns_come_from_the_kind_table" -q -n 0 --timeout=1800',
    "python_database_kinds_smoke": "'tests/test_database_kinds.py::test_5_feature_columns_come_from_the_kind_table[python]' -q -n 0 --timeout=1800",
    "python_feature_api_smoke": 'tests/test_feature_command.py -k "python and test_2_the_new_feature_works_like_projects" -q -n 0 --timeout=1800',
    "python_feature_history_smoke": 'tests/test_feature_command.py -k "python and test_4_the_feature_keeps_history_and_its_tests_pass_at_once" -q -n 0 --timeout=1800',
    "python_feature_permissions_smoke": 'tests/test_feature_access.py -k "feature-python and test_3_each_feature_checks_its_permissions" -q -n 0 --timeout=1800',
}
STARTERS = {"starter_smoke", "python_starter_smoke"}
FIXTURES = {"tests/test_starter_tree.py", "tests/test_libs_layout.py"}
FEATURES = STARTERS | {
    "python_database_kinds_smoke",
    "python_feature_api_smoke", "python_feature_history_smoke",
    "python_feature_permissions_smoke",
}
TEXT = {
    "skill.md", "brief.md", "review.md", "review-light.md", "story.md",
    "cold-read.md", "handover.md", "delegation.md", "start.md", "run-reference.md",
    "records-only-action.yml", "review-tests.py",
}
# First matching row wins. Unknown smoke inputs keep the full coverage.
AREAS = [
    *((path, STARTERS, False) for path in sorted(FIXTURES)),
    ("src/forge/templates/skills/agents/assistant-module/**", STARTERS, True),
    *(("src/forge/templates/" + name, set(), False) for name in sorted(TEXT)),
    ("src/forge/templates/design/**", STARTERS, False),
    ("src/forge/feature*.py", FEATURES, False),
    ("src/forge/templates/feature/**", FEATURES, False),
    ("src/forge/templates/starter/**", set(FULL), False),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base", nargs="?")
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()
    all_jobs = args.all or os.environ.get("GITHUB_EVENT_NAME") in {
        "schedule", "workflow_dispatch"}
    if not all_jobs and not args.base:
        parser.error("give the pull request base or --all")
    selected = dict.fromkeys(FULL, False) if all_jobs else {}
    if not all_jobs:
        paths = subprocess.check_output(
            ["git", "diff", "--no-renames", "--name-only", "-z", f"{args.base}...HEAD"],
        ).decode("utf-8").split("\0")
        for path in filter(None, paths):
            # Only smoke inputs affect the area choice. Forge records, plans,
            # docs and regression tests often accompany the template change.
            if not (path.startswith("src/forge/templates/")
                    or fnmatchcase(path, "src/forge/feature*.py")
                    or path in FIXTURES
                    or path in {".github/workflows/starter-smoke.yml", "scripts/smoke_select.py"}):
                continue
            jobs, assistant_only = next(
                ((jobs, assistant) for pattern, jobs, assistant in AREAS
                 if fnmatchcase(path, pattern)), (set(FULL), False))
            for job in jobs:
                selected[job] = selected.get(job, True) and assistant_only
    for job, full in FULL.items():
        arguments = full
        if selected.get(job):
            expression = "python" if job.startswith("python_") else "not python"
            arguments = f'tests/test_assistant_*.py -k "{expression}" -q -n 0 --timeout=1800'
        print(f"{job}={'true' if job in selected else 'false'}")
        print(f"{job}_args={arguments}")


if __name__ == "__main__":
    main()
