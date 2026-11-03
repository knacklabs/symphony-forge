"""Init, sync and work deliver the approved safe logging instructions."""
import re
import shutil
from pathlib import Path

import pytest

from conftest import ROOT
from test_setup import LISTED, _fresh_client, _version
from test_worker import calls, install_claude


STORY = "FORGE-REQLOG-1"


BUILT_IN = (
    "- Built in: each API request writes one log line with its method, route, status, time "
    "taken and request id, never the query string; LOG_LEVEL picks the lowest level written; "
    "password, token, secret, key and authorization values are removed from log details; "
    "Mainline sends error alerts from the error lines, so the app has no error-tracking service."
)
CONDITIONAL = (
    "In an app with libs/core/server/src/common/request-log.middleware.ts or set_log_level "
    "in apps/api/app/core/logging.py, also copy this line into ## Fixed rules: "
    f'"{BUILT_IN}"'
)
STANDARDS = (
    "- With `libs/core/server/src/common/request-log.middleware.ts` (TypeScript) or "
    "`set_log_level` in `apps/api/app/core/logging.py` (Python), the next three rules are "
    "built in. Other apps keep their logger, which may write all levels and keep secrets: "
    "never log secrets; add these rules only in a story that copies the starter's logger.",
    "- At any depth, context fields whose names hold `password`, `token`, `secret`, `key` "
    "or `authorization` get `[removed]` values. Log only needed ids.",
    "- Each API request writes one `info` line, `API request`: context has `method`, matched "
    "`route` pattern, `status`, `durationMs`; the line has the request's `correlationId`. "
    "Never include query strings, real paths, headers or bodies. "
    "Health checks and web pages write no line.",
    "- `LOG_LEVEL` (`debug`, `info`, `warn` or `error`; `info` when unset) picks the lowest "
    "level written.",
    "- Mainline sends error alerts from the `error` lines, each with its `errorId`. "
    "Add no error-tracking service to the app.",
)
BRIEF = (
    "Add no error-tracking service; Mainline sends alerts from the error lines. In an app "
    "with `request-log.middleware.ts` or `set_log_level` in `app/core/logging.py`, the logger "
    "writes each API request's line and removes password, token, secret, key and authorization "
    "values from its context, so add no request logging or redaction there."
)
CONVENTIONS = {
    "backend.md": (
        "In an app with `libs/core/server/src/common/request-log.middleware.ts`, "
        "`requestLogMiddleware` writes the request line and `JsonLogger` removes secret "
        "values and reads `LOG_LEVEL` through `getLogLevel()`. Add no other request logging, "
        "redaction or error-tracking code."
    ),
    "python.md": (
        "In an app whose `app/core/logging.py` has `set_log_level`, `log_event` removes "
        "secret values and writes nothing below `LOG_LEVEL`, which the lifespan sets at "
        "start with `set_log_level`. The security middleware writes the request line. "
        "Add no other request logging, redaction or error-tracking code."
    ),
    "deploy.md": (
        "Mainline sends error alerts from the app's `error` log lines. Each carries an "
        "`errorId`, which the person sees on the error screen, so search the platform logs "
        "for it. In an app whose `.env.example` names `LOG_LEVEL`, set it in the platform's "
        "settings to change how much the app writes."
    ),
}
PYTHON_LOGS = (
    "Log with `log_event(request, level, message, module, context)` from `app.core` "
    "(`app/core/logging.py`), not print and not the stdlib `logging` module. It writes one "
    "JSON line to stdout with the backend.md fields at the top level: `timestampUtc`, "
    "`level`, `message`, `context`, `environment` (from `APP_ENV`), `serviceName`, `module` "
    "and `correlationId`. Code without a request passes `None` with `environment` and "
    "`correlation_id`. The security middleware in `app/core/security.py` takes "
    "`x-correlation-id` or makes a UUID, keeps it on `request.state.correlation_id`, and "
    "returns it in the response; `log_event` adds it to each line, and outgoing calls send "
    "it. An app made before this starter keeps its own logger; follow the one it has."
)


@pytest.mark.platform
@pytest.mark.parametrize("setup", ["new init", "previous release"])
def test_4_the_guides_state_the_log_rules(repo, gh, tmp_path, setup):
    # Prompt contract: init and earlier-release sync must deliver the pinned instructions,
    # without teaching an older app that it already has the new logger. Other guide tests
    # cover different rules. Only worker delivery is stubbed; no production seam is added.
    log = install_claude(repo)
    if setup == "new init":
        client, made = _fresh_client(repo, gh, tmp_path)
        assert made.returncode == 0, made.stdout + made.stderr
    else:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
        client = repo.path
        config = client / "forge.toml"
        config.write_text(config.read_text("utf-8").replace(
            'version = "v1.2.2"', f'version = "{_version(repo)}"'), "utf-8")
        repo.git("add", "-A", cwd=client)
        repo.git("commit", "-q", "-m", "Upgrade the earlier client", cwd=client)
        repo.git("push", "-q", "origin", "main", cwd=client)

    started = repo.forge("fix", "start", "Check logging guidance", "--done",
                         "The logging guidance is delivered", "--kind", "mechanical", cwd=client)
    assert started.returncode == 0, started.stdout + started.stderr
    client = client.parent / f"{client.name}-fix-check-logging-guidance"
    if setup == "previous release":
        synced = repo.forge("sync", cwd=client)
        assert synced.returncode == 0, synced.stdout + synced.stderr
        changed = {line.split(None, 1)[1] for line in
                   repo.git("status", "--porcelain", "-uall", cwd=client).splitlines()}
        assert changed <= LISTED  # No existing app file changes on sync.

    for host in (".claude", ".codex"):
        guide = " ".join((client / host / "skills/forge/SKILL.md").read_text("utf-8").split())
        assert CONDITIONAL in guide, host
        assert guide.count(BUILT_IN) == 1, host  # Never in the unconditional outlines.
        standards = " ".join((client / host / "skills/forge/standards.md")
                             .read_text("utf-8").split())
        for instruction in STANDARDS:
            assert instruction in standards, (host, instruction)

    config = client / "forge.toml"
    config.write_text(config.read_text("utf-8").replace(
        'workers = "split"', 'workers = "claude"').replace(
        'workers = "codex"', 'workers = "claude"'), "utf-8")
    repo.git("add", "-A", cwd=client)
    repo.git("commit", "-q", "-m", "Use the current logging guidance", cwd=client)
    worked = repo.forge("work", "check-logging-guidance", cwd=client)
    assert worked.returncode == 0, worked.stdout + worked.stderr
    brief = " ".join(calls(log)[-1]["brief"].split())
    assert BRIEF in brief
    for instruction in STANDARDS:
        assert instruction in brief
    conventions = re.search(r"how-to for each concern .*? in `([^`]+)`", brief)
    assert conventions, brief
    for name, instruction in CONVENTIONS.items():
        page = " ".join((Path(conventions[1]) / name).read_text("utf-8").split())
        assert instruction in page, name
        if name == "backend.md":
            assert "process.env.APP_ENV" in page
            assert "NODE_ENV" not in page
        if name == "python.md":
            logs = page.split("## Logs", 1)[1].split("## Errors", 1)[0]
            assert PYTHON_LOGS in logs
            assert 'log_event(request, "info", "Project created", "app.projects", ' in logs
            assert "JSON formatter" not in logs
