"""Check that a feature removed by hand left nothing behind. It reads text and changes no file."""
from __future__ import annotations

import re
from pathlib import Path

from forge import repo

COMMANDS = [{"words": "task feature-check", "help": "Check that a removed feature left nothing behind.",
             "args": [(["plural"], {})], "run": "check", "changes_state": False, "position": 106,
             "listing": "| `forge task feature-check <plural>` | Checks that a removed feature left nothing behind |"}]

SKIPPED = (".git/", "docs/", "plans/", ".factory/", ".claude/", ".codex/")
COMMENT = ("//", "/*", "*", "#", "{/*", "<!--")
# A comment that ends a code line, a block comment, a Python docstring and an example value are not
# a use of a feature. The block comment and the docstring are blanked out before the scan; an example
# value is found by its key and runs to the end of its bracket or line.
INLINE_COMMENT = re.compile(r"(?:^|\s)(?:#|//|/\*)|<!--")
BLOCK_COMMENT = re.compile(r"(?<![^\s{(,;])/\*.*?\*/|<!--.*?-->", re.S)
DOCSTRING = re.compile(
    r"(?P<head>(?:\A(?:[ \t]*(?:#[^\n]*)?\n)*|:[ \t]*\n(?:[ \t]*\n)*)[ \t]*)"
    r"(?P<doc>[rRuUbB]?(?P<q>\"{3}|'{3}).*?(?P=q))", re.S)
EXAMPLE_KEY = re.compile(r"\bexamples?[\"'\s]*[:=]\s*")
NOT_MODULES = {"core", "shared", "demo"}
# Kinds that are always a leftover and never a use: (c) permission names, (m) Python model names,
# (x) example values.
LEFTOVER_ONLY = {"c", "m", "x"}
PYTHON_FILES = ("routes", "service", "tools", "permissions")
# A name never continues into a longer one: clients is not clients-archive.
BEFORE, AFTER = r"(?<![A-Za-z0-9_-])", r"(?![A-Za-z0-9_-])"


def _blank(text: str) -> str:
    return re.sub(r"[^\n]", " ", text)


def _example_spans(text: str) -> list[tuple[int, int]]:
    """Where each example value sits: a bracketed value to its closing bracket, any other to its line end."""
    spans = []
    for key in EXAMPLE_KEY.finditer(text):
        end, depth = key.end(), 0
        if text[end:end + 1] in ("[", "{", "("):
            for end in range(end, len(text)):
                depth += (text[end] in "[{(") - (text[end] in "]})")
                if depth == 0:
                    break
        else:
            line_end = text.find("\n", end)
            end = len(text) if line_end < 0 else line_end
        spans.append((key.start(), end))
    return spans


def _model_names(root: Path, module: str, python: bool) -> list[str]:
    """The data model names the feature keeps: Python classes in models.py that name the schema, or
    the Prisma accessor of each model that holds the schema, in any schema file."""
    if python:
        path = root / f"apps/api/app/{module}/models.py"
        text = path.read_text("utf-8") if path.is_file() else ""
        named = re.search(rf"[\"']schema[\"']\s*:\s*[\"']{module}[\"']|\bschema\s*=\s*[\"']{module}[\"']", text)
        return re.findall(r"^class (\w+)\(", text, re.M) if named else []
    schema = re.compile(rf'@@schema\(\s*"{module}"\s*\)')
    found = []
    for path in sorted((root / "apps/api/prisma/schema").glob("*.prisma")):
        for name, body in re.findall(r"^model\s+(\w+)\s*\{(.*?)^\}", path.read_text("utf-8"), re.M | re.S):
            if schema.search(body):
                found.append(name[0].lower() + name[1:])
    return found


