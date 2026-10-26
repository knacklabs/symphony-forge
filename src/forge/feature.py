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
             "run": "build", "changes_state": True}]

STARTER = Path(__file__).parent / "templates/starter"
RESERVED = {"id", "organisationId", "createdAtUtc", "updatedAtUtc", "createdByAccountId",
            "modifiedByAccountId", "deletedAtUtc", "deletedByAccountId", "createdByEmail",
            "modifiedByEmail", "deletedByEmail", "organisation", "createdByAccount",
            "modifiedByAccount", "deletedByAccount", "search", "deleted", "limit",
            "sortBy", "sortOrder", "after", "before"}
KEYWORDS = set("break case catch class const continue debugger default delete do else enum export extends false finally for function if import in instanceof new null return super switch this throw true try typeof var void while with yield let static await implements interface package private protected public".split())


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
            if token not in contract_text or not re.search(r"\bget\s*\(", contract_text):
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
    if (root / "libs" / plural).exists():
        _refuse(f"The feature folder libs/{plural} already exists.", "choose a new feature name.")
    # Check what wiring needs before rendering anything. An app may remove its projects feature.
    required = ["apps/api/src/app.module.ts", "apps/api/prisma/schema/base.prisma",
                "apps/api/prisma/schema/auth.prisma", "apps/api/prisma/schema/organisations.prisma",
                "apps/api/prisma/schema/history.prisma", "libs/organisations/server/src/index.ts",
                "libs/history/contracts/src/index.ts", "apps/api/package.json", "apps/api/tsconfig.json",
                "eslint.config.mjs", "pnpm-lock.yaml", "scripts/test-build.mjs"]
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

    files = render_feature_api(fields, one, plural, kinds)
    files.update(render_schema(plural, one, fields, kinds))
    title = "".join(word.capitalize() for word in plural.split("-"))
    names = {"projects": plural, "Projects": title, "PROJECTS": plural.replace("-", "_").upper(),
             "Project": model, "project": one}
    def rename(text: str) -> str:
        return re.sub("projects|Projects|PROJECTS|Project|project", lambda match: names[match[0]], text)
    targets = sorted({field["target"] for field in fields if field["kind"] == "link"})
    for kind in ("contracts", "server"):
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
    lockpath = "pnpm-lock.yaml"
    lock = current[lockpath]
    api_importer = _importer(lock, "apps/api")
    lock = lock.replace(api_importer, api_importer.rstrip() + f"\n      '@app/{plural}-server':\n        specifier: workspace:*\n        version: link:../../libs/{plural}/server\n\n", 1)
    shipped_lock = (STARTER / lockpath).read_text(encoding="utf-8")
    additions = []
    for kind in ("contracts", "server"):
        block = rename(_importer(shipped_lock, f"libs/projects/{kind}"))
        if kind == "server":
            block = block.rstrip() + "\n" + "".join(f"      '@app/{target}-contracts':\n        specifier: workspace:*\n        version: link:../../{target}/contracts\n" for target in targets) + "\n"
        additions.append(block)
    files[lockpath] = _insert(lock, "importers:\n", "\n" + "".join(additions), lockpath)
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
