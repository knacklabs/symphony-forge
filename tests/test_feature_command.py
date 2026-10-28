"""The feature command builds starter API modules from the plan's shell line."""
import ast
import json
import os
import re
import shlex
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest

from test_setup import _fresh_client
from test_starter_tree import _LIVE_RUNS, LIVE, _junit_cases, _run_live_starter
from test_worker import calls, install_claude

ROOT = Path(__file__).resolve().parents[1]
STARTER = ROOT / "src/forge/templates/starter"
PYTHON_STARTER = ROOT / "src/forge/templates/starter-python"
ADOPTED = ROOT / "tests/fixtures/adopted-v1.2.2/client"

CLIENT_LINE = "forge task feature clients --one client --field 'name:text'"
STORY = "FORGE-FEATURE-1"
JOBS_LINE = (
    "forge task feature jobs --one job --field 'name:text' "
    "--field 'description?:long-text' --field 'status:status(planned|active|done)' "
    "--field 'client?:link(clients)' --field 'hoursBudget?:number' "
    "--field 'budget?:money' --field 'dueDate?:date' "
    "--field 'contactEmail?:email' --field 'billable:yes-no'"
)
NOTES_LINE = "forge task feature notes --one note --field 'title:text'"
SALES_ORDERS_LINE = "forge task feature sales-orders --one sales-order --field 'name:text'"
# The first text field is not the one called name, a status is optional and a link is required.
TASKS_LINE = ("forge task feature tasks --one task --field 'code:text' --field 'name:text' "
              "--field 'stage?:status(open|closed)' --field 'job:link(jobs)'")


