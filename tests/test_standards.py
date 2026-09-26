"""The standards page, the client stack conventions and the guide: what every worker and reader gets.

Each test is named test_<criterion>_<rule> after the spec's acceptance criterion it proves.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from test_task import story
from test_worker import calls, install_claude

ROOT = Path(__file__).resolve().parents[1]
SPEC = (ROOT / "docs" / "specs" / "lean-forge-v1.md").read_text(encoding="utf-8")
PAGE = (ROOT / "src" / "forge" / "standards.md").read_text(encoding="utf-8")
CONVENTIONS_DIR = ROOT / "src" / "forge" / "templates" / "conventions"
CONVENTIONS = sorted((ROOT / "src" / "forge" / "templates" / "conventions").glob("*.md"))
GUIDE = (ROOT / "docs" / "guide.md").read_text(encoding="utf-8")
ADD_LATER = "add when a story's new moving parts names it"


def _prose(text: str) -> list[str]:
    """The lines outside fenced code blocks: a code example isn't a rule."""
    return re.sub(r"(?ms)^```.*?^```", "", text).splitlines()


def test_36_client_apps_simple(repo, tmp_path):
    # The page stays short and opens with Forge's 13 principles, word for word from the spec, then
    # the 11 client-app principles the spec names, in order.
    assert len(PAGE.splitlines()) <= 320
    forge_principles = re.findall(r"^\d+\. (.+)$", SPEC.split("\n## Principles\n")[1].split("\n## ")[0],
                                  re.M)
    names = re.search(r"client-app principles on the standards page: (.+?)\. They add", SPEC, re.S)[1]
    client_principles = re.split(r",\s+(?:and\s+)?", " ".join(names.split()).lower())
    assert len(forge_principles) == 13 and len(client_principles) == 11
    assert re.findall(r"^## (.*)$", PAGE, re.M)[:2] == ["Forge's 13 principles",
                                                         "The 11 client-app principles"]
    _, forge_part, client_part, *_ = re.split(r"^## .*$", PAGE, flags=re.M)
    assert re.findall(r"^\d+\. (.+)$", forge_part, re.M) == forge_principles
    titles = re.findall(r"^\d+\. \*\*(.+?)\.\*\*", client_part, re.M)
    assert [title.lower() for title in titles] == client_principles

    # No rule asks for an interface per service, microservices, future-growth planning or a split
    # by line count: every line that mentions one limits or forbids it.
    shipped = [line for text in [PAGE, *(p.read_text(encoding="utf-8") for p in CONVENTIONS)]
               for line in _prose(text)]
    for concern in (r"\binterface", r"microservice|future growth", r"\bsplit\b.*\bline"):
        for line in shipped:
            if re.search(concern, line, re.I):
                assert re.search(r"\b(only|no|not|never)\b", line, re.I), line

    # The stack conventions name Redis, queues, Terraform, OIDC and a monitoring stack only as added later.
    later = re.compile(r"\b(redis|queue|terraform|oidc|monitoring)s?\b", re.I)
    named = [line for p in CONVENTIONS for line in p.read_text(encoding="utf-8").splitlines()
             if later.search(line)]
    for line in named:
        assert ADD_LATER in line.lower().replace("`", ""), line
    assert {match.lower() for line in named for match in later.findall(line)} == {
        "redis", "queue", "terraform", "oidc", "monitoring"}

    _carried_over_rules_are_on_their_pages()
    _logger_example_writes_the_documented_fields(tmp_path)

    # Every worker brief, for a task or a fix, carries the whole page.
    log = install_claude(repo)
    repo.write("forge.toml", f'version = "{repo.forge("--version").stdout.split()[-1]}"\n'
                             'models.build = { model = "opus", effort = "high" }\n'
                             'models.lite = { model = "sonnet", effort = "medium" }\n')
    repo.git("add", "forge.toml")
    repo.git("commit", "-q", "-m", "Pin Forge")
    repo.git("push", "-q", "origin", "main")
    story(repo)
    assert repo.forge("task", "start", "BOARD/PAGE").returncode == 0
    fix = repo.forge("fix", "start", "Fix the login typo", "--done", "The login page says Log in")
    assert fix.returncode == 0, fix.stderr
    for item in ("BOARD/PAGE", "fix-the-login-typo"):
        built = repo.forge("work", item)
        assert built.returncode == 0, built.stderr
        assert PAGE.strip() in calls(log)[-1]["brief"], item

    # The guide names every command in the command table, and nothing else.
    table: set[str] = set()
    for name in re.search(r"\{([^}]+)\}", repo.forge("--help").stdout)[1].split(","):
        subs = re.search(r"\{([^}]+)\}", repo.forge(name, "--help").stdout)
        table |= {f"{name} {sub}" for sub in subs[1].split(",")} if subs else {name}
    groups = {command.split()[0] for command in table if " " in command}
    named_in_guide = {f"{first} {second}" if first in groups else first
                      for first, second in re.findall(r"\bforge ([a-z][\w-]*)(?: ([a-z][\w-]*))?",
                                                      GUIDE)}
    assert named_in_guide == table, (f"not commands: {sorted(named_in_guide - table)}; "
                                     f"missing: {sorted(table - named_in_guide)}")


