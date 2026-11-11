"""The removal check reads a client app after the agent removes a feature by hand.

Every case builds features with the build command in a repo and reads files; nothing runs the app.
"""
import json
import os
import re
import shutil
from pathlib import Path

import pytest

from test_feature_command import (
    ADOPTED,
    CLIENT_LINE,
    JOBS_LINE,
    SHELLS,
    _adopted_python_starter,
    _adopted_starter,
    _run_line,
)
from test_setup import _fresh_client

STORY = "FORGE-FEATUREDROP-1"
ALL_CLEAR = "Nothing points at people any more."
ARCHIVE_LINE = "forge task feature people-archive --one person-archive --field 'name:text'"
PEOPLE_LINE = "forge task feature people --one person --field 'name:text'"
CLIENTS_ARCHIVE_LINE = "forge task feature clients-archive --one client-archive --field 'name:text'"
NO_MODEL_TS = ("Forge could not find the data model for people in apps/api/prisma/schema, so it did "
               "not look for database calls by model.")
NO_MODEL_PY = ("Forge could not find the data model for people in apps/api/app/people/models.py, "
               "so it did not check that the database setup can still import it.")


def _is_python(stack: str) -> bool:
    return stack in ("python", "earlier adopted python")


def _app(repo, gh, tmp_path, stack: str) -> Path:
    if stack == "earlier adopted":
        return _adopted_starter(repo)
    if stack == "earlier adopted python":
        return _adopted_python_starter(repo)
    client, initialized = _fresh_client(repo, gh, tmp_path, "--starter",
                                        "python" if stack == "python" else "react")
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    return client


def _build(repo, client: Path, *lines: str) -> None:
    for line in lines:
        built = _run_line(repo, client, SHELLS[0], line)
        assert built.returncode == 0, built.stdout + built.stderr


def _commit(repo, client: Path, message: str) -> str:
    # Fixture history bypasses the branch gates, as the build command's tests do.
    hooks = f"core.hooksPath={(client.parent / 'no-fixture-hooks').as_posix()}"
    repo.git("add", "-A", cwd=client)
    repo.git("-c", hooks, "commit", "-q", "-m", message, cwd=client)
    return repo.git("rev-parse", "HEAD", cwd=client)


def _snapshot(client: Path) -> dict[str, bytes | None]:
    """Every file in the work tree by its bytes (a folder by None), so a change to a file that was
    already modified, a new file and a new empty folder all show."""
    found: dict[str, bytes | None] = {}
    for folder, folders, names in os.walk(client):
        folders[:] = [name for name in folders if name != ".git"]
        for name in folders + [name for name in names if name != ".git"]:
            path = Path(folder, name)
            found[path.relative_to(client).as_posix()] = path.read_bytes() if path.is_file() else None
    return found


def _check(repo, client: Path, plural: str) -> tuple[int, str]:
    # The check is read-only: no file is changed, added or removed, whatever its Git status was.
    before, status = _snapshot(client), repo.git("status", "--porcelain", "--untracked-files=all", cwd=client)
    done = repo.forge("task", "feature-check", plural, cwd=client)
    after = _snapshot(client)
    absent = object()
    changed = sorted(path for path in before.keys() | after.keys()
                     if before.get(path, absent) != after.get(path, absent))
    assert not changed, changed
    assert repo.git("status", "--porcelain", "--untracked-files=all", cwd=client) == status
    return done.returncode, done.stdout + done.stderr


def _listed(output: str) -> set[tuple[str, str]]:
    """The leftover lines as (path, text)."""
    return {(found[1], found[3]) for found in re.finditer(r"^(\S+?):(\d+)  (.*)$", output, re.M)}


def _still_there(output: str) -> set[str]:
    return set(re.findall(r"^(\S+)  still there$", output, re.M))


def _users(output: str) -> str:
    return next((line for line in output.splitlines() if line.startswith("The feature ")), "")


def _edit(client: Path, rel: str, change) -> None:
    path = client / rel
    path.write_text(change(path.read_text("utf-8")), encoding="utf-8")