def _run_line(repo, client: Path, shell: str, line: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PATH"] = str(repo.bin) + os.pathsep + env.get("PATH", "")
    return subprocess.run([shell, "-c", line], cwd=client, env=env, capture_output=True,
                          text=True, encoding="utf-8", timeout=240)


def _written_paths(result: subprocess.CompletedProcess[str], client: Path) -> set[str]:
    paths = {line.removeprefix("Wrote ") for line in result.stdout.splitlines()
             if line.startswith("Wrote ")}
    assert paths, result.stdout
    for rel in paths:
        assert (client / rel).is_file(), rel
    return paths


def _assert_api_output(client: Path, plural: str, one: str, shell_paths: set[str]) -> Path:
    model = "".join(part.capitalize() for part in one.split("-"))
    title = "".join(part.capitalize() for part in plural.split("-"))
    required = {
        f"libs/{plural}/contracts/package.json",
        f"libs/{plural}/contracts/project.json",
        f"libs/{plural}/contracts/tsconfig.json",
        f"libs/{plural}/contracts/src/index.ts",
        f"libs/{plural}/server/package.json",
        f"libs/{plural}/server/project.json",
        f"libs/{plural}/server/tsconfig.json",
        f"libs/{plural}/server/src/index.ts",
        f"libs/{plural}/server/src/{plural}.controller.ts",
        f"libs/{plural}/server/src/{plural}.dto.ts",
        f"libs/{plural}/server/src/{plural}.module.ts",
        f"libs/{plural}/server/src/{plural}.permissions.ts",
        f"libs/{plural}/server/src/{plural}.service.ts",
        f"apps/api/prisma/schema/{plural}.prisma",
        "apps/api/test/" + plural + ".e2e-spec.ts",
        "apps/api/prisma/schema/base.prisma",
        "apps/api/prisma/schema/auth.prisma",
        "apps/api/prisma/schema/organisations.prisma",
        "apps/api/src/app.module.ts",
        "apps/api/package.json",
        "apps/api/tsconfig.json",
        "eslint.config.mjs",
        "pnpm-lock.yaml",
        "scripts/test-build.mjs",
    }
    assert required <= shell_paths
    migration_paths = [rel for rel in shell_paths
                       if re.fullmatch(
                           rf"apps/api/prisma/migrations/\d{{14}}_{re.escape(plural)}/migration.sql",
                           rel)]
    assert len(migration_paths) == 1
    assert all((client / rel).is_file() for rel in required)

    project = json.loads((client / f"libs/{plural}/contracts/project.json").read_text("utf-8"))
    assert project["tags"] == ["type:contracts", f"scope:{plural}"]
    server_project = json.loads((client / f"libs/{plural}/server/project.json").read_text("utf-8"))
    assert server_project["tags"] == ["type:server", f"scope:{plural}"]
    base = (client / "apps/api/prisma/schema/base.prisma").read_text("utf-8")
    assert re.search(r'schemas\s*=\s*\[[^\]]*"' + re.escape(plural) + r'"', base)
    auth = (client / "apps/api/prisma/schema/auth.prisma").read_text("utf-8")
    organisation = (client / "apps/api/prisma/schema/organisations.prisma").read_text("utf-8")
    assert f'created{title} {model}[] @relation("{model}CreatedBy")' in auth
    assert f'modified{title} {model}[] @relation("{model}ModifiedBy")' in auth
    assert f'deleted{title} {model}[] @relation("{model}DeletedBy")' in auth
    assert f'{plural.replace("-", "_")} {model}[]' in organisation
    module = (client / "apps/api/src/app.module.ts").read_text("utf-8")
    assert re.search(rf"import \{{ {title}Module \}} from '@app/{plural}-server';", module)
    assert re.search(rf"\b{title}Module,", module)
    api_package = json.loads((client / "apps/api/package.json").read_text("utf-8"))
    assert f"@app/{plural}-server" in api_package["dependencies"]
    api_tsconfig = json.loads((client / "apps/api/tsconfig.json").read_text("utf-8"))
    assert {"path": f"../../libs/{plural}/server"} in api_tsconfig["references"]
    constraints = (client / "eslint.config.mjs").read_text("utf-8")
    assert re.search(
        rf"sourceTag: 'scope:{plural}', onlyDependOnLibsWithTags: "
        rf"\['scope:{plural}', 'scope:core', 'scope:shared', 'type:contracts'\]",
        constraints,
    )
    lock = (client / "pnpm-lock.yaml").read_text("utf-8")
    assert f"libs/{plural}/contracts:" in lock
    assert f"libs/{plural}/server:" in lock
    build = (client / "scripts/test-build.mjs").read_text("utf-8")
    assert f"libs/{plural}/contracts/dist" in build
    assert f"libs/{plural}/server/dist" in build
    return client / migration_paths[0]


def _assert_python_api_output(
    client: Path, plural: str, one: str, shell_paths: set[str]
) -> Path:
    required = {
        f"apps/api/app/{plural}/__init__.py",
        f"apps/api/app/{plural}/models.py",
        f"apps/api/app/{plural}/schema.py",
        f"apps/api/app/{plural}/service.py",
        f"apps/api/app/{plural}/routes.py",
        f"apps/api/app/{plural}/permissions.py",
        f"apps/api/tests/test_{plural}.py",
        "apps/api/tests/test_module_schemas.py",
        f"libs/{plural}/contracts/package.json",
        f"libs/{plural}/contracts/tsconfig.json",
        f"libs/{plural}/contracts/src/index.ts",
        f"libs/{plural}/web/package.json",
        f"libs/{plural}/web/project.json",
        f"libs/{plural}/web/tsconfig.json",
        f"libs/{plural}/web/src/hooks/{plural}-hooks.ts",
        f"libs/{plural}/web/src/hooks/{plural}-hooks.test.tsx",
        f"libs/{plural}/web/src/pages/{plural}-page.tsx",
        f"apps/web/e2e/{plural}.spec.ts",
        "apps/api/app/main.py",
        "apps/api/migrations/env.py",
        "apps/api/pyproject.toml",
        "apps/web/src/app.tsx",
        "apps/web/src/components/app-shell.tsx",
        "apps/web/package.json",
        "pnpm-lock.yaml",
    }
    assert required <= shell_paths
    migration_paths = [
        rel for rel in shell_paths
        if re.fullmatch(rf"apps/api/migrations/versions/\d{{4}}_{re.escape(plural)}\.py", rel)
    ]
    assert len(migration_paths) == 1
    assert all((client / rel).is_file() for rel in required)
    migration_path = client / migration_paths[0]
    contracts = json.loads((client / f"libs/{plural}/contracts/package.json").read_text("utf-8"))
    assert contracts["dependencies"]["@app/shared-api-types"] == "workspace:*"
    contract_source = (client / f"libs/{plural}/contracts/src/index.ts").read_text("utf-8")
    assert "import type { components } from '@app/shared-api-types'" in contract_source
    assert "z.object(" in contract_source
    schema_test = (client / "apps/api/tests/test_module_schemas.py").read_text("utf-8")
    assert f'"{plural}.{one.replace("-", "_")}"' in schema_test
    filters = [
        re.search(rf"{owner}_schema\.nspname IN \(([^)]*)\)", schema_test)
        for owner in ("source", "target")
    ]
    assert all(filter_match and repr(plural) in filter_match[1] for filter_match in filters)
    revisions = {}
    migration_dir = client / "apps/api/migrations/versions"
    for path in migration_dir.glob("[0-9][0-9][0-9][0-9]_*.py"):
        module = ast.parse(path.read_text("utf-8"), filename=str(path))
        assignments = {}
        for node in module.body:
            if isinstance(node, ast.Assign):
                targets, value = node.targets, node.value
            elif isinstance(node, ast.AnnAssign):
                targets, value = [node.target], node.value
            else:
                continue
            if value is not None:
                for target in targets:
                    if isinstance(target, ast.Name) and target.id in {"revision", "down_revision"}:
                        assignments[target.id] = ast.literal_eval(value)
        revisions[path] = (assignments["revision"], assignments["down_revision"])
    generated_revision, generated_parent = revisions[migration_path]
    prior = {path: (revision, parent) for path, (revision, parent) in revisions.items()
             if path != migration_path}
    prior_revisions = {revision: parent for revision, parent in prior.values()}
    prior_parents = {parent for parent in prior_revisions.values() if parent is not None}
    [current_head] = set(prior_revisions) - prior_parents
    next_number = max(int(path.name[:4]) for path in prior) + 1
    assert int(migration_path.name[:4]) == next_number
    assert generated_revision not in prior_revisions
    assert generated_parent == current_head
    api_module = (client / "apps/api/app/main.py").read_text("utf-8")
    assert f"from app.{plural} import router as {plural}_router" in api_module
    assert f"app.include_router({plural}_router)" in api_module
    environment = (client / "apps/api/migrations/env.py").read_text("utf-8")
    assert f"import app.{plural}" in environment
    pyproject = tomllib.loads((client / "apps/api/pyproject.toml").read_text("utf-8"))
    assert any(
        contract.get("name") == f"{plural} internals"
        for contract in pyproject["tool"]["importlinter"]["contracts"]
    )
    return migration_path


def _adopted_starter(repo) -> Path:
    shutil.copytree(ADOPTED, repo.path, dirs_exist_ok=True)
    shutil.copytree(STARTER, repo.path, dirs_exist_ok=True)
    permissions = repo.path / "libs/projects/server/src/projects.permissions.ts"
    original_permissions = permissions.read_text("utf-8")
    customised_permissions = original_permissions.replace(
        "member: ['view', 'create', 'edit']", "member: []"
    )
    assert customised_permissions != original_permissions
    permissions.write_text(customised_permissions, encoding="utf-8")
    expected_permissions = permissions.read_bytes()
    config = repo.path / "forge.toml"
    version = repo.forge("--version").stdout.split()[-1]
    config.write_text(config.read_text("utf-8").replace('"v1.2.2"', f'"{version}"'),
                      encoding="utf-8")
    repo.git("checkout", "-q", "-b", "fix/feature-command-adopted")
    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stdout + synced.stderr
    assert permissions.read_bytes() == expected_permissions
    return repo.path


def _adopted_python_starter(repo) -> Path:
    shutil.copytree(ADOPTED, repo.path, dirs_exist_ok=True)
    shutil.copytree(STARTER, repo.path, dirs_exist_ok=True)
    shutil.copytree(PYTHON_STARTER, repo.path, dirs_exist_ok=True)
    permissions = repo.path / "apps/api/app/projects/permissions.py"
    original_permissions = permissions.read_text("utf-8")
    customised_permissions = original_permissions.replace(
        '"member": ["view", "create", "edit"]', '"member": []'
    )
    assert customised_permissions != original_permissions
    permissions.write_text(customised_permissions, encoding="utf-8")
    expected_permissions = permissions.read_bytes()
    config = repo.path / "forge.toml"
    version = repo.forge("--version").stdout.split()[-1]
    config.write_text(config.read_text("utf-8").replace('"v1.2.2"', json.dumps(version)),
                      encoding="utf-8")
    repo.git("checkout", "-q", "-b", "fix/feature-command-python-adopted")
    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stdout + synced.stderr
    assert permissions.read_bytes() == expected_permissions
    return repo.path


def _normalized_outputs(outputs: dict[str, bytes]) -> dict[str, bytes]:
    return {
        re.sub(r"migrations/(?:\d{14}|versions/\d{4})_", "migrations/<revision>_", rel): content
        for rel, content in outputs.items()
    }


def _feature_args(plural: str, one: str, fields: list[str]) -> list[str]:
    return ["task", "feature", plural, "--one", one,
            *(argument for field in fields for argument in ("--field", field))]


def _generated_contracts_and_link_tests_parse_and_cursors_encode(repo, gh, tmp_path):
    # Audit: emitted code must parse and its cursor encoder must run. The file/wiring
    # checks do not execute output and missed broken declarations and renamed locals.
    # Node checks the public generated artifacts, with no Forge imports or test seam.
    node = shutil.which("node")
    if not node:
        pytest.skip("Node 24 or later is needed to check generated TypeScript syntax.")
    version = subprocess.run([node, "--version"], capture_output=True, text=True, timeout=30)
    if version.returncode or int(version.stdout.strip().lstrip("v").split(".")[0]) < 24:
        pytest.skip("Node 24 or later is needed to check generated TypeScript syntax.")
    client, initialized = _fresh_client(repo, gh, tmp_path, "--starter", "react")
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    for plural, one, fields in (
        ("clients", "client", ["name:text"]),
        ("jobs", "job", ["name:text", "client:link(clients)"]),
        ("tasks", "task", ["name:text", "status:status(active|planned)",
                             "job:link(jobs)", "project:link(projects)"]),
    ):
        result = repo.forge(*_feature_args(plural, one, fields), cwd=client)
        assert result.returncode == 0, result.stdout + result.stderr
    script = r'''
import { readFileSync } from 'node:fs';
import { stripTypeScriptTypes } from 'node:module';
import { spawnSync } from 'node:child_process';
import assert from 'node:assert/strict';
const failures = [];
for (const plural of ['clients', 'jobs', 'tasks']) {
  for (const path of [`libs/${plural}/contracts/src/index.ts`, `apps/api/test/${plural}.e2e-spec.ts`]) {
    try {
      const source = stripTypeScriptTypes(readFileSync(path, 'utf8'));
      const checked = spawnSync(process.execPath, ['--check', '--input-type=module'], { input: source, encoding: 'utf8' });
      assert.equal(checked.status, 0, checked.stderr);
    } catch (error) { failures.push(`${path}: ${error.message}`); }
  }
  try {
    const service = readFileSync(`libs/${plural}/server/src/${plural}.service.ts`, 'utf8');
    const encoder = service.match(/function encodeCursor\([\s\S]*?\n}/)[0];
    const encode = new Function(`${stripTypeScriptTypes(encoder)}; return encodeCursor;`)();
    const id = '018f0000-0000-7000-8000-000000000001';
    const cursor = encode('name', { id, name: 'First' });
    assert.deepEqual(JSON.parse(Buffer.from(cursor, 'base64url').toString('utf8')), ['name', 'First', id]);
  } catch (error) { failures.push(`${plural} cursor: ${error.message}`); }
}
assert.deepEqual(failures, []);
'''
    checked = subprocess.run([node, "--input-type=module", "-e", script], cwd=client,
                             capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert checked.returncode == 0, checked.stdout + checked.stderr


def feature_live_run(repo, gh, tmp_path_factory) -> dict:
    """Run one new starter app with the item 1 features, a notes feature whose members get no
    permission and a tasks feature with a code before its name, an optional status and a
    required link, once per pytest session; the run cleans
    up before it returns."""
    if "feature" not in _LIVE_RUNS:
        client, initialized = _fresh_client(repo, gh, tmp_path_factory.mktemp("feature-app"),
                                            "--starter", "react")
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr
        for line in (CLIENT_LINE, JOBS_LINE, NOTES_LINE, TASKS_LINE):
            built = repo.forge(*shlex.split(line)[1:], cwd=client)
            assert built.returncode == 0, built.stdout + built.stderr
        permissions = client / "libs/notes/server/src/notes.permissions.ts"
        mapping = permissions.read_text("utf-8")
        assert "member: ['view', 'create', 'edit']" in mapping
        permissions.write_text(mapping.replace("member: ['view', 'create', 'edit']", "member: []"),
                               encoding="utf-8")
        _LIVE_RUNS["feature"] = _run_live_starter(
            tmp_path_factory, ((client, Path(".")),), ("GET /health returned 200",))
    return _LIVE_RUNS["feature"]


def feature_python_client(repo, gh, tmp_path) -> Path:
    """Build the Python API and web features used by generated live tests."""
    if "feature-python-client" not in _LIVE_RUNS:
        client, initialized = _fresh_client(repo, gh, tmp_path, "--starter", "python")
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr
        for line in (CLIENT_LINE, JOBS_LINE, NOTES_LINE, TASKS_LINE, SALES_ORDERS_LINE):
            built = repo.forge(*shlex.split(line)[1:], cwd=client)
            assert built.returncode == 0, built.stdout + built.stderr
        permissions = client / "apps/api/app/notes/permissions.py"
        mapping = permissions.read_text("utf-8")
        allowed = '"member": ["view", "create", "edit"]'
        assert allowed in mapping
        permissions.write_text(mapping.replace(allowed, '"member": []', 1), encoding="utf-8")
        _LIVE_RUNS["feature-python-client"] = client
    return _LIVE_RUNS["feature-python-client"]


def feature_python_live_run(repo, gh, tmp_path_factory) -> dict:
    """Run generated Python API and browser tests against their real app and database."""
    if "feature-python" not in _LIVE_RUNS:
        client = feature_python_client(
            repo, gh, tmp_path_factory.mktemp("feature-python-app")
        )
        _LIVE_RUNS["feature-python"] = _run_live_starter(
            tmp_path_factory, ((client, Path(".")),), ("GET /health returned 200",)
        )
    return _LIVE_RUNS["feature-python"]


def require_feature_cases(cases: list[str], report: str, expected) -> None:
    """Each expected case passed in the named generated test file of the run's report."""
    for name in expected:
        assert any(report.casefold() in case and name.casefold() in case for case in cases), (
            f"no passing case {name!r} in {report}; cases: {cases}")


@pytest.mark.platform
@pytest.mark.timeout(1800)
@pytest.mark.parametrize("starter", ["typescript", "python"])
def test_2_the_new_feature_works_like_projects(repo, gh, tmp_path, tmp_path_factory, starter):
    # Audit: the item 1 lines must give the feature its screens, wiring and tests, and the app's
    # own run must pass them through the real API, database and browser. A missing route,
    # sidebar or search item, a form without a field's control or that shows no field's error and
    # focus, a required link the form cannot fill, a list that forgets its
    # filters on reload, or a detail screen without its recent changes fails the live flows.
    # The existing generated TypeScript feature run and Python projects run do not cover a
    # generated Python feature or a public hyphenated slug crossing API permissions and web
    # access. The app's reports own this behavior, with no test seam.
    starter_name = "react" if starter == "typescript" else "python"
    client, initialized = _fresh_client(repo, gh, tmp_path, "--starter", starter_name)
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    written = set()
    for line in (CLIENT_LINE, JOBS_LINE):
        result = _run_line(repo, client, SHELLS[0], line)
        assert result.returncode == 0, result.stdout + result.stderr
        written |= _written_paths(result, client)
    web_paths = {
        "libs/jobs/web/package.json", "libs/jobs/web/project.json", "libs/jobs/web/tsconfig.json",
        "libs/jobs/web/src/index.ts", "libs/jobs/web/src/hooks/jobs-hooks.ts",
        "libs/jobs/web/src/hooks/jobs-hooks.test.tsx", "libs/jobs/web/src/pages/jobs-page.tsx",
        "libs/jobs/web/src/pages/job-detail-page.tsx", "libs/jobs/web/src/pages/job-form-dialog.tsx",
        "apps/web/e2e/jobs.spec.ts", "apps/web/src/app.tsx", "apps/web/src/components/app-shell.tsx",
        "apps/web/package.json",
    }
    assert web_paths <= written
    web = json.loads((client / "libs/jobs/web/project.json").read_text("utf-8"))
    assert web["tags"] == ["type:web", "scope:jobs"]
    if starter == "python":
        _assert_python_api_output(client, "jobs", "job", written)
    if LIVE:
        live = (feature_live_run(repo, gh, tmp_path_factory) if starter == "typescript"
                else feature_python_live_run(repo, gh, tmp_path_factory))
        if starter == "typescript":
            require_feature_cases(live["api"], "jobs.e2e-spec.ts", (
                "creates, lists, reads, updates, soft-deletes, and restores",
                "pages forward and backward by every sortable field",
                "searches and filters the feature list",
                "keeps another organisation from reading or changing",
                "rejects bad fields, unknown inputs, and unknown list parameters",
                "keeps formula-leading text safe in CSV",
            ))
        else:
            require_feature_cases(live["api"], "test_jobs", (
                "test_creates_lists_reads_updates_and_deletes_a_job",
                "test_rejects_a_whitespace_only_name",
                "test_requires_sign_in_and_csrf_before_jobs_changes",
                "test_pages_jobs_with_next_and_previous_cursors",
                "test_filters_jobs_by_search_and_filters",
                "test_keeps_another_organisation_from_reading_or_changing_a_job",
                "test_rejects_bad_fields_unknown_inputs_and_unknown_list_parameters",
                "test_keeps_formula_leading_text_safe_in_csv",
            ))
            require_feature_cases(live["api"], "test_sales_orders", (
                "test_each_sales_orders_endpoint_refuses_a_member_without_its_permission",
            ))
        require_feature_cases(live["browser"], "jobs.spec.ts", (
            "create, view, edit, and delete a job",
            "a reloaded jobs list link keeps its search, filters and page",
            "a job's detail screen shows its recent changes",
        ))
        if starter == "python":
            require_feature_cases(live["browser"], "sales-orders.spec.ts", (
                "create, view, edit, and delete a sales order",
            ))
        # A required link: the form checks and focuses it, and the flows link each task to a job.
        require_feature_cases(live["browser"], "tasks.spec.ts", ("create, view, edit, and delete a task",))


def _assert_kind_indexes(migration: str, kinds: dict, schema: str, model: str, field: dict) -> None:
    kind = kinds["kinds"][field["kind"]]
    column = field.get("column", field["name"] + ("Id" if field["kind"] == "link" else ""))
    options = ", ".join("'" + option.replace("'", "''") + "'" for option in field.get("options", []))
    for enabled, key in (("filter_index", "filter_index"), ("search_index", "search_index"),
                         ("index", "index")):
        if kind[enabled]:
            expected = kinds["table"][key].replace("{table}", model).replace(
                "{schema}", schema).replace("{column}", column).replace("{options}", options)
            assert expected in migration


@pytest.mark.platform
@pytest.mark.timeout(1800)
@pytest.mark.parametrize("starter", ["typescript", "python"])
def test_4_the_feature_keeps_history_and_its_tests_pass_at_once(
    repo, gh, tmp_path, tmp_path_factory, starter
):
    # Audit: this protects the shipped kind table's storage, input-bound, sort and history
    # contracts plus the real generated history flow. A renderer can omit an index or validation
    # limit, advertise an unusable sort value, or skip a history row; the TypeScript case and the
    # Python projects case do not cover this generated Python feature. The command and live app
    # are the owning boundaries; no seam.
    starter_name = "react" if starter == "typescript" else "python"
    client, initialized = _fresh_client(repo, gh, tmp_path, "--starter", starter_name)
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    clients = repo.forge(*_feature_args("clients", "client", ["name:text"]), cwd=client)
    assert clients.returncode == 0, clients.stdout + clients.stderr
    fields = ["name:text", "description?:long-text", "status:status(planned|active|done)",
              "client?:link(clients)", "hoursBudget?:number", "budget?:money", "dueDate?:date",
              "contactEmail?:email", "billable:yes-no"]
    built = repo.forge(*_feature_args("jobs", "job", fields), cwd=client)
    assert built.returncode == 0, built.stdout + built.stderr

    kinds = tomllib.loads((ROOT / "src/forge/templates/feature/kinds.toml").read_text("utf-8"))
    if starter == "python":
        # Audit: generation must leave both minimal and nine-kind Python output ready for
        # the starter's formatter check. Fixing one template layout misses other field mixes;
        # existing non-live checks only parse output. Use the real pinned formatter after the
        # real feature commands, with no production seam or substitute formatter.
        written = _written_paths(clients, client) | _written_paths(built, client)
        # A module after projects alphabetically makes Ruff's implicit namespace-import
        # usage move to that module. Clients/jobs alone cannot expose lost Alembic imports
        # or an unused starter noqa; the real lint check below owns this regression.
        tasks = repo.forge(*_feature_args("tasks", "task", ["name:text"]), cwd=client)
        assert tasks.returncode == 0, tasks.stdout + tasks.stderr
        written |= _written_paths(tasks, client)
        python_files = sorted("../../" + path for path in written if path.endswith(".py"))
        formatted = subprocess.run(
            ["uv", "run", "ruff", "format", "--check", *python_files],
            cwd=client / "apps/api", capture_output=True, text=True, encoding="utf-8",
            timeout=240,
        )
        assert formatted.returncode == 0, formatted.stdout + formatted.stderr
        linted = subprocess.run(
            ["uv", "run", "ruff", "check", *python_files],
            cwd=client / "apps/api", capture_output=True, text=True, encoding="utf-8",
            timeout=240,
        )
        assert linted.returncode == 0, linted.stdout + linted.stderr
        migration_paths = list((client / "apps/api/migrations/versions").glob("*_jobs.py"))
        assert len(migration_paths) == 1
        migration_path = migration_paths[0]
        migration = migration_path.read_text("utf-8")
        migration_module = ast.parse(migration, filename=str(migration_path))
        upgrade = next(
            node for node in migration_module.body
            if isinstance(node, ast.FunctionDef) and node.name == "upgrade"
        )
        sql_statements = [
            node.args[0].value for node in ast.walk(upgrade)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute) and node.func.attr == "execute"
            and node.args and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ]
        sql = "\n".join(sql_statements)
        models = (client / "apps/api/app/jobs/models.py").read_text("utf-8")
        schema_file = (client / "apps/api/app/jobs/schema.py").read_text("utf-8")
        schema_tree = ast.parse(schema_file)
        input_model = next(
            node for node in schema_tree.body
            if isinstance(node, ast.ClassDef) and node.name == "JobInput"
        )
        input_fields = {
            node.target.id: node
            for node in input_model.body
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
        }
        list_query = next(
            node for node in schema_tree.body
            if isinstance(node, ast.ClassDef) and node.name == "JobListQuery"
        )
        sort_annotation = next(
            node.annotation for node in list_query.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "sort_by"
        )
        assert isinstance(sort_annotation, ast.Subscript)
        assert isinstance(sort_annotation.value, ast.Name)
        assert sort_annotation.value.id == "Literal"
        sort_values = (
            sort_annotation.slice.elts
            if isinstance(sort_annotation.slice, ast.Tuple)
            else [sort_annotation.slice]
        )
        assert [ast.literal_eval(value) for value in sort_values] == [
            "name", "status", "clientId", "hoursBudget", "budget", "dueDate",
            "contactEmail", "billable", "createdAtUtc", "updatedAtUtc",
        ]
        assert sql.lstrip().startswith('CREATE SCHEMA "jobs";')
        assert 'CREATE TABLE "jobs"."job"' in sql
        assert sql.index('CREATE SCHEMA "jobs";') < sql.index('CREATE TABLE "jobs"."job"')
        assert '"organisation_id"' in sql
        assert '"created_by_account_id"' in sql
        assert '"modified_by_account_id"' in sql
        assert '"deleted_at_utc"' in sql
        assert '"deleted_by_account_id"' in sql
        assert '{"schema": "jobs"}' in models
        assert 'ForeignKey("core.organisation.id"' in models
        assert 'ForeignKey("core.account.id"' in models
        assert 'ForeignKey("clients.' not in models

        def table_sql(template_name: str, column: str = "") -> str:
            expected = (kinds["table"][template_name].replace("{table}", "job")
                        .replace("{schema}", "jobs").replace("{column}", column)
                        .replace("{options}", ""))
            for camel, snake in (("organisationId", "organisation_id"),
                                 ("updatedAtUtc", "updated_at_utc"),
                                 ("deletedAtUtc", "deleted_at_utc")):
                expected = expected.replace(camel, snake)
            return expected

        assert table_sql("list_index") in sql
        assert table_sql("updated_at_trigger") in sql
        assert table_sql("soft_delete_trigger") in sql
        assert "CREATE TYPE" not in sql

        declarations = {
            "name": ("text", True, []),
            "description": ("long-text", False, []),
            "status": ("status", True, ["planned", "active", "done"]),
            "client_id": ("link", False, []),
            "hours_budget": ("number", False, []),
            "budget": ("money", False, []),
            "due_date": ("date", False, []),
            "contact_email": ("email", False, []),
            "billable": ("yes-no", True, []),
        }
        for column, (kind_name, required, options) in declarations.items():
            kind = kinds["kinds"][kind_name]
            declaration = next(
                (line for line in sql.splitlines()
                 if re.match(rf'^\s*"{re.escape(column)}"\s+', line)),
                None,
            )
            assert declaration, column
            assert kind["sql"] in declaration, (column, declaration)
            assert ("NOT NULL" in declaration) is required, column
            assert kind["sqlalchemy"].split(", server_default")[0] in models, column
            schema_field = input_fields.get(column)
            assert schema_field, column
            if kind_name == "status":
                literal = schema_field.annotation
                assert isinstance(literal, ast.Subscript)
                assert isinstance(literal.value, ast.Name) and literal.value.id == "Literal"
                assert [ast.literal_eval(option) for option in literal.slice.elts] == options
            else:
                annotation = ast.unparse(schema_field.annotation)
                assert kind["pydantic"] in annotation, (column, annotation)
            if kind_name == "number":
                assert isinstance(schema_field.value, ast.Call)
                assert isinstance(schema_field.value.func, ast.Name)
                assert schema_field.value.func.id == "Field"
                constraints = {
                    keyword.arg: ast.literal_eval(keyword.value)
                    for keyword in schema_field.value.keywords
                    if keyword.arg is not None
                }
                assert constraints["max_digits"] == 19
                assert constraints["decimal_places"] == 4
            if kind_name == "money":
                assert isinstance(schema_field.value, ast.Call)
                assert isinstance(schema_field.value.func, ast.Name)
                assert schema_field.value.func.id == "Field"
                constraints = {
                    keyword.arg: ast.literal_eval(keyword.value)
                    for keyword in schema_field.value.keywords
                    if keyword.arg is not None
                }
                assert constraints["ge"] == -(2**31)
                assert constraints["le"] == 2**31 - 1
            if kind["check"]:
                expected_check = (
                    kind["check"].replace("{table}", "job")
                    .replace("{column}", column)
                    .replace("{options}", ", ".join(f"'{item}'" for item in options))
                )
                assert expected_check in sql, (column, expected_check)
            for enabled, template_name in (("filter_index", "filter_index"),
                                           ("search_index", "search_index"),
                                           ("index", "index")):
                if kind[enabled]:
                    assert table_sql(template_name, column) in sql, (column, enabled)
        assert '"client_id" UUID' in sql
        assert 'idx_job_client_id_link' in sql
        assert 'FOREIGN KEY ("client_id")' not in sql
        assert "REFERENCES clients." not in sql
        assert 'REFERENCES core.organisation("id")' in sql
        assert 'REFERENCES core.account("id")' in sql
        if LIVE:
            live = feature_python_live_run(repo, gh, tmp_path_factory)
            require_feature_cases(live["api"], "test_jobs", (
                "test_records_each_job_change_in_the_change_history",
            ))
            require_feature_cases(
                _junit_cases(live["folder"] / "test-results/formats.xml"),
                "jobs-hooks.test.tsx",
                ("job hooks",),
            )
        return

    migration_paths = list((client / "apps/api/prisma/migrations").glob("*_*jobs/migration.sql"))
    assert len(migration_paths) == 1
    migration = migration_paths[0].read_text("utf-8")
    schema = (client / "apps/api/prisma/schema/jobs.prisma").read_text("utf-8")
    assert migration.startswith('CREATE SCHEMA "jobs";')
    assert 'CREATE TABLE "jobs"."Job"' in migration
    assert '@@schema("jobs")' in schema
    assert "CREATE TYPE" not in migration
    assert '"organisationId"' in migration
    assert 'REFERENCES core."Organisation"' in migration
    assert 'REFERENCES core."Account"' in migration
    for audit in ("createdByAccountId", "modifiedByAccountId", "deletedAtUtc", "deletedByAccountId"):
        assert f'"{audit}"' in migration
    assert (kinds["table"]["list_index"].replace("{table}", "Job")
            .replace("{schema}", "jobs")) in migration
    assert kinds["table"]["updated_at_trigger"].replace("{table}", "Job") in migration
    assert kinds["table"]["soft_delete_trigger"].replace("{table}", "Job") in migration

    declarations = {
        "name": ("text", True, []),
        "description": ("long-text", False, []),
        "status": ("status", True, ["planned", "active", "done"]),
        "clientId": ("link", False, []),
        "hoursBudget": ("number", False, []),
        "budget": ("money", False, []),
        "dueDate": ("date", False, []),
        "contactEmail": ("email", False, []),
        "billable": ("yes-no", True, []),
    }
    for column, (kind_name, required, options) in declarations.items():
        kind = kinds["kinds"][kind_name]
        declaration = re.search(rf'^\s*"{re.escape(column)}" (.+),$', migration, re.M)
        assert declaration and declaration[1].startswith(kind["sql"]), column
        assert ("NOT NULL" in declaration[1]) is required, column
        if kind["check"]:
            expected = (kind["check"].replace("{table}", "Job").replace("{column}", column)
                        .replace("{options}", ", ".join(f"'{item}'" for item in options)))
            assert expected in migration
        _assert_kind_indexes(migration, kinds, "jobs", "Job", {
            "name": column, "column": column, "kind": kind_name, "options": options,
        })
    assert '"clientId"' in migration
    assert 'CREATE INDEX "idx_Job_clientId_link" ON "jobs"."Job" ("clientId");' in migration
    assert 'FOREIGN KEY ("clientId")' not in migration
    assert "REFERENCES clients." not in migration

    contract = (client / "libs/jobs/contracts/src/index.ts").read_text("utf-8")
    assert "export interface JobsApi" in contract and "export const JOBS_API" in contract
    service = (client / "libs/jobs/server/src/jobs.service.ts").read_text("utf-8")
    assert "@Inject(CLIENTS_API)" in service
    assert ".get(" in service
    server_package = json.loads((client / "libs/jobs/server/package.json").read_text("utf-8"))
    assert server_package["dependencies"]["@app/clients-contracts"] == "workspace:*"
    server_tsconfig = json.loads((client / "libs/jobs/server/tsconfig.json").read_text("utf-8"))
    assert {"path": "../../clients/contracts"} in server_tsconfig["references"]
    api_test = (client / "apps/api/test/jobs.e2e-spec.ts").read_text("utf-8")
    assert "records each job change in the change history" in api_test
    for kind, scope in (("contracts", "type:contracts"), ("server", "type:server")):
        project = json.loads((client / f"libs/jobs/{kind}/project.json").read_text("utf-8"))
        assert project["tags"] == [scope, "scope:jobs"]
    assert "sourceTag: 'scope:jobs'" in (client / "eslint.config.mjs").read_text("utf-8")
    if LIVE:
        live = feature_live_run(repo, gh, tmp_path_factory)
        for plural, one in (("clients", "client"), ("jobs", "job"), ("notes", "note")):
            require_feature_cases(live["api"], f"{plural}.e2e-spec.ts",
                                  (f"records each {one} change in the change history",))
            require_feature_cases(_junit_cases(live["folder"] / "test-results/formats.xml"),
                                  f"{plural}-hooks.test.tsx", (f"{one} hooks",))


@pytest.mark.platform
@pytest.mark.parametrize("case", ["plain init", "earlier-adopted", "typescript", "python"],
                         ids=["plain-init", "adopted-v1.2.2", "typescript", "python"])
def test_6_unsupported_apps_refuse_without_changing_the_worktree(repo, gh, tmp_path, case):
    """Non-starters and incomplete older starters get actionable, side-effect-free refusals.

    The command must leave both unsupported app types unchanged. New-init and earlier-adopted
    apps prove the no-starter refusal; the incomplete starter proves that the missing module is
    named. Neither overlap is covered by the feature behavior tests, and the real CLI needs no seam.
    """
    if case in {"plain init", "earlier-adopted"}:
        adopted = case == "earlier-adopted"
        if adopted:
            shutil.copytree(ADOPTED, repo.path, dirs_exist_ok=True)
            config = repo.path / "forge.toml"
            version = repo.forge("--version").stdout.split()[-1]
            config.write_text(config.read_text("utf-8").replace('"v1.2.2"', json.dumps(version)),
                              encoding="utf-8")
            repo.git("checkout", "-q", "-b", "fix/feature-command-refusal-adopted")
            synced = repo.forge("sync")
            assert synced.returncode == 0, synced.stdout + synced.stderr
            client = repo.path
        else:
            client, initialized = _fresh_client(repo, gh, tmp_path)
            assert initialized.returncode == 0, initialized.stdout + initialized.stderr

        before = repo.git("status", "--porcelain", cwd=client)
        if not adopted:
            assert before == ""
        refused = repo.forge(*_feature_args("jobs", "job", ["name:text"]), cwd=client)
        message = refused.stdout + refused.stderr
        assert refused.returncode != 0
        assert "needs a starter app" in message.lower(), message
        assert "Next: build this feature by hand in this app." in message, message
        assert repo.git("status", "--porcelain", cwd=client) == before
        return

    starter = case
    # Audit: an older starter must name its missing history prerequisite and leave the worktree
    # unchanged. A Python check that looks only for TypeScript markers could generate a broken
    # feature in an older Python app; the existing case covered only the TypeScript starter.
    # This runs the real command against each starter without a production seam.
    starter_name = "react" if starter == "typescript" else "python"
    client, initialized = _fresh_client(repo, gh, tmp_path, "--starter", starter_name)
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    if starter == "typescript":
        shutil.rmtree(client / "libs/history")
        (client / "apps/api/prisma/schema/history.prisma").unlink()
        missing = "apps/api/prisma/schema/history.prisma"
    else:
        # Inventory wiring has its own prerequisite: missing anchors must refuse before
        # any generated files are written. History-only coverage cannot reach this failure;
        # these cases use the command boundary with no production seam.
        inventory = client / "apps/api/tests/test_module_schemas.py"
        original = inventory.read_text("utf-8")
        for contents, expected in (
            (None, "Missing apps/api/tests/test_module_schemas.py"),
            (original.replace("EXPECTED_TABLE_SCHEMAS =", "OLD_TABLE_SCHEMAS ="),
             "The expected table inventory is missing"),
            (original.replace("target_schema.nspname IN", "target_schema.nspname NOT IN"),
             "The schema ownership check is missing"),
        ):
            if contents is None:
                inventory.unlink()
            else:
                inventory.write_text(contents, "utf-8")
            before = repo.git("status", "--porcelain", cwd=client)
            refused = repo.forge(*_feature_args("jobs", "job", ["name:text"]), cwd=client)
            message = refused.stdout + refused.stderr
            assert refused.returncode != 0 and expected in message, message
            assert "Next: build this feature by hand in this app." in message, message
            assert repo.git("status", "--porcelain", cwd=client) == before
            inventory.write_text(original, "utf-8")
        # A real formatter configuration error must report that files were already written
        # and give a recovery command. The successful format check cannot cover this lifecycle.
        pyproject = client / "apps/api/pyproject.toml"
        project_source = pyproject.read_text("utf-8")
        pyproject.write_text(project_source.replace('target-version = "py314"',
                                                     'target-version = "invalid"'), "utf-8")
        refused = repo.forge(*_feature_args("invoices", "invoice", ["name:text"]), cwd=client)
        message = refused.stdout + refused.stderr
        assert refused.returncode != 0, message
        assert "The feature files were written, but Python formatting failed." in message
        assert "Next: run uv --directory apps/api run ruff check --select I,F401,RUF100 --fix" in message
        assert "then uv --directory apps/api run ruff format app migrations tests." in message
        assert (client / "apps/api/app/invoices/schema.py").is_file()
        pyproject.write_text(project_source, "utf-8")
        shutil.rmtree(client / "apps/api/app/history")
        missing = "apps/api/app/history/__init__.py"
    before = repo.git("status", "--porcelain", cwd=client)
    refused = repo.forge(*_feature_args("jobs", "job", ["name:text"]), cwd=client)
    message = refused.stdout + refused.stderr
    assert refused.returncode != 0
    assert missing in message, message
    assert "Next: build this feature by hand in this app." in message, message
    assert repo.git("status", "--porcelain", cwd=client) == before


SHELLS = [shutil.which("bash"), *([shutil.which("zsh")] if shutil.which("zsh") else [])]
assert SHELLS[0], "The planner command must run through bash -c."


def _assert_feature_guidance(repo, client: Path, log: Path) -> None:
    # Audit: (1) delivered planner/worker instructions are a prompt contract;
    # (2) omitting them from init/sync or work breaks it; (3) generation checks
    # do not cover prompts, so extend their new/adopted owner test;
    # (4) this uses real commands, with no new production seam or model result.
    for host in (".claude", ".codex"):
        skill = (client / host / "skills/forge/SKILL.md").read_text("utf-8")
        assert CLIENT_LINE in skill
        assert JOBS_LINE in skill.replace("\n", " ")
        assert "When a plan adds a new feature" in skill

    # Publish this fixture's current starter and settings so work's main merge
    # sees the same app. Only the external worker is stubbed, not brief rendering.
    if repo.git("branch", "--show-current", cwd=client) == "main":
        repo.git("switch", "-qc", "fix/feature-guidance", cwd=client)
    config = client / "forge.toml"
    config.write_text(re.sub(r'workers = "[^"]+"', 'workers = "claude"',
                             config.read_text("utf-8")), "utf-8")
    repo.git("add", "-A", cwd=client)
    # Fixture history bypasses branch and default-push gates for these two
    # setup commands only. The real fix start and work below keep their hooks.
    hooks = f"core.hooksPath={(client.parent / 'no-fixture-hooks').as_posix()}"
    repo.git("-c", hooks, "commit", "-q", "-m",
             "Keep the starter and its generated features", cwd=client)
    if repo.git("branch", "--show-current", cwd=client) != "main":
        branch = repo.git("branch", "--show-current", cwd=client)
        repo.git("switch", "main", cwd=client)
        repo.git("merge", "--ff-only", branch, cwd=client)
    repo.git("-c", hooks, "push", "-q", "origin", "main", cwd=client)
    started = repo.forge("fix", "start", "Add a starter feature", "--done",
                         "The new feature works", "--kind", "mechanical", cwd=client)
    assert started.returncode == 0, started.stdout + started.stderr
    previous_calls = len(calls(log))
    built = repo.forge("work", "add-a-starter-feature", cwd=client)
    assert built.returncode == 0, built.stdout + built.stderr
    delivered = calls(log)
    assert len(delivered) == previous_calls + 1
    brief = delivered[-1]["brief"]
    assert "As your first step" in brief
    assert "forge task feature <plural> --one <singular> --field '<field>:<kind>'" in brief
    assert "view, create, edit, delete and restore" in brief
    assert "Members can view, create and edit" in brief
    assert "cannot delete or restore" in brief
    assert "see deleted items" in brief
    assert "Admins have all five" in brief
    assert "keep that mapping in one place" in brief
    assert "every screen and API call" in brief


@pytest.mark.platform
@pytest.mark.parametrize("starter,case", [("typescript", "parser"),
                         *[(starter, shell) for starter in ("typescript", "python")
                           for shell in SHELLS]],
                         ids=["generated-contracts",
                              *[f"{starter}-{Path(shell).name}"
                                for starter in ("typescript", "python") for shell in SHELLS]])
def test_1_feature_contracts_parse_and_plan_lines_build_in_one_step(repo, gh, tmp_path, starter, case):
    # The command line is the contract; each shell preserves it, and generated source parses.
    # Separate tests previously duplicated this criterion and let parser and command cases drift.
    if case == "parser":
        _generated_contracts_and_link_tests_parse_and_cursors_encode(repo, gh, tmp_path)
    else:
        _plan_line_builds_the_feature_in_one_step(repo, gh, tmp_path, case, starter)


def _plan_line_builds_the_feature_in_one_step(repo, gh, tmp_path, shell, starter):
    """The shell lines work in new and adopted starters and report existing output files."""
    starter_name = "react" if starter == "typescript" else "python"
    new_path = tmp_path / "new"
    new_path.mkdir()
    new_client, initialized = _fresh_client(repo, gh, new_path, "--starter", starter_name)
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    if starter == "typescript":
        adopted_client = _adopted_starter(repo)
        log = install_claude(repo)
    else:
        adopted_client = _adopted_python_starter(repo)
        log = None

    outputs = {}
    for label, client in (("new", new_client), ("adopted", adopted_client)):
        outputs[label] = {}
        for plural, one, line in (
            ("clients", "client", CLIENT_LINE),
            ("jobs", "job", JOBS_LINE),
        ):
            result = _run_line(repo, client, shell, line)
            assert result.returncode == 0, result.stdout + result.stderr
            written = _written_paths(result, client)
            migration = (
                _assert_api_output(client, plural, "client" if plural == "clients" else "job", written)
                if starter == "typescript" else _assert_python_api_output(
                    client, plural, one, written
                )
            )
            outputs[label][plural] = {
                rel: (client / rel).read_bytes() for rel in written
            }
            assert migration in [client / rel for rel in written]
        if log is not None:
            _assert_feature_guidance(repo, client, log)

    for plural in ("clients", "jobs"):
        assert _normalized_outputs(outputs["new"][plural]) == _normalized_outputs(
            outputs["adopted"][plural])

    if starter == "python":
        result = _run_line(repo, new_client, shell, SALES_ORDERS_LINE)
        assert result.returncode == 0, result.stdout + result.stderr
        written = _written_paths(result, new_client)
        permissions = ast.parse(
            (new_client / "apps/api/app/sales_orders/permissions.py").read_text("utf-8")
        )
        # The singular permission symbol matches the starter's PROJECT_PERMISSIONS and the
        # generated tools' JOB_PERMISSIONS contract; plural API paths remain unchanged.
        permission_assignment = next(
            node for node in permissions.body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name)
                and target.id == "SALES_ORDER_PERMISSIONS"
                for target in node.targets
            )
        )
        permission_call = permission_assignment.value
        assert isinstance(permission_call, ast.Call)
        assert isinstance(permission_call.func, ast.Name)
        assert permission_call.func.id == "define_permissions"
        assert ast.literal_eval(permission_call.args[0]) == "sales-orders"

        routes_path = new_client / "apps/api/app/sales_orders/routes.py"
        assert routes_path.relative_to(new_client).as_posix() in written
        routes = ast.parse(routes_path.read_text("utf-8"))
        router = next(
            node for node in ast.walk(routes)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "APIRouter"
        )
        assert next(
            ast.literal_eval(keyword.value)
            for keyword in router.keywords
            if keyword.arg == "prefix"
        ) == "/api/v1/sales-orders"
        permission_names = {
            expression.value.id
            for call in ast.walk(routes)
            if isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
            and call.func.id == "require_permission"
            for expression in call.args
            if isinstance(expression, ast.Attribute)
            and isinstance(expression.value, ast.Name)
            and expression.attr in {"view", "create", "edit", "delete", "restore"}
        }
        assert permission_names == {"SALES_ORDER_PERMISSIONS"}

    before = repo.git("status", "--porcelain", cwd=new_client)
    duplicate = _run_line(repo, new_client, shell, JOBS_LINE)
    refusal = duplicate.stdout + duplicate.stderr
    assert duplicate.returncode != 0 and "already exists" in refusal.lower(), refusal
    assert "Next:" in refusal
    assert repo.git("status", "--porcelain", cwd=new_client) == before

    for fields, expected in (
        (["name:text", "Due-date:date"], "camelCase"),
        (["name:text", "due}:date"], "camelCase"),
        (["name:text", "id:text"], "reserved"),
        (["name:text", "deleted:yes-no"], "reserved"),
        (["name:text", "name:text"], "twice"),
        (["name:text", "size:large"], "size"),
        (["name:text", "owner:link(people)"], "people"),
    ):
        before = repo.git("status", "--porcelain", cwd=new_client)
        line = "forge task feature samples --one sample " + " ".join(
            "--field " + shlex.quote(field) for field in fields
        )
        refused = _run_line(repo, new_client, shell, line)
        message = refused.stdout + refused.stderr
        assert refused.returncode != 0 and expected.lower() in message.lower(), message
        assert "Next:" in message
        assert repo.git("status", "--porcelain", cwd=new_client) == before

    if starter == "python":
        before = repo.git("status", "--porcelain", cwd=new_client)
        refused = _run_line(
            repo, new_client, shell,
            "forge task feature samples --one sample --field 'name:text' --field 'lambda:text'",
        )
        message = refused.stdout + refused.stderr
        assert refused.returncode != 0 and "lambda" in message.lower() and "reserved" in message.lower(), message
        assert "Next:" in message
        assert repo.git("status", "--porcelain", cwd=new_client) == before

    for plural, one, expected in (
        ("classrooms", "class", "reserved"),
        ("assignments", "project", "already exists"),
        ("pages", "page", "already a name in the feature's screens"),
    ):
        before = repo.git("status", "--porcelain", cwd=new_client)
        refused = _run_line(
            repo, new_client, shell,
            f"forge task feature {plural} --one {one} --field 'name:text'",
        )
        message = refused.stdout + refused.stderr
        assert refused.returncode != 0 and expected.lower() in message.lower(), message
        assert "Next:" in message
        assert repo.git("status", "--porcelain", cwd=new_client) == before

    before = repo.git("status", "--porcelain", cwd=new_client)
    refused = _run_line(
        repo, new_client, shell,
        "forge task feature samples --one sample --field 'paid:yes-no'",
    )
    message = refused.stdout + refused.stderr
    assert refused.returncode != 0 and "text field" in message.lower(), message
    assert "Next:" in message
    assert repo.git("status", "--porcelain", cwd=new_client) == before