def check(args) -> int:
    root, plural = repo.root(), args.plural
    if not re.fullmatch(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*", plural):
        raise repo.Refused("Feature names need lower-case words separated by hyphens.",
                           "correct the feature line and run it again.")
    python = (root / "apps/api/app/main.py").is_file()
    if not python and not (root / "apps/api/src/app.module.ts").is_file():
        raise repo.Refused(
            "forge task feature-check needs a starter app (one made with forge init --starter), and "
            "this app has neither apps/api/app/main.py nor apps/api/src/app.module.ts.",
            "search the code for the feature's name, then run the app's own build and tests.")
    module = plural.replace("-", "_")
    title = "".join(word.capitalize() for word in plural.split("-"))
    pl, mod = re.escape(plural), re.escape(module)
    accessors = _model_names(root, module, python)
    quoted = rf"[\"'`]{pl}(?:/[^\"'`\n]*)?[\"'`]"
    patterns = {
        # (a) also finds the project reference ../../<plural>/contracts; (b) also finds a relative route
        # (path="people", @Controller('people'), @Get('people')), a page import (./pages/people),
        # ${BASE}/people and app://people resources.
        "a": [rf"@app/{pl}-(?:contracts|server|web){AFTER}", rf"{BEFORE}libs/{pl}/", rf"{BEFORE}scope:{pl}{AFTER}",
              rf"\.\./{pl}/"],
        "b": [rf"/api/v1/(?:agent-tools/)?{pl}{AFTER}", rf"[\"'`}}]/{pl}{AFTER}", rf"app://{pl}{AFTER}",
              rf"(?:\b(?:path|to|href)\s*[=:]|@(?:Controller|Get|Post|Put|Patch|Delete|All)\()\s*\{{?\s*{quoted}",
              rf"(?:from|import|require\()\s*[\"'`][^\"'`\n]*/{pl}(?:/[^\"'`\n]*)?[\"'`]"],
        "c": [rf"{BEFORE}{pl}\.(?:view|create|edit|delete|restore){AFTER}"],
        "e": [rf"{BEFORE}(?:{title}(?:Module|Tools|Api|Controller|Service)|{mod.upper()}_API){AFTER}"],
        "g": [rf'(?i)INSERT\s+INTO\s+"?{mod}"?\s*\.'],
        "h": [rf"{BEFORE}{mod}_(?:(?:search|get|create|update|delete|restore){AFTER}|(?=[\"'`]|\$\{{))"],
    }
    if python:
        patterns["d"] = [rf"(?m)^[ \t]*(?:import|from) app\.{mod}{AFTER}", rf"{BEFORE}{mod}_router{AFTER}",
                         rf"(?m)^[ \t]*from (?:app|\.\.) import[^\n]*{BEFORE}{mod}{AFTER}",
                         rf"(?m)^[ \t]*from \.\.{mod}{AFTER}"]
    if accessors:  # (f) a Prisma accessor on any client, or (m) a Python model, its alias or service
        models = "|".join(accessors)
        calls = "create|createMany|createManyAndReturn|findMany|findFirst|findFirstOrThrow|findUnique|" \
                "findUniqueOrThrow|update|updateMany|upsert|delete|deleteMany|count|aggregate|groupBy"
        patterns["m" if python else "f"] = (
            [rf"{BEFORE}(?:{models})(?:Model|Service)?\(|[(\[,]\s*(?:{models})(?:Model|Service)?\s*[,)\]]"] if python
            else [rf"{BEFORE}(?:prisma|tx)\.(?:{models}){AFTER}", rf"\.(?:{models})\.(?:{calls}){AFTER}"])
    compiled = [(kind, re.compile(source)) for kind, sources in patterns.items() for source in sources]
    removed = "|".join(PYTHON_FILES)
    in_kept_module = [re.compile(source) for source in (
        rf"app\.{mod}\.(?:{removed}){AFTER}", rf"from app\.{mod} import[^\n]*\b(?:{removed})\b",
        rf"from \.(?:{removed}){AFTER}", rf"from \. import[^\n]*\b(?:{removed})\b",
        rf"{BEFORE}register_tools\s*\(")]

    # What counts as removed: each of these that exists is still there.
    gone = [f"libs/{plural}/"]
    gone += ([f"apps/api/app/{module}/{name}.py" for name in PYTHON_FILES] + [f"apps/api/tests/test_{module}.py"]
             if python else [f"apps/api/test/{plural}.e2e-spec.ts"])
    still = [path for path in gone if (root / path).exists()]
    kept = f"apps/api/app/{module}/" if python else "apps/api/prisma/"
    skipped = SKIPPED + (("apps/api/migrations/",) if python else (kept,))

    listing = repo.run("git", "ls-files", "-co", "--exclude-standard", "-z", cwd=root).stdout.split("\0")
    leftovers: list[tuple[str, int, str]] = []
    users: dict[str, list[str]] = {}
    for rel in sorted(set(listing) - {""}):
        path = root / rel
        if rel.startswith(skipped) or rel in gone or rel.startswith(gone[0]) or not path.is_file():
            continue
        try:
            text = path.read_text("utf-8")
        except UnicodeDecodeError:
            continue
        lines = text.splitlines()
        restricted = python and rel.startswith(kept)
        found: dict[int, str] = {}
        code = BLOCK_COMMENT.sub(lambda match: _blank(match[0]), text)
        if rel.endswith(".py"):
            code = DOCSTRING.sub(lambda match: match["head"] + _blank(match["doc"]), code)
        examples = _example_spans(code)
        for kind, pattern in ([("d", p) for p in in_kept_module] if restricted else compiled):
            if kind == "m" and not rel.endswith(".py"):
                continue
            for match in pattern.finditer(code):
                number = code.count("\n", 0, match.start()) + 1
                before = code[code.rfind("\n", 0, match.start()) + 1:match.start()]
                if lines[number - 1].lstrip().startswith(COMMENT) or INLINE_COMMENT.search(before):
                    continue
                inside = any(start <= match.start() < end for start, end in examples)
                found[number] = found.get(number, "") + ("x" if inside else kind)
        parts = rel.split("/")
        owner = (parts[1] if rel.startswith("libs/") and len(parts) > 2 else
                 parts[3] if rel.startswith("apps/api/app/") and len(parts) > 4 else "")
        for number, kinds in sorted(found.items()):
            if owner and owner not in NOT_MODULES | {plural, module} and set(kinds) - LEFTOVER_ONLY:
                users.setdefault(owner, []).append(f"{rel}:{number}")
            else:
                leftovers.append((rel, number, lines[number - 1].strip()))

    for path in still:
        print(f"{path}  still there")
    if users:
        print(f"The feature {plural} is used by {', '.join(users)} "
              f"({' '.join(place for places in users.values() for place in places)}).")
    for rel, number, text in leftovers:
        print(f"{rel}:{number}  {text}")
    if users:
        print("Next: tell the person which features use it, and ask which feature to change first.")
    elif still or leftovers:
        print(f"Next: change or remove each line above, then run forge task feature-check {plural} again.")
    missing = ""
    if not accessors and python:
        missing = (f"Forge could not find the data model for {plural} in apps/api/app/{module}/models.py, "
                   "so it did not check that the database setup can still import it.\nNext: keep "
                   "models.py as the guide says, or tell the person the check could not confirm it.")
    elif not accessors:
        missing = (f"Forge could not find the data model for {plural} in apps/api/prisma/schema, so it did "
                   "not look for database calls by model.\nNext: search the code for that model's calls by "
                   "hand and tell the person the check could not confirm them.")
    if missing:
        print(missing)
    if still or users or leftovers or missing:
        return 1
    print(f"Nothing points at {plural} any more.")
    return 0
