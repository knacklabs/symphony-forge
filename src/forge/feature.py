"""Copy a named feature from the installed starter, then wire its API into the app."""
from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path
from typing import NoReturn

from forge import repo

COMMANDS = [{"words": "task feature", "help": "Build a feature from the starter.",
             "args": [(["plural"], {}), (["--one"], {"required": True}),
                      (["--field"], {"action": "append", "required": True})],
             "run": "build", "changes_state": True, "position": 105,
             "listing": "| `forge task feature <plural> --one <singular> --field '<name>:<kind>'` | Builds a feature from the starter |"}]

STARTER = Path(__file__).parent / "templates/starter"
RESERVED = {"id", "organisationId", "createdAtUtc", "updatedAtUtc", "createdByAccountId",
            "modifiedByAccountId", "deletedAtUtc", "deletedByAccountId", "createdByEmail",
            "modifiedByEmail", "deletedByEmail", "organisation", "createdByAccount",
            "modifiedByAccount", "deletedByAccount", "search", "deleted", "limit",
            "sortBy", "sortOrder", "after", "before"}
KEYWORDS = set("break case catch class const continue debugger default delete do else enum export extends false finally for function if import in instanceof new null return super switch this throw true try typeof var void while with yield let static await implements interface package private protected public".split())


def _camel_name(slug: str) -> str:
    return re.sub(r"-([a-z0-9])", lambda match: match[1].upper(), slug)


def _refuse(message: str, next_step: str = "correct the feature line and run it again.") -> NoReturn:
    raise repo.Refused(message, next_step)


def _fields(values: list[str], root: Path, kinds: dict) -> list[dict]:
    fields = []
    columns = set()
    for value in values:
        match = re.fullmatch(r"([a-z][A-Za-z0-9]*)(\?)?:([a-z-]+)(?:\(([^()]*)\))?", value)
        if not match:
            _refuse(f"The field {value!r} needs a camelCase name and a kind.")
        name, optional, kind, detail = match.groups()
        column = name + "Id" if kind == "link" else name
        if column in RESERVED or name in RESERVED:
            _refuse(f"The field name {name!r} is reserved for the feature.")
        if column in columns:
            _refuse(f"The field name {column!r} occurs twice.")
        if kind not in kinds or kind == "table":
            _refuse(f"The field {name!r} has an unknown kind {kind!r}.")
        if (kind in ("status", "link")) != (detail is not None):
            _refuse(f"The field {name!r} needs {kind}(...) only for a status list or link.")
        options = detail.split("|") if kind == "status" else []
        if kind == "status" and (not all(re.fullmatch(r"[a-z][a-z0-9-]*", option) for option in options)
                                 or len(set(options)) != len(options)):
            _refuse(f"The status field {name!r} needs distinct lower-case options separated by |.")
        if kind == "link":
            if not re.fullmatch(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*", detail):
                _refuse(f"The link field {name!r} needs a feature name.")
            contract = root / f"libs/{detail}/contracts/src/index.ts"
            token = detail.replace("-", "_").upper() + "_API"
            contract_text = contract.read_text(encoding="utf-8") if contract.is_file() else ""
            entry = root / f"apps/api/app/{detail.replace('-', '_')}/__init__.py"
            public_python = contract.is_file() and entry.is_file() and "Service" in entry.read_text(encoding="utf-8")
            if not (public_python if (root / "apps/api/app/main.py").is_file() else
                    token in contract_text and re.search(r"\bget\s*\(", contract_text)):
                _refuse(f"The linked feature {detail!r} is missing its public API.",
                        "build the linked feature first, then run this line again.")
        columns.add(column)
        fields.append({"name": name, "column": column, "kind": kind, "optional": bool(optional),
                       "options": options, "target": detail if kind == "link" else None})
    if not any(field["kind"] == "text" and not field["optional"] for field in fields):
        _refuse("A feature needs a text field that is required for its name.",
                "add --field 'name:text' and run the line again.")
    return fields


def _dump(value: dict) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False) + "\n"


def _insert(text: str, anchor: str, addition: str, path: str) -> str:
    if text.count(anchor) != 1:
        _refuse(f"This feature needs a starter app. The required line is missing in {path}.",
                "build this feature by hand in this app.")
    return text.replace(anchor, anchor + addition, 1)


