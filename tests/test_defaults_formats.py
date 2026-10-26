"""New starters format dates, times and money in one place and export every table one way."""
import re
import subprocess
import sys
from pathlib import Path

import pytest

from test_libs_layout import lint_starter  # noqa: F401 - a module fixture, installed once here
from test_starter_tree import LIVE, STARTER, _require_cases, live_run

STORY = "FORGE-DEFAULTS-1"

LINT_MESSAGE = "Format dates, times, numbers and money with the helpers in @app/shared-util."
FORMAT_FLOW = "dates show in the person's time zone and the constitution's format"
DOWNLOAD_FLOW = "Export CSV downloads the projects list"
CSV_API_CASES = ("projects export as CSV", "members export as CSV", "change history exports as CSV")
PYTHON_CSV_API_CASES = (
    "test_projects_export_as_csv",
    "test_members_export_as_csv",
    "test_change_history_exports_as_csv",
)
HAND_FORMAT_CASES = {
    "a web file formats a date by hand": (
        Path("libs") / "projects" / "web" / "src" / "pages" / "hand-format.tsx",
        "export const today = new Intl.DateTimeFormat('en').format(new Date());\n",
    ),
    "an API module formats money by hand": (
        Path("libs") / "projects" / "server" / "src" / "hand-format.ts",
        "export const total = (1234).toLocaleString();\n",
    ),
    "a web file formats cents by hand": (
        Path("libs") / "projects" / "web" / "src" / "hooks" / "hand-money.tsx",
        "export const total = (1234 / 100).toFixed(2);\n",
    ),
}
FORMAT_HELPERS = STARTER / "libs" / "shared" / "util" / "src" / "format.ts"
CSV_WRITER = STARTER / "libs" / "core" / "server" / "src" / "common" / "csv.ts"


def _app_sources():
    for pattern in (
        "apps/*/src/**/*.ts",
        "apps/*/src/**/*.tsx",
        "libs/*/*/src/**/*.ts",
        "libs/*/*/src/**/*.tsx",
    ):
        for path in STARTER.glob(pattern):
            if not {"node_modules", "dist"}.intersection(path.parts):
                yield path


@pytest.mark.platform
@pytest.mark.timeout(1800)
def test_3_dates_times_and_money_come_from_the_shared_helpers(tmp_path_factory, lint_starter):
    assert FORMAT_HELPERS.is_file(), "the starter has no shared format helpers"
    # Python init copies this canonical util library. The Python first-commit test owns that copy contract.
    assert LINT_MESSAGE in (STARTER / "eslint.config.mjs").read_text(encoding="utf-8")
    for path in _app_sources():
        if path == FORMAT_HELPERS:
            continue
        text = path.read_text(encoding="utf-8")
        for hand_format in ("Intl.", "toLocale", ".toFixed("):
            assert hand_format not in text, (path.relative_to(STARTER).as_posix(), hand_format)

    if not LIVE:
        return
    _require_cases(live_run(tmp_path_factory)["browser"], (FORMAT_FLOW,))
    live, skip_reason = lint_starter
    assert live is not None, skip_reason
    copy, env, corepack = live
    for case, (relative, source) in HAND_FORMAT_CASES.items():
        added_file = copy / relative
        added_file.write_text(source, encoding="utf-8")
        try:
            result = subprocess.run(
                [corepack, "pnpm", "run", "lint"], cwd=copy, env=env,
                capture_output=True, text=True, timeout=300, shell=sys.platform == "win32",
            )
        finally:
            added_file.unlink(missing_ok=True)
        output = result.stdout + result.stderr
        assert result.returncode != 0, (case, output)
        # ESLint's stylish output drops the message's final full stop.
        assert LINT_MESSAGE.removesuffix(".") in output, (case, output)


@pytest.mark.platform
@pytest.mark.timeout(1800)
def test_4_each_table_exports_csv_from_one_shared_code_path(tmp_path_factory):
    assert CSV_WRITER.is_file(), "the starter has no shared CSV writer"
    writers = [path.relative_to(STARTER).as_posix() for path in _app_sources()
               if "text/csv" in path.read_text(encoding="utf-8")]
    assert writers == [CSV_WRITER.relative_to(STARTER).as_posix()], writers
    web_sources = [STARTER / "apps" / "web" / "src", *STARTER.glob("libs/*/web/src")]
    pages = [path for source in web_sources for path in source.rglob("*-page.tsx")
             if "<Table" in path.read_text(encoding="utf-8")]
    assert pages, "no list screen renders a table"
    for page in pages:
        text = page.read_text(encoding="utf-8")
        assert re.search(r'href="/api/v1/[a-z-]+/export"\s+download', text), page.name

    if LIVE:
        live = live_run(tmp_path_factory)
        _require_cases(live["api"], CSV_API_CASES)
        _require_cases(live["browser"], (DOWNLOAD_FLOW,))
