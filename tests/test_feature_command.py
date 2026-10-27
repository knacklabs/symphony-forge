"""The feature command builds starter API modules from the plan's shell line."""
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


def _normalized_outputs(outputs: dict[str, bytes]) -> dict[str, bytes]:
    return {
        re.sub(r"migrations/\d{14}_", "migrations/<timestamp>_", rel): content
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


def require_feature_cases(cases: list[str], report: str, expected) -> None:
    """Each expected case passed in the named generated test file of the run's report."""
    for name in expected:
        assert any(report.casefold() in case and name.casefold() in case for case in cases), (
            f"no passing case {name!r} in {report}; cases: {cases}")


@pytest.mark.platform
@pytest.mark.timeout(1800)
@pytest.mark.parametrize("starter", ["typescript"])
def test_2_the_new_feature_works_like_projects(repo, gh, tmp_path, tmp_path_factory, starter):
    # Audit: the item 1 lines must give the feature its screens, wiring and tests, and the app's
    # own run must pass them through the real API, database and browser. A missing route,
    # sidebar or search item, a form without a field's control or that shows no field's error and
    # focus, a required link the form cannot fill, a list that forgets its
    # filters on reload, or a detail screen without its recent changes fails the live flows.
    # The app's reports own the behaviour; this test names the cases.
    client, initialized = _fresh_client(repo, gh, tmp_path, "--starter", "react")
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    written = set()
    for line in (CLIENT_LINE, JOBS_LINE):
        result = _run_line(repo, client, SHELLS[0], line)
        assert result.returncode == 0, result.stdout + result.stderr
        written |= _written_paths(result, client)
    assert {
        "libs/jobs/web/package.json", "libs/jobs/web/project.json", "libs/jobs/web/tsconfig.json",
        "libs/jobs/web/src/index.ts", "libs/jobs/web/src/hooks/jobs-hooks.ts",
        "libs/jobs/web/src/hooks/jobs-hooks.test.tsx", "libs/jobs/web/src/pages/jobs-page.tsx",
        "libs/jobs/web/src/pages/job-detail-page.tsx", "libs/jobs/web/src/pages/job-form-dialog.tsx",
        "apps/web/e2e/jobs.spec.ts", "apps/web/src/app.tsx", "apps/web/src/components/app-shell.tsx",
        "apps/web/package.json",
    } <= written
    web = json.loads((client / "libs/jobs/web/project.json").read_text("utf-8"))
    assert web["tags"] == ["type:web", "scope:jobs"]
    if LIVE:
        live = feature_live_run(repo, gh, tmp_path_factory)
        require_feature_cases(live["api"], "jobs.e2e-spec.ts", (
            "creates, lists, reads, updates, soft-deletes, and restores",
            "pages forward and backward by every sortable field",
            "searches and filters the feature list",
            "keeps another organisation from reading or changing",
            "rejects bad fields, unknown inputs, and unknown list parameters",
            "keeps formula-leading text safe in CSV",
        ))
        require_feature_cases(live["browser"], "jobs.spec.ts", (
            "create, view, edit, and delete a job",
            "a reloaded jobs list link keeps its search, filters and page",
            "a job's detail screen shows its recent changes",
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
def test_4_the_feature_keeps_history_and_its_tests_pass_at_once(repo, gh, tmp_path, tmp_path_factory):
    """The shipped kind table controls generated SQL, indexes and linked API contracts."""
    client, initialized = _fresh_client(repo, gh, tmp_path, "--starter", "react")
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    clients = repo.forge(*_feature_args("clients", "client", ["name:text"]), cwd=client)
    assert clients.returncode == 0, clients.stdout + clients.stderr
    fields = ["name:text", "description?:long-text", "status:status(planned|active|done)",
              "client?:link(clients)", "hoursBudget?:number", "budget?:money", "dueDate?:date",
              "contactEmail?:email", "billable:yes-no"]
    built = repo.forge(*_feature_args("jobs", "job", fields), cwd=client)
    assert built.returncode == 0, built.stdout + built.stderr

    kinds = tomllib.loads((ROOT / "src/forge/templates/feature/kinds.toml").read_text("utf-8"))
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
@pytest.mark.parametrize("case", ["plain init", "earlier-adopted", "older-starter"],
                         ids=["plain-init", "adopted-v1.2.2", "older-starter-missing-history"])
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

    client, initialized = _fresh_client(repo, gh, tmp_path, "--starter", "react")
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    shutil.rmtree(client / "libs/history")
    (client / "apps/api/prisma/schema/history.prisma").unlink()
    before = repo.git("status", "--porcelain", cwd=client)
    refused = repo.forge(*_feature_args("jobs", "job", ["name:text"]), cwd=client)
    message = refused.stdout + refused.stderr
    assert refused.returncode != 0
    assert "apps/api/prisma/schema/history.prisma" in message, message
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
@pytest.mark.parametrize("case", ["parser", *SHELLS],
                         ids=["generated-contracts", *[Path(shell).name for shell in SHELLS]])
def test_1_feature_contracts_parse_and_plan_lines_build_in_one_step(repo, gh, tmp_path, case):
    # The command line is the contract; each shell preserves it, and generated source parses.
    # Separate tests previously duplicated this criterion and let parser and command cases drift.
    if case == "parser":
        _generated_contracts_and_link_tests_parse_and_cursors_encode(repo, gh, tmp_path)
    else:
        _plan_line_builds_the_feature_in_one_step(repo, gh, tmp_path, case)


def _plan_line_builds_the_feature_in_one_step(repo, gh, tmp_path, shell):
    """The shell lines work in new and adopted starters and report existing output files."""
    new_client, initialized = _fresh_client(repo, gh, tmp_path, "--starter", "react")
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    adopted_client = _adopted_starter(repo)
    log = install_claude(repo)

    outputs = {}
    for label, client in (("new", new_client), ("adopted", adopted_client)):
        outputs[label] = {}
        for plural, line in (("clients", CLIENT_LINE), ("jobs", JOBS_LINE)):
            result = _run_line(repo, client, shell, line)
            assert result.returncode == 0, result.stdout + result.stderr
            written = _written_paths(result, client)
            migration = _assert_api_output(client, plural, "client" if plural == "clients" else "job", written)
            outputs[label][plural] = {
                rel: (client / rel).read_bytes() for rel in written
            }
            assert migration in [client / rel for rel in written]
        _assert_feature_guidance(repo, client, log)

    for plural in ("clients", "jobs"):
        assert _normalized_outputs(outputs["new"][plural]) == _normalized_outputs(
            outputs["adopted"][plural])

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