def _before(text: str, anchor: str, addition: str, path: str) -> str:
    return _insert(text, anchor, "", path).replace(anchor, addition + anchor, 1)


def _link_names(fields: list[dict], root: Path) -> dict[str, dict[str, str]]:
    """For each linked feature: the field that names its items (the first required text in its
    schema) and its required fields' examples, which the browser flows send to make one."""
    names = {}
    for target in sorted({field["target"] for field in fields if field["kind"] == "link"}):
        contract = (root / f"libs/{target}/contracts/src/index.ts").read_text(encoding="utf-8")
        # Query examples (such as sortBy) are not fields accepted by create.
        schema = re.search(r"export const \w+Schema = z\.object\(\{(.*?)^\}\)\.strict\(\);",
                           contract, re.M | re.S)
        contract = schema[1] if schema else ""
        match = re.search(r"^\s+(\w+): z\.string\(\)\.trim\(\)\.min\(1\)", contract, re.M)
        if not match:
            _refuse(f"The linked feature {target!r} has no required text field for its name.",
                    "build the linked feature with this command first, then run this line again.")
        required = re.findall(r"^\s+(\w+): (?!.*\.optional\(\)).*\.meta\(\{ description: .*, example: (.+) \}\),$", contract, re.M)
        names[target] = {"name": match[1], "examples": ", ".join(
            f"{column}: {example}" for column, example in required if column != match[1])}
    return names


def _importer(lock: str, path: str) -> str:
    match = re.search(r"^  " + re.escape(path) + r":(?:[^\n]*\n)(?:(?!  \S|\S).*(?:\n|$))*", lock, re.M)
    if not match:
        _refuse(f"This feature needs a starter app. The importer {path} is missing in pnpm-lock.yaml.",
                "build this feature by hand in this app.")
    return match[0]