def _drop_lines(client: Path, rel: str, word: str) -> None:
    _edit(client, rel, lambda text: "".join(
        line for line in text.splitlines(True) if word not in line))


def _drop_importers(client: Path, plural: str) -> None:
    """Remove the feature's importer blocks and the app's dependency lines from the lock file."""
    lines = (client / "pnpm-lock.yaml").read_text("utf-8").splitlines(True)
    kept, i = [], 0
    while i < len(lines):
        if lines[i].startswith(f"  libs/{plural}/"):
            i += 1
            while i < len(lines) and (lines[i].startswith("    ") or not lines[i].strip()):
                i += 1
        elif f"'@app/{plural}-server':" in lines[i]:
            i += 3
        else:
            kept.append(lines[i])
            i += 1
    (client / "pnpm-lock.yaml").write_text("".join(kept), encoding="utf-8")


def _remove_by_hand(client: Path, stack: str, plural: str = "people") -> None:
    """The guide's fixed list for the stack, literally: delete, edit, keep the data layer."""
    module = plural.replace("-", "_")
    shutil.rmtree(client / "libs" / plural)
    _drop_importers(client, plural)
    if _is_python(stack):
        folder = client / f"apps/api/app/{module}"
        for name in ("routes", "service", "tools", "permissions"):
            (folder / f"{name}.py").unlink()
        (client / f"apps/api/tests/test_{module}.py").unlink()
        (folder / "__init__.py").write_text(
            f"from app.{module} import models  # noqa: F401\n", encoding="utf-8")
        _drop_lines(client, "apps/api/app/main.py", f"{module}_router")
        _edit(client, "package.json",
              lambda text: text.replace(f"libs/{plural}/contracts/tsconfig.json ", ""))
        return
    (client / f"apps/api/test/{plural}.e2e-spec.ts").unlink()
    title = "".join(word.capitalize() for word in plural.split("-"))
    _drop_lines(client, "apps/api/src/app.module.ts", f"{title}Module")
    _drop_lines(client, "eslint.config.mjs", f"scope:{plural}'")
    _edit(client, "scripts/test-build.mjs", lambda text: re.sub(
        rf"\s*'libs/{plural}/(?:server|contracts)/dist',", "", text))
    for rel, change in (
        ("apps/api/package.json", lambda data: data["dependencies"].pop(f"@app/{plural}-server")),
        ("apps/api/tsconfig.json", lambda data: data["references"].remove(
            {"path": f"../../libs/{plural}/server"}))):
        data = json.loads((client / rel).read_text("utf-8"))
        change(data)
        (client / rel).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _plant(client: Path, stack: str) -> set[tuple[str, str]]:
    """Leave one line per class in the client's own files, plus lines that must not be listed.
    Returns what the check must list: a line starting with "+" is listed."""
    expected: set[tuple[str, str]] = set()

    def write(rel: str, *lines: str) -> None:
        path = client / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(line.lstrip("+") for line in lines) + "\n", encoding="utf-8")
        expected.update((rel, line.lstrip("+").split("\n")[0].strip())
                        for line in lines if line.startswith("+"))

    write("apps/web/src/links.ts",
          "+import type { Person } from '@app/people-contracts';",
          "+export const tag = 'scope:people';",
          "+export const can = 'people.view';",
          "+export const mod = PeopleModule;",
          '+<Route path="/people" element={<Page />} />',
          "+{ label: 'People', to: '/people' },",
          '+<Route path="people" element={<PeoplePage />} />',
          "+import PeoplePage from './pages/people';",
          "+export const url = `${API_BASE}/people`;",
          "+@Controller('people')",
          "+@Get('people/export')",
          "+providers: [PeopleController],",
          "+providers: [PeopleService],",
          "@Controller('people-archive')",
          "@Get('people-archive')",
          "export const archiveClasses = [PeopleArchiveController, PeopleArchiveService];",
          "// uses /api/v1/people",
          "export const seen = 1; // see /api/v1/people",
          '<Route path="people-archive" element={<PeopleArchivePage />} />',
          "import ArchivePage from './pages/people-archive';",
          "export const archive = '/api/v1/people-archive';",
          "export const archiveTools = '/api/v1/agent-tools/people-archive';",
          "export const archiveTool = 'people_archive_search';",
          "export const archiveModule = PeopleArchiveModule;")
    # A generated file over 1 MB is read like any other.
    big = "apps/web/src/api-types.json"
    (client / big).write_text(" " * 1_100_000 + '\n"/api/v1/people": {}\n', encoding="utf-8")
    expected.add((big, '"/api/v1/people": {}'))
    if _is_python(stack):
        write("apps/api/app/demo/loader.py",
              "def load(session):",
              "+    from app.people import PeopleService",
              '+    session.execute(text("""INSERT INTO\n        people.person (name) VALUES (\'Ada\')"""))',
              "+    session.add(Person(name='Ada'))",
              "+    session.add(PersonModel(name='Ada'))",
              "+    service = PersonService(session)",
              "    session.add(PersonArchive(name='Ada'))",
              "    session.add(PersonArchiveModel(name='Ada'))",
              "    seen = 1  # see /api/v1/people")
        write("apps/api/tests/test_tool_names.py",
              '+assert "people_search" in names',
              '+assert any(n.startswith("people_") for n in names)',
              '+client.get("/api/v1/agent-tools/people")')
        with (client / "apps/api/app/people/__init__.py").open("a", encoding="utf-8") as handle:
            handle.write("from app.people.routes import router\nregister_tools()\n")
        expected.update(("apps/api/app/people/__init__.py", line)
                        for line in ("from app.people.routes import router", "register_tools()"))
    else:
        write("apps/api/src/demo/seed.ts",
              "+await prisma.person.create({ data: { name: 'Ada' } });",
              "+await db.person.create({ data: { name: 'Ada' } });",
              "await db.personArchive.create({ data: { name: 'Ada' } });",
              "+await prisma.$executeRaw`INSERT INTO\n  people.person (name) VALUES ('Ada')`;")
        write("apps/api/test/tool-names.e2e-spec.ts",
              "+expect(names).toContain('people_search');",
              "+const name = `people_${action}`;",
              "+names.filter((n) => n.startsWith('people_'));",
              "+await request(app).get('/api/v1/agent-tools/people');")
    return expected