CARRIED_OVER_RULES = {
    "standards.md": ["details.fieldErrors", "at debug", "PUT replaces", "?search=", "a replay is refused",
                     "CSRF", "RoleUser", "system account", "unique field", "never make HTTP calls",
                     "static text", "logs, temporary tables", "mailing-list", "Terraform", "TFSec"],
    "api.md": ["1-4 line description", "one PascalCase tag", "never `Misc`", "ErrorResponseDto",
               "error-code list", "path and query param"],
    "backend.md": ["and local and dev too", "idempotent", "CreateXDto", "*.handler.ts", "never whole objects",
                   "4xx at debug", "implements LoggerService"],
    "frontend.md": ["packages/shared", "x-correlation-id"],
    "testing.md": ["idempotency test", "failure test"],
    "stack.md": ["ESLint", "Prettier", "Terraform"],
}


def _carried_over_rules_are_on_their_pages():
    # Each rule the constitution holds and a worker needs is one line on the page that owns it,
    # and no page still names AWS CDK, since the owner chose Terraform.
    for name, phrases in CARRIED_OVER_RULES.items():
        path = ROOT / "src" / "forge" / ("standards.md" if name == "standards.md" else f"templates/conventions/{name}")
        text = path.read_text(encoding="utf-8")
        for phrase in phrases:
            assert phrase in text, f"{name} misses: {phrase}"
    for path in [ROOT / "src" / "forge" / "standards.md", *CONVENTIONS]:
        assert "CDK" not in path.read_text(encoding="utf-8"), path.name


def _logger_example_writes_the_documented_fields(tmp_path):
    # Run backend.md's own logger and its own call: a fixed message, the context object and the
    # required fields at the top level, none nested inside `message`.
    assert shutil.which("node"), "needs node to run the documented TypeScript"
    blocks = re.findall(r"```ts\n(.*?)```", (CONVENTIONS_DIR / "backend.md").read_text(encoding="utf-8"), re.S)
    logger = next(b for b in blocks if "implements LoggerService" in b).replace("@Injectable()\n", "")
    call = next(line for b in blocks for line in b.splitlines() if "this.logger.log(" in line)
    script = tmp_path / "logger.ts"
    script.write_text("const correlationStore = { getStore: () => 'c-1' };\n"
                      "type LoggerService = object;\n"
                      f"{logger}\nconst invoiceId = 'inv-1';\nconst correlationId = 'c-1';\n"
                      f"const self = {{ logger: new JsonLogger() }};\n{call.replace('this.', 'self.')}\n",
                      encoding="utf-8")
    out = subprocess.run(["node", str(script)], capture_output=True, text=True, check=True,
                         env={**os.environ, "NODE_ENV": "Local"}).stdout
    entry = json.loads(out.strip().splitlines()[-1])
    assert entry["message"] == "Invoice paid" and entry["context"] == {"invoiceId": "inv-1"}
    for field in ("timestampUtc", "level", "environment", "serviceName", "module", "correlationId"):
        assert entry.get(field) not in (None, ""), field