def build(args) -> int:
    root = repo.root()
    plural, one = args.plural, args.one
    for name in (plural, one):
        if not re.fullmatch(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*", name):
            _refuse("Feature names need lower-case words separated by hyphens.")
    if one in KEYWORDS:
        _refuse(f"The singular name {one!r} is a reserved TypeScript word.", "choose another singular name.")
    from forge.feature_web import taken_names
    for name in {_camel_name(plural), _camel_name(one)} & taken_names():
        _refuse(f"The name {name!r} is already a name in the feature's screens.", "choose another feature name.")
    if (root / "libs" / plural).exists():
        _refuse(f"The feature folder libs/{plural} already exists.", "choose a new feature name.")
    if (root / "apps/api/app/main.py").is_file():
        return _build_python(args, root)
    # Check what wiring needs before rendering anything. An app may remove its projects feature.
    required = ["apps/api/src/app.module.ts", "apps/api/prisma/schema/base.prisma",
                "apps/api/prisma/schema/auth.prisma", "apps/api/prisma/schema/organisations.prisma",
                "apps/api/prisma/schema/history.prisma", "libs/organisations/server/src/index.ts",
                "libs/history/contracts/src/index.ts", "apps/api/package.json", "apps/api/tsconfig.json",
                "eslint.config.mjs", "pnpm-lock.yaml", "scripts/test-build.mjs",
                "apps/web/src/app.tsx", "apps/web/src/components/app-shell.tsx", "apps/web/package.json"]
    for path in required:
        if not (root / path).is_file():
            _refuse(f"This feature needs a starter app. Missing {path}.",
                    "build this feature by hand in this app.")
    current = {path: (root / path).read_text(encoding="utf-8") for path in required}
    for anchor in ("import { OrganisationsModule } from '@app/organisations-server';", "    OrganisationsModule,"):
        _insert(current[required[0]], anchor, "", required[0])
    model = "".join(word.capitalize() for word in one.split("-"))
    for schema_file in (root / "apps/api/prisma/schema").glob("*.prisma"):
        if re.search(r"^model\s+" + re.escape(model) + r"\s*\{", schema_file.read_text(encoding="utf-8"), re.M):
            _refuse(f"The model {model} already exists in {schema_file.name}.", "choose another singular name.")
    kinds = tomllib.loads((Path(__file__).parent / "templates/feature/kinds.toml").read_text(encoding="utf-8"))
    fields = _fields(args.field, root, kinds["kinds"])
    from forge.feature_api import render_feature_api
    from forge.feature_schema import render_schema
    from forge.feature_web import render_feature_web

    include_mcp = (root / "libs/core/server/src/common/tools.ts").is_file()
    files = render_feature_api(fields, one, plural, kinds, include_mcp=include_mcp)
    files.update(render_schema(plural, one, fields, kinds))
    files.update(render_feature_web(fields, one, plural, kinds, _link_names(fields, root), include_mcp=include_mcp))
    title = "".join(word.capitalize() for word in plural.split("-"))
    names = {"projects": plural, "Projects": title, "PROJECTS": plural.replace("-", "_").upper(),
             "Project": model, "project": one}
    def rename(text: str) -> str:
        return re.sub("projects|Projects|PROJECTS|Project|project", lambda match: names[match[0]], text)
    targets = sorted({field["target"] for field in fields if field["kind"] == "link"})
    for kind in ("contracts", "server", "web"):
        for source in (STARTER / f"libs/projects/{kind}").glob("*.json"):
            value = json.loads(rename(source.read_text(encoding="utf-8")))
            if kind == "server":
                if source.name == "package.json":
                    value["dependencies"].update({f"@app/{target}-contracts": "workspace:*" for target in targets})
                elif source.name == "tsconfig.json":
                    value["references"].extend({"path": f"../../{target}/contracts"} for target in targets)
            files[f"libs/{plural}/{kind}/{source.name}"] = _dump(value)
    app = required[0]
    files[app] = _insert(current[app], "import { OrganisationsModule } from '@app/organisations-server';",
                         f"\nimport {{ {title}Module }} from '@app/{plural}-server';", app)
    files[app] = _insert(files[app], "    OrganisationsModule,", f"\n    {title}Module,", app)
    base = required[1]
    files[base] = _insert(current[base], '"core",', f' "{plural.replace("-", "_")}",', base)
    if '"partialIndexes"' not in files[base]:
        previews = re.search(r'generator\s+client\s*\{[^}]*?\bpreviewFeatures\s*=\s*\[', files[base])
        if previews:
            files[base] = files[base][:previews.end()] + '"partialIndexes", ' + files[base][previews.end():]
        else:
            files[base] = _insert(files[base], 'generator client {', '\n  previewFeatures = ["partialIndexes"]', base)
    for path, model_name in ((required[2], "Account"), (required[3], "Organisation")):
        if model_name == "Account":
            lines = "\n".join(f'  {verb}{title} {model}[] @relation("{model}{relation}By")'
                              for verb, relation in (("created", "Created"), ("modified", "Modified"), ("deleted", "Deleted")))
        else:
            lines = f"  {plural.replace('-', '_')} {model}[]"
        files[path] = _insert(current[path], f"model {model_name} {{", "\n" + lines, path)
    package = "apps/api/package.json"
    data = json.loads(current[package])
    data["dependencies"][f"@app/{plural}-server"] = "workspace:*"
    files[package] = _dump(data)
    tsconfig = "apps/api/tsconfig.json"
    data = json.loads(current[tsconfig])
    data["references"].append({"path": f"../../libs/{plural}/server"})
    files[tsconfig] = _dump(data)
    eslint = "eslint.config.mjs"
    comment = "// Add a scope line here for each new module. Other modules expose only their contracts."
    files[eslint] = _insert(current[eslint], comment,
                            f"\n          {{ sourceTag: 'scope:{plural}', onlyDependOnLibsWithTags: ['scope:{plural}', 'scope:core', 'scope:shared', 'type:contracts'] }},", eslint)
    build_script = "scripts/test-build.mjs"
    files[build_script] = _insert(current[build_script], "'apps/api/dist',",
                                  f" 'libs/{plural}/server/dist', 'libs/{plural}/contracts/dist',", build_script)
    # The starter's schema test lists every table's schema; a new app's copy names this one too.
    database_test = "apps/api/test/database.e2e-spec.ts"
    anchor = "Project: 'projects', ChangeRecord: 'history',"
    if (root / database_test).is_file() and anchor in (text := (root / database_test).read_text(encoding="utf-8")):
        current[database_test] = text
        files[database_test] = text.replace(anchor, anchor + f" {model}: '{plural.replace('-', '_')}',", 1)
    files.update(_wire_web(current, plural, one, model, title))
    lockpath = "pnpm-lock.yaml"
    lock = current[lockpath]
    api_importer = _importer(lock, "apps/api")
    lock = lock.replace(api_importer, api_importer.rstrip() + f"\n      '@app/{plural}-server':\n        specifier: workspace:*\n        version: link:../../libs/{plural}/server\n\n", 1)
    web_importer = _importer(lock, "apps/web")
    lock = lock.replace(web_importer, web_importer.rstrip() + f"\n      '@app/{plural}-web':\n        specifier: workspace:*\n        version: link:../../libs/{plural}/web\n\n", 1)
    shipped_lock = (STARTER / lockpath).read_text(encoding="utf-8")
    additions = []
    for kind in ("contracts", "server", "web"):
        block = rename(_importer(shipped_lock, f"libs/projects/{kind}"))
        if kind == "server":
            block = block.rstrip() + "\n" + "".join(f"      '@app/{target}-contracts':\n        specifier: workspace:*\n        version: link:../../{target}/contracts\n" for target in targets) + "\n"
        additions.append(block)
    files[lockpath] = _insert(lock, "importers:\n", "\n" + "".join(additions), lockpath)
    _write(root, current, files)
    if not include_mcp:
        print(f"This app has no MCP server, so {plural} get no agent tools or resources.")
    return 0


def _wire_web(current, plural, one, model, title):
    files = {}
    words = plural.replace("-", " ")
    plural_title, one_title = words[:1].upper() + words[1:], one.replace("-", " ")[:1].upper() + one.replace("-", " ")[1:]
    route = f"/{plural}"
    web_app = "apps/web/src/app.tsx"
    files[web_app] = _insert(current[web_app], "import { NotFoundPage } from '@/pages/not-found-page';",
                             f"\nimport {{ {model}Crumbs, {model}DetailPage, {title}Page }} from '@app/{plural}-web';", web_app)
    files[web_app] = _insert(files[web_app], "    '/members': 'Members',", f"\n    '{route}': '{plural_title}',", web_app)
    files[web_app] = _insert(files[web_app], ")[location.pathname] ?? (",
                             f"matchPath('{route}/:id', location.pathname) ? '{one_title}' : ", web_app)
    files[web_app] = _before(files[web_app], '      <Route path="/members" element={<MembersPage />}',
                             f'      <Route path="{route}" element={{<{title}Page />}} handle={{{{ permission: \'{plural}.view\' }}}} errorElement={{<RouteErrorPage />}} />\n'
                             f'      <Route path="{route}/:id" element={{<{model}DetailPage />}} handle={{{{ crumbs: <{model}Crumbs />, permission: \'{plural}.view\' }}}} errorElement={{<RouteErrorPage />}} />\n', web_app)
    shell = "apps/web/src/components/app-shell.tsx"
    icon = f"{title}Icon"
    files[shell] = _insert(current[shell], "import type { ComponentProps, ReactNode } from 'react';",
                           f"\nimport {{ Folder as {icon} }} from 'lucide-react';", shell)
    files[shell] = _before(files[shell], "            <SidebarMenuItem>\n              <SidebarMenuButton asChild isActive={pathname === '/members'}",
                           f"            {{useCan('{plural}.view') && (\n              <SidebarMenuItem>\n"
                           f"                <SidebarMenuButton asChild isActive={{pathname === '{route}' || pathname.startsWith('{route}/')}} tooltip=\"{plural_title}\">\n"
                           f"                  <Link to=\"{route}\"><{icon} /><span>{plural_title}</span></Link>\n"
                           f"                </SidebarMenuButton>\n              </SidebarMenuItem>\n            )}}\n", shell)
    files[shell] = _insert(files[shell], "function SearchBox({ account }: { account: Account }) {",
                           f"\n  const canView{title} = useCan('{plural}.view');", shell)
    files[shell] = _before(files[shell], "            <CommandItem onSelect={() => goTo('/members')}>Members</CommandItem>",
                           f"            {{canView{title} && <CommandItem onSelect={{() => goTo('{route}')}}>{plural_title}</CommandItem>}}\n", shell)
    files[shell] = _insert(files[shell], "'/members': 'Members',", f" '{route}': '{plural_title}',", shell)
    web_package = "apps/web/package.json"
    data = json.loads(current[web_package])
    data["dependencies"][f"@app/{plural}-web"] = "workspace:*"
    files[web_package] = _dump(data)
    return files


def _write(root, current, files):
    # Refusals, rendering and anchor checks finish before the first write.
    for path in files:
        if (root / path).exists() and path not in current:
            _refuse(f"The feature file {path} already exists.", "choose a new feature name.")
    for path, text in files.items():
        destination = root / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(text, encoding="utf-8")
        print(f"Wrote {path}")
    return 0


def _build_python(args, root: Path) -> int:
    import keyword

    from forge.feature_python import render_feature_python
    from forge.feature_web import render_feature_web

    plural, one = args.plural, args.one
    module = plural.replace("-", "_")
    model = "".join(word.capitalize() for word in one.split("-"))
    title = "".join(word.capitalize() for word in plural.split("-"))
    required = ["apps/api/app/main.py", "apps/api/app/organisations/__init__.py",
                "apps/api/app/history/__init__.py", "apps/api/app/core/permissions.py",
                "apps/api/migrations/env.py", "apps/api/pyproject.toml",
                "apps/api/tests/test_module_schemas.py",
                "libs/history/contracts/src/index.ts", "apps/web/src/app.tsx",
                "apps/web/src/components/app-shell.tsx", "apps/web/package.json",
                "package.json", "pnpm-lock.yaml"]
    for path in required:
        if not (root / path).is_file():
            _refuse(f"This feature needs a starter app. Missing {path}.",
                    "build this feature by hand in this app.")
    current = {path: (root / path).read_text(encoding="utf-8") for path in required}
    if (root / f"apps/api/app/{module}").exists():
        _refuse(f"The feature folder apps/api/app/{module} already exists.", "choose a new feature name.")
    for source in (root / "apps/api/app").glob("*/models.py"):
        if re.search(r"^class\s+" + re.escape(model) + r"\s*\(", source.read_text(encoding="utf-8"), re.M):
            _refuse(f"The model {model} already exists in {source.parent.name}.", "choose another singular name.")
    kinds = tomllib.loads((Path(__file__).parent / "templates/feature/kinds.toml").read_text(encoding="utf-8"))
    fields = _fields(args.field, root, kinds["kinds"])
    for name in (module, one.replace("-", "_"), *(field["column"] for field in fields)):
        if keyword.iskeyword(name):
            _refuse(f"The name {name!r} is a reserved Python word.", "choose another name and run the line again.")
    include_mcp = (root / "apps/api/app/core/tools.py").is_file()
    files = render_feature_python(fields, one, plural, kinds, root, include_mcp=include_mcp)
    files.update(render_feature_web(
        fields, one, plural, kinds, _link_names(fields, root), include_mcp=include_mcp
    ))
    files.update(_wire_web(current, plural, one, model, title))
    main = "apps/api/app/main.py"
    files[main] = _insert(current[main], "from app.organisations import router as organisations_router",
                          f"\nfrom app.{module} import router as {module}_router", main)
    files[main] = _insert(files[main], "app.include_router(organisations_router)",
                          f"\napp.include_router({module}_router)", main)
    env = "apps/api/migrations/env.py"
    files[env] = _insert(current[env], "import app.organisations",
                         f"\nimport app.{module}  # noqa: F401", env)
    config = "apps/api/pyproject.toml"
    contract = (f'[[tool.importlinter.contracts]]\nname = "{plural} internals"\n'
                f'type = "protected"\nprotected_modules = ["app.{module}.*"]\n'
                f'allowed_importers = ["app.{module}"]\n'
                'broken_contract_guidance = "A module uses another module only through its public service in its __init__.py, never through its internal files."\n\n')
    files[config] = _before(current[config], "[tool.mypy]", contract, config)
    schema_tests = "apps/api/tests/test_module_schemas.py"
    schema_source = current[schema_tests]
    inventory = re.search(r"(?ms)^EXPECTED_TABLE_SCHEMAS = \(\n(.*?)^\)", schema_source)
    if inventory is None:
        _refuse(f"This feature needs a starter app. The expected table inventory is missing in {schema_tests}.",
                "build this feature by hand in this app.")
    table_schemas = set(re.findall(r'^\s*"([^"]+)",\s*$', inventory[1], re.M))
    table_schemas.add(f"{module}.{one.replace('-', '_')}")
    expected = "EXPECTED_TABLE_SCHEMAS = (\n" + "".join(
        f'    "{value}",\n' for value in sorted(table_schemas)
    ) + ")"
    schema_source = schema_source[:inventory.start()] + expected + schema_source[inventory.end():]
    module_schema_filters = re.compile(r"((?:source|target)_schema\.nspname IN \()([^)]*)(\))")

    def include_feature_schema(match: re.Match[str]) -> str:
        schemas = set(re.findall(r"'([^']+)'", match[2]))
        schemas.add(module)
        return match[1] + ", ".join(f"'{value}'" for value in sorted(schemas)) + match[3]

    schema_source, filter_count = module_schema_filters.subn(include_feature_schema, schema_source)
    if filter_count != 2:
        _refuse(f"This feature needs a starter app. The schema ownership check is missing in {schema_tests}.",
                "build this feature by hand in this app.")
    files[schema_tests] = schema_source
    python_starter = Path(__file__).parent / "templates/starter-python"
    for kind in ("contracts", "web"):
        source_root = python_starter if kind == "contracts" else STARTER
        for source in (source_root / f"libs/projects/{kind}").glob("*.json"):
            files[f"libs/{plural}/{kind}/{source.name}"] = source.read_text(encoding="utf-8").replace("projects", plural)
        # Python contracts use OpenAPI types; the shared starter supplies the Nx metadata.
        project = STARTER / f"libs/projects/{kind}/project.json"
        files[f"libs/{plural}/{kind}/project.json"] = project.read_text(encoding="utf-8").replace("projects", plural)
    package = "package.json"
    data = json.loads(current[package])
    anchor = "apps/web/tsconfig.json"
    data["scripts"]["typecheck"] = _before(data["scripts"]["typecheck"], anchor,
        f"libs/{plural}/contracts/tsconfig.json libs/{plural}/web/tsconfig.json ", package)
    files[package] = _dump(data)
    lockpath = "pnpm-lock.yaml"
    lock = current[lockpath]
    importer = _importer(lock, "apps/web")
    lock = lock.replace(importer, importer.rstrip() + f"\n      '@app/{plural}-web':\n        specifier: workspace:*\n        version: link:../../libs/{plural}/web\n\n", 1)
    additions = []
    for kind in ("contracts", "web"):
        source = python_starter if kind == "contracts" else STARTER
        shipped = (source / lockpath).read_text(encoding="utf-8")
        additions.append(_importer(shipped, f"libs/projects/{kind}").replace("projects", plural))
    files[lockpath] = _insert(lock, "importers:\n", "\n" + "".join(additions), lockpath)
    _write(root, current, files)
    if not include_mcp:
        print(f"This app has no MCP server, so {plural} get no agent tools or resources.")
    python_files = sorted("../../" + path for path in files if path.endswith(".py"))
    # Keep F401 enabled so Ruff retains necessary model-import suppressions.
    for command in (("check", "--select", "I,F401,RUF100", "--fix"), ("format",)):
        formatted = repo.run("uv", "run", "ruff", *command, *python_files, cwd=root / "apps/api")
        if formatted.returncode:
            print(formatted.stdout + formatted.stderr, end="")
            _refuse("The feature files were written, but Python formatting failed.",
                    "run uv --directory apps/api run ruff check --select I,F401,RUF100 --fix app migrations tests, "
                    "then uv --directory apps/api run ruff format app migrations tests.")
    return 0