def _unplant(client: Path, stack: str) -> None:
    for rel in ("apps/web/src/links.ts", "apps/web/src/api-types.json", "apps/api/app/demo/loader.py",
                "apps/api/tests/test_tool_names.py", "apps/api/src/demo/seed.ts",
                "apps/api/test/tool-names.e2e-spec.ts"):
        (client / rel).unlink(missing_ok=True)
    if _is_python(stack):
        (client / "apps/api/app/people/__init__.py").write_text(
            "from app.people import models  # noqa: F401\n", encoding="utf-8")


@pytest.mark.platform
@pytest.mark.timeout(1800)
@pytest.mark.parametrize("case", ["typescript", "python", "earlier adopted", "earlier adopted python",
                                  "plain init", "earlier-adopted"])
def test_1_the_check_lists_what_still_points_at_a_removed_feature(repo, gh, tmp_path, case):
    if case in ("plain init", "earlier-adopted"):
        if case == "earlier-adopted":
            shutil.copytree(ADOPTED, repo.path, dirs_exist_ok=True)
            client = repo.path
        else:
            client, initialized = _fresh_client(repo, gh, tmp_path)
            assert initialized.returncode == 0, initialized.stdout + initialized.stderr
        before = repo.git("status", "--porcelain", cwd=client)
        code, message = _check(repo, client, "people")
        assert code != 0 and "needs a starter app" in message
        assert "neither apps/api/app/main.py nor apps/api/src/app.module.ts" in message
        assert ("Next: search the code for the feature's name, then run the app's own build "
                "and tests.") in message
        assert repo.git("status", "--porcelain", cwd=client) == before
        return
    client = _app(repo, gh, tmp_path, case)
    _build(repo, client, PEOPLE_LINE, ARCHIVE_LINE)
    _commit(repo, client, "Build people and people-archive")

    code, first = _check(repo, client, "people")
    assert code != 0
    here = {"libs/people/", "apps/api/test/people.e2e-spec.ts"}
    if _is_python(case):
        here = {"libs/people/", "apps/api/tests/test_people.py",
                *(f"apps/api/app/people/{name}.py"
                  for name in ("routes", "service", "tools", "permissions"))}
    assert here <= _still_there(first), first
    assert not [path for path in _still_there(first) if "archive" in path]
    # A wiring line is listed before the list is done.
    wiring = "apps/api/app/main.py" if _is_python(case) else "apps/api/src/app.module.ts"
    assert any(path == wiring for path, _ in _listed(first)), first

    before = repo.git("status", "--porcelain", cwd=client)
    for name in ("../apps", "People"):
        code, message = _check(repo, client, name)
        assert code != 0 and "Feature names need lower-case words separated by hyphens." in message
    assert repo.git("status", "--porcelain", cwd=client) == before

    _remove_by_hand(client, case)
    expected = _plant(client, case)
    code, listing = _check(repo, client, "people")
    assert code != 0 and ALL_CLEAR not in listing
    assert _listed(listing) == expected, listing
    assert not _still_there(listing) and not _users(listing)

    _unplant(client, case)
    code, listing = _check(repo, client, "people")
    assert (code, ALL_CLEAR in listing) == (0, True), listing

    # A wiring line left in place after the list is listed too.
    repo.git("checkout", "--", wiring if _is_python(case) else "eslint.config.mjs", cwd=client)
    code, listing = _check(repo, client, "people")
    leftover = {path for path, _ in _listed(listing)}
    assert code != 0 and (wiring if _is_python(case) else "eslint.config.mjs") in leftover, listing


