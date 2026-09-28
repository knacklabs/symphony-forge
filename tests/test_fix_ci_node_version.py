"""Forge sync selects the Node version before a client repo's tests run."""
import json

import pytest

STORY = "FIX-THE-CI-WORKFLOW-FORGE-GENERATES-RUNS-A-N"


@pytest.mark.parametrize("files, expected", [
    ({".nvmrc": "24\n", ".node-version": "22\n",
      "package.json": '{"engines":{"node":"20"}}'}, "node-version-file: .nvmrc"),
    ({".node-version": "24\n", "package.json": '{"engines":{"node":"20"}}'},
     "node-version-file: .node-version"),
    ({"package.json": '{"engines":{"node":">=24"}}'}, 'node-version: ">=24"'),
    ({"package.json": "{}"}, None),
])
def test_1_sync_sets_up_node_before_package_tests(repo, files, expected):
    repo.git("checkout", "-q", "-b", "fix/node-tests")
    repo.write("forge.toml", f'version = "{repo.forge("--version").stdout.split()[-1]}"\ntest = "npm ci && npm test"\nchecks = ["tests", "forge-pr-check"]\n')
    for name, content in files.items():
        repo.write(name, content)
    result = repo.forge("sync")
    assert result.returncode == 0, result.stderr
    workflow = (repo.path / ".github/workflows/forge.yml").read_text(encoding="utf-8")
    tests_job = workflow.split("\n  tests:\n")[1].split("\n  forge-pr-check:\n")[0]
    setup = tests_job.index("- uses: actions/setup-node@v7")
    command = tests_job.index(f"- run: {json.dumps('npm ci && npm test')}")
    assert setup < command
    if expected:
        assert expected in tests_job[setup:command]
    else:
        assert "node-version:" not in tests_job[setup:command]
        assert "node-version-file:" not in tests_job[setup:command]


def test_2_sync_keeps_python_only_tests_job(repo):
    repo.git("checkout", "-q", "-b", "fix/python-tests")
    repo.write("forge.toml", f'version = "{repo.forge("--version").stdout.split()[-1]}"\ntest = "uv run pytest"\nchecks = ["tests", "forge-pr-check"]\n')
    repo.write("pyproject.toml", "[project]\nname = 'example'\n")
    result = repo.forge("sync")
    assert result.returncode == 0, result.stderr
    workflow = (repo.path / ".github/workflows/forge.yml").read_text(encoding="utf-8")
    tests_job = workflow.split("\n  tests:\n")[1].split("\n  forge-pr-check:\n")[0]
    assert "actions/setup-node" not in tests_job
    assert '- run: "uv run pytest"' in tests_job
