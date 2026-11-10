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
NOT_MODULES = {"core", "shared", "demo"}
PYTHON_FILES = ("routes", "service", "tools", "permissions")
# A name never continues into a longer one: clients is not clients-archive.
BEFORE, AFTER = r"(?<![A-Za-z0-9_-])", r"(?![A-Za-z0-9_-])"


def _model_accessors(root: Path, module: str) -> list[str]:
    """The Prisma accessor of each model that holds the feature's schema, in any schema file."""
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
    accessors = [] if python else _model_accessors(root, module)
    # Class (c), the permission names, is a leftover and never a use.
    patterns = {
        "a": [rf"@app/{pl}-(?:contracts|server|web){AFTER}", rf"{BEFORE}libs/{pl}/", rf"{BEFORE}scope:{pl}{AFTER}"],
        "b": [rf"/api/v1/(?:agent-tools/)?{pl}{AFTER}", rf"[\"'`]/{pl}{AFTER}"],
        "c": [rf"{BEFORE}{pl}\.(?:view|create|edit|delete|restore){AFTER}"],
        "e": [rf"{BEFORE}(?:{title}(?:Module|Tools|Api)|{mod.upper()}_API){AFTER}"],
        "g": [rf'(?i)INSERT\s+INTO\s+"?{mod}"?\s*\.'],
        "h": [rf"{BEFORE}{mod}_(?:(?:search|get|create|update|delete|restore){AFTER}|(?=[\"'`]|\$\{{))"],
    }
    if python:
        patterns["d"] = [rf"(?m)^[ \t]*(?:import|from) app\.{mod}{AFTER}", rf"{BEFORE}{mod}_router{AFTER}"]
    if accessors:
        patterns["f"] = [rf"{BEFORE}(?:prisma|tx)\.(?:{'|'.join(accessors)}){AFTER}"]
    compiled = [(kind, re.compile(source)) for kind, sources in patterns.items() for source in sources]
    names = "|".join(PYTHON_FILES)
    in_kept_module = [re.compile(source) for source in (
        rf"app\.{mod}\.(?:{names}){AFTER}", rf"from app\.{mod} import[^\n]*\b(?:{names})\b",
        rf"from \.(?:{names}){AFTER}", rf"from \. import[^\n]*\b(?:{names})\b")]

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
        if rel.startswith(skipped) or rel in gone or rel.startswith(gone[0]) or not path.is_file() \
                or path.stat().st_size > 1_000_000:
            continue
        try:
            text = path.read_text("utf-8")
        except UnicodeDecodeError:
            continue
        lines = text.splitlines()
        restricted = python and rel.startswith(kept)
        found: dict[int, str] = {}
        for kind, pattern in ([("d", p) for p in in_kept_module] if restricted else compiled):
            for match in pattern.finditer(text):
                number = text.count("\n", 0, match.start()) + 1
                if not lines[number - 1].lstrip().startswith(COMMENT):
                    found[number] = found.get(number, "") + kind
        parts = rel.split("/")
        owner = (parts[1] if rel.startswith("libs/") and len(parts) > 2 else
                 parts[3] if rel.startswith("apps/api/app/") and len(parts) > 4 else "")
        for number, kinds in sorted(found.items()):
            if owner and owner not in NOT_MODULES | {plural, module} and kinds.strip("c"):
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
    if python:
        models = root / f"apps/api/app/{module}/models.py"
        if not (models.is_file() and re.search(rf"[\"']{mod}[\"']", models.read_text("utf-8"))):
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