def _no_comments(output: str) -> bool:
    return not [text for _, text in _listed(output)
                if text.startswith(("//", "/*", "*", "#", "{/*", "<!--"))]


@pytest.mark.platform
@pytest.mark.timeout(1800)
@pytest.mark.parametrize("stack", ["typescript", "python", "earlier adopted"])
def test_2_the_check_names_the_features_that_use_the_feature(repo, gh, tmp_path, stack):
    client = _app(repo, gh, tmp_path, stack)
    python = _is_python(stack)
    # In a new starter app the starter's own examples are leftovers, never users, and its comments
    # are not listed. The earlier starter's sign-in pages link to /projects, which is a real use.
    if stack != "earlier adopted":
        code, own = _check(repo, client, "projects")
        assert code != 0 and not _users(own) and _no_comments(own), own
        if stack == "typescript":
            assert any(path.startswith("libs/shared/util") for path, _ in _listed(own)), own
            assert any("projects.view" in text for _, text in _listed(own)), own
        else:
            assert any(path.startswith("apps/api/tests/") for path, _ in _listed(own)), own
        # The starter's tests also read the feature's agent resources by address.
        mcp = "apps/api/tests/test_mcp.py" if python else "apps/api/test/mcp.e2e-spec.ts"
        assert any(path == mcp and "app://projects/fields" in text for path, text in _listed(own)), own

    _build(repo, client, CLIENT_LINE, CLIENTS_ARCHIVE_LINE, JOBS_LINE)
    _commit(repo, client, "Build clients, clients-archive and jobs")
    code, out = _check(repo, client, "clients")
    users = _users(out)
    assert code != 0 and "is used by jobs" in users, out
    assert ("apps/api/app/jobs/service.py" if python else "libs/jobs/server/package.json") in users
    assert "archive" not in users

    if not python:
        # The package line and the project reference each name jobs on their own.
        package = client / "libs/jobs/server/package.json"
        package.write_text(re.sub(r'\n\s*"@app/clients-contracts": "workspace:\*",?', "",
                                  package.read_text("utf-8")), encoding="utf-8")
        assert "libs/jobs/server/tsconfig.json:" in _users(_check(repo, client, "clients")[1])
        # A web call by address counts, even when jobs imports nothing from clients.
        picker = client / "libs/jobs/web/src/clients-picker.tsx"
        picker.parent.mkdir(parents=True)
        picker.write_text("api.get('/clients');\n", encoding="utf-8")
        assert "libs/jobs/web/src/clients-picker.tsx" in _users(_check(repo, client, "clients")[1])

    # A tool name in code is a use; the same words in a comment are not.
    tool = "apps/api/app/jobs/tool_names.py" if python else "libs/jobs/server/src/tool-names.ts"
    (client / tool).write_text(f"x = 'clients_search'\n{'#' if python else '//'} calls /api/v1/clients"
                               " and clients_search\n", encoding="utf-8")
    # Other import and address forms are uses; an inline comment and an example text are not.
    forms = "apps/api/app/jobs/imports.py" if python else "libs/jobs/server/src/forms.ts"
    sample = 'sample = {"example": "/clients"}' if python else "export const sample = { example: '/clients' };"
    # A block comment, a docstring and an example object that start on an earlier line are not uses.
    quiet = (['def docs():', '    """Reads clients.', '', '    See /api/v1/clients for the list.', '    """',
              'many = {', '    "example": {', '        "link": "/clients",', '    },', '}'] if python else
             ['/*', '  Calls /api/v1/clients', '*/', 'export const many = {', '  example: {',
              "    link: '/clients',", '  },', '};'])
    body = (["from app import clients", "from ..clients import ClientService",
             "value = 1  # see /api/v1/clients", sample] if python else
            ["export const base = `${API_BASE}/clients`;", "export const seen = 1; // see /api/v1/clients",
             sample]) + quiet
    (client / forms).write_text("\n".join(body) + "\n", encoding="utf-8")
    # Files outside the module folders are leftovers.
    web = "apps/web/src/jobs-call.ts"
    (client / web).parent.mkdir(parents=True, exist_ok=True)
    (client / web).write_text("api.get('/api/v1/clients');\n", encoding="utf-8")
    if python:
        _edit(client, "libs/shared/api-types/openapi.json", lambda text: text.replace(
            '"paths": {', '"paths": {\n    "/api/v1/clients": {},', 1))
    code, out = _check(repo, client, "clients")
    users = _users(out)
    assert re.search(re.escape(tool) + r":1(?!\d)", users), users
    assert not re.search(re.escape(tool) + r":2(?!\d)", users), users
    for number in ((1, 2) if python else (1,)):
        assert re.search(re.escape(forms) + rf":{number}(?!\d)", users), users
    for number in range(3 if python else 2, len(body) + 1):
        assert not re.search(re.escape(forms) + rf":{number}(?!\d)", users), users
    assert (forms, sample.strip()) in _listed(out)
    assert (forms, '"link": "/clients",' if python else "link: '/clients',") in _listed(out)
    assert not [text for path, text in _listed(out) if path == forms and "/api/v1/clients" in text]
    assert web not in users and (web, "api.get('/api/v1/clients');") in _listed(out)
    if python:
        assert "libs/shared" not in users
        assert ("libs/shared/api-types/openapi.json", '"/api/v1/clients": {},') in _listed(out)

    # Nothing uses jobs, and jobs does not use itself.
    code, out = _check(repo, client, "jobs")
    assert code != 0 and not _users(out), out


@pytest.mark.platform
@pytest.mark.timeout(1800)
@pytest.mark.parametrize("stack", ["typescript", "python", "earlier adopted"])
def test_3_the_check_keeps_the_data_layer_out_of_the_list(repo, gh, tmp_path, stack):
    client = _app(repo, gh, tmp_path, stack)
    python = _is_python(stack)
    _build(repo, client, PEOPLE_LINE, ARCHIVE_LINE)
    before = _commit(repo, client, "Build people and people-archive")
    _remove_by_hand(client, stack)

    def has(rel: str, text: str) -> bool:
        return text in (client / rel).read_text("utf-8")

    if python:
        kept = ["apps/api/app/people/models.py", "apps/api/app/people/__init__.py"]
        assert has("apps/api/migrations/env.py", "import app.people")
        assert has("apps/api/pyproject.toml", "people internals")
        assert has("apps/api/tests/test_module_schemas.py", '"people.person"')
        assert list((client / "apps/api/migrations/versions").glob("*_people.py"))
    else:
        kept = ["apps/api/prisma/schema/people.prisma"]
        assert has("apps/api/prisma/schema/base.prisma", '"people"')
        assert has("apps/api/prisma/schema/auth.prisma", "createdPeople Person[]")
        assert has("apps/api/prisma/schema/organisations.prisma", "people Person[]")
        assert has("apps/api/test/database.e2e-spec.ts", "Person: 'people'")
        assert list((client / "apps/api/prisma/migrations").glob("*_people"))
    assert all((client / rel).is_file() for rel in kept)
    code, out = _check(repo, client, "people")
    assert (code, ALL_CLEAR in out) == (0, True), out
    assert not _listed(out) and not _still_there(out)

    # The removal added and deleted no migration (new files included) and wrote no DROP.
    repo.git("add", "-A", cwd=client)
    changes = [line.split("\t") for line in
               repo.git("diff", "--cached", "--name-status", before, cwd=client).splitlines()]
    assert not [path for status, path in changes
                if "migrations" in path and status[0] in "AD"], changes
    diff = repo.git("diff", "--cached", before, cwd=client)
    assert not [line for line in diff.splitlines() if line.startswith("+") and "DROP" in line]

    # The database tests call the starter's API: a call to the removed feature is listed.
    test_file = "apps/api/tests/test_module_schemas.py" if python else "apps/api/test/database.e2e-spec.ts"
    copy = test_file.replace("schemas.py", "schemas_copy.py") if python else \
        test_file.replace("database.", "database-copy.")
    call = 'client.get("/api/v1/people")' if python else "await request(app).get('/api/v1/people');"
    shutil.copy(client / test_file, client / copy)
    with (client / copy).open("a", encoding="utf-8") as handle:
        handle.write(call + "\n")
    code, out = _check(repo, client, "people")
    assert code != 0 and _listed(out) == {(copy, call)}, out
    (client / copy).unlink()

    if python:
        models = client / "apps/api/app/people/models.py"
        # A file that names the schema but holds no model is not a data model either.
        models.write_text('schema = "people"  # the "people" schema\n', encoding="utf-8")
        code, out = _check(repo, client, "people")
        assert code != 0 and NO_MODEL_PY in out and ALL_CLEAR not in out, out
        models.unlink()
        code, out = _check(repo, client, "people")
        assert code != 0 and NO_MODEL_PY in out and ALL_CLEAR not in out, out
        assert ("Next: keep models.py as the guide says, or tell the person the check could not "
                "confirm it.") in out
        repo.git("checkout", "--", "apps/api/app/people/models.py", cwd=client)
        assert _check(repo, client, "people")[0] == 0
        return
    # The model may sit in another schema file; it is found by its schema line.
    schema = client / "apps/api/prisma/schema"
    (schema / "misc.prisma").write_text((schema / "people.prisma").read_text("utf-8"), encoding="utf-8")
    (schema / "people.prisma").unlink()
    seed = "apps/api/src/demo/seed.ts"
    (client / seed).parent.mkdir(parents=True, exist_ok=True)
    (client / seed).write_text("await prisma.person.create({ data: { name: 'Ada' } });\n", encoding="utf-8")
    code, out = _check(repo, client, "people")
    assert code != 0 and _listed(out) == {(seed, "await prisma.person.create({ data: { name: 'Ada' } });")}, out
    (client / seed).unlink()
    assert _check(repo, client, "people")[0] == 0
    # With no model left, the check never reports all clear.
    (schema / "misc.prisma").unlink()
    code, out = _check(repo, client, "people")
    assert code != 0 and NO_MODEL_TS in out and ALL_CLEAR not in out, out
    assert ("Next: search the code for that model's calls by hand and tell the person the check "
            "could not confirm them.") in out
