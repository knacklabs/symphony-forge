#!/usr/bin/env python3
from __future__ import annotations

import base64
import copy
import hashlib
import io
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

# Windows/default-console UTF-8 safety. Python points stdout/stderr at the
# platform's ANSI code page (cp1252 on Windows), so the em-dashes, arrows and
# check marks this tooling prints raise UnicodeEncodeError mid-write and abort
# the command — `forge next` and even `--help` crash on a fresh Windows box.
# Force UTF-8 at import (errors="replace" degrades a stray glyph rather than
# crashing). This is the belt to the `./forge`/`forge.cmd` launchers' exported
# PYTHONUTF8=1: a direct `python factory/scripts/<script>.py` invocation never
# gets that env, and every entrypoint here imports factory_lib.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):  # replaced/detached stream, or closed
        pass


def repo_root() -> Path:
    out = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        check=True,
        capture_output=True,
        text=True,
        env=clean_git_env(), encoding="utf-8", errors="surrogateescape",
    )
    return Path(out.stdout.strip())


def vendored_client(root: Path) -> bool:
    """True when this repo VENDORED the harness — factory/ and the vendored
    adapters/canon are infrastructure a `forge upgrade` may rewrite mid-task, not
    the task's product. The source harness repo has no constitution/VENDORED_FROM
    marker; every client that ran forge upgrade/adopt/scaffold gets one."""
    return (root / "constitution" / "VENDORED_FROM").is_file()


def factory_dir(root: Path | None = None) -> Path:
    return (root or repo_root()) / ".factory"


def story_dir(root: Path, key: str) -> Path:
    """Return the canonical evidence directory for one story."""
    if not isinstance(key, str) or not key or key in (".", "..") \
            or "/" in key or "\\" in key:
        raise ValueError("story key must be one path component")
    return factory_dir(root) / "stories" / key


def story_uses_scoped_layout(root: Path, key: str) -> bool:
    """Return whether a story is marked for scoped state."""
    return story_dir(root, key).is_dir()


def active_story_key(root: Path) -> str:
    """The active story, read cheaply and memoised against run.json.

    `evidence_path` needs only this one field, but reached it through
    `load_json(run_state_path(...))` — a full parse plus `derive_phase`'s extra
    stats — and the board calls `evidence_path` a dozen times per story across
    every story in the roadmap. Reading just the key, once per run.json version,
    removes that amplification. Memoised on the file's stamp, so a run-pointer
    change is picked up immediately."""
    from forge_cli import fscache

    path = run_state_path(root)

    def compute() -> str:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return ""
        if not isinstance(data, dict):
            return ""
        return str(data.get("issue_key") or data.get("story") or "")

    return fscache.cached(
        f"active_story:{path}", fscache.file_stamp(path), compute)


def evidence_path(
    root: Path,
    key: str | None,
    name: str,
    *,
    for_write: bool = False,
) -> Path:
    """Resolve story evidence, retaining legacy live and history reads.

    Intake creates the story directory for the new layout. Its presence is
    therefore also the write-layout marker; an active story without it is a
    legacy story whose live singleton must remain writable.
    """
    relative = Path(name)
    if relative.is_absolute() or not relative.parts or any(
            part in ("", ".", "..") for part in relative.parts):
        raise ValueError("evidence name must be a contained relative path")
    live = factory_dir(root) / relative
    if not key:
        return live

    scoped_dir = story_dir(root, key)
    scoped = scoped_dir / relative
    active = active_story_key(root) == key
    if for_write:
        return scoped if story_uses_scoped_layout(root, key) or not active else live
    if scoped.exists():
        return scoped
    if active and live.exists():
        return live

    archived = factory_dir(root) / "history" / key / relative
    if archived.exists():
        return archived
    return scoped


def _active_story_key(root: Path) -> str:
    return active_story_key(root)


_RUN_STATE_ROOTS: dict[Path, Path] = {}


def run_state_path(
    root: Path | None = None,
    key: str | None = None,
    *,
    for_write: bool = False,
) -> Path:
    """Resolve the worktree-local run pointer, with legacy fallback.

    The protected pointer is authoritative for reads. Intake supplies the
    story key for writes, so only a story with the scoped-layout marker writes
    there; a legacy story continues using tracked run.json.
    """
    base = root or repo_root()
    legacy = factory_dir(base) / "run.json"
    try:
        protected = git_control_dir(base) / "run.json"
    except SystemExit:
        if legacy.is_file() and not for_write:
            return legacy
        raise
    if for_write and key:
        path = protected if story_uses_scoped_layout(base, key) else legacy
        if path == protected:
            _RUN_STATE_ROOTS[protected] = base
        return path
    if protected.is_file():
        _RUN_STATE_ROOTS[protected] = base
        return protected
    return legacy


def derive_phase(root: Path, state: dict[str, Any]) -> str:
    """Derive durable lifecycle progress while retaining transient phases."""
    stored = state.get("phase", "")
    key = state.get("issue_key") or state.get("story")
    if not isinstance(key, str) or not key or not story_uses_scoped_layout(root, key):
        return stored if isinstance(stored, str) else ""

    scoped = story_dir(root, key)
    implied = ""
    if (scoped / "decomposition.json").is_file():
        implied = "implementing"
    if (scoped / "tests.json").is_file() or (scoped / "verify.json").is_file():
        implied = "testing"
    if (scoped / "tests.json").is_file() and (scoped / "verify.json").is_file():
        implied = "reviewing"
    if selected_review_ready_for_functional_check(root, state):
        implied = "functional-check"

    order = (
        "discovery", "planning", "decomposing", "awaiting-approval",
        "implementing", "testing", "reviewing", "functional-check",
        "pr-ready", "shipped", "done",
    )
    if stored not in order or implied not in order:
        return stored if isinstance(stored, str) else implied
    return order[max(order.index(stored), order.index(implied))]


def decomposition_state_path(
    root: Path | None = None,
    key: str | None = None,
    *,
    for_write: bool = False,
) -> Path:
    base = root or repo_root()
    story = key or _active_story_key(base)
    return evidence_path(base, story, "decomposition.json", for_write=for_write)


def clean_git_env() -> dict[str, str]:
    return {
        key: value for key, value in os.environ.items()
        if not key.startswith("GIT_")
    }


def verify_state_path(
    root: Path | None = None,
    key: str | None = None,
    *,
    for_write: bool = False,
) -> Path:
    base = root or repo_root()
    story = key or _active_story_key(base)
    return evidence_path(base, story, "verify.json", for_write=for_write)


def tests_state_path(
    root: Path | None = None,
    key: str | None = None,
    *,
    for_write: bool = False,
) -> Path:
    base = root or repo_root()
    story = key or _active_story_key(base)
    return evidence_path(base, story, "tests.json", for_write=for_write)


def review_dir(root: Path | None = None, key: str | None = None) -> Path:
    base = root or repo_root()
    story = key or _active_story_key(base)
    return evidence_path(base, story, "reviews")


FRONTMATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.DOTALL)
# Substring match, not a YAML parse: these scripts are stdlib-only by design
# (see check_dual_runtime.py's harness.yaml allowlist reader).
# [ \t]* deliberately, NOT \s*: \s crosses newlines, so an empty
# `signoff_record:` would capture the NEXT top-level key as the pin.
SIGNOFF_PIN = re.compile(r"^signoff_record:[ \t]*[\"']?([^\"'\s#]+)", re.MULTILINE)
# "is the key present at top level", as distinct from "does it have a value" —
# a substring test would also match the key inside a comment or an indented
# mapping, which a project-owned harness.yaml may legitimately contain.
SIGNOFF_KEY = re.compile(r"^signoff_record:", re.MULTILINE)
DOC_START = re.compile(r"---(?:[\s#]|\Z)")


def parse_frontmatter(text: str) -> dict[str, str]:
    match = FRONTMATTER.match(text)
    if not match:
        return {}
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip().strip('"').strip("'")
    return fields


# `\r?` before the anchor, matching FRONTMATTER above: multiline `$` sits before
# the `\n` and cannot consume a `\r`, so without it every heading in a CRLF
# document misses and the gate refuses a document whose headings are plainly
# there. `[ \t]+` after the hashes for the same reason a tab is not a typo.
SECTION_HEADING = re.compile(r"^##[ \t]+([^\r\n]+?)[ \t]*\r?$", re.MULTILINE)
# The optional ATX closing run: `## Why ##` names Why, `# #` names nothing.
# Anchored to start-or-whitespace so a hash that belongs to the name survives
# (`## Sharp C#`). Exported because the H1 check needs the same rule — one
# answer to "what is this heading called", or the two drift.
ATX_CLOSING_RUN = re.compile(r"(?:^|[ \t]+)#+[ \t]*\r?$")
# CommonMark's fence rule, as a line test rather than a document-wide regex.
# A backtick opener's info string may not contain a backtick, which is why
# ```` ```json `x` ```` opens nothing.
FENCE_LINE = re.compile(r"^ {0,3}(?P<run>`{3,}|~{3,})(?P<info>[^\r\n]*)$")
# A block-level comment opener. Deliberately not any `<!--`: the substring also
# appears inside inline code (`` `<!--` ``) and prose about comments, and an
# opener taken from there swallows every heading after it.
COMMENT_OPEN = re.compile(r" {0,3}<!--")
# A list marker, because a fence's indentation alone does not say whether it
# belongs to a list item: CommonMark lets a TOP-LEVEL fence indent up to three
# spaces too, and closing that one early hands the example's headings to the
# document.
LIST_ITEM = re.compile(r"^ {0,3}(?:[-*+]|\d{1,9}[.)])[ \t]")
# The raw HTML blocks that hold their content VERBATIM until a closing tag.
# Deliberately not every block tag: a `<div>` block ends at a blank line, so a
# heading after that blank line really is the document's own, and masking to
# `</div>` would refuse a complete spec.
RAW_BLOCK_OPEN = re.compile(r" {0,3}<(pre|script|style|textarea)[ \t>]", re.I)
# CommonMark's type-6 block tags, verbatim from the spec rather than a list
# someone picked: a hand-chosen subset invites "why not this one too" forever,
# and every answer is an argument. These blocks end at a blank line or the end
# of the document, so a heading after that blank line IS the document's own —
# masking to `</div>` instead would refuse a complete spec.
HTML_BLOCK_TAGS = (
    "address|article|aside|base|basefont|blockquote|body|caption|center|col|"
    "colgroup|dd|details|dialog|dir|div|dl|dt|fieldset|figcaption|figure|"
    "footer|form|frame|frameset|h1|h2|h3|h4|h5|h6|head|header|hr|html|iframe|"
    "legend|li|link|main|menu|menuitem|nav|noframes|ol|optgroup|option|p|"
    "param|search|section|summary|table|tbody|td|tfoot|th|thead|title|tr|"
    "track|ul"
)
HTML_BLOCK_OPEN = re.compile(rf" {{0,3}}</?({HTML_BLOCK_TAGS})[ \t>/]", re.I)


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def example_ranges(text: str) -> list[tuple[int, int]]:
    """Character spans holding fenced blocks, HTML comments and raw HTML —
    illustration, not document structure.

    A `## Why` inside an example is an example of a heading, so counting it lets
    a spec satisfy the capture gate without ever stating why. Both constructs
    are line-state machines in the spec and only behave when read as one, so
    this is a SINGLE pass with one state: a fence marker inside a comment and a
    comment marker inside a fence are both just text, and separate passes made
    each construct able to change the other's state. Callers exclude headings
    that START inside a span and still slice bodies from the original text, or
    a section whose content is only an example would read as empty.

    Every ambiguity resolves toward masking LESS, because the two directions
    are not symmetric. Masking too little means an author who wrote their
    sections only inside an example reaches the grill that `spec confirm`
    requires anyway. Masking too much refuses a document whose sections are
    plainly present — the failure this gate exists to remove. That is why an
    unterminated construct masks nothing at all: a stray opener is a typo, and
    reading everything after it as an example is how earlier attempts turned a
    complete spec into a refusal.
    """
    ranges: list[tuple[int, int]] = []
    fence: tuple[str, int, int] | None = None
    # (closing marker, start offset) for the constructs that run verbatim to a
    # marker rather than to a matching fence line: HTML comments and raw blocks.
    verbatim: tuple[str, int] | None = None
    # A container block, which ends at a blank line or the end of the document.
    html_block_at: int | None = None
    opened_at = 0
    offset = 0
    in_list = False
    for line in text.splitlines(keepends=True):
        match = FENCE_LINE.match(line.rstrip("\r\n"))
        if html_block_at is not None and not line.strip():
            ranges.append((html_block_at, offset))
            html_block_at = None
        if fence is not None and line.strip() and _indent(line) < fence[2]:
            # A fence opened inside a list item ends when the item does, so an
            # outdented line closes it. Only fences opened inside a list carry
            # a non-zero guard (see below), so a top-level fence — which may
            # itself be indented up to three spaces — is never closed early.
            ranges.append((opened_at, offset))
            fence = None
        if fence is None and verbatim is None:
            if LIST_ITEM.match(line):
                in_list = True
            elif line.strip() and _indent(line) == 0:
                in_list = False
        if verbatim is not None:
            marker, started = verbatim
            if (closes := line.lower().find(marker)) != -1:
                ranges.append((started, offset + closes + len(marker)))
                verbatim = None
        elif fence is not None:
            # CommonMark allows only spaces and tabs after a closing fence, so
            # `strip()` — which also eats NBSP and every other Unicode space —
            # would close a block the renderer leaves open.
            if (match
                    and match.group("run")[0] == fence[0]
                    and len(match.group("run")) >= fence[1]
                    and not match.group("info").strip(" \t")):
                ranges.append((opened_at, offset + len(line)))
                fence = None
        elif match and (match.group("run")[0] == "~"
                        or "`" not in match.group("info")):
            # The outdent guard is the fence's own indentation ONLY inside a
            # list; at top level it is 0, which no line can undercut.
            fence = (match.group("run")[0], len(match.group("run")),
                     match.start("run") if in_list else 0)
            opened_at = offset
        elif opener := COMMENT_OPEN.match(line):
            verbatim = _verbatim_span(ranges, line, offset, opener.end(), "-->")
        elif opener := RAW_BLOCK_OPEN.match(line):
            verbatim = _verbatim_span(
                ranges, line, offset, opener.end(),
                f"</{opener.group(1).lower()}>",
            )
        elif html_block_at is None and HTML_BLOCK_OPEN.match(line):
            html_block_at = offset
        offset += len(line)
    if html_block_at is not None:
        # End of document terminates a container block — that is the spec, not
        # a deviation, so unlike a stray fence there is nothing unterminated
        # here to be lenient about.
        ranges.append((html_block_at, len(text)))
    return ranges


def _verbatim_span(
    ranges: list[tuple[int, int]], line: str, offset: int, start: int, marker: str
) -> tuple[str, int] | None:
    """Close the span on this line, or report it still open."""
    if (closes := line.lower().find(marker, start)) == -1:
        return marker, offset
    ranges.append((offset, offset + closes + len(marker)))
    return None


def outside_examples(text: str, matches) -> list:
    """The matches that start outside every example span (example_ranges)."""
    ranges = example_ranges(text)
    return [
        match for match in matches
        if not any(start <= match.start() < end for start, end in ranges)
    ]


def ledger_dir(legacy: Path) -> Path:
    """The directory form of a ledger that used to be one .jsonl file."""
    return legacy.with_suffix("")


def append_ledger_record(legacy: Path, record: dict, record_id: str) -> Path:
    """Write one record as its own file (decision 0022).

    Many writers appending to ONE file is the only reason these ledgers ever
    conflicted, and every mechanism built to manage that — a per-clone merge
    driver, .gitattributes rules, scaffold wiring — existed to paper over it.
    Distinct files do not conflict, so there is nothing to merge, nothing to
    order, and no driver to register.
    """
    directory = ledger_dir(legacy)
    directory.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9._-]", "-", record_id)[:120] or "record"
    # A microsecond suffix, because two records of the same ledger can be
    # written inside one second — `quickfix start` then `done` on a fast
    # machine — and filenames that tie put the ledger in ALPHABETICAL order,
    # which is how "done" came to precede "open". Filenames are not the
    # ordering (that is each record's timestamp), but they must not fight it.
    path = directory / f"{safe}-{datetime.now(timezone.utc):%H%M%S%f}.json"
    dump_json(path, record)
    return path


def read_ledger_records(legacy: Path) -> list[dict]:
    """Every record: the directory form plus any legacy .jsonl still present.

    Reading both is what lets a repo adopt the directory form without a
    migration — history stays readable and nothing is rewritten. Order comes
    from each record's own timestamp, never from file position, because
    position was never information and a merge rewrote it anyway.
    """
    records: list[dict] = []
    directory = ledger_dir(legacy)
    if directory.is_dir():
        for path in sorted(directory.glob("*.json")):
            entry = load_json(path, default=None)
            if isinstance(entry, dict):
                records.append(entry)
    if legacy.is_file():
        for lineno, line in enumerate(legacy.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                # LOUD, never skipped: a malformed line is a merge artifact or
                # a hand edit, and a silently-dropped record is the knowledge
                # this ledger exists to keep, lost quietly.
                raise SystemExit(
                    f"{legacy.name} line {lineno} is not valid JSON (merge "
                    f"artifact or hand edit?): {line[:80]!r} — repair it; "
                    "records are managed by the forge commands."
                )
            if not isinstance(entry, dict):
                raise SystemExit(f"{legacy.name} line {lineno} must be a JSON object")
            records.append(entry)
    seen: set[str] = set()
    unique: list[dict] = []
    for entry in records:
        key = json.dumps(entry, sort_keys=True)
        if key not in seen:
            seen.add(key)
            unique.append(entry)
    return sorted(unique, key=_ledger_order)


def _ledger_order(record: dict) -> tuple:
    """Chronological where a record says when it happened, stable otherwise."""
    for field in ("at", "ts", "timestamp", "started_at", "recorded_at"):
        value = record.get(field)
        if isinstance(value, str) and value:
            return (0, value)
    return (1, json.dumps(record, sort_keys=True))


def parse_sections(text: str) -> dict[str, str]:
    """Map level-two Markdown heading names to their stripped bodies.

    The single answer to "does this document have this section, with content".
    Sign-off, spec confirmation and doctor all ask it; when they each decided
    separately, they disagreed — `##  Why` was a section to one and a section
    named " Why" to another, so a lookup missed and a gate refused a document
    that was complete.
    """
    headings = outside_examples(text, SECTION_HEADING.finditer(text))
    return {
        ATX_CLOSING_RUN.sub("", heading.group(1)).strip(): text[
            heading.end():headings[index + 1].start()
            if index + 1 < len(headings) else len(text)
        ].strip()
        for index, heading in enumerate(headings)
    }


# A safe slug, deliberately: the pin is read back by the stdlib regex above,
# which stops at whitespace, quotes and `#`, so any other name would read back
# TRUNCATED. `forge decision new <slug>` already slugifies.
CLIENT_SIGNOFF_NAME = re.compile(r"[0-9]{4}-[a-z0-9-]*client-signoff\.md")


def insert_signoff_pin(text: str, relative: str) -> str:
    """Set the top-level signoff_record key, preserving any YAML prologue.

    ponytail: a targeted line edit, not a YAML rewrite — these scripts are
    stdlib-only, so there is no parser to round-trip through. Replacing an
    existing key is a line substitution; ADDING one must land after any
    directives and document marker, since prepending before `---` would turn a
    single mapping into a two-document stream that consumers cannot read.
    """
    updated, count = re.subn(
        r"^signoff_record:.*$", f'signoff_record: "{relative}"', text,
        count=1, flags=re.MULTILINE,
    )
    if count:
        return updated
    lines = text.splitlines(keepends=True)
    cut = 0
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("%") or not stripped or stripped.startswith("#"):
            continue
        # A document-start marker may carry an inline comment after ANY YAML
        # whitespace (`--- # doc`, `---\t# doc`) or none at all. Missing a form
        # inserts the key BEFORE the marker, making a second document.
        if DOC_START.match(stripped):
            cut = index + 1
        break
    return "".join(lines[:cut]) + f'signoff_record: "{relative}"\n' + "".join(lines[cut:])


def canonical_signoff_path(root: Path, relative: str) -> str:
    """The canonical repo-relative path of a valid sign-off record, or ''.

    Returns the CANONICAL form, never the caller's spelling: a value that
    resolves to a valid record can still be absolute (machine-specific, broken
    in every other clone) or carry quotes and newlines that inject YAML when
    written into harness.yaml. Callers must persist what this returns.

    Enforced at the READER, which is authoritative, not only where a path is
    written: auto-discovery can glob a symlink whose target lies outside, and
    the upgrade migration carries a path out of gitignored run.json. Without
    this, any file with `status: accepted` and a `confirmed_by` satisfies every
    sign-off gate. resolve() collapses symlinks and `..` before the check.
    """
    if not relative:
        return ""
    try:
        decisions = (root / "docs" / "decisions").resolve()
        target = (root / relative).resolve()
        if not target.is_file():
            return ""
    except (OSError, RuntimeError):
        # A malformed symlink chain must read as "invalid pin" with the normal
        # actionable message, never a traceback out of a hook or pr_ready.
        # RuntimeError too: non-strict resolve() raises it for a symlink LOOP on
        # Python 3.10-3.12, which is what CI runs.
        return ""
    if target.parent != decisions:
        return ""
    # fullmatch, not match: `$` also matches before a trailing newline, so a
    # file named "0001-client-signoff.md\n" would validate and then write a
    # multi-line pin that the reader truncates.
    if not CLIENT_SIGNOFF_NAME.fullmatch(target.name):
        return ""
    try:
        return target.relative_to(root.resolve()).as_posix()
    except ValueError:
        return ""


def valid_signoff_path(root: Path, relative: str) -> bool:
    """Is `relative` a client-signoff record DIRECTLY under docs/decisions?

    Enforced at the READER, which is authoritative, not only where a path is
    written: auto-discovery can glob a symlink whose target lies outside, and
    the upgrade migration carries a path out of gitignored run.json.
    """
    return bool(canonical_signoff_path(root, relative))


def signoff_pin(root: Path) -> str:
    """The decision record harness.yaml pins as THE project sign-off, or ''."""
    manifest = root / "harness.yaml"
    # A symlinked manifest would let reads (and record_signoff's write) escape
    # the repo, so the committed, clone-stable answer would not be committed at
    # all. is_file() follows links; is_symlink() is the check that matters.
    if manifest.is_symlink() or not manifest.is_file():
        return ""
    match = SIGNOFF_PIN.search(manifest.read_text(encoding="utf-8"))
    return match.group(1) if match else ""


def client_signoff(root: Path) -> tuple[bool, str]:
    """Is the project signed off, and if not, why not?

    DERIVED, never recorded. The pin lives in committed harness.yaml and the
    proof lives in the committed decision record, so a fresh worktree reads the
    same answer as every other: there is no per-worktree state to re-establish,
    and no later record can displace the pinned one. Sign-off is ONE gate for
    the project (WORKFLOW.md), not one per task — the per-task human gate is
    plan approval, which is grilled and enforced against the same issue.
    """
    pinned = signoff_pin(root)
    if not pinned:
        return False, (
            "Client sign-off required first. Get docs/decisions/NNNN-client-signoff.md "
            "accepted (non-empty confirmed_by), then run "
            "`python3 factory/scripts/record_signoff.py` to pin it in harness.yaml."
        )
    # Require the pin to BE canonical, not merely to resolve: the recovery path
    # is a hand edit to harness.yaml, and an absolute path would resolve here
    # while failing in every differently-located clone — exactly the
    # same-answer-everywhere guarantee this pin exists to provide.
    if canonical_signoff_path(root, pinned) != pinned:
        return False, (
            f"harness.yaml pins signoff_record: {pinned}, which is not a readable "
            "client sign-off record directly under docs/decisions/ "
            "(NNNN-<slug>client-signoff.md, no symlink out of the directory). "
            "Re-pin harness.yaml to the accepted record."
        )
    record = root / pinned
    fields = parse_frontmatter(record.read_text(encoding="utf-8"))
    if fields.get("status") != "accepted" or not fields.get("confirmed_by"):
        return False, (
            f"{pinned} is pinned as the project sign-off but is not an accepted, "
            "human-confirmed record (needs status: accepted and a non-empty confirmed_by)."
        )
    return True, ""


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _proof_object_or_default(path: Path | str, data: Any, default: Any) -> Any:
    """Treat valid non-object task-proof JSON as malformed proof."""
    parts = Path(path).parts
    task_marker = len(parts) >= 6 and (
        parts[-6] == ".factory"
        and parts[-5] == "stories"
        and parts[-3] == "tasks"
        and parts[-1] == "pr-ready.json"
    )
    if task_marker or (
        ".factory" in parts and Path(path).name in {"verify.json", "tests.json"}
    ):
        return data if isinstance(data, dict) else {}
    return data


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    data = json.loads(path.read_text(encoding="utf-8"))
    data = _proof_object_or_default(path, data, default)
    run_root = _RUN_STATE_ROOTS.get(path)
    if run_root is not None and isinstance(data, dict):
        data = {**data, "phase": derive_phase(run_root, data)}
    return data


def _raw_json_object(path: Path) -> dict[str, Any]:
    """Read one JSON object without run-state phase derivation."""
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def raw_run_state(root: Path) -> dict[str, Any]:
    """Read the protected run pointer without recursively deriving its phase."""
    return _raw_json_object(run_state_path(root))


def dump_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def atomic_dump_json(path: Path, data: Any) -> None:
    """Publish JSON through a same-directory temporary file and replacement."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent,
    )
    os.close(descriptor)
    temporary = Path(name)
    try:
        dump_json(temporary, data)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


# Git's control dir is constant for a worktree over a process's lifetime, but
# resolving it shells out to git twice. The board resolves it ~100× per poll
# (once per run_state_path / evidence_path call), which turned a single request
# into ~16s of subprocess churn on Windows. Memoise per resolved root so a
# request costs two git calls, not two hundred. Only successful results are
# cached; a failure re-runs so a transient git error is not pinned for the
# process's life.
_GIT_CONTROL_DIR_CACHE: dict[Path, Path] = {}
_GIT_CONTROL_DIR_LITERAL: dict[Path, Path] = {}


def git_control_dir(root: Path) -> Path:
    # Callers hand the same Path object back hundreds of times per board
    # render, and `resolve()` is itself a filesystem call -- on Windows the
    # single largest cost in the polled path. Key the fast lane on the path AS
    # GIVEN, falling through to the resolved cache for a root spelled a new
    # way. A given path cannot come to mean a different repository inside one
    # process, so this cannot go stale.
    literal = _GIT_CONTROL_DIR_LITERAL.get(root)
    if literal is not None:
        return literal
    resolved = root.resolve()
    cached = _GIT_CONTROL_DIR_CACHE.get(resolved)
    if cached is not None:
        _GIT_CONTROL_DIR_LITERAL[root] = cached
        return cached
    proc = subprocess.run(
        ["git", "rev-parse", "--absolute-git-dir"],
        cwd=root,
        capture_output=True,
        text=True,
        env=clean_git_env(), encoding="utf-8", errors="surrogateescape",
    )
    top = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=root,
        capture_output=True,
        text=True,
        env=clean_git_env(), encoding="utf-8", errors="surrogateescape",
    )
    if (
        proc.returncode != 0
        or top.returncode != 0
        or not proc.stdout.strip()
        or Path(top.stdout.strip()).resolve() != resolved
    ):
        raise SystemExit(
            "Cannot resolve Git's protected control directory for factory state."
        )
    result = Path(proc.stdout.strip()) / "forge"
    _GIT_CONTROL_DIR_CACHE[resolved] = result
    _GIT_CONTROL_DIR_LITERAL[root] = result
    return result


def protected_decomposition_state_path(root: Path) -> Path:
    return git_control_dir(root) / "decomposition.json"


def active_task_id(root: Path) -> str:
    """The task this working copy is executing, or "" for a story-level run.

    `forge task start` stamps `task_id` into the worktree's own run pointer, so
    a recorder running there knows which task its proof belongs to without the
    caller having to say. A story-level run has no task_id and keeps writing
    story-scoped evidence, which is what makes the change backward compatible
    rather than a flag day.
    """
    pointer = raw_run_state(root)
    task_id = pointer.get("task_id") if isinstance(pointer, dict) else ""
    return task_id if isinstance(task_id, str) else ""


def proof_path(
    root: Path,
    key: str | None,
    name: str,
    *,
    task_id: str = "",
    for_write: bool = False,
) -> Path:
    """Where THIS run's proof belongs: the task's directory when a task owns
    the run, the story's when one does not."""
    resolved = task_id or active_task_id(root)
    if resolved:
        return task_evidence_path(root, key, resolved, name, for_write=for_write)
    return evidence_path(root, key, name, for_write=for_write)


def task_evidence_path(
    root: Path,
    key: str | None,
    task_id: str,
    name: str,
    *,
    for_write: bool = False,
) -> Path:
    """Proof belonging to ONE task.

    Reviews, verify and tests were story-scoped singletons: one
    `reviews/quality.json` per story, rewritten by every task in turn. So a
    story's recorded review described whichever task ran last, and a task PR's
    proof check read a file that might describe a different task entirely.
    Per-task review was real in execution and fictional in storage.

    Task proof therefore lives under the task's own directory, beside the
    completion marker that already lives there. Story-level artifacts keep
    their meaning: they are about the story, not a stand-in for its parts.
    """
    for label, value in (("story key", key or ""), ("task id", task_id)):
        if (not isinstance(value, str) or not value
                or value in {".", ".."} or Path(value).name != value
                or "\\" in value):
            raise ValueError(f"{label} must be one path component")
    return evidence_path(
        root, key, f"tasks/{task_id}/{name}", for_write=for_write)


def proof_read_path(root: Path, key: str | None, name: str) -> Path:
    """Where a reader finds proof: task-owned while a task owns the run.

    `proof_path` answers where a WRITER puts proof, and per-task runs put it
    under the task. Readers that resolved story-only therefore missed proof the
    recorders had just written — the review gate, the board, the phase summary,
    the stage rows and the review brief all did. A missing task artifact stays
    missing: falling back could certify one task with a story run's evidence.
    Story-level runs retain their story path because they have no task identity.
    """
    task_id = active_task_id(root)
    if task_id and key:
        return task_evidence_path(root, key, task_id, name)
    return evidence_path(root, key, name)


def task_marker_path(key: str, task_id: str) -> Path:
    """Return the committed marker shared by task start and task closeout."""
    for label, value in (("story key", key), ("task id", task_id)):
        if (
            not isinstance(value, str) or not value
            or value in {".", ".."} or Path(value).name != value
            or "\\" in value
        ):
            raise ValueError(f"{label} must be one path component")
    return Path(".factory") / "stories" / key / "tasks" / task_id / "pr-ready.json"


# The trunk branch of a repo does not change during a process, but resolving it
# shells out to git (symbolic-ref, sometimes a networked `remote show`). The
# board calls it once per task per render — memoize against the deciding refs so
# the board's hot path pays that cost once per change, not N times per render.


def default_trunk_branch(root: Path) -> str:
    """The repo's integration trunk — origin's default branch, not a hardcoded
    'main'. Task markers, the task-start base, and the branch-review diff all
    live on whatever ``origin/HEAD`` points at (main / develop / trunk / …), so
    deriving it keeps the harness correct on every repo instead of only on
    main-trunk ones. Falls back to 'main' when the default cannot be resolved,
    which preserves prior behaviour for main-trunk repos (zero regression).

    Memoized against the refs that DECIDE the answer, not for the lifetime of
    the process. The board resolves this once per task per render, so removing
    the subprocess amplification is worth it — but "stable for a process" holds
    only for a one-shot CLI run. The board runs for hours, and a repo that
    gains an origin/HEAD, or repoints it, while the board is up would otherwise
    be answered forever from a cache nothing could refill."""
    from forge_cli import fscache

    return fscache.cached(f"trunk_branch:{root}", _trunk_ref_stamp(root),
                          lambda: _resolve_trunk_branch(root))


def _trunk_ref_stamp(root: Path) -> tuple:
    """What origin/HEAD resolution actually reads. `config` counts too: adding
    the `origin` remote is what turns the fallback path into a real answer."""
    from forge_cli import fscache

    try:
        git_dir = git_control_dir(root).parent
    except SystemExit:
        return ()
    # From inside a linked worktree the refs live in the shared control dir.
    common = (git_dir.parent.parent
              if git_dir.parent.name == "worktrees" else git_dir)
    return tuple(
        fscache.file_stamp(common / name)
        for name in ("refs/remotes/origin/HEAD", "packed-refs", "config")
    )


def _resolve_trunk_branch(root: Path) -> str:
    # Branch/ref names are UTF-8 (unlike arbitrary file paths), so strict UTF-8
    # decoding is correct here and needs no lossless surrogateescape.
    result = "main"
    ref = subprocess.run(
        ["git", "symbolic-ref", "--quiet", "refs/remotes/origin/HEAD"],
        cwd=root, capture_output=True, text=True, env=clean_git_env(),
        encoding="utf-8",
    )
    if ref.returncode == 0 and ref.stdout.strip():
        result = ref.stdout.strip().rsplit("/", 1)[-1]
    else:
        # origin/HEAD not set locally — ask the remote once, then fall back.
        show = subprocess.run(
            ["git", "remote", "show", "origin"],
            cwd=root, capture_output=True, text=True, env=clean_git_env(),
            encoding="utf-8",
        )
        for line in show.stdout.splitlines():
            if "HEAD branch:" in line:
                name = line.split("HEAD branch:", 1)[1].strip()
                if name and name != "(unknown)":
                    result = name
                    break
    return result


# How long a trunk fetch stays "fresh enough", in seconds. ZERO everywhere by
# default: the frontier and the per-task ship gate must see a marker the instant
# it lands, so every CLI process fetches live. Only the long-running BOARD
# process raises it (see `forge_cli.board.make_server`) — it re-renders every few
# seconds, a network fetch per render is what made opening a story take ~1s, and
# a few seconds of staleness on "has this marker landed yet" costs a read-only
# dashboard nothing.
MARKER_FETCH_TTL = 0.0
_TRUNK_FETCH_AT: dict[tuple[str, str], tuple[float, bool]] = {}
# Two locks, so a request never waits on the network when it need not: the
# state lock guards the dict for a lookup; the run lock serialises the fetch
# itself (two fetches of one ref at once race on FETCH_HEAD and the ref lock).
_TRUNK_FETCH_STATE = threading.Lock()
_TRUNK_FETCH_RUN = threading.Lock()
# A failed fetch is reused for at most this long, whatever the window: a board
# polling an offline remote does not wait on it every poll, and still sees the
# network come back within one poll.
_TRUNK_FETCH_FAILURE_TTL = 10.0

# Set by the board server only (make_server). A board re-derives the same git
# facts on every request; with this on, a fact whose inputs are files git
# rewrites whenever the answer can change is reused until those files change.
# Every CLI process leaves it off, so the gates keep asking git directly.
BOARD_MEMO = False


def _board_memo(namespace: str, stamp: tuple, compute):
    if not BOARD_MEMO:
        return compute()
    from forge_cli import fscache

    return fscache.cached(namespace, stamp, compute)


def _git_dirs(root: Path) -> tuple[Path, Path] | None:
    """(this worktree's git dir, the shared common dir), or None outside git."""
    try:
        git_dir = git_control_dir(root).parent
    except SystemExit:
        return None
    common = (git_dir.parent.parent
              if git_dir.parent.name == "worktrees" else git_dir)
    return git_dir, common


def _trunk_fetch_window(key: tuple[str, str], ttl: float) -> bool | None:
    if ttl <= 0.0:
        return None
    with _TRUNK_FETCH_STATE:
        last = _TRUNK_FETCH_AT.get(key)
    if last is None:
        return None
    at, ok = last
    valid = ttl if ok else min(ttl, _TRUNK_FETCH_FAILURE_TTL)
    return ok if time.monotonic() - at < valid else None


def fetch_trunk(root: Path, trunk: str, *, ttl: float = 0.0) -> bool:
    """Fetch ``origin/<trunk>`` and report whether it should now be present.

    With ``ttl > 0`` a fetch made within the last ``ttl`` seconds is reused
    instead of hitting the network again. The board process raises
    ``MARKER_FETCH_TTL``, and that floor applies to EVERY fetch made in that
    process: the per-render one in ``task_rows`` and the ones ``forge next``
    makes through ``task_marker_on_main``, which used to go around the window
    and pay a network round trip (2.7 s on a real remote) per marker check.
    A call that finds a fetch inside its window never waits on one in flight.
    Every CLI process leaves the TTL at zero and stays live.
    """
    ttl = max(ttl, MARKER_FETCH_TTL)
    key = (str(root), trunk)
    reused = _trunk_fetch_window(key, ttl)
    if reused is not None:
        return reused
    with _TRUNK_FETCH_RUN:
        # Another caller may have fetched while this one waited for the lock.
        reused = _trunk_fetch_window(key, ttl)
        if reused is not None:
            return reused
        ok = _fetch_trunk_now(root, trunk)
        with _TRUNK_FETCH_STATE:
            _TRUNK_FETCH_AT[key] = (time.monotonic(), ok)
        return ok


def _fetch_trunk_now(root: Path, trunk: str) -> bool:
    fetch = subprocess.run(
        ["git", "fetch", "origin", trunk], cwd=root, capture_output=True,
        text=True, env=clean_git_env(), encoding="utf-8", errors="surrogateescape",
    )
    return fetch.returncode == 0


def refresh_trunk(root: Path, trunk: str) -> bool:
    """Fetch now, whatever the window says, and start a fresh window.

    For a refresher on its own clock (the board's). Requests that find the
    previous fetch still inside its window do not wait for this one.
    """
    key = (str(root), trunk)
    with _TRUNK_FETCH_RUN:
        ok = _fetch_trunk_now(root, trunk)
        with _TRUNK_FETCH_STATE:
            _TRUNK_FETCH_AT[key] = (time.monotonic(), ok)
        return ok


def task_marker_on_main(
    root: Path, key: str, task_id: str, *, refresh: bool = True,
) -> bool:
    """Report whether the trunk's tree contains the task's completion marker.

    'main' in the name is historical: the branch queried is the resolved trunk
    (``default_trunk_branch``), so a develop/trunk repo finds its markers too.

    ``refresh=True`` (default) fetches ``origin/<trunk>`` first — the live check
    the frontier and per-task ship gates need. ``refresh=False`` checks only the
    already-fetched origin ref, so the board can fetch the trunk once per render
    and then check every task's marker without a network call each.
    """
    marker = task_marker_path(key, task_id)
    trunk = default_trunk_branch(root)
    if refresh and not fetch_trunk(root, trunk):
        # No origin, or an offline/transient fetch: the marker cannot be
        # confirmed on the trunk, so report not-yet-shipped rather than crashing
        # every caller. `forge next` and the board read this on repos that have
        # no origin (they never crash); the per-task ship gate re-checks live.
        return False

    def ask() -> bool:
        snapshot_proc = subprocess.run(
            ["git", "rev-parse", "--verify", f"origin/{trunk}^{{commit}}"],
            cwd=root, capture_output=True, text=True, env=clean_git_env(),
            encoding="utf-8", errors="surrogateescape",
        )
        snapshot = snapshot_proc.stdout.strip() if snapshot_proc.returncode == 0 else ""
        if not snapshot:
            return False
        marker_rel = marker.as_posix()
        try:
            payload = _read_git_json(root, marker_rel, snapshot)
        except SystemExit:
            return False
        if not _valid_task_marker(
                root, payload, task_id, inspected_head=snapshot):
            return False
        if payload.get("reconciled") is True:
            return True

        def reader(path: str) -> dict | None:
            return _read_git_json(root, path, snapshot)

        return not task_proof_problems(
            root, key, {"id": task_id}, reader=reader,
            marker=payload, inspected_head=snapshot,
        )

    dirs = _git_dirs(root) if BOARD_MEMO else None
    if dirs is None:
        return ask()
    from forge_cli import fscache

    # Fixed by where origin/<trunk> points; git rewrites the loose ref or
    # packed-refs whenever that moves. `forge next` asks this for every
    # shipped task on each recompute (17 checks on one repo).
    common = dirs[1]
    stamp = (fscache.file_stamp(common / "refs" / "remotes" / "origin" / trunk),
             fscache.file_stamp(common / "packed-refs"))
    return _board_memo(f"board:marker:{common}:{trunk}:{marker.as_posix()}",
                       stamp, ask)


def _has_origin(root: Path) -> bool:
    """Whether an `origin` remote is configured (cheap; no network). Marker-on-
    trunk per-task routing only applies when there is a trunk to ship a PR to;
    without an origin the frontier keeps its stage-status behaviour."""
    def ask() -> bool:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"], cwd=root,
            capture_output=True, text=True, env=clean_git_env(),
            encoding="utf-8",
        )
        return result.returncode == 0

    dirs = _git_dirs(root) if BOARD_MEMO else None
    if dirs is None:
        return ask()
    from forge_cli import fscache

    # Remotes live in config; a worktree-scoped config can add one too.
    git_dir, common = dirs
    stamp = (fscache.file_stamp(common / "config"),
             fscache.file_stamp(git_dir / "config.worktree"))
    return _board_memo(f"board:has_origin:{git_dir}", stamp, ask)


def raw_open_flags(flags: int) -> int:
    """Flags for an os.open() whose written bytes must land on disk unchanged.

    On Windows a descriptor opened without O_BINARY is text-mode: the C runtime
    rewrites every LF in os.write() as CRLF. The review brief's sha256 was
    taken from the LF body in memory and checked against the file, so every
    close on a Windows host refused with "review brief hash does not match the
    saved all.md" until the file was converted by hand. Every raw open the
    harness writes bytes through takes its flags from here.
    """
    return flags | getattr(os, "O_BINARY", 0)


def _windows_reparse_point(path: Path) -> bool:
    info = os.lstat(path)
    return bool(
        hasattr(info, "st_file_attributes")
        and info.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def _safe_factory_nt_open(
        directory: Path, parts: tuple[str, ...], flags: int) -> int | None:
    """Open a factory leaf after refusing Windows reparse points.

    Windows lacks dir_fd, so this lstat-based walk has a narrower TOCTOU window
    than the POSIX fd walk. That matches the deferred hard-link/TOCTOU hardening
    backlog; the post-open regular-file and link-count check remains mandatory.
    """
    try:
        directory.mkdir(parents=True, exist_ok=True)
        if _windows_reparse_point(directory):
            return None
        parent = directory
        for part in parts[:-1]:
            parent = parent / part
            parent.mkdir(exist_ok=True)
            if _windows_reparse_point(parent):
                return None
        leaf = parent / parts[-1]
        if os.path.lexists(leaf) and _windows_reparse_point(leaf):
            return None
        return os.open(leaf, raw_open_flags(flags), 0o600)
    except OSError:
        return None


def _safe_factory_fd(root: Path, name: str, flags: int) -> int | None:
    """Open one direct .factory diagnostic file without following links.

    Workers own the workspace, so these mirrors are never authoritative. The
    orchestrator still must not follow a swapped file or parent directory when
    publishing a diagnostic copy.
    """
    if Path(name).name != name:
        raise ValueError("factory diagnostic name must be one path component")
    directory = factory_dir(root)
    if os.name == "nt":
        descriptor = _safe_factory_nt_open(directory, (name,), flags)
        if descriptor is None:
            return None
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            os.close(descriptor)
            return None
        return descriptor
    try:
        directory.mkdir(parents=True, exist_ok=True)
        directory_fd = os.open(
            directory,
            os.O_RDONLY
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_NOFOLLOW", 0),
        )
    except OSError:
        return None
    try:
        descriptor = os.open(
            name,
            flags | getattr(os, "O_NOFOLLOW", 0),
            0o600,
            dir_fd=directory_fd,
        )
    except OSError:
        os.close(directory_fd)
        return None
    os.close(directory_fd)
    info = os.fstat(descriptor)
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        os.close(descriptor)
        return None
    return descriptor


def safe_factory_append(root: Path, name: str, line: bytes) -> bool:
    descriptor = _safe_factory_fd(
        root, name, os.O_WRONLY | os.O_CREAT | os.O_APPEND)
    if descriptor is None:
        return False
    try:
        os.write(descriptor, line)
    finally:
        os.close(descriptor)
    return True


def safe_factory_write_json(root: Path, name: str, data: Any) -> bool:
    descriptor = _safe_factory_fd(root, name, os.O_WRONLY | os.O_CREAT)
    if descriptor is None:
        return False
    body = (json.dumps(data, indent=2) + "\n").encode()
    try:
        os.ftruncate(descriptor, 0)
        os.write(descriptor, body)
    finally:
        os.close(descriptor)
    return True


def safe_factory_write_bytes(root: Path, relative: str, body: bytes) -> bool:
    """Write a nested diagnostic file without following workspace symlinks."""
    rel = Path(relative)
    if rel.is_absolute() or not rel.parts or any(
            part in {"", ".", ".."} for part in rel.parts):
        return False
    directory = factory_dir(root)
    if os.name == "nt":
        descriptor = _safe_factory_nt_open(
            directory, rel.parts, os.O_WRONLY | os.O_CREAT)
        if descriptor is None:
            return False
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            os.close(descriptor)
            return False
        try:
            os.ftruncate(descriptor, 0)
            os.write(descriptor, body)
        finally:
            os.close(descriptor)
        return True
    try:
        directory.mkdir(parents=True, exist_ok=True)
        parent_fd = os.open(
            directory,
            os.O_RDONLY
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_NOFOLLOW", 0),
        )
    except OSError:
        return False
    try:
        for part in rel.parts[:-1]:
            try:
                os.mkdir(part, 0o700, dir_fd=parent_fd)
            except FileExistsError:
                pass
            child_fd = os.open(
                part,
                os.O_RDONLY
                | getattr(os, "O_DIRECTORY", 0)
                | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=parent_fd,
            )
            os.close(parent_fd)
            parent_fd = child_fd
        descriptor = os.open(
            rel.parts[-1],
            os.O_WRONLY | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0),
            0o600,
            dir_fd=parent_fd,
        )
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            os.close(descriptor)
            return False
        try:
            os.ftruncate(descriptor, 0)
            os.write(descriptor, body)
        finally:
            os.close(descriptor)
        return True
    except OSError:
        return False
    finally:
        os.close(parent_fd)


def gate(
    root: Path,
    *,
    signoff: bool = False,
    approved_plan: bool = False,
    decomposition: bool = False,
    lite_window_ok: bool = False,
) -> dict[str, Any]:
    """The factory precondition matrix, in one place.

    Every artifact-writing script calls this with the preconditions its phase
    requires. Missing run state always fails — no gate is skippable by
    deleting .factory/run.json.
    """
    state = load_json(run_state_path(root), default={})
    if not state:
        raise SystemExit("Missing .factory/run.json. Run intake first.")
    active_window = load_json(factory_dir(root) / "quickfix.json", default={})
    lite_open = lite_window_ok and active_window.get("profile") == "lite"
    if signoff:
        ok, why = client_signoff(root)
        if not ok:
            raise SystemExit(why)
    issue = state.get("issue_key", "")
    if approved_plan and not lite_open:
        plan_files = list((root / "plans" / "active").glob(f"{issue}-*.md")) if issue else []
        if state.get("plan_status") != "approved" or not plan_files:
            raise SystemExit(
                "An approved, saved plan is required first "
                f"(plans/active/{issue or '<issue>'}-*.md via `forge.py plan save`)."
            )
    if decomposition and not lite_open:
        if (
            state.get("decomposition_status") != "recorded"
            or not protected_decomposition_state_path(root).exists()
        ):
            raise SystemExit(
                "Recorded decomposition is required first "
                "(record_decomposition_from_json.py after plan approval)."
            )
    return state


def load_review_artifacts(
    root: Path,
    *,
    require_head: bool = False,
    blockers_only: bool = False,
) -> tuple[dict[str, dict], list[str]]:
    """Load the active Lite window's three ephemeral review artifacts."""
    from forge_cli.readiness import review_passed

    reviews: dict[str, dict] = {}
    problems: list[str] = []
    head = head_sha(root)
    key = _active_story_key(root)
    active_window = load_json(factory_dir(root) / "quickfix.json", default={})
    if active_window.get("profile") != "lite":
        return {}, ["lite review window is not active"]
    window_base = active_window.get("base_sha")
    for aspect in ("quality", "performance", "security"):
        path = evidence_path(root, key or None, f"reviews/{aspect}.json")
        data = load_json(path, default={})
        if not data:
            problems.append(str(path.relative_to(root)))
            continue
        relative = path.relative_to(root).as_posix()
        if not unmigrated_fixed_review_paths(root, [relative]):
            problems.append(f"{aspect} review is preserved migration history")
            continue
        if require_head and data.get("commit") != head:
            stamp = data.get("commit")
            shown = stamp[:8] if isinstance(stamp, str) and stamp else "missing"
            expected = head[:8] if isinstance(head, str) else "missing"
            problems.append(
                f"{aspect} review must be stamped at HEAD {expected} (got {shown})"
            )
        stamped_base = data.get("review_base_sha")
        current_review = (
            isinstance(window_base, str)
            and _git_commit_exists(root, window_base)
            and isinstance(head, str)
            and head != window_base
            and data.get("commit") == head
            and _git_is_ancestor(root, window_base, head)
            and (stamped_base is None or stamped_base == window_base)
        )
        if not current_review:
            problems.append(f"{aspect} review does not belong to the open Lite window")
            continue
        reviews[aspect] = data
        if data.get("blocking_findings") or (
            not blockers_only and not review_passed(data)
        ):
            requirement = "have no blockers" if blockers_only else "be >= 8 with no blockers"
            problems.append(f"{aspect} review must {requirement}")
    return reviews, problems


def branch_diff_digest(root: Path) -> str:
    """Hash the committed product diff from the trunk to the current HEAD."""
    from forge_cli.stages import WORKFLOW_PATHS, committed_paths

    trunk = default_trunk_branch(root)
    merge_base = subprocess.run(
        ["git", "merge-base", f"origin/{trunk}", "HEAD"],
        cwd=root, capture_output=True, text=True, env=clean_git_env(),
        encoding="utf-8", errors="surrogateescape",
    )
    if merge_base.returncode != 0 or not merge_base.stdout.strip():
        raise SystemExit(
            f"Cannot bind the branch review: origin/{trunk} has no merge base with HEAD."
        )
    base_sha = merge_base.stdout.strip()
    current_head = head_sha(root)
    paths = sorted(
        path for path in committed_paths(root, base_sha, current_head)
        if not path.startswith(WORKFLOW_PATHS)
    )
    if not paths:
        return hashlib.sha256(b"").hexdigest()
    diff = subprocess.run(
        ["git", "diff", "--binary", "--no-ext-diff", base_sha, current_head,
         "--", *paths],
        cwd=root, capture_output=True, env=clean_git_env(),
    )
    if diff.returncode != 0:
        raise SystemExit("Cannot bind the branch review: git diff failed.")
    return hashlib.sha256(diff.stdout).hexdigest()


def require_coherent_review_run(
    root: Path,
    reviews: dict[str, dict],
    *,
    expected_branch_diff_digest: str | None = None,
) -> list[str]:
    """Return close-gate problems for a split or stale three-lens review run."""
    aspects = ("quality", "performance", "security")
    if any(aspect not in reviews for aspect in aspects):
        return []
    fields = ("review_run_id", "brief_sha256", "branch_diff_digest")
    bindings = [tuple(reviews[aspect].get(field) for field in fields)
                for aspect in aspects]
    if any(not isinstance(value, str) or not value for binding in bindings
           for value in binding):
        return [
            "quality, performance, and security reviews must echo one "
            "review_run_id, brief_sha256, and branch_diff_digest from "
            "`./forge review-brief --all`"
        ]
    if len(set(bindings)) != 1:
        return [
            "quality, performance, and security reviews must share one "
            "review_run_id, brief_sha256, and branch_diff_digest"
        ]
    review_run_id, brief_sha256, recorded_digest = bindings[0]
    expected_run_id = hashlib.sha256(
        (brief_sha256 + recorded_digest).encode()
    ).hexdigest()
    if review_run_id != expected_run_id:
        return [
            "review_run_id must equal sha256(brief_sha256 + branch_diff_digest)"
        ]
    current_digest = (
        expected_branch_diff_digest
        if expected_branch_diff_digest is not None
        else branch_diff_digest(root)
    )
    if recorded_digest != current_digest:
        return [
            "branch review is stale: branch_diff_digest does not match the "
            "current committed product diff; rerun `./forge review-brief --all` "
            "and all three lenses"
        ]
    return []


def require_all_stages_done(root: Path) -> list[str]:
    """Return decomposition task ids whose execution stage is not done."""
    from forge_cli.stages import load_stages

    decomposition = load_json(protected_decomposition_state_path(root), default={})
    stages = {
        stage.get("id"): stage
        for stage in load_stages(root).get("stages", [])
        if isinstance(stage, dict)
    }
    return [
        task["id"]
        for task in decomposition.get("tasks", [])
        if isinstance(task, dict)
        and isinstance(task.get("id"), str)
        and stages.get(task["id"], {}).get("status") != "done"
    ]


def _read_git_json(root: Path, path: str, treeish: str) -> dict | None:
    proc = subprocess.run(
        ["git", "show", f"{treeish}:{path}"], cwd=root, capture_output=True,
        text=True, encoding="utf-8", env=clean_git_env(),
    )
    if proc.returncode != 0:
        return None
    try:
        value = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise SystemExit(
            f"{path} at {treeish} is not valid JSON: {exc}"
        ) from exc
    return _proof_object_or_default(path, value, None)


def _read_git_bytes(root: Path, path: str, treeish: str) -> bytes | None:
    proc = subprocess.run(
        ["git", "show", f"{treeish}:{path}"], cwd=root, capture_output=True,
        env=clean_git_env(),
    )
    return proc.stdout if proc.returncode == 0 else None


def _task_contract(
    root: Path, key: str, task_id: str,
    reader: Callable[[str], dict | None] | None,
) -> tuple[dict | None, str | None]:
    """Resolve the complete task contract instead of trusting a projection."""
    if not task_id:
        return None, "task proof requires a non-empty task identity"

    if reader is not None:
        # A scoped record, when present, is the one authority for this story.
        # The root and history layouts are only candidates when that record is
        # absent; never join two decompositions or fall through after a miss.
        candidates = (
            f".factory/stories/{key}/decomposition.json",
            ".factory/decomposition.json",
            f".factory/history/{key}/decomposition.json",
        )
        data = None
        for path in candidates:
            candidate = reader(path)
            if candidate is None:
                continue
            if (path == ".factory/decomposition.json"
                    and (not isinstance(candidate, dict)
                         or candidate.get("story") != key)):
                continue
            data = candidate
            break
    else:
        if active_story_key(root) == key:
            # The protected control-dir copy is authoritative for the active
            # story, including when it is missing or lacks this task.
            data = load_json(protected_decomposition_state_path(root), default=None)
        else:
            # evidence_path already selects this story's scoped or historical
            # record. Do not use the active story's root singleton as a fallback.
            data = load_json(decomposition_state_path(root, key), default=None)

    if isinstance(data, dict):
        match = next(
            (item for item in data.get("tasks", [])
             if isinstance(item, dict) and item.get("id") == task_id),
            None,
        )
        if match is not None:
            return match, None
        return None, f"{task_id}: protected decomposition has no matching task contract"
    return None, (
        f"{task_id}: protected decomposition is missing; CI cannot determine "
        "the task contract or user-facing proof requirement"
    )


_COMMIT_ID = re.compile(r"^[0-9a-fA-F]{7,64}$")
_PROOF_LENSES = ("quality", "performance", "security")
def _git_commit_exists(root: Path, value: object) -> bool:
    if not isinstance(value, str) or not _COMMIT_ID.fullmatch(value):
        return False
    proc = subprocess.run(
        ["git", "cat-file", "-e", f"{value}^{{commit}}"],
        cwd=root, capture_output=True, env=clean_git_env(),
    )
    return proc.returncode == 0


def _git_is_ancestor(root: Path, ancestor: str, descendant: str) -> bool:
    proc = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        cwd=root, capture_output=True, env=clean_git_env(),
    )
    return proc.returncode == 0


def _valid_task_marker(
    root: Path, marker: object, task_id: str, *, inspected_head: str = "",
) -> bool:
    if not isinstance(marker, dict) or marker.get("task_id") != task_id:
        return False
    if any(
        not isinstance(marker.get(field), str) or not marker[field].strip()
        for field in ("branch", "base_main_sha", "commit", "sealed_at")
    ):
        return False
    base = marker["base_main_sha"]
    seal = marker["commit"]
    if not _git_commit_exists(root, base) or not _git_commit_exists(root, seal):
        return False
    review_base = marker.get("review_base_sha")
    if review_base is not None and (
        not _git_commit_exists(root, review_base)
        or not _git_is_ancestor(root, review_base, seal)
    ):
        return False
    head = inspected_head or head_sha(root)
    return bool(
        head
        and _git_is_ancestor(root, base, seal)
        and _git_is_ancestor(root, seal, head)
    )


def _committed_task_marker(
    root: Path, key: str, task_id: str, marker: object,
    reader: Callable[[str], dict | None] | None,
    *, inspected_head: str = "",
) -> tuple[dict | None, str | None]:
    """Return a valid marker, refusing an invalid committed identity."""
    marker_path = f".factory/stories/{key}/tasks/{task_id}/pr-ready.json"
    if reader is None:
        try:
            committed = _read_git_json(root, marker_path, "HEAD")
        except SystemExit:
            return None, f"{task_id}: task PR marker committed at HEAD is invalid"
        if committed is None:
            return None, None
        if committed != marker:
            return None, f"{task_id}: task PR marker differs from marker committed at HEAD"
        marker = committed
    elif marker is None:
        return None, None
    if not _valid_task_marker(
            root, marker, task_id, inspected_head=inspected_head):
        return None, f"{task_id}: task PR marker is invalid"
    return marker, None


def _marker_publication_commit(
    root: Path, marker_path: str, *, inspected_head: str = "HEAD",
) -> str:
    """The commit that published the marker's CURRENT SEAL: the earliest
    commit on the way to `inspected_head` whose marker names the same sealed
    `commit`. A later rewrite of the same seal's metadata does not move it
    (proof stays pinned to the publication); a reseal after a post-seal fix
    names a new commit and moves it to that seal's publication. Before
    2026-09-15 this was the first commit that ever added the file, so every
    proof reader compared a resealed task's selected review with the FIRST
    seal's ("selected review pointer changed after task marker"). A file
    without a sealed `commit` (a review generation) resolves as before."""
    def sealed(treeish: str) -> str | None:
        shown = subprocess.run(
            ["git", "show", f"{treeish}:{marker_path}"],
            cwd=root, capture_output=True, env=clean_git_env(),
        )
        if shown.returncode != 0:
            return None
        try:
            document = json.loads(shown.stdout.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
        value = document.get("commit") if isinstance(document, dict) else None
        return value if isinstance(value, str) and value else None

    proc = subprocess.run(
        ["git", "log", "--reverse", "--format=%H", inspected_head, "--", marker_path],
        cwd=root, capture_output=True, text=True, env=clean_git_env(),
        encoding="utf-8",
    )
    commits = proc.stdout.split() if proc.returncode == 0 else []
    if not commits:
        return ""
    current = sealed(inspected_head)
    if current is None:
        return commits[0]
    return next((commit for commit in commits if sealed(commit) == current), "")


def _proof_commit_problems(
    root: Path,
    task_id: str,
    records: list[tuple[str, dict]],
    *,
    expected_head: str = "",
    base: str = "",
    seal: str = "",
    compare_product: bool = True,
) -> list[str]:
    """Keep recorder stamps current, or inside one verified historical seal."""
    problems: list[str] = []
    seal_digest = ""
    product_digests: dict[str, str] = {}
    if base and seal and compare_product:
        from forge_cli.stages import workflow_prefixes

        seal_digest = product_tree_digest(
            root, seal, exclude=workflow_prefixes(root),
        )
        product_digests[seal] = seal_digest
    checked: set[tuple[str, str]] = set()
    for label, record in records:
        if not isinstance(record, dict):
            continue
        stamped_task = record.get("task_id")
        if stamped_task is not None and stamped_task != task_id:
            problems.append(
                f"{task_id}: {label} proof is owned by task {stamped_task!r}"
            )
        commit = record.get("commit")
        if expected_head:
            if commit != expected_head:
                problems.append(
                    f"{task_id}: {label} proof is stamped at {commit!r}, not HEAD"
                )
            continue
        if not base or not seal:
            continue
        if not _git_commit_exists(root, commit):
            problems.append(f"{task_id}: {label} proof has no valid commit stamp")
            continue
        if not _git_is_ancestor(root, base, commit) or not _git_is_ancestor(
            root, commit, seal
        ):
            problems.append(
                f"{task_id}: {label} proof commit is outside the task base-to-seal range"
            )
            continue
        identity = (label, str(commit))
        if identity in checked:
            continue
        checked.add(identity)
        if compare_product:
            from forge_cli.stages import workflow_prefixes

            commit_key = str(commit)
            if commit_key not in product_digests:
                product_digests[commit_key] = product_tree_digest(
                    root, commit_key, exclude=workflow_prefixes(root),
                )
            if product_digests[commit_key] != seal_digest:
                problems.append(
                    f"{task_id}: product content changed after {label} proof was recorded"
                )
    return problems


def _proof_review_problems(
    root: Path,
    task_id: str,
    reviews: dict[str, dict],
    *,
    strict: bool,
    expected_branch_diff_digest: str | None = None,
) -> list[str]:
    """Validate all three review artifacts, including task binding when modern."""
    from forge_cli.readiness import review_passed

    problems: list[str] = []
    for lens in _PROOF_LENSES:
        review = reviews.get(lens)
        if not review:
            problems.append(
                f"{task_id}: no {lens} review — `./forge review {task_id}` runs all "
                "three lenses in Codex and records them")
            continue
        if strict and review.get("task_id") != task_id:
            problems.append(f"{task_id}: {lens} review is not owned by task {task_id!r}")
        try:
            passed = review_passed(review)
        except (TypeError, ValueError):
            passed = False
        if not passed:
            blockers = review.get("blocking_findings")
            blocking = (len(blockers) if isinstance(blockers, (list, tuple, dict, set))
                        else int(bool(blockers)))
            problems.append(
                f"{task_id}: {lens} review is not clean ({blocking} blocking "
                f"finding(s), score {review.get('score')!r}) — delegate the fixes "
                f"with `./forge delegate {task_id}`, commit, then rerun "
                f"`./forge review {task_id}`")

    if strict and all(lens in reviews for lens in _PROOF_LENSES):
        problems.extend(
            require_coherent_review_run(
                root, reviews,
                expected_branch_diff_digest=expected_branch_diff_digest,
            )
        )
    return problems


def _current_task_review_inputs(
    root: Path,
    key: str,
    task_id: str,
    task: dict,
    *,
    reader: Callable[[str], dict | None] | None = None,
    reader_treeish: str = "",
    branch: str = "",
    delta_id: str = "",
) -> tuple[dict | None, list[str]]:
    """Read the current task inputs in the same shape review-brief uses.

    A sealed task's brief is historical, but its task-owned plan, grill and
    report must still be the current records.  Reading those paths from HEAD
    (or the local worktree before sealing) catches a report edit after review
    without letting a later task's global ``all.md`` replace the sealed brief.
    """
    from forge_cli.review_brief import _approved_task_inputs

    if reader is None and not branch:
        try:
            return _approved_task_inputs(
                root, task,
            ), []
        except SystemExit as exc:
            return None, [str(exc)]

    prefix = f".factory/stories/{key}"
    plan_path = f"{prefix}/task-plans/{task_id}.md"
    grill_path = f"{prefix}/grills/tasks/{task_id}.json"
    tests_path = f"{prefix}/tasks/{task_id}/tests.json"

    def read_json(path: str) -> dict | None:
        if reader is not None:
            return reader(path)
        return load_json(root / path, default=None)

    def read_bytes(path: str) -> bytes | None:
        if reader is not None:
            return _read_git_bytes(root, path, reader_treeish or "HEAD")
        try:
            return (root / path).read_bytes()
        except OSError:
            return None

    raw_plan = read_bytes(plan_path)
    if raw_plan is None:
        return None, [f"{task_id}: current approved task plan is missing"]
    try:
        plan_text = raw_plan.decode("utf-8")
    except UnicodeDecodeError:
        return None, [f"{task_id}: current approved task plan is not UTF-8"]
    contract_text = render_recorded_task_contract(root, task_id, key)
    if not contract_text:
        return None, [f"{task_id}: current recorded task contract is missing"]
    grill = read_json(grill_path)
    tests = read_json(tests_path)
    automated = tests.get("automated") if isinstance(tests, dict) else None
    if not isinstance(grill, dict) or not isinstance(automated, dict):
        return None, [
            f"{task_id}: current task grill and automated report are required"
        ]
    if not branch.strip() and reader is None:
        state = load_json(run_state_path(root), default={})
        branch = str(state.get("branch") or "").strip()
    if not branch.strip() and reader is None:
        proc = subprocess.run(
            ["git", "branch", "--show-current"], cwd=root,
            capture_output=True, text=True, encoding="utf-8", env=clean_git_env(),
        )
        branch = proc.stdout.strip() if proc.returncode == 0 else ""
    return {
        "story": key,
        "task_id": task_id,
        "branch": branch,
        "delta_id": delta_id,
        "plan_text": plan_text,
        "contract_text": contract_text,
        "plan_sha256": _plan_body_digest_bytes(raw_plan),
        "grill": grill,
        "automated": automated,
    }, []


def _review_input_problems(
    root: Path,
    key: str,
    task_id: str,
    task: dict,
    reviews: dict[str, dict],
    *,
    reader: Callable[[str], dict | None] | None = None,
    reader_treeish: str = "",
    brief_treeish: str = "",
    brief_fallback_treeish: str = "",
    branch: str = "",
    delta_id: str = "",
) -> list[str]:
    """Bind clean review artifacts to the exact complete approved inputs.

    The review run already binds one ``brief_sha256`` across its lenses.  This
    predicate additionally verifies that the saved brief bytes are that hash
    and that its complete approved-input section is exactly the current,
    task-owned section rendered by review-brief's shared pure producer.
    """
    brief_path = ".factory/review-briefs/all.md"
    if brief_treeish:
        brief_bytes = _read_git_bytes(root, brief_path, brief_treeish)
        if brief_bytes is None and brief_fallback_treeish:
            brief_bytes = _read_git_bytes(root, brief_path, brief_fallback_treeish)
    elif reader is not None:
        brief_bytes = _read_git_bytes(root, brief_path, reader_treeish or "HEAD")
    else:
        try:
            brief_bytes = (root / brief_path).read_bytes()
        except OSError:
            brief_bytes = None
    if brief_bytes is None:
        return [
            f"{task_id}: review brief is not published at the task's proof tip"
        ]

    problems: list[str] = []
    expected_hash = hashlib.sha256(brief_bytes).hexdigest()
    for lens in _PROOF_LENSES:
        review = reviews.get(lens)
        if isinstance(review, dict) and review.get("brief_sha256") != expected_hash:
            problems.append(
                f"{task_id}: {lens} review brief hash does not match the saved all.md"
            )
    try:
        body = brief_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return problems + [f"{task_id}: saved review brief is not UTF-8"]

    inputs, input_problems = _current_task_review_inputs(
        root, key, task_id, task, reader=reader, reader_treeish=reader_treeish,
        branch=branch,
        delta_id=delta_id,
    )
    if input_problems:
        return problems + input_problems
    assert inputs is not None
    try:
        from forge_cli.review_brief import render_approved_inputs_section
        section = "\n".join(render_approved_inputs_section(inputs))
    except (AttributeError, TypeError, ValueError, SystemExit) as exc:
        return problems + [
            f"{task_id}: cannot render the complete approved-input section: {exc}"
        ]
    if body.count(section) != 1:
        problems.append(
            f"{task_id}: saved review brief does not contain exactly one current "
            "complete approved-input section"
        )
    return problems


def _modern_task_proof_problems(
    root: Path, key: str, task: dict,
    read: Callable[[str], dict], *,
    expected_head: str | None = None,
    marker_publication_commit: str = "",
    expected_branch_diff_digest: str | None = None,
    reader: Callable[[str], dict | None] | None = None,
    reader_treeish: str = "",
    brief_treeish: str = "",
    brief_fallback_treeish: str = "",
    review_branch: str = "",
    proof_base: str = "",
    proof_seal: str = "",
    expected_review_delta: str = "",
    selected_reader: Callable[[str], dict | None] | None = None,
    selected_bytes_reader: Callable[[str], bytes | None] | None = None,
    sealed_commit: str = "",
    selected_upgrade_after_marker: bool = False,
    history_head: str = "HEAD",
) -> list[str]:
    """The fail-closed proof predicate for a task-owned bundle."""
    from forge_cli.readiness import tests_passed, verify_passed

    task_id = str(task.get("id") or "")
    if not task_id:
        return ["task proof requires a non-empty task identity"]
    problems: list[str] = []
    verify = read("verify.json")
    if not isinstance(verify, dict) or not verify_passed(verify):
        problems.append(
            f"{task_id}: no passing verify — from its worktree run "
            "`python3 factory/scripts/verify.py`")

    tests = read("tests.json")
    automated = tests.get("automated") if isinstance(tests, dict) else None
    if (not isinstance(automated, dict)
            or automated.get("status") != "passed"
            or automated.get("blocking_findings")):
        problems.append(
            f"{task_id}: no passing automated tests — run them, then record with "
            "`python3 factory/scripts/record_test_from_json.py --kind automated "
            "--input <json>`")
    if bool(task.get("user_facing")):
        functional = tests.get("functional") if isinstance(tests, dict) else None
        if not isinstance(functional, dict):
            problems.append(
                f"{task_id}: user_facing, so a functional check is required — run "
                "the functional-checker, then record with "
                "`python3 factory/scripts/record_test_from_json.py --kind functional "
                "--input <json>`")
        else:
            try:
                functional_passed = tests_passed(functional, functional=True)
            except (TypeError, ValueError):
                functional_passed = False
            if functional.get("status") != "passed" or not functional_passed:
                problems.append(
                    f"{task_id}: functional check must be passed, have no blockers, "
                    "and score >= 8 — fix what it found and re-record it")

    authoritative_review_paths: set[str] = set()
    generation, _selection, review_generation_problems = read_selected_review_generation(
        root, key, task_id, reader=selected_reader,
        bytes_reader=selected_bytes_reader, expected_delta_id=expected_review_delta,
        sealed_commit=sealed_commit, consumed_paths=authoritative_review_paths,
    )
    problems.extend(review_generation_problems)
    reviews = (
        generation.get("lenses", {})
        if isinstance(generation, dict) else {lens: {} for lens in _PROOF_LENSES}
    )
    declared = [
        str(contract.get("id") or "")
        for contract in task.get("plan_contracts") or []
        if isinstance(contract, dict) and contract.get("id")
    ]
    implemented = {
        verdict.get("contract_id")
        for verdict in reviews.get("quality", {}).get("contract_verdicts") or []
        if isinstance(verdict, dict) and verdict.get("verdict") == "implemented"
    }
    unverified = [contract_id for contract_id in declared if contract_id not in implemented]
    if unverified:
        problems.append(
            f"{task_id}: quality review must verify every plan contract as "
            f"implemented; unverified: {', '.join(unverified)} — compose the "
            "reviewer prompt with `./forge review-brief --all`"
        )
    if marker_publication_commit:
        proof_root = f".factory/stories/{key}/tasks/{task_id}"
        history_review_paths = set(authoritative_review_paths)
        allowed_upgrade_paths: set[str] = set()
        generation_changes: set[str] = set()
        generation_change_error = ""
        if selected_upgrade_after_marker and isinstance(generation, dict):
            generation_rel, selection_rel = _review_relpaths(
                key, task_id, str(generation.get("generation_id") or ""),
            )
            history_review_paths.discard(generation_rel)
            allowed_upgrade_paths.add(selection_rel)
            generation_publication = _marker_publication_commit(root, generation_rel)
            if generation_publication and not _git_is_ancestor(
                    root, marker_publication_commit, generation_publication):
                generation_change_error = "upgrade generation publication is invalid"
            elif generation_publication:
                generation_changes, generation_change_error = _paths_changed_after(
                    root, generation_publication, [generation_rel], head=history_head,
                )
        changed, change_error = _paths_changed_after(
            root, marker_publication_commit,
            [f"{proof_root}/verify.json", f"{proof_root}/tests.json",
             *sorted(history_review_paths)],
            head=history_head,
        )
        changed.update(generation_changes)
        if change_error or generation_change_error:
            problems.append(
                f"{task_id}: cannot inspect proof history after task marker: "
                f"{change_error or generation_change_error}"
            )
        for path in sorted(changed - allowed_upgrade_paths):
            problems.append(
                f"{task_id}: {path.removeprefix(proof_root + '/')} proof "
                "changed after task marker"
            )
    # The recorder stamps the containing tests.json record. Nested reports are
    # payloads within that one artifact and do not carry an independent proof
    # commit in every historical fixture.
    records = [("verify", verify), ("tests", tests)]
    records.extend((f"reviews.{lens}", reviews[lens])
                   for lens in _PROOF_LENSES)
    if proof_base and proof_seal:
        problems.extend(
            _proof_commit_problems(
                root, task_id, records, base=proof_base, seal=proof_seal,
            )
        )
    else:
        problems.extend(
            _proof_commit_problems(
                root, task_id, records,
                expected_head=expected_head or head_sha(root) or "",
            )
        )
    review_delta = (
        expected_branch_diff_digest
        if expected_branch_diff_digest is not None
        else expected_review_delta
        or (str(generation.get("delta_id") or "") if sealed_commit
            and isinstance(generation, dict) else None)
    )
    problems.extend(
        _proof_review_problems(
            root, task_id, reviews, strict=True,
            expected_branch_diff_digest=review_delta,
        )
    )
    problems.extend(
        _review_input_problems(
            root, key, task_id, task, reviews,
            reader=reader, reader_treeish=reader_treeish,
            brief_treeish=brief_treeish,
            brief_fallback_treeish=brief_fallback_treeish,
            branch=review_branch,
            delta_id=review_delta or "",
        )
    )
    return problems


def task_proof_problems(
    root: Path, key: str, task: dict, *,
    reader: Callable[[str], dict | None] | None = None,
    marker: dict | None = None,
    preseal: bool = False,
    inspected_head: str = "",
) -> list[str]:
    """One task's proof, using one task-aware predicate everywhere.

    Every run reads only the task-owned bundle. A committed task marker binds
    post-seal local and CI reads to its sealed product and proof; pre-seal
    callers always require the current task tree. Marker-bound upgrade
    generations are the sole fixed-proof migration representation.
    """
    task_id = str(task.get("id") or "")
    fixed_review_paths = [
        f".factory/stories/{key}/reviews/{aspect}.json"
        for aspect in _PROOF_LENSES
    ] + [
        f".factory/stories/{key}/tasks/{task_id}/reviews/{aspect}.json"
        for aspect in _PROOF_LENSES
    ]
    fixed_review_paths = unmigrated_fixed_review_paths(
        root, fixed_review_paths, reader=reader,
        reader_treeish=inspected_head,
    )
    if fixed_review_paths:
        if has_completed_lean_migration_manifest(root, reader=reader):
            guidance = f"record a fresh review with `forge review {task_id}`"
            message = "legacy fixed review files are not runtime proof; " + guidance
        else:
            message = (
                "legacy fixed review proof is no longer runtime authority; "
                "run `forge upgrade`"
            )
        return [
            f"{task_id}: {message}"
        ]
    task, contract_problem = _task_contract(root, key, task_id, reader)
    if contract_problem:
        return [contract_problem]
    assert task is not None

    def read_task(name: str) -> dict:
        rel = f".factory/stories/{key}/tasks/{task_id}/{name}"
        if reader is not None:
            return reader(rel) or {}
        return load_json(task_evidence_path(root, key, task_id, name), default={})

    marker_path = f".factory/stories/{key}/tasks/{task_id}/pr-ready.json"
    if marker is None:
        try:
            marker = reader(marker_path) if reader is not None else load_json(
                root / marker_path, default=None
            )
        except (json.JSONDecodeError, OSError, TypeError, ValueError):
            return [f"{task_id}: task PR marker is invalid"]

    marker_context = None
    missing_marker = False
    if not preseal:
        marker_context, marker_problem = _committed_task_marker(
            root, key, task_id, marker, reader, inspected_head=inspected_head,
        )
        if marker_problem:
            return [marker_problem]
        if marker_context is not None and marker_context.get("reconciled") is True:
            return []
        missing_marker = marker_context is None

    expected_head = inspected_head or head_sha(root) or ""
    proof_base = ""
    proof_seal = ""
    marker_publication_commit = ""
    expected_branch_diff_digest = None
    review_base = ""
    if marker_context is not None:
        sealed_commit = str(marker_context["commit"])
        expected_head = sealed_commit
        proof_base = str(marker_context["base_main_sha"])
        proof_seal = sealed_commit
        marker_publication_commit = _marker_publication_commit(
            root, marker_path, inspected_head=inspected_head or "HEAD",
        )
        review_base = str(marker_context.get("review_base_sha") or "")
        expected_branch_diff_digest = (
            product_delta_digest(root, review_base, sealed_commit)
            if review_base else None
        )
    if not proof_base and reader is None:
        proof_base = _stage_baseline_for(root, task_id)
    if not proof_base and reader is None:
        state = load_json(run_state_path(root), default={})
        proof_base = str(state.get("base_main_sha") or "")
    if proof_base and expected_head and _git_commit_exists(root, proof_base):
        proof_seal = expected_head

    selected_reader = reader
    selected_bytes_reader = None
    selected_upgrade_after_marker = False
    expected_review_delta = ""
    sealed_review_commit = ""
    if marker_context is not None:
        sealed_review_commit = str(marker_context["commit"])
        selected_treeish = marker_publication_commit or sealed_review_commit
        selected_reader = lambda path, treeish=selected_treeish: _read_git_json(
            root, path, treeish
        )
        selected_bytes_reader = lambda path, treeish=selected_treeish: _read_git_bytes(
            root, path, treeish
        )
        _generation_rel, selection_rel = _review_relpaths(key, task_id)
        marker_selection = selected_reader(selection_rel)
        try:
            current_selection = (
                reader(selection_rel) if reader is not None else
                load_json(root / selection_rel, default=None)
            )
        except (json.JSONDecodeError, SystemExit) as exc:
            return [f"{task_id}: selected review pointer is invalid: {exc}"]
        if current_selection != marker_selection:
            current_bytes_reader = (
                (lambda path: _read_git_bytes(
                    root, path, inspected_head or "HEAD"))
                if reader is not None else None
            )
            current_generation, _current_pointer, current_problems = (
                read_selected_review_generation(
                    root, key, task_id, reader=reader,
                    bytes_reader=current_bytes_reader,
                    sealed_commit=sealed_review_commit,
                )
            )
            if (current_problems or not isinstance(current_generation, dict)
                    or current_generation.get("origin") != "upgrade"):
                return [
                    f"{task_id}: selected review pointer changed after task marker "
                    "without a valid marker-bound sealed upgrade",
                    *current_problems,
                ]
            selected_reader = reader
            selected_bytes_reader = current_bytes_reader
            selected_upgrade_after_marker = True
    elif reader is not None:
        selected_bytes_reader = lambda path: _read_git_bytes(
            root, path, inspected_head or "HEAD")
    elif proof_base:
        review_base = effective_review_base(root, task_id) or proof_base
        expected_review_delta = product_delta_digest(root, review_base)

    problems = _modern_task_proof_problems(
        root, key, task, read_task,
        expected_head=expected_head,
        marker_publication_commit=marker_publication_commit,
        expected_branch_diff_digest=expected_branch_diff_digest,
        reader=reader, reader_treeish=inspected_head,
        brief_treeish=(marker_publication_commit
                       if marker_context is not None else ""),
        review_branch=(str(marker_context.get("branch") or "")
                       if marker_context is not None else ""),
        proof_base=proof_base,
        proof_seal=proof_seal,
        expected_review_delta=expected_review_delta,
        selected_reader=selected_reader,
        selected_bytes_reader=selected_bytes_reader,
        sealed_commit=sealed_review_commit,
        selected_upgrade_after_marker=selected_upgrade_after_marker,
        history_head=inspected_head or "HEAD",
    )
    if missing_marker:
        problems.insert(0, f"{task_id}: committed pr-ready marker is missing")
    return problems


def unmigrated_fixed_review_paths(
    root: Path, candidates: list[str], *,
    reader: Callable[[str], dict | None] | None = None,
    reader_treeish: str = "",
) -> list[str]:
    """Return existing fixed-review files not recorded as preserved history."""
    migrations = factory_dir(root) / "migrations"
    manifest_paths = {
        ".factory/migrations/lean-workflow-v2.json",
        ".factory/migrations/lean-workflow-v2-supplement.json",
    }
    manifest_paths.update(
        path.relative_to(root).as_posix()
        for path in migrations.glob("lean-workflow-v2*.json")
    )
    preserved: set[tuple[str, str]] = set()
    for relative in sorted(manifest_paths):
        path = root / relative
        try:
            manifest = reader(relative) if reader is not None else load_json(
                path, default=None,
            )
        except (OSError, json.JSONDecodeError, SystemExit, TypeError, ValueError):
            continue
        if (not isinstance(manifest, dict)
                or manifest.get("generated_by") != "upgrade"
                or manifest.get("version") != "lean-workflow-v2"
                or not isinstance(manifest.get("completed_at"), str)
                or not manifest["completed_at"].strip()):
            continue
        for entry in manifest.get("preserved_entries") or []:
            if (isinstance(entry, dict)
                    and isinstance(entry.get("path"), str)
                    and isinstance(entry.get("sha256"), str)):
                preserved.add((entry["path"], entry["sha256"]))

    remaining: list[str] = []
    for relative in candidates:
        if reader is not None:
            if reader(relative) is None:
                continue
            body = _read_git_bytes(
                root, relative, reader_treeish or "HEAD",
            )
            if body is None:
                remaining.append(relative)
                continue
        else:
            candidate_path = root / relative
            if not candidate_path.is_file():
                continue
            try:
                body = candidate_path.read_bytes()
            except OSError:
                remaining.append(relative)
                continue
        digest = hashlib.sha256(body).hexdigest()
        if (relative, digest) not in preserved:
            remaining.append(relative)
    return remaining


def has_completed_lean_migration_manifest(
    root: Path, *, reader: Callable[[str], dict | None] | None = None,
) -> bool:
    """Whether this repository has a completed Lean migration manifest."""
    paths = {
        ".factory/migrations/lean-workflow-v2.json",
        ".factory/migrations/lean-workflow-v2-supplement.json",
    }
    migrations = factory_dir(root) / "migrations"
    paths.update(
        path.relative_to(root).as_posix()
        for path in migrations.glob("lean-workflow-v2*.json")
    )
    for relative in sorted(paths):
        try:
            manifest = reader(relative) if reader is not None else load_json(
                root / relative, default=None,
            )
        except (OSError, json.JSONDecodeError, SystemExit, TypeError, ValueError):
            continue
        if (isinstance(manifest, dict)
                and manifest.get("generated_by") == "upgrade"
                and manifest.get("version") == "lean-workflow-v2"
                and isinstance(manifest.get("completed_at"), str)
                and manifest["completed_at"].strip()):
            return True
    return False


def run_is_task_level(root: Path, key: str = "", tasks: list[dict] | None = None) -> bool:
    """Whether this story ships task by task (per-task PRs and markers) or as
    one story -- the one answer every closeout gate must agree on.

    The pointer's `base_main_sha` says so only inside a task worktree: `forge
    task start` writes it there, and nothing writes it into the story's own
    pointer. So a story whose every task had shipped as its own PR was still
    classed story-level at closeout and asked for the story-wide verify,
    three-lens review and functional pass that the per-task flow retired
    (WF-1, 2026-09-14). The markers are the evidence: a story-level run cannot
    produce one, so a task marker on the trunk -- or committed in this tree --
    means task-level.
    """
    state = load_json(run_state_path(root), default={})
    if state.get("base_main_sha"):
        return True
    key = key or _active_story_key(root)
    if tasks is None:
        decomposition = load_json(protected_decomposition_state_path(root), default={})
        tasks = [t for t in decomposition.get("tasks", []) if isinstance(t, dict)]
    ids = [str(t.get("id") or "") for t in tasks if t.get("id")]
    if not key or not ids:
        return False
    try:
        if any((root / task_marker_path(key, task_id)).is_file() for task_id in ids):
            return True
    except ValueError:
        return False
    fetch_trunk(root, default_trunk_branch(root))
    return any(task_marker_on_main(root, key, task_id, refresh=False) for task_id in ids)


def require_closeout_order(root: Path) -> list[str]:
    """Story closeout, sourced from the proof its TASKS produced.

    A story used to re-prove itself: a second verify, a second three-lens
    review and a second functional check over the whole story diff, all
    stamped at HEAD. Under per-task PRs every task has already shipped with
    exactly that proof over its own diff, and each task PR is gated on it — so
    the story-level pass re-reviewed reviewed code, and one late fix in the
    last task invalidated the evidence of every task before it.

    The story is the sum of its tasks. What remains story-shaped is the
    outcome: what shipped and what someone can now do, which no single task
    can answer.
    """
    from forge_cli.outcome import load_outcome
    problems: list[str] = []
    head = head_sha(root)
    expected = head[:8] if head else "missing"

    open_stages = require_all_stages_done(root)
    if open_stages:
        problems.append(
            f"stage completion: {', '.join(open_stages)} not done — work each "
            "stage (forge stage start → implement/test → commit → verify and "
            "record task tests → forge review → forge stage done; WORKFLOW.md "
            "Stage Loop)"
        )

    key = _active_story_key(root)
    decomposition = load_json(protected_decomposition_state_path(root), default={})
    tasks = [t for t in decomposition.get("tasks", []) if isinstance(t, dict)]
    fixed_reviews = [
        evidence_path(root, key, f"reviews/{aspect}.json")
        for aspect in ("quality", "performance", "security")
    ] + [
        evidence_path(
            root, key, f"tasks/{task.get('id')}/reviews/{aspect}.json",
        )
        for task in tasks
        for aspect in ("quality", "performance", "security")
    ]
    unmigrated_reviews = unmigrated_fixed_review_paths(
        root, [path.relative_to(root).as_posix() for path in fixed_reviews],
    )
    if unmigrated_reviews:
        task_ids = sorted({
            parts[4] for relative in unmigrated_reviews
            if len(parts := Path(relative).parts) > 4 and parts[3] == "tasks"
        })
        if not has_completed_lean_migration_manifest(root):
            problems.append(
                "legacy fixed review proof is no longer runtime authority; "
                "run `forge upgrade`"
            )
        else:
            guidance = ", ".join(
                f"`forge review {task_id}`" for task_id in task_ids
            ) or "the story's current task"
            problems.append(
                "legacy fixed review files are not runtime proof; record a "
                f"fresh review with {guidance}"
            )
    trunk = default_trunk_branch(root)
    trunk_available = bool(tasks) and fetch_trunk(root, trunk)
    missing_trunk_markers = [
        str(task.get("id") or "")
        for task in tasks
        if not trunk_available or not task_marker_on_main(
            root, key, str(task.get("id") or ""), refresh=False,
        )
    ]
    if missing_trunk_markers:
        problems.append(
            "every task must have its committed pr-ready marker on the trunk; "
            f"missing: {', '.join(missing_trunk_markers)}"
        )
    if not tasks:
        problems.append("recorded decomposition must contain at least one task")

    outcome = load_outcome(root) or {}
    if not outcome.get("outcome"):
        problems.append(
            "the shipped outcome — `forge.py outcome set \"<what changed and what "
            "someone can now do>\"` (one paragraph, in a reader's language)"
        )
    elif outcome.get("commit") != head:
        stamp = outcome.get("commit")
        shown = stamp[:8] if isinstance(stamp, str) and stamp else "missing"
        problems.append(
            f"outcome must be stamped at HEAD {expected} (got {shown}) — rerun "
            "`forge.py outcome set`"
        )
    return problems


SCHEMA_TYPES = {"str": str, "int": int, "bool": bool, "list": list, "dict": dict}


def schema_path(root: Path, name: str) -> Path:
    return root / "factory" / "schemas" / f"{name}.json"


def validate_payload(root: Path, name: str, payload: dict) -> None:
    """The determinism contract's front door: refuse any externally-authored
    artifact that does not match its factory/schemas/ spec, including a
    generated_by value outside the pinned allowlist. Extra keys are allowed."""
    path = schema_path(root, name)
    schema = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(
            f"REFUSED by factory/schemas/{path.name}:\n- payload must be a JSON object, "
            f"got {type(payload).__name__}"
        )
    problems: list[str] = []

    def check(field: str, kind: str, value: Any) -> None:
        ok = isinstance(value, SCHEMA_TYPES[kind])
        if kind != "bool" and isinstance(value, bool):
            ok = False
        if not ok:
            problems.append(f"'{field}' must be {kind}")

    for field, kind in schema.get("required", {}).items():
        if field not in payload:
            problems.append(f"missing required '{field}' ({kind})")
        else:
            check(field, kind, payload[field])
    for field, kind in schema.get("optional", {}).items():
        if field in payload:
            check(field, kind, payload[field])
    for field, bounds in (schema.get("ranges") or {}).items():
        value = payload.get(field)
        if isinstance(value, int) and not isinstance(value, bool):
            low, high = bounds
            if not (low <= value <= high):
                problems.append(f"'{field}' must be within {low}..{high} (got {value})")
    allowed = schema.get("generated_by", [])
    generator = payload.get("generated_by")
    if allowed and generator is not None and generator not in allowed:
        problems.append(
            f"generated_by {generator!r} is not pinned for this artifact — allowed: "
            f"{', '.join(allowed)}. Adopting a new tool is a harness PR "
            f"(harness.yaml + the schema file), never a local choice."
        )
    if problems:
        raise SystemExit(
            f"REFUSED by factory/schemas/{path.name}:\n- " + "\n- ".join(problems)
        )


REVIEW_GENERATION_FORMAT = "forge-review-generation/v1"
REVIEW_SELECTION_FORMAT = "forge-review-selection/v1"
_LOWER_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _review_set_schema(root: Path) -> dict:
    return json.loads(schema_path(root, "review-set").read_text(encoding="utf-8"))


def _review_set_fail(problems: list[str]) -> None:
    if problems:
        raise SystemExit(
            "REFUSED by factory/schemas/review-set.json:\n- " + "\n- ".join(problems)
        )


def validate_review_document(
    root: Path, document: dict, *, allow_missing_generation_id: bool = False,
) -> None:
    """Validate either exact review generation or exact selected pointer."""
    if not isinstance(document, dict):
        _review_set_fail(["document must be a JSON object"])
    schema = _review_set_schema(root)
    formats = schema.get("formats") or {}
    spec = formats.get(document.get("format"))
    if not isinstance(spec, dict):
        _review_set_fail([f"unknown format {document.get('format')!r}"])
    problems: list[str] = []
    if document.get("format") == REVIEW_SELECTION_FORMAT:
        expected = set(spec.get("fields") or [])
    else:
        origin = document.get("origin")
        origin_fields = spec.get("origin_fields") or {}
        if origin not in origin_fields:
            problems.append(f"origin must be one of {', '.join(origin_fields)}")
            expected = set(spec.get("common_fields") or [])
        else:
            expected = set(spec.get("common_fields") or []) | set(origin_fields[origin])
        if allow_missing_generation_id:
            expected.discard("generation_id")
    if set(document) != expected:
        problems.append(
            "fields must be exactly " + ", ".join(sorted(expected))
        )
    for field in (
        "format", "story", "task_id", "generation_id", "generation_sha256",
        "delta_id", "selected_at", "origin", "generated_by", "review_run_id",
        "brief_sha256", "inspected_commit", "recorded_at",
    ):
        if field in document and (
            not isinstance(document[field], str) or not document[field].strip()
        ):
            problems.append(f"{field} must be a non-empty string")
    for field in ("generation_id", "generation_sha256", "delta_id", "brief_sha256"):
        if field in document and not _LOWER_SHA256.fullmatch(str(document[field])):
            problems.append(f"{field} must be a lowercase SHA256")
    if document.get("format") == REVIEW_SELECTION_FORMAT:
        _review_set_fail(problems)
        return
    origin = document.get("origin")
    if document.get("generated_by") not in schema.get("generated_by", []):
        problems.append("generated_by is not pinned for review-set artifacts")
    if ((origin in {"combined", "rejection"} and document.get("generated_by") != "autoreview")
            or (origin == "upgrade" and document.get("generated_by") != "upgrade")):
        problems.append("generated_by does not match review generation origin")
    helper = document.get("helper")
    review_input = document.get("input")
    raw = document.get("raw_result")
    decoded = b""
    if origin in {"combined", "rejection"}:
        if not isinstance(helper, dict) or set(helper) != {"path", "version", "sha256"}:
            problems.append("helper needs exactly path, version, sha256")
        else:
            if any(not isinstance(helper[key], str) or not helper[key].strip()
                   for key in ("path", "version")):
                problems.append("helper path and version must be non-empty strings")
            if not _LOWER_SHA256.fullmatch(str(helper.get("sha256", ""))):
                problems.append("helper sha256 must be a lowercase SHA256")
        if not isinstance(review_input, dict) or set(review_input) != {"sha256", "bytes"}:
            problems.append("input needs exactly sha256 and bytes")
        elif (not _LOWER_SHA256.fullmatch(str(review_input.get("sha256", "")))
              or not isinstance(review_input.get("bytes"), int)
              or isinstance(review_input.get("bytes"), bool)
              or review_input["bytes"] < 0):
            problems.append("input needs a lowercase SHA256 and non-negative byte count")
        if not isinstance(raw, dict) or set(raw) != {"encoding", "sha256", "bytes", "data"}:
            problems.append("raw_result needs exactly encoding, sha256, bytes, data")
        else:
            try:
                decoded = base64.b64decode(raw.get("data", ""), validate=True)
            except (TypeError, ValueError):
                problems.append("raw_result data must be RFC4648 base64")
            if raw.get("encoding") != "base64":
                problems.append("raw_result encoding must be base64")
            if (not isinstance(raw.get("bytes"), int) or isinstance(raw.get("bytes"), bool)
                    or raw.get("bytes") != len(decoded)):
                problems.append("raw_result bytes must equal the decoded byte count")
            if raw.get("sha256") != hashlib.sha256(decoded).hexdigest():
                problems.append("raw_result sha256 does not match the decoded bytes")
            if (isinstance(raw.get("data"), str)
                    and base64.b64encode(decoded).decode("ascii") != raw["data"]):
                problems.append("raw_result data is not canonical RFC4648 base64")
    lenses = document.get("lenses")
    if not isinstance(lenses, dict) or set(lenses) != {
        "quality", "performance", "security",
    }:
        problems.append("lenses needs exactly quality, performance, security")
    else:
        for lens, payload in lenses.items():
            try:
                validate_payload(root, "review", payload)
            except SystemExit as exc:
                problems.append(f"{lens} lens is invalid: {exc}")
            if isinstance(payload, dict) and payload.get("task_id") != document.get("task_id"):
                problems.append(f"{lens} lens is not owned by {document.get('task_id')}")
            if not isinstance(payload, dict):
                continue
            if origin in {"combined", "rejection"}:
                for lens_field, generation_field in (
                    ("review_run_id", "review_run_id"),
                    ("brief_sha256", "brief_sha256"),
                    ("branch_diff_digest", "delta_id"),
                    ("commit", "inspected_commit"),
                ):
                    if payload.get(lens_field) != document.get(generation_field):
                        problems.append(
                            f"{lens} lens {lens_field} does not match generation "
                            f"{generation_field}"
                        )
            blocking = payload.get("blocking_findings")
            non_blocking = payload.get("non_blocking_findings", [])
            if isinstance(blocking, list) and isinstance(non_blocking, list):
                score = max(0, int(10 - 3 * len(blocking)
                                   - min(2.0, 0.5 * len(non_blocking))))
                recommendation = (
                    "request-changes" if blocking else
                    "approve-with-caveats" if non_blocking else "approve"
                )
                if payload.get("score") != score:
                    problems.append(f"{lens} lens score does not match its findings")
                if payload.get("recommendation") != recommendation:
                    problems.append(
                        f"{lens} lens recommendation does not match its findings"
                    )
    if origin == "rejection":
        rejection = document.get("rejection")
        if not isinstance(rejection, dict) or set(rejection) != {
            "source_generation_id", "source_generation_sha256",
            "root_generation_id", "history",
        }:
            problems.append("rejection needs exact source/root identity and history")
        else:
            for field in ("source_generation_id", "source_generation_sha256", "root_generation_id"):
                if not _LOWER_SHA256.fullmatch(str(rejection.get(field, ""))):
                    problems.append(f"rejection {field} must be a lowercase SHA256")
            history = rejection.get("history")
            if not isinstance(history, list) or not history:
                problems.append("rejection history must be non-empty")
            else:
                for index, entry in enumerate(history, 1):
                    if (not isinstance(entry, dict) or set(entry) != {
                        "finding_fingerprint", "reason", "citation", "actor",
                        "lesson_path", "lesson_sha256",
                    } or any(not isinstance(value, str) or not value.strip()
                             for value in entry.values())):
                        problems.append(f"rejection history[{index}] has an invalid shape")
                    elif (not _LOWER_SHA256.fullmatch(entry["finding_fingerprint"])
                          or not _LOWER_SHA256.fullmatch(entry["lesson_sha256"])
                          or Path(entry["lesson_path"]).is_absolute()
                          or any(part in {"", ".", ".."}
                                 for part in Path(entry["lesson_path"]).parts)):
                        problems.append(f"rejection history[{index}] has invalid identities")
    elif origin == "upgrade":
        upgrade = document.get("upgrade")
        if not isinstance(upgrade, dict) or set(upgrade) != {
            "inventory_digest", "source_kind", "legacy_artifacts", "sealed_commit",
        }:
            problems.append("upgrade needs exact inventory/source/artifact/seal fields")
        else:
            if not _LOWER_SHA256.fullmatch(str(upgrade.get("inventory_digest", ""))):
                problems.append("upgrade inventory_digest must be a lowercase SHA256")
            if upgrade.get("source_kind") != "sealed":
                problems.append("upgrade source_kind must be sealed")
            sealed = upgrade.get("sealed_commit")
            if not isinstance(sealed, str) or not sealed.strip():
                problems.append("sealed upgrade needs sealed_commit")
            artifacts = upgrade.get("legacy_artifacts")
            if not isinstance(artifacts, list) or len(artifacts) != 3:
                problems.append("upgrade legacy_artifacts needs three entries")
            else:
                expected_aspects = ["performance", "quality", "security"]
                if [entry.get("aspect") if isinstance(entry, dict) else None
                        for entry in artifacts] != expected_aspects:
                    problems.append("upgrade legacy_artifacts must be sorted by aspect")
                for entry in artifacts:
                    if (not isinstance(entry, dict) or set(entry) != {"aspect", "path", "sha256"}
                            or not isinstance(entry.get("path"), str)
                            or not _LOWER_SHA256.fullmatch(str(entry.get("sha256", "")))):
                        problems.append("upgrade legacy artifact has an invalid shape")
                        break
    if origin in {"combined", "rejection"}:
        try:
            raw_report = json.loads(decoded.decode("utf-8"))
            from forge_cli.review import _actual_passes, _pass_sections, _tagged_finding
            raw_passes = _actual_passes(raw_report)
            for _label, provider in raw_passes:
                _pass_sections(provider)
                findings = provider.get("findings", [])
                if not isinstance(findings, list):
                    raise SystemExit("combined review pass findings must be a list")
                for finding in findings:
                    _tagged_finding(finding)
            merged = raw_report.get("findings", [])
            if not isinstance(merged, list):
                raise SystemExit("combined review findings must be a list")
            for finding in merged:
                _tagged_finding(finding)
        except (UnicodeDecodeError, json.JSONDecodeError, SystemExit) as exc:
            problems.append(f"raw_result is not a valid combined helper report: {exc}")
    _review_set_fail(problems)


def review_generation_id(document: dict) -> str:
    content = {key: value for key, value in document.items() if key != "generation_id"}
    canonical = json.dumps(
        content, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def review_generation_bytes(document: dict) -> bytes:
    return (json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def review_finding_fingerprint(finding: object) -> str:
    if not isinstance(finding, dict):
        raise SystemExit("review finding identity must be an object")
    identity = {field: finding.get(field) for field in ("file_path", "line", "title")}
    if (not isinstance(identity["file_path"], str) or not identity["file_path"]
            or not isinstance(identity["line"], int) or isinstance(identity["line"], bool)
            or identity["line"] < 1 or not isinstance(identity["title"], str)
            or not identity["title"]):
        title = identity["title"]
        category = finding.get("category")
        area = finding.get("area")
        summary = finding.get("summary")
        match = (re.fullmatch(
            r"VERDICT (?P<contract>[A-Za-z0-9._:-]+): "
            r"(?P<verdict>partial|missing)", str(title or ""),
        ) if isinstance(title, str) else None)
        if (finding.get("file_path") == "" and finding.get("line") is None
                and match and category == f"plan-contract-{match['verdict']}"
                and isinstance(area, str) and area.strip()
                and isinstance(summary, str)
                and summary.startswith(f"{match['contract']}:")):
            identity = {
                "kind": "plan-contract-verdict",
                "area": area,
                "contract_id": match["contract"],
                "verdict": match["verdict"],
                "summary": summary,
            }
        else:
            raise SystemExit("review finding identity needs file_path, line, and title")
    canonical = json.dumps(
        identity, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def classify_scope_entries(root: Path, scope: list[str], revision: str) -> list[str]:
    """Preserve exact entries; mark only explicit or baseline Git trees as dirs."""
    classified: list[str] = []
    for entry in scope:
        raw = entry.strip()
        if not raw:
            continue
        path = raw.rstrip("/")
        is_directory = raw.endswith("/")
        if not is_directory and revision:
            result = subprocess.run(
                ["git", "cat-file", "-t", f"{revision}:{path}"], cwd=root,
                capture_output=True, text=True, env=clean_git_env(), encoding="utf-8",
            )
            is_directory = result.returncode == 0 and result.stdout.strip() == "tree"
        classified.append(path + ("/" if is_directory else ""))
    return classified


def _rejection_successor_problems(
    candidate: dict, source: dict, source_sha256: str,
) -> list[str]:
    problems: list[str] = []
    if source.get("origin") not in {"combined", "rejection"}:
        return ["rejection source must be a combined or rejection generation"]
    for field in (
        "format", "generated_by", "story", "task_id", "review_run_id",
        "brief_sha256", "inspected_commit", "delta_id", "helper", "input",
        "raw_result",
    ):
        if candidate.get(field) != source.get(field):
            problems.append(f"rejection changed preserved {field}")
    rejection = candidate.get("rejection") or {}
    if rejection.get("source_generation_id") != source.get("generation_id"):
        problems.append("rejection source_generation_id does not name its source")
    if rejection.get("source_generation_sha256") != source_sha256:
        problems.append("rejection source_generation_sha256 does not hash its source file")
    expected_root = (source.get("rejection") or {}).get(
        "root_generation_id", source.get("generation_id"))
    if rejection.get("root_generation_id") != expected_root:
        problems.append("rejection root_generation_id does not name the combined root")
    history = rejection.get("history")
    source_history = ((source.get("rejection") or {}).get("history") or [])
    if (not isinstance(history, list) or history[:-1] != source_history
            or len(history) != len(source_history) + 1):
        problems.append("rejection history must append exactly one source entry")
        return problems
    entry = history[-1]
    source_lenses = source.get("lenses") or {}
    candidate_lenses = candidate.get("lenses") or {}
    changed = [lens for lens in ("quality", "performance", "security")
               if candidate_lenses.get(lens) != source_lenses.get(lens)]
    if len(changed) != 1:
        problems.append("rejection must change exactly one lens")
        return problems
    lens = changed[0]
    original = source_lenses[lens]
    blocking = original.get("blocking_findings") or []
    matches = []
    for finding in blocking:
        try:
            fingerprint = review_finding_fingerprint(finding)
        except SystemExit:
            # Malformed ordinary findings cannot be the exact source selected
            # for rejection; the count check below refuses the successor.
            continue
        if fingerprint == entry.get("finding_fingerprint"):
            matches.append(finding)
    if len(matches) != 1:
        problems.append("rejection history does not identify one source blocking finding")
        return problems
    finding = matches[0]
    expected = copy.deepcopy(original)
    expected["blocking_findings"].remove(finding)
    expected.setdefault("rejected_findings", []).append({
        "finding": finding,
        "reason": entry["reason"],
        "cite": entry["citation"],
        "rejected_at": candidate.get("recorded_at"),
        "rejected_by": entry["actor"],
        "task_id": candidate.get("task_id"),
    })
    remaining = len(expected["blocking_findings"])
    caveats = len(expected.get("non_blocking_findings") or [])
    expected["score"] = max(0, int(10 - 3 * remaining - min(2.0, 0.5 * caveats)))
    expected["recommendation"] = (
        "request-changes" if remaining else
        "approve-with-caveats" if caveats else "approve"
    )
    if candidate_lenses.get(lens) != expected:
        problems.append("rejection lens is not the exact one-finding successor")
    return problems


def _review_relpaths(key: str, task_id: str, generation_id: str = "") -> tuple[str, str]:
    base = f".factory/stories/{key}/tasks/{task_id}/reviews"
    generation = f"{base}/generations/{generation_id}.json" if generation_id else ""
    return generation, f"{base}/selected.json"


def _safe_review_leaf(
    root: Path, path: Path, *, required: bool, create_parents: bool = False,
    links: int = 1,
) -> bool:
    try:
        relative = path.relative_to(root)
        current = root
        root_info = current.lstat()
        if (not stat.S_ISDIR(root_info.st_mode) or current.is_symlink()
                or _windows_reparse_point(current)):
            return False
        for part in relative.parts[:-1]:
            current = current / part
            try:
                info = current.lstat()
            except FileNotFoundError:
                if not create_parents:
                    return False
                current.mkdir()
                info = current.lstat()
            if (not stat.S_ISDIR(info.st_mode) or current.is_symlink()
                    or _windows_reparse_point(current)):
                return False
        try:
            info = path.lstat()
        except FileNotFoundError:
            return not required
        return (stat.S_ISREG(info.st_mode) and not path.is_symlink()
                and not _windows_reparse_point(path) and info.st_nlink == links)
    except (OSError, ValueError):
        return False


def _read_review_bytes(root: Path, path: Path) -> bytes:
    if not _safe_review_leaf(root, path, required=True):
        raise SystemExit(f"unsafe review proof path: {path}")
    return path.read_bytes()


def read_selected_review_generation(
    root: Path, key: str, task_id: str, *,
    reader: Callable[[str], dict | None] | None = None,
    bytes_reader: Callable[[str], bytes | None] | None = None,
    expected_delta_id: str = "", sealed_commit: str = "",
    consumed_paths: set[str] | None = None,
) -> tuple[dict | None, dict | None, list[str]]:
    """Read and recompute the one selected immutable generation."""
    _generation_unused, selection_rel = _review_relpaths(key, task_id)
    if consumed_paths is not None:
        consumed_paths.add(selection_rel)
    try:
        if reader is None:
            selection_bytes = _read_review_bytes(root, root / selection_rel)
            selection = json.loads(selection_bytes)
        else:
            selection = reader(selection_rel)
            selection_bytes = bytes_reader(selection_rel) if bytes_reader else None
            if selection_bytes is None:
                return None, None, [f"{task_id}: selected review pointer is missing"]
        validate_review_document(root, selection)
        generation_rel, _ = _review_relpaths(key, task_id, selection["generation_id"])
        if consumed_paths is not None:
            consumed_paths.add(generation_rel)
        if reader is None:
            generation_bytes = _read_review_bytes(root, root / generation_rel)
            generation = json.loads(generation_bytes)
        else:
            generation = reader(generation_rel)
            generation_bytes = bytes_reader(generation_rel) if bytes_reader else None
            if generation_bytes is None:
                return None, selection, [f"{task_id}: selected review generation is missing"]
        validate_review_document(root, generation)
    except (OSError, UnicodeError, json.JSONDecodeError, SystemExit) as exc:
        return None, None, [f"{task_id}: selected review proof is invalid: {exc}"]
    problems: list[str] = []
    if generation.get("generation_id") != review_generation_id(generation):
        problems.append(f"{task_id}: selected review generation id does not recompute")
    generation_sha = hashlib.sha256(generation_bytes).hexdigest()
    if selection.get("generation_sha256") != generation_sha:
        problems.append(f"{task_id}: selected review generation file hash does not match")
    for field in ("story", "task_id", "generation_id", "delta_id"):
        if selection.get(field) != generation.get(field):
            problems.append(f"{task_id}: selected review {field} does not match its generation")
    if selection.get("story") != key or selection.get("task_id") != task_id:
        problems.append(f"{task_id}: selected review pointer is copied from another task")
    if expected_delta_id and selection.get("delta_id") != expected_delta_id:
        problems.append(f"{task_id}: selected review generation is stale for the current delta")
    if generation.get("origin") == "upgrade":
        upgrade = generation.get("upgrade") or {}
        if upgrade.get("source_kind") == "sealed":
            if not sealed_commit or upgrade.get("sealed_commit") != sealed_commit:
                problems.append(
                    f"{task_id}: upgrade review generation lacks the exact sealed binding"
                )
        elif sealed_commit:
            problems.append(
                f"{task_id}: active upgrade generation cannot certify a sealed task"
            )
    if not problems and generation.get("origin") == "rejection":
        descendant = generation
        seen: set[str] = set()
        while descendant.get("origin") == "rejection":
            descendant_id = str(descendant.get("generation_id") or "")
            if descendant_id in seen:
                problems.append(f"{task_id}: rejection review lineage contains a cycle")
                break
            seen.add(descendant_id)
            source_id = str((descendant.get("rejection") or {}).get(
                "source_generation_id") or "")
            source_rel, _ = _review_relpaths(key, task_id, source_id)
            if consumed_paths is not None:
                consumed_paths.add(source_rel)
            try:
                if reader is None:
                    source_bytes = _read_review_bytes(root, root / source_rel)
                    source = json.loads(source_bytes)
                else:
                    source = reader(source_rel)
                    source_bytes = bytes_reader(source_rel) if bytes_reader else None
                    if source_bytes is None or not isinstance(source, dict):
                        raise ValueError("source generation is missing")
                validate_review_document(root, source)
            except (OSError, UnicodeError, json.JSONDecodeError, ValueError, SystemExit) as exc:
                problems.append(f"{task_id}: rejection review source is invalid: {exc}")
                break
            if source.get("generation_id") != review_generation_id(source):
                problems.append(f"{task_id}: rejection source generation id does not recompute")
                break
            source_sha = hashlib.sha256(source_bytes).hexdigest()
            lineage = _rejection_successor_problems(descendant, source, source_sha)
            if lineage:
                problems.extend(f"{task_id}: {problem}" for problem in lineage)
                break
            lesson = descendant["rejection"]["history"][-1]
            lesson_rel = lesson["lesson_path"]
            if consumed_paths is not None:
                consumed_paths.add(lesson_rel)
            try:
                lesson_bytes = (
                    _read_review_bytes(root, root / lesson_rel)
                    if reader is None else
                    (bytes_reader(lesson_rel) if bytes_reader else None)
                )
                if lesson_bytes is None:
                    raise ValueError("lesson is missing")
            except (OSError, ValueError, SystemExit) as exc:
                problems.append(f"{task_id}: rejection lesson is invalid: {exc}")
                break
            if hashlib.sha256(lesson_bytes).hexdigest() != lesson["lesson_sha256"]:
                problems.append(f"{task_id}: rejection lesson hash does not match")
                break
            descendant = source
    return generation, selection, problems


def review_lineage_paths(root: Path, key: str, task_id: str) -> list[Path]:
    """Return every immutable generation and lesson needed to seal selection."""
    generation, _selection, problems = read_selected_review_generation(root, key, task_id)
    if problems or not isinstance(generation, dict):
        raise SystemExit("invalid selected review lineage: " + "; ".join(
            problems or ["selected generation is missing"]
        ))
    paths: list[Path] = []
    seen_lessons: set[str] = set()
    current = generation
    while True:
        generation_rel, _ = _review_relpaths(key, task_id, current["generation_id"])
        paths.append(Path(generation_rel))
        if current.get("origin") != "rejection":
            break
        for entry in current["rejection"]["history"]:
            lesson = entry["lesson_path"]
            if lesson not in seen_lessons:
                seen_lessons.add(lesson)
                paths.append(Path(lesson))
        source_rel, _ = _review_relpaths(
            key, task_id, current["rejection"]["source_generation_id"])
        current = json.loads(_read_review_bytes(root, root / source_rel))
    return paths


def selected_review_problems(
    root: Path, key: str, task_id: str, delta_id: str,
) -> list[str]:
    generation, _selection, problems = read_selected_review_generation(
        root, key, task_id, expected_delta_id=delta_id,
    )
    if problems or not isinstance(generation, dict):
        return problems or [f"{task_id}: selected review generation is missing"]
    from forge_cli.readiness import review_passed
    for lens in ("quality", "performance", "security"):
        if not review_passed(generation["lenses"].get(lens)):
            problems.append(f"{task_id}: selected {lens} review is not clean")
    return problems


def _publish_immutable_review_file(root: Path, destination: Path, body: bytes) -> None:
    temporary = destination.with_name(f".{destination.name}.{os.getpid()}.tmp")
    if _safe_review_leaf(root, destination, required=True, links=2):
        destination_info = destination.lstat()
        prefix = f".{destination.name}."
        candidates = [
            path for path in destination.parent.iterdir()
            if path.name.startswith(prefix) and path.name.endswith(".tmp")
            and path.name[len(prefix):-4].isdigit()
        ]
        if len(candidates) != 1 or not _safe_review_leaf(
                root, candidates[0], required=True, links=2):
            raise SystemExit("unsafe interrupted review generation links")
        temporary = candidates[0]
        temporary_info = temporary.lstat()
        same_inode = ((destination_info.st_dev, destination_info.st_ino)
                      == (temporary_info.st_dev, temporary_info.st_ino))
        if not same_inode or destination.read_bytes() != body \
                or temporary.read_bytes() != body:
            raise SystemExit("interrupted review generation link does not match")
        temporary.unlink()
    if not _safe_review_leaf(root, destination, required=False, create_parents=True):
        raise SystemExit(f"unsafe review generation destination: {destination}")
    if destination.exists():
        if _read_review_bytes(root, destination) != body:
            raise SystemExit("review generation id collision with unequal bytes")
        return
    if not _safe_review_leaf(root, temporary, required=False, create_parents=True):
        raise SystemExit(f"unsafe review generation temporary path: {temporary}")
    # The readback below compares bytes: raw_open_flags keeps LF as LF on
    # Windows, or every generation refused (temporary readback differs).
    flags = raw_open_flags(
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0))
    descriptor = os.open(temporary, flags, 0o600)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise SystemExit("review generation temporary leaf is not a single-link file")
        view = memoryview(body)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise SystemExit("review generation temporary write was incomplete")
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    try:
        if _read_review_bytes(root, temporary) != body:
            raise SystemExit("review generation temporary readback differs")
        try:
            os.link(temporary, destination, follow_symlinks=False)
        except FileExistsError:
            if _read_review_bytes(root, destination) != body:
                raise SystemExit("review generation id collision with unequal bytes")
        temporary.unlink()
        if _read_review_bytes(root, destination) != body:
            raise SystemExit("published review generation readback differs")
    finally:
        if temporary.exists() and not temporary.is_symlink():
            temporary.unlink()


def _replace_review_selection(root: Path, destination: Path, selection: dict) -> None:
    body = review_generation_bytes(selection)
    if not _safe_review_leaf(root, destination, required=False, create_parents=True):
        raise SystemExit(f"unsafe review selection destination: {destination}")
    temporary = destination.with_name(f".{destination.name}.{os.getpid()}.tmp")
    if not _safe_review_leaf(root, temporary, required=False, create_parents=True):
        raise SystemExit(f"unsafe review selection temporary path: {temporary}")
    descriptor = os.open(  # raw_open_flags: see _publish_immutable_review_file
        temporary, raw_open_flags(
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)),
        0o600,
    )
    try:
        view = memoryview(body)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise SystemExit("review selection temporary write was incomplete")
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    try:
        if _read_review_bytes(root, temporary) != body:
            raise SystemExit("review selection temporary readback differs")
        os.replace(temporary, destination)
        if _read_review_bytes(root, destination) != body:
            raise SystemExit("published review selection readback differs")
    finally:
        if temporary.exists() and not temporary.is_symlink():
            temporary.unlink()


def publish_review_generation(
    root: Path, key: str, task_id: str, candidate: dict, *,
    expected_source_id: str = "", update_stamp: bool = False,
    lesson_records: list[tuple[str, bytes]] = (),
    on_selection_lock_wait: Callable[[], None] | None = None,
) -> tuple[dict, dict]:
    """Publish generation first and selected.json last under one protected lock."""
    validate_review_document(root, candidate, allow_missing_generation_id=True)
    if candidate.get("story") != key or candidate.get("task_id") != task_id:
        raise SystemExit("review generation is copied from another story or task")
    generation = dict(candidate)
    generation["generation_id"] = review_generation_id(generation)
    validate_review_document(root, generation)
    generation_body = review_generation_bytes(generation)
    generation_sha = hashlib.sha256(generation_body).hexdigest()
    generation_rel, selection_rel = _review_relpaths(key, task_id, generation["generation_id"])
    from forge_cli.delegate import delegation_exclusion
    if on_selection_lock_wait is not None:
        on_selection_lock_wait()
    with delegation_exclusion(
        root, task_id, kind="review-selection",
    ):
        if update_stamp and generation.get("origin") in {"combined", "rejection"}:
            from forge_cli.stages import (
                load_stages, require_current_review_meaning, task_for,
            )
            stage = next((row for row in load_stages(root).get("stages", [])
                          if row.get("id") == task_id), {})
            require_current_review_meaning(
                root, stage, task_for(root, task_id), generation,
            )
        current = None
        selection_path = root / selection_rel
        if selection_path.exists() or selection_path.is_symlink():
            current_bytes = _read_review_bytes(root, selection_path)
            try:
                current = json.loads(current_bytes)
                validate_review_document(root, current)
            except (json.JSONDecodeError, SystemExit) as exc:
                raise SystemExit(f"current review selection is invalid: {exc}") from exc
        if expected_source_id and (
            not isinstance(current, dict) or current.get("generation_id") != expected_source_id
        ):
            raise SystemExit("review selection changed before rejection publication")
        if generation.get("origin") == "rejection":
            rejection = generation["rejection"]
            if not current or rejection["source_generation_id"] != current.get("generation_id") \
                    or rejection["source_generation_sha256"] != current.get("generation_sha256"):
                raise SystemExit("rejection source is not the currently selected generation")
            source_rel, _ = _review_relpaths(key, task_id, current["generation_id"])
            source_bytes = _read_review_bytes(root, root / source_rel)
            try:
                source = json.loads(source_bytes)
                validate_review_document(root, source)
            except (json.JSONDecodeError, SystemExit) as exc:
                raise SystemExit(f"selected rejection source is invalid: {exc}") from exc
            if source.get("generation_id") != review_generation_id(source) \
                    or hashlib.sha256(source_bytes).hexdigest() != current.get(
                        "generation_sha256"):
                raise SystemExit("selected rejection source identity is invalid")
            lineage = _rejection_successor_problems(
                generation, source, hashlib.sha256(source_bytes).hexdigest(),
            )
            _review_set_fail(lineage)
            selected_source, _selected_pointer, source_problems = (
                read_selected_review_generation(
                    root, key, task_id, expected_delta_id=generation["delta_id"],
                )
            )
            if (source_problems or not isinstance(selected_source, dict)
                    or selected_source.get("generation_id") != source.get("generation_id")):
                raise SystemExit(
                    "selected rejection source lineage is invalid: "
                    + "; ".join(source_problems or ["wrong selected source"])
                )
        if generation.get("origin") in {"combined", "rejection"}:
            live_head = head_sha(root) or ""
            if generation.get("inspected_commit") != live_head:
                raise SystemExit("review generation inspected_commit is no longer current HEAD")
            live_delta = product_delta_digest(
                root, effective_review_base(root, task_id, live_head),
            )
            if generation.get("delta_id") != live_delta:
                raise SystemExit("review generation delta_id is stale at publication")
        for lesson_rel, lesson_body in lesson_records:
            lesson_path = root / lesson_rel
            _publish_immutable_review_file(root, lesson_path, lesson_body)
        if generation.get("origin") == "rejection":
            newest = generation["rejection"]["history"][-1]
            lesson_bytes = _read_review_bytes(root, root / newest["lesson_path"])
            if hashlib.sha256(lesson_bytes).hexdigest() != newest["lesson_sha256"]:
                raise SystemExit("rejection lesson hash does not match before publication")
        _publish_immutable_review_file(root, root / generation_rel, generation_body)
        if current and current.get("generation_id") == generation["generation_id"] \
                and current.get("generation_sha256") == generation_sha:
            selection = current
        else:
            selection = {
                "format": REVIEW_SELECTION_FORMAT, "story": key, "task_id": task_id,
                "generation_id": generation["generation_id"],
                "generation_sha256": generation_sha, "delta_id": generation["delta_id"],
                "selected_at": now_iso(),
            }
            validate_review_document(root, selection)
            if expected_source_id:
                latest = json.loads(_read_review_bytes(root, selection_path))
                if latest.get("generation_id") != expected_source_id:
                    raise SystemExit("review selection changed before pointer replacement")
            _replace_review_selection(root, selection_path, selection)
        published, _pointer, published_problems = read_selected_review_generation(
            root, key, task_id, expected_delta_id=generation["delta_id"],
            sealed_commit=(generation.get("upgrade") or {}).get("sealed_commit", "")
            if generation.get("origin") == "upgrade" else "",
        )
        if published_problems or not isinstance(published, dict) \
                or published.get("generation_id") != generation["generation_id"]:
            raise SystemExit(
                "selected review generation failed readback: "
                + "; ".join(published_problems or ["wrong selected generation"])
            )
        if update_stamp:
            blocking = sum(
                len(lens.get("blocking_findings") or [])
                for lens in generation["lenses"].values()
            )
            from forge_cli.stages import revoke_stage_review_stamp, stamp_stage_review
            if blocking:
                revoke_stage_review_stamp(root, task_id)
            else:
                stamp_stage_review(root, task_id, lenses=("quality", "performance", "security"))
        return generation, selection


def head_sha(root: Path | None = None) -> str | None:
    proc = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root or repo_root(),
        capture_output=True, text=True, env=clean_git_env(), encoding="utf-8",
    )
    return proc.stdout.strip() if proc.returncode == 0 else None


def active_task_user_facing(root: Path) -> bool:
    """Design-skill enforcement is PER TASK, not per story. A user_facing story
    (e.g. one whose web app is a later task) still contains backend tasks with
    no UI; forcing those to attest UI design skills is the bug this resolves.
    Resolve the active stage's task and read ITS OWN user_facing flag, defaulting
    to False when the task does not declare one — the planner marks UI tasks
    user_facing: true, and the task grill enforces that a user_facing story does
    so for the task(s) that build UI."""
    stages = load_json(git_control_dir(root) / "stages.json", default={})
    active = next((s for s in stages.get("stages", [])
                   if isinstance(s, dict) and s.get("status") == "active"), None)
    if not active:
        return False
    decomposition = load_json(
        protected_decomposition_state_path(root), default={})
    task = next((t for t in decomposition.get("tasks", [])
                 if isinstance(t, dict) and t.get("id") == active.get("id")), {})
    return bool(task.get("user_facing"))


def require_skills(root: Path, name: str, payload: dict) -> None:
    """Feature-type skill enforcement (same trust model as generated_by):
    when the ACTIVE TASK is user_facing, the artifact must ATTEST the phase's
    mandatory skills in skills_used. Advisory skills are listed too when used,
    but only the required set gates."""
    schema = json.loads(schema_path(root, name).read_text(encoding="utf-8"))
    required = schema.get("required_skills", {})
    if not required:
        return
    if not active_task_user_facing(root):
        return
    used = payload.get("skills_used") or []
    missing = [s for s in required.get("user_facing", []) if s not in used]
    if missing:
        raise SystemExit(
            f"user-facing task: this artifact must attest the mandatory design skills "
            f"in skills_used — missing: {', '.join(missing)}. Load them, do the work "
            "with them, and list them (pinned in harness.yaml; installed by doctor)."
        )


def sha256_of(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _grill_exempt(rel: str, ignore_names: tuple[str, ...]) -> bool:
    # Expected exhaust is DECISION RECORDS only — a product doc whose name
    # merely contains an ignore token must still stale the grill.
    return rel.startswith("docs/decisions/") and any(
        token in Path(rel).name for token in ignore_names
    )


def grill_key_suffix(
    gate: str, task_id: str = "", artifact: str | Path = "",
    root: Path | None = None,
) -> str:
    """Suffix a task grill by id and a chosen-file grill by its path."""
    if gate == "task":
        return task_id
    if gate not in {"spec", "epics"} or not artifact:
        return ""
    base = (root or repo_root()).resolve()
    path = Path(artifact).expanduser()
    if not path.is_absolute():
        path = base / path
    path = path.resolve()
    key_path = path.relative_to(base).as_posix() if path.is_relative_to(base) else path.as_posix()
    return f"{path.stem}-{hashlib.sha256(key_path.encode('utf-8')).hexdigest()[:16]}"


def grill_evidence_name(
    gate: str, task_id: str = "", artifact: str | Path = "",
    root: Path | None = None,
) -> str:
    suffix = grill_key_suffix(gate, task_id, artifact, root)
    if gate == "task":
        return f"grills/tasks/{suffix}.json"
    return f"grills/{gate}{'-' + suffix if suffix else ''}.json"


def require_grill(
    root: Path,
    gate: str,
    prefixes: tuple[str, ...],
    ignore_names: tuple[str, ...] = (),
    expect_digest_of: Path | None = None,
) -> None:
    """Handover gates call this: a fresh, passing grill or no passage.

    `ignore_names` filters expected exhaust (decision records created AFTER
    the grill) from staleness. `expect_digest_of` binds the grill to the
    exact artifact being gated: the recorded input_sha256 must match that
    file, so grilling proposal A never approves proposal B."""
    key = _active_story_key(root) if gate == "plan" else ""
    name = grill_evidence_name(gate, artifact=expect_digest_of or "", root=root)
    path = evidence_path(root, key, name)
    data = load_json(path, default={})
    if (gate in {"spec", "epics"} and expect_digest_of is not None
            and not path.exists()):
        legacy = load_json(
            evidence_path(root, key, f"grills/{gate}.json"), default={},
        )
        if legacy.get("input_sha256") == sha256_of(expect_digest_of):
            data = legacy
    if not data:
        raise SystemExit(
            f"Handover grill required first: interrogate the handover for gaps and "
            f"contradictions per factory/prompts/griller.md, resolve findings, then record "
            f"`python3 factory/scripts/record_grill_from_json.py --gate {gate}`."
        )
    if any(field not in data for field in (
            "cold_input_sha256", "final_artifact_sha256",
            "finding_dispositions")):
        raise SystemExit(
            f"the {gate} grill uses a removed coldless authority format; "
            "run `forge upgrade` before continuing."
        )
    if data.get("verdict") != "pass":
        raise SystemExit(
            f".factory/grills/{gate}.json verdict is {data.get('verdict')!r} — resolve the "
            "recorded findings and re-grill; this gate needs a pass."
        )
    if not data.get("commit") and head_sha(root):
        raise SystemExit(
            f".factory/grills/{gate}.json has no commit stamp — re-record with current tooling."
        )
    if expect_digest_of is not None:
        actual = (
            plan_digest_without_assumptions(expect_digest_of)
            if gate == "plan"
            else sha256_of(expect_digest_of)
        )
        if data.get("input_sha256") != actual:
            raise SystemExit(
                f"the {gate} grill was not recorded against THIS input "
                f"({expect_digest_of.name}) — re-grill the current version and record with "
                f"`record_grill_from_json.py --gate {gate} --input-digest {expect_digest_of}`."
            )
    stale = [
        f for f in changed_since(root, data.get("commit") or "", prefixes)
        if not _grill_exempt(f, ignore_names)
    ]
    # Freshness includes the WORKING TREE: uncommitted edits to guarded docs
    # must stale the grill just like committed ones.
    proc = subprocess.run(["git", "status", "--porcelain"], cwd=root,
                          capture_output=True, text=True,
                          encoding="utf-8", errors="surrogateescape")
    if proc.returncode == 0:
        for line in proc.stdout.splitlines():
            rel = line[3:].split(" -> ")[-1].strip().strip('"')
            if rel.startswith(prefixes) and not _grill_exempt(rel, ignore_names):
                stale.append(f"{rel} (uncommitted)")
    if stale:
        advice = (
            f"Commit it, then run `forge grill run --gate {gate}` again."
            if any("(uncommitted)" in entry for entry in stale)
            else "Re-run the grill against the current docs."
        )
        raise SystemExit(
            f"the {gate} grill is STALE — handover docs changed since it ran: "
            f"{', '.join(stale[:5])}. {advice}"
        )


def require_task_grill(
    root: Path, task_id: str, task: dict, *, treeish: str = "",
) -> None:
    """Require a passing grill bound to the current grounding inputs."""
    key = _active_story_key(root)
    path = evidence_path(root, key, f"grills/tasks/{task_id}.json")
    data = load_json(path, default={})
    record_command = (
        "python3 factory/scripts/record_grill_from_json.py --gate task "
        f"--task {task_id}"
    )
    if not data:
        raise SystemExit(
            f"Task grill required first: grill {task_id}, resolve findings, then record "
            f"`{record_command}`."
        )
    cold_fields = (
        "cold_input_sha256", "final_artifact_sha256", "finding_dispositions",
    )
    missing_cold_field = any(field not in data for field in cold_fields)
    legacy_inflight = (
        missing_cold_field
        and _legacy_inflight_task_grill(root, task, data, treeish=treeish)
    )
    if missing_cold_field and not legacy_inflight:
        raise SystemExit(
            f"the {task_id} task grill uses a removed coldless authority format; "
            "run `forge upgrade` before continuing."
        )
    if not legacy_inflight:
        if any(
            not isinstance(data.get(field), str)
            or re.fullmatch(r"[0-9a-f]{64}", data[field]) is None
            for field in cold_fields[:2]
        ) or not isinstance(data["finding_dispositions"], list):
            raise SystemExit(
                f".factory/grills/tasks/{task_id}.json has malformed cold proof; "
                f"re-record `{record_command}`."
            )
        if data["cold_input_sha256"] != data["final_artifact_sha256"]:
            amendments = data.get("amendments")
            artifact_delta = data.get("artifact_delta")
            disposition_findings = {
                entry["finding"] for entry in data["finding_dispositions"]
                if isinstance(entry, dict)
                and isinstance(entry.get("finding"), str)
            }
            indexes = []
            if (not isinstance(amendments, list) or not amendments
                    or not isinstance(artifact_delta, list)):
                raise SystemExit(
                    f".factory/grills/tasks/{task_id}.json has a malformed "
                    f"amendment bridge; re-record `{record_command}`."
                )
            for amendment in amendments:
                findings = (amendment.get("findings")
                            if isinstance(amendment, dict) else None)
                if (
                    not isinstance(amendment, dict)
                    or any(
                        not isinstance(amendment.get(field), str)
                        or not amendment[field].strip()
                        for field in ("change", "reason", "source")
                    )
                    or not isinstance(findings, list) or not findings
                    or any(not isinstance(finding, str) for finding in findings)
                    or len(set(findings)) != len(findings)
                    or any(finding not in disposition_findings for finding in findings)
                    or type(amendment.get("delta_index")) is not int
                ):
                    raise SystemExit(
                        f".factory/grills/tasks/{task_id}.json has a malformed "
                        f"amendment bridge; re-record `{record_command}`."
                    )
                indexes.append(amendment["delta_index"])
            if sorted(indexes) != list(range(len(artifact_delta))):
                raise SystemExit(
                    f".factory/grills/tasks/{task_id}.json has a malformed "
                    f"amendment bridge; re-record `{record_command}`."
                )
    if data.get("verdict") != "pass":
        raise SystemExit(
            f".factory/grills/tasks/{task_id}.json verdict is "
            f"{data.get('verdict')!r} — resolve the recorded findings, re-grill, then "
            f"record `{record_command}`; this gate needs a pass."
        )
    if not data.get("commit"):
        raise SystemExit(
            f".factory/grills/tasks/{task_id}.json has no commit stamp — re-record "
            f"with current tooling using `{record_command}`."
        )
    if not task_grill_grounding_matches(root, task, data, treeish=treeish):
        # A digest mismatch has two very different causes, and reporting both as
        # "STALE" sent a reader hunting for a content change that never
        # happened. When the grill was ground on a DIFFERENT BASIS than the one
        # being checked, the inputs may be identical -- the two sides simply
        # measured against different trees, which no amount of re-grilling in
        # the wrong directory can converge.
        required_basis = "stage-baseline" if treeish else "working-tree"
        recorded_basis = data.get("grounding_basis")
        if recorded_basis and recorded_basis != required_basis:
            home = task_state_root(root, task_id)
            where = (f"cd {home} && " if home.resolve() != root.resolve() else "")
            raise SystemExit(
                f"the {task_id} task grill was ground on the {recorded_basis}, "
                f"but this task's stage requires the {required_basis}. The grill "
                "itself may be perfectly good — the two sides measured against "
                "different trees, which happens when the grill is recorded "
                "outside the task's own worktree (stage state lives per "
                "worktree, and the copies drift). Re-record it from the task's "
                f"worktree: `{where}{record_command}`. Nothing needs re-deciding "
                "and no digest should be edited by hand — the recorder computes "
                "it, and from there it computes the right one."
            )
        raise SystemExit(
            f"the {task_id} task grill is STALE — its grounding inputs changed. "
            f"Re-grill and record `{record_command}`; --task-digest was removed "
            "because the digest is derived from the protected contract, approved "
            "plan, and product tree. Tip: record the task grill LAST, immediately "
            "before native approval / `stage start` — committing any tracked file "
            "outside .factory/ and plans/ (docs/, factory/scripts/, source) between "
            "grilling and approving changes the product tree and re-stales it."
        )


def task_digest(task: dict) -> str:
    """Return the unchanged four-field stage measurement digest."""
    payload = json.dumps(
        {
            key: task.get(key)
            for key in (
                "write_scope",
                "required_tests",
                "verify_commands",
                "acceptance_criteria",
            )
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def measurement_contract(task: dict) -> dict:
    """Return the fields an active stage measures mechanically."""
    return {field: task.get(field) for field in MEASUREMENT_CONTRACT_FIELDS}


def task_plan_binding_digest(root: Path, task_id: str, grill: dict) -> str:
    """Return the live approved task-plan digest, or ``""`` on any mismatch."""
    plan = evidence_path(
        root, _active_story_key(root), f"task-plans/{task_id}.md",
    )
    if not plan.is_file():
        return ""
    digest = plan_digest_without_assumptions(plan)
    task = next(
        (item for item in load_json(
            protected_decomposition_state_path(root), default={}
        ).get("tasks", [])
         if isinstance(item, dict) and item.get("id") == task_id),
        {"id": task_id},
    )
    if not _task_plan_approval_matches_digest(root, task, grill, digest):
        return ""
    return digest


def story_plan_digest(root: Path) -> str:
    """Return the live approved story-plan body digest, or ``""``."""
    decomposition = load_json(protected_decomposition_state_path(root), default={})
    plan_file = decomposition.get("plan_file")
    if not isinstance(plan_file, str) or not plan_file.strip():
        return ""
    plan = root / plan_file
    return plan_digest_without_assumptions(plan) if plan.is_file() else ""


def _native_story_approval_recorded(
    root: Path, story: str, record: dict, *, path: Path | None = None,
) -> bool:
    """Whether one story-approval record is its real native-event tombstone."""
    runtime = record.get("runtime")
    session = record.get("session_id")
    event = record.get("event_id")
    expected_actor = {
        "claude": "human-via-Claude",
        "codex": "human-via-Codex",
    }.get(runtime)
    if (
        expected_actor is None
        or record.get("approved_by") != expected_actor
        or record.get("plan_kind") != "story"
        or record.get("story") != story
        or record.get("task") != ""
        or re.fullmatch(
            r"[0-9a-f]{64}", record.get("approved_plan_sha256") or "",
        ) is None
        or not all(
            isinstance(value, str) and value.strip()
            for value in (record.get("approved_at"), session, event)
        )
    ):
        return False
    replay_key = hashlib.sha256(
        f"{runtime}\0{session}\0{event}".encode("utf-8")
    ).hexdigest()
    replay = evidence_path(
        root, story, f"approval-events/{replay_key}.json",
    )
    if path is not None and path != replay:
        return False
    try:
        return load_json(replay, default={}) == record
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False


def approved_story_plan_predecessors(
    root: Path, current_digest: str,
) -> tuple[str, ...]:
    """Return authenticated predecessor digests for the current approval.

    The transition is authority only when the live run, selected approval
    record, and consumed native-event tombstone all name the same story and
    old-to-new digest pair.  Callers use it narrowly to preserve an unchanged
    task's cold proof across a human-approved story-plan edit.
    """
    if re.fullmatch(r"[0-9a-f]{64}", current_digest or "") is None:
        return ()
    state = raw_run_state(root)
    story = str(state.get("story") or state.get("issue_key") or "").strip()
    relative = state.get("plan_file")
    if (
        not story
        or state.get("plan_status") != "approved"
        or state.get("approved_plan_sha256") != current_digest
        or not isinstance(relative, str)
    ):
        return ()
    plan = root / relative
    if not plan.is_file() or plan_digest_without_assumptions(plan) != current_digest:
        return ()
    try:
        record = load_json(
            evidence_path(root, story, "plan-approval.json"), default={},
        )
    except (OSError, UnicodeError, json.JSONDecodeError):
        return ()
    if not isinstance(record, dict):
        return ()
    if (
        record.get("approved_plan_sha256") != current_digest
        or not _native_story_approval_recorded(root, story, record)
    ):
        return ()

    predecessors: list[str] = []
    seen = {current_digest}
    event_dir = evidence_path(root, story, "approval-events")
    while True:
        previous = record.get("previous_approved_plan_sha256")
        if (
            re.fullmatch(r"[0-9a-f]{64}", previous or "") is None
            or previous in seen
        ):
            break
        matches = []
        for path in event_dir.glob("*.json"):
            try:
                candidate = load_json(path, default={})
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                # A malformed sibling is an authenticated-history failure. Do
                # not skip it and grant authority from a different replay.
                raise SystemExit(
                    f"cannot authenticate story approval history: "
                    f"approval event {path.name} is unreadable ({exc})"
                ) from exc
            if (
                isinstance(candidate, dict)
                and candidate.get("approved_plan_sha256") == previous
                and _native_story_approval_recorded(
                    root, story, candidate, path=path,
                )
            ):
                matches.append(candidate)
        if len(matches) != 1:
            break
        predecessors.append(previous)
        seen.add(previous)
        record = matches[0]
    return tuple(predecessors)


def validated_measurement_launch(
    root: Path,
    task: dict,
    stage: dict,
    origin_task_sha256: str,
    origin_measurement: dict,
    launch_id: str = "",
) -> dict | None:
    """Return the launch or native preparation anchoring a measurement receipt."""
    from forge_cli.delegate import (
        argv_digest, brief_path, current_delegation, load_delegations,
    )
    from forge_cli.stages import (
        _host_native_preparation_scope, _successful_launch_entry_valid,
    )

    task_id = str(task.get("id") or "")
    entry = current_delegation(
        root,
        task_id,
        stage_started_at=str(stage.get("started_at") or ""),
        task_sha256=origin_task_sha256,
        ignore_lock=True,
    )
    if entry is None:
        try:
            candidates = [
                row for row in load_delegations(root)
                if row.get("transport") == "host-native"
                and row.get("task") == task_id
                and row.get("stage_started_at") == stage.get("started_at")
                and row.get("write") is True
            ]
        except (OSError, SystemExit, ValueError):
            return None
        if not candidates:
            return None
        entry = next((row for row in candidates
                      if row.get("launch_id") == launch_id), None) \
            if launch_id else candidates[-1]
        if entry is None:
            return None
        if launch_id:
            scope = entry.get("write_scope")
            brief = brief_path(root, task_id)
            if (
                entry.get("transport") != "host-native"
                or entry.get("write") is not True
                or entry.get("launch_status") != "prepared"
                or entry.get("task_sha256") != origin_task_sha256
                or entry.get("stage_started_at") != stage.get("started_at")
                or not isinstance(scope, list)
                or not scope
                or any(not isinstance(item, str) or not item.strip()
                       for item in scope)
                or entry.get("write_scope") != origin_measurement.get("write_scope")
                or entry.get("model") != ""
                or entry.get("effort") != ""
                or entry.get("argv") != []
                or entry.get("argv_sha256") != argv_digest([])
                or entry.get("brief_path") != brief.relative_to(root).as_posix()
                or not isinstance(entry.get("brief_sha256"), str)
                or re.fullmatch(r"[0-9a-f]{64}", entry["brief_sha256"]) is None
                or any(key in entry for key in (
                    "pid", "pgid", "pid_started", "process_token", "session_id",
                    "output_path", "stderr_path", "executable_path", "companion_path",
                ))
            ):
                return None
        else:
            scope = _host_native_preparation_scope(root, task_id, stage, task)
        identity = entry.get("launch_id")
        if (entry.get("story") != _active_story_key(root)
                or entry.get("task_sha256") != origin_task_sha256
                or entry.get("launch_status") != "prepared"
                or scope != origin_measurement.get("write_scope")
                or entry.get("write_scope") != scope
                or not isinstance(identity, str)
                or re.fullmatch(r"[A-Za-z0-9._-]+", identity) is None
                or (launch_id and identity != launch_id)):
            return None
        return entry
    if not entry:
        return None
    if (
        entry.get("launch_status") != "succeeded"
        or entry.get("write") is not True
        or entry.get("story") != _active_story_key(root)
        or entry.get("stage_started_at") != stage.get("started_at")
        or entry.get("task_sha256") != origin_task_sha256
        or entry.get("write_scope") != origin_measurement.get("write_scope")
        or (launch_id and entry.get("launch_id") != launch_id)
    ):
        return None
    return entry if _successful_launch_entry_valid(
        root, task_id, stage, entry,
    ) else None


def _measurement_receipt_chain_matches(
    root: Path,
    task: dict,
    stage: dict,
    grill: dict,
    receipts: list,
    *,
    permitted_story_digests: set[str],
    task_plan_digest: str,
    expected: object,
) -> tuple[dict, dict, str] | None:
    """Validate immutable receipt shape, grounding, links, and launch identity."""
    task_id = str(task.get("id") or "")
    previous_measurement = None
    origin_task = None
    origin_measurement = None
    launch_id = ""
    required = {
        "generated_by", "recorded_at", "story", "task_id", "stage_started_at",
        "stage_base_sha", "source_grill_input_sha256", "story_plan_sha256",
        "task_plan_sha256", "semantic_grounding_sha256", "from_task_sha256",
        "to_task_sha256", "from_measurement", "to_measurement", "launch_id",
    }
    for index, receipt in enumerate(receipts):
        if not isinstance(receipt, dict) or set(receipt) != required:
            return None
        before = receipt.get("from_measurement")
        after = receipt.get("to_measurement")
        receipt_story_digest = receipt.get("story_plan_sha256")
        current_launch_id = receipt.get("launch_id")
        if (not isinstance(before, dict) or not isinstance(after, dict)
                or not isinstance(current_launch_id, str)
                or re.fullmatch(r"[A-Za-z0-9._-]+", current_launch_id) is None):
            return None
        if set(before) != set(MEASUREMENT_CONTRACT_FIELDS) \
                or set(after) != set(MEASUREMENT_CONTRACT_FIELDS):
            return None
        if (
            receipt.get("generated_by") != "record_decomposition_from_json"
            or receipt.get("story") != _active_story_key(root)
            or receipt.get("task_id") != task_id
            or receipt.get("stage_started_at") != stage.get("started_at")
            or receipt.get("stage_base_sha") != stage.get("base_sha")
            or receipt.get("source_grill_input_sha256") != grill.get("input_sha256")
            or receipt_story_digest not in permitted_story_digests
            or receipt.get("task_plan_sha256") != task_plan_digest
            or receipt.get("semantic_grounding_sha256")
            != grounding_digest(
                root, task, in_stage=True, _plan_sha256=receipt_story_digest,
            )
            or receipt.get("from_task_sha256") != expected
            or (previous_measurement is not None and before != previous_measurement)
        ):
            return None
        before_task = {**task, **before}
        after_task = {**task, **after}
        if (task_digest(before_task) != receipt.get("from_task_sha256")
                or task_digest(after_task) != receipt.get("to_task_sha256")):
            return None
        if index == 0:
            if not grounding_matches(
                root, before_task, grill.get("input_sha256"), in_stage=True,
                _plan_sha256=receipt_story_digest,
            ):
                return None
            origin_task = before_task
            origin_measurement = before
            launch_id = current_launch_id
        elif current_launch_id != launch_id:
            return None
        expected = receipt.get("to_task_sha256")
        previous_measurement = after
    if (expected != task_digest(task)
            or previous_measurement != measurement_contract(task)
            or origin_task is None or origin_measurement is None):
        return None
    return origin_task, origin_measurement, launch_id


def _measurement_continuity_matches(
    root: Path,
    task: dict,
    grill: dict,
    *,
    allow_unbound_story_reapproval: bool = False,
) -> bool:
    """Validate the complete recorder-owned active-stage receipt chain."""
    task_id = str(task.get("id") or "")
    stage = task_stage_record(root, task_id)
    receipts = stage.get("measurement_continuity")
    if stage.get("status") not in ("active", "done") \
            or not isinstance(receipts, list) or not receipts:
        return False
    story_digest = story_plan_digest(root)
    decomposition = load_json(
        protected_decomposition_state_path(root), default={},
    )
    transition_is_bound = decomposition.get("plan_sha256") == story_digest
    previous_story_digests = (
        approved_story_plan_predecessors(root, story_digest)
        if transition_is_bound or allow_unbound_story_reapproval
        else ()
    )
    permitted_story_digests = {story_digest}
    permitted_story_digests.update(previous_story_digests)
    task_plan = evidence_path(
        root, _active_story_key(root), f"task-plans/{task_id}.md",
    )
    task_plan_digest = (
        plan_digest_without_assumptions(task_plan) if task_plan.is_file() else ""
    )
    if (not story_digest or not task_plan_digest
            or grill.get("approved_task_plan_sha256") != task_plan_digest):
        return False
    current_task_sha256 = task_digest(task)
    if stage.get("status") == "done":
        if stage.get("task_sha256") != current_task_sha256:
            return False
        first = receipts[0]
        expected = first.get("from_task_sha256") if isinstance(first, dict) else None
    else:
        expected = stage.get("task_sha256")
    chain = _measurement_receipt_chain_matches(
        root, task, stage, grill, receipts,
        permitted_story_digests=permitted_story_digests,
        task_plan_digest=task_plan_digest,
        expected=expected,
    )
    if chain is None:
        return False
    origin_task, origin_measurement, launch_id = chain
    return validated_measurement_launch(
        root,
        origin_task,
        stage,
        str(receipts[0].get("from_task_sha256") or ""),
        origin_measurement,
        launch_id,
    ) is not None


def task_grill_grounding_matches(
    root: Path,
    task: dict,
    grill: dict,
    *,
    treeish: str = "",
    allow_unbound_story_reapproval: bool = False,
) -> bool:
    """Accept current grounding or an exact recorder-owned continuity chain."""
    if grounding_matches(
        root,
        task,
        grill.get("input_sha256"),
        treeish=treeish,
        in_stage=task_in_stage(root, str(task.get("id") or "")),
    ):
        return True
    current_story_digest = story_plan_digest(root)
    decomposition = load_json(
        protected_decomposition_state_path(root), default={},
    )
    transition_is_bound = decomposition.get("plan_sha256") == current_story_digest
    previous_story_digests = (
        approved_story_plan_predecessors(root, current_story_digest)
        if transition_is_bound or allow_unbound_story_reapproval
        else ()
    )
    for previous_story_digest in previous_story_digests:
        if grounding_matches(
            root,
            task,
            grill.get("input_sha256"),
            treeish=treeish,
            in_stage=task_in_stage(root, str(task.get("id") or "")),
            _plan_sha256=previous_story_digest,
        ):
            return True
    return _measurement_continuity_matches(
        root,
        task,
        grill,
        allow_unbound_story_reapproval=allow_unbound_story_reapproval,
    )


CONTRACT_BLOCK_START = "<!-- forge:contract -->"
CONTRACT_BLOCK_END = "<!-- /forge:contract -->"
_CONTRACT_BLOCK = re.compile(
    rb"\n?" + re.escape(CONTRACT_BLOCK_START.encode()) + rb".*?"
    + re.escape(CONTRACT_BLOCK_END.encode()) + rb"\n?", re.DOTALL)


def strip_derived_sections(text: bytes) -> bytes:
    """Drop the harness-rendered contract block before hashing a plan.

    The block is rendered FROM the recorded decomposition (see
    `render_task_contract_block`), so it cannot drift from the contract and
    is not something a human authored or a grill judged. Hashing it made a
    scope widening -- which re-renders the block -- stale the plan approval.
    """
    return _CONTRACT_BLOCK.sub(b"\n", text)


def plan_digest_without_assumptions(path: Path) -> str:
    """The plan digest every grill and approval binds to: the authored BODY,
    without the frontmatter block and without implementation-time appendices.

    Same digest as ``plan_body_digest``. Hashing the frontmatter too meant
    `plan save`'s own `saved:` timestamp changed the digest, so a grill
    recorded against the draft never matched the saved copy and every plan
    needed a second grill record before it could be approved."""
    return plan_body_digest(path)


def plan_body_digest(path: Path) -> str:
    """Hash the authored plan body, excluding harness-managed content.

    Line endings are normalised to LF before hashing so the digest is stable
    across platforms and Git's autocrlf. Both the cold-grill bridge and shared
    native approval recorder use this function; saving on Windows therefore
    cannot create a spurious approval mismatch.
    """
    return _plan_body_digest_bytes(path.read_bytes())


def _plan_body_digest_bytes(raw: bytes) -> str:
    """Hash plan bytes using the same body-only rules as live plan reads."""
    normalised = raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    normalised = strip_derived_sections(normalised)
    frontmatter = re.match(br"\A---\n(.*?)\n---\n", normalised, re.DOTALL)
    body = normalised[frontmatter.end():] if frontmatter else normalised
    # Authored frontmatter (decisions_reviewed, ...) is part of what was
    # grilled and approved, so it is hashed too; only the fields `plan save`
    # stamps itself are dropped, so saving never changes the digest.
    authored = b"\n".join(
        line for line in (frontmatter.group(1).split(b"\n") if frontmatter else [])
        if not re.match(PLAN_SAVE_OWNED_FIELDS, line)
    )
    approved_body = body.partition(b"\n## Implementation Assumptions")[0]
    # Trailing newlines are normalised because `strip_derived_sections`
    # substitutes a newline for the contract block, and the block is appended
    # after one. Removing it therefore leaves one MORE trailing newline than
    # the file carried before the block existed, so the first render of the
    # block changed this digest and native approval refused with "the plan
    # CHANGED" against byte-identical authored text.
    approved_body = approved_body.rstrip(b"\n") + b"\n"
    return hashlib.sha256(authored + b"\n---\n" + approved_body).hexdigest()


# Frontmatter keys `plan save` writes itself (plus saved:/updated: stamps):
# harness bookkeeping, never something a grill read.
PLAN_SAVE_OWNED_FIELDS = rb"(issue|title|status|saved|updated|story):"


def render_task_contract_block(task: dict, amendments: dict | None = None) -> str:
    """The recorded contract, rendered for a reader of the task plan.

    Written once, in the decomposition; rendered here; never hand-copied. The
    plan used to carry its own copy of the criteria and the file list, held
    equal to the contract by a Codex cold read -- five of T2's six "blockers"
    were that copy drifting. A rendered block cannot drift.
    """
    lines = [CONTRACT_BLOCK_START,
             "## Contract (recorded)", "",
             "Rendered by the harness from the recorded decomposition; edit the "
             "decomposition, not this block. It is excluded from the plan's "
             "approval and grill digests, so a re-render never stales either.", ""]
    objective = str(task.get("objective") or "").strip()
    if objective:
        lines += ["**Objective.** " + objective, ""]
    criteria = [str(c) for c in task.get("acceptance_criteria") or []]
    lines += ["**Acceptance criteria**", ""]
    lines += [f"- {c}" for c in criteria] or ["- (none recorded)"]
    lines.append("")
    scope = [str(p) for p in task.get("write_scope") or []]
    lines += ["**Write scope** (what `stage done` measures the diff against)", ""]
    lines += [f"- {p}" for p in scope] or ["- (none recorded)"]
    added = (amendments or {}).get("added_paths") or []
    if added:
        reasons = {}
        for entry in (amendments or {}).get("amendments") or []:
            for path in entry.get("added_paths") or []:
                reasons.setdefault(path, str(entry.get("reason") or ""))
        lines += ["", "**Scope amendments** (measured paths the scope did not name, "
                  "recorded with `forge stage amend-scope`)", ""]
        lines += [f"- {p}" + (f" -- {reasons[p]}" if reasons.get(p) else "")
                  for p in added]
    lines.append("")
    tests = task.get("required_tests") or []
    lines += ["**Required tests** (run by `stage done`)", ""]
    lines += [f"- `{t.get('id')}` -- `{t.get('command')}` ({t.get('path')})"
              for t in tests if isinstance(t, dict)] or ["- (none recorded)"]
    lines.append("")
    verify = [str(v) for v in task.get("verify_commands") or []]
    lines += ["**Verify commands**", ""]
    lines += [f"- `{v}`" for v in verify] or ["- (none recorded)"]
    budget = task.get("review_budget") or {}
    if isinstance(budget, dict) and budget:
        lines += ["", f"**Review budget.** {budget.get('max_changed_files')} files / "
                  f"{budget.get('max_changed_lines')} lines"
                  + (f" -- {budget.get('reason')}" if budget.get("reason") else "")]
    lines += [CONTRACT_BLOCK_END]
    return "\n".join(lines) + "\n"


def render_recorded_task_contract(
    root: Path, task_id: str, story: str | None = None,
) -> str:
    """Render a task contract from recorded decomposition state, never its plan."""
    from forge_cli.stages import scope_amendments_path

    key = story or _active_story_key(root)
    active = key == _active_story_key(root)
    shipped = (
        (story_dir(root, key) / "shipped.json").is_file()
        or (factory_dir(root) / "history" / key / "shipped.json").is_file()
    )
    decomposition_path = (
        protected_decomposition_state_path(root)
        if active and not shipped
        else decomposition_state_path(root, key)
    )
    decomposition = load_json(decomposition_path, default={})
    task = next(
        (item for item in decomposition.get("tasks", [])
         if isinstance(item, dict) and item.get("id") == task_id),
        None,
    )
    if task is None:
        return ""
    amendments = {}
    if active and not shipped:
        amendments = (load_json(scope_amendments_path(root), default={})
                      .get("tasks", {}).get(task_id, {}))
    return render_task_contract_block(task, amendments)


def refresh_task_plan_contract(root: Path, task_id: str, task: dict) -> bool:
    """Remove an older rendered contract without adding it back."""
    plan = evidence_path(
        root, _active_story_key(root), f"task-plans/{task_id}.md",
    )
    if not plan.is_file():
        return False
    original = plan.read_bytes()
    stripped = strip_derived_sections(original)
    if stripped == original:
        return False
    plan.write_bytes(stripped)
    return True


def approved_plan_digest(
    root: Path, state: dict[str, Any], plan: Path,
) -> str | None:
    """Return the digest authorized by a consumed native approval event."""
    digest = state.get("approved_plan_sha256")
    story = str(state.get("story") or state.get("issue_key") or "").strip()
    if (state.get("plan_status") != "approved"
            or not story
            or not isinstance(digest, str)
            or re.fullmatch(r"[0-9a-f]{64}", digest) is None):
        return None
    try:
        record = load_json(
            evidence_path(root, story, "plan-approval.json"), default={},
        )
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if (not isinstance(record, dict)
            or record.get("approved_plan_sha256") != digest
            or not _native_story_approval_recorded(root, story, record)):
        return None
    return digest


def validated_task_marker_commit(root: Path, key: str, task_id: str) -> str:
    """Return a marker's sealed commit without treating it as completion proof."""
    marker = load_json(root / task_marker_path(key, task_id), default={})
    committed, problem = _committed_task_marker(
        root, key, task_id, marker, None,
    )
    return "" if problem or committed is None else str(committed["commit"])


def require_approved_plan_digest(root: Path) -> str:
    """Return the live approved-plan digest or require a fresh approval."""
    state = load_json(run_state_path(root), default={})
    plan_file = state.get("plan_file")
    plan = root / plan_file if isinstance(plan_file, str) else None
    approved = (
        approved_plan_digest(root, state, plan)
        if plan is not None and plan.is_file()
        else None
    )
    live = (
        plan_digest_without_assumptions(plan)
        if plan is not None and plan.is_file()
        else None
    )
    if (state.get("plan_status") == "approved"
            and isinstance(approved, str) and approved
            and live is not None and live != approved):
        raise SystemExit(
            "approved plan binding no longer matches the live plan. Display the "
            "exact current plan in native Plan Mode and consume a fresh approval; "
            "a post-approval edit returns to its approver, not another cold read."
        )
    if (
        not isinstance(approved, str)
        or not approved
        or plan is None
        or not plan.is_file()
        or live != approved
    ):
        raise SystemExit(
            "approved plan binding is missing or no longer matches the live plan. "
            "Complete the current plan grill and native approval."
        )
    return approved


def harness_owned_prefixes() -> tuple[str, ...]:
    """Paths the workflow writes while a task is being planned or worked —
    the run/stage/evidence tree, plans, decision records, the context ledger.
    None of them is the product a grill read."""
    from forge_cli.review import HARNESS_PREFIXES
    from forge_cli.stages import WORKFLOW_PATHS
    return tuple(sorted(set(WORKFLOW_PATHS) | set(HARNESS_PREFIXES)))


def product_excluded_prefixes(root: Path) -> tuple[str, ...]:
    """The ONE definition of "not product": the workflow ledgers, plans,
    decision records, and in a vendored client the harness machinery.

    Four lists used to answer this question -- the stage measure, the review
    scope, the stamp's tree digest and the grill's grounding -- and they
    disagreed: a decision record was not a scope stray but did stale the
    review stamp. Every closeout check now asks this function, so a path is
    product for all of them or for none.
    """
    from forge_cli.stages import measure_prefixes
    return measure_prefixes(root)


def product_delta_digest(root: Path, base_sha: str, head: str = "") -> str:
    """Hash of the product diff this task's branch made since `base_sha`.

    This is what a review reads and what a seal ships, so it is what the
    review stamp binds to -- and nothing else. Contract text, brief text,
    decision records and evidence commits change none of these bytes, so
    none of them can stale a review any more. Two different diffs can leave
    the tree in the same state; a tree digest could not tell them apart, this
    can.

    Base -> INDEX, not base -> HEAD: the reviewed tree is stamped while it is
    staged and committed afterwards, and the digest must not move at that
    commit. `stage done` requires a clean index at close, so there it equals
    base -> HEAD. Paths are the branch's own commits (`committed_paths`,
    first-parent) plus what is staged, so a trunk merge received mid-stage
    is not attributed to the stage.
    """
    from forge_cli.stages import _git, committed_paths
    historical = bool(head)
    head = head or head_sha(root) or ""
    empty = hashlib.sha256(b"").hexdigest()
    if not base_sha or not head:
        return empty
    excluded = product_excluded_prefixes(root)
    # The lossless git helper the stage measure uses (encoding-hygiene
    # allowlisted); a bare call here failed the hygiene gate.
    # Only add paths that differ between the current HEAD and index. Comparing
    # the index with the stage base also attributes paths brought in by a trunk
    # merge to this task, undoing committed_paths()' first-parent merge filter.
    paths: set[str] = set()
    if not historical:
        staged_raw = _git(root, "diff", "--cached", "--name-only", "-z", "HEAD")
        paths = {path for path in staged_raw.split("\0") if path}
    if base_sha != head:
        paths |= committed_paths(root, base_sha, head)
    ordered = sorted(path for path in paths if not path.startswith(excluded))
    if not ordered:
        return empty
    range_args = [base_sha, head] if historical else ["--cached", base_sha]
    diff = subprocess.run(
        ["git", "diff", "--binary", "--no-ext-diff", *range_args, "--", *ordered],
        cwd=root, capture_output=True, env=clean_git_env(),
    )
    if diff.returncode != 0:
        raise SystemExit("cannot derive the product delta digest: git diff failed")
    return hashlib.sha256(diff.stdout).hexdigest()

def product_tree_digest(root: Path, treeish: str = "",
                        exclude: tuple[str, ...] = (".factory/", "plans/")) -> str:
    """Hash product blobs from the index, or from a named historical tree."""
    dirs = _git_dirs(root) if BOARD_MEMO else None
    if dirs is None:
        return _product_tree_digest_now(root, treeish, exclude)
    from forge_cli import fscache

    git_dir, common = dirs
    if treeish:
        # An object id names the same tree forever; a ref name can move.
        if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", treeish):
            return _product_tree_digest_now(root, treeish, exclude)
        namespace, stamp = f"board:tree:{common}:{treeish}:{exclude}", ()
    else:
        # `ls-files --stage` reads this worktree's index and nothing else.
        namespace = f"board:index-tree:{git_dir}:{exclude}"
        stamp = (fscache.file_stamp(git_dir / "index"),)
    return _board_memo(namespace, stamp,
                       lambda: _product_tree_digest_now(root, treeish, exclude))


def _product_tree_digest_now(root: Path, treeish: str,
                             exclude: tuple[str, ...]) -> str:
    git_args = (["ls-tree", "-r", "-z", treeish]
                if treeish else ["ls-files", "--stage", "-z"])
    proc = subprocess.run(
        ["git", *git_args],
        cwd=root,
        capture_output=True,
        text=True,
        env=clean_git_env(),
        encoding="utf-8",
        errors="surrogateescape",
    )
    if proc.returncode != 0:
        raise SystemExit(
            "cannot derive the task grounding digest from Git: "
            + proc.stderr.strip()
        )
    blobs: list[tuple[str, str]] = []
    for entry in proc.stdout.split("\0"):
        if not entry:
            continue
        metadata, path = entry.split("\t", 1)
        if path.startswith(exclude):
            continue
        fields = metadata.split()
        blobs.append((path, fields[2] if treeish else fields[1]))
    payload = json.dumps(sorted(blobs), separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode()).hexdigest()


GROUNDING_CONTRACT_FIELDS = (
    # What the task IS. A change here changes the work, so the grill that
    # examined the old version no longer speaks to the new one.
    "objective",
    "acceptance_criteria",
    "plan_contracts",
    "write_scope",
    "required_tests",
    "verify_commands",
    "user_facing",
)
# Once the stage is OPEN, three of those fields stop being what the work IS
# and become how the work is MEASURED: `write_scope` is enforced by measuring
# the diff, `required_tests` and `verify_commands` by running them. Each has a
# mechanical gate that can actually check it; a cold reader can only guess at
# them. Widening scope or fixing a test command mid-stage therefore changes
# nothing the grill judged, and re-grilling on it re-asked a question whose
# answer had not changed (T2: a scope widening cost a 21-minute re-grill, a
# plan rewrite and a human re-approval for zero code change).
IN_STAGE_GROUNDING_FIELDS = (
    "objective",
    "acceptance_criteria",
    "plan_contracts",
    "user_facing",
)
MEASUREMENT_CONTRACT_FIELDS = ("write_scope", "required_tests", "verify_commands")
# Deliberately NOT grounded: `review_budget` and `reviewer_focus` are
# bookkeeping for the reviewer, and `title`/`id`/`epic_id` are labels. Raising
# a file-count ceiling used to invalidate the grill and force a full re-grill
# round — the ceiling is a stop on runaway scope, never a statement about what
# the task must do.


def task_in_stage(root: Path, task_id: str) -> bool:
    """True once `stage start` has opened this task's stage.

    From this moment the product tree moves because of the work the grill
    authorised, so it stops being part of the grounding.
    """
    return task_stage_record(root, task_id).get("status") in ("active", "done")


def grounding_digest(root: Path, task: dict, *, treeish: str = "",
                     in_stage: bool = False,
                     fields: tuple[str, ...] | None = None,
                     _plan_sha256: str | None = None) -> str:
    """Bind a task grill to what the work IS: the substantive contract, the
    approved plan, and — only before the stage opens — the product tree."""
    if _plan_sha256 is None:
        decomposition = load_json(
            protected_decomposition_state_path(root), default={},
        )
        plan_file = decomposition.get("plan_file")
        if not isinstance(plan_file, str) or not plan_file.strip():
            plan_file = load_json(run_state_path(root), default={}).get("plan_file")
        if not isinstance(plan_file, str) or not plan_file.strip():
            raise SystemExit(
                "cannot derive the task grounding digest: the protected decomposition "
                "does not name its approved plan"
            )
        plan = (root / plan_file).resolve()
        try:
            plan.relative_to(root.resolve())
        except ValueError:
            raise SystemExit(
                "cannot derive the task grounding digest: plan path escapes the repo: "
                f"{plan_file!r}"
            )
        if not plan.is_file():
            raise SystemExit(
                f"cannot derive the task grounding digest: approved plan {plan_file!r} "
                "does not exist"
            )
        _plan_sha256 = plan_digest_without_assumptions(plan)
    if fields is None:
        fields = IN_STAGE_GROUNDING_FIELDS if in_stage else GROUNDING_CONTRACT_FIELDS
    body = {
        "contract": {field: task.get(field) for field in fields},
        "plan_sha256": _plan_sha256,
    }
    # The product tree is part of the grounding only until the stage opens.
    # Before work starts, the plan was grilled against a codebase and a change
    # there means the grill read something else. After work starts, the tree
    # moves BECAUSE OF the work the grill authorised, so binding to it makes
    # the gate self-defeating: committing the implementation stales the grill,
    # and the grill is what `forge delegate` needs to fix the implementation.
    # Harness-owned paths (a decision record, the context ledger) are left
    # out even before the stage: writing one is the workflow doing its job,
    # not the codebase the grill read changing under it.
    if not in_stage:
        body["product_tree_sha256"] = product_tree_digest(
            root, treeish, exclude=harness_owned_prefixes())
    payload = json.dumps(body, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def legacy_grounding_digest(
        root: Path, task: dict, *, treeish: str = "",
        _plan_sha256: str | None = None,
) -> str:
    """Return the exact pre-Lean in-flight grill fingerprint.

    Decision 0066 permits one already-open task to carry its old whole-task
    grounding while its substantive inputs remain unchanged.  This recognises
    that one serialized shape only; it does not make other retired grill
    formats runtime authority.
    """
    if _plan_sha256 is None:
        decomposition = load_json(
            protected_decomposition_state_path(root), default={},
        )
        plan_file = decomposition.get("plan_file") or load_json(
            run_state_path(root), default={},
        ).get("plan_file")
        if not isinstance(plan_file, str) or not plan_file.strip():
            raise SystemExit(
                "cannot derive the task grounding digest: the protected decomposition "
                "does not name its approved plan"
            )
        plan = (root / plan_file).resolve()
        if not plan.is_file():
            raise SystemExit(
                f"cannot derive the task grounding digest: approved plan {plan_file!r} "
                "does not exist"
            )
        _plan_sha256 = plan_digest_without_assumptions(plan)
    payload = json.dumps(
        {
            "contract": task,
            "plan_sha256": _plan_sha256,
            "product_tree_sha256": product_tree_digest(root, treeish),
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def grounding_matches(root: Path, task: dict, recorded: str, *,
                      treeish: str = "", in_stage: bool = False,
                      _plan_sha256: str | None = None) -> bool:
    """Does a recorded grill still bind its inputs?

    Accept current grounding, exact in-stage predecessor rules, or the one
    authenticated pre-Lean in-flight shape from Decision 0066.
    """
    if not recorded:
        return False
    if recorded == grounding_digest(
        root, task, treeish=treeish, in_stage=in_stage,
        _plan_sha256=_plan_sha256,
    ):
        return True
    if in_stage:
        # Recorded in-stage under the previous rule, which still grounded the
        # three measurement fields. Those fields have not moved if this
        # matches, so the record is as good as one made today.
        if recorded == grounding_digest(
            root,
            task,
            treeish=treeish,
            in_stage=True,
            fields=GROUNDING_CONTRACT_FIELDS,
            _plan_sha256=_plan_sha256,
        ):
            return True
        # Stamped BEFORE the stage opened, so the tree was part of it. The
        # stage pinned that same tree as its baseline, so measuring against
        # the baseline reproduces exactly what was recorded. Without this the
        # act of opening the stage staled every grill.
        baseline = _stage_baseline_for(root, str(task.get("id") or ""))
        if baseline:
            try:
                if recorded == grounding_digest(
                    root,
                    task,
                    treeish=baseline,
                    in_stage=False,
                    _plan_sha256=_plan_sha256,
                ):
                    return True
            except SystemExit:
                pass
    try:
        return recorded == legacy_grounding_digest(
            root, task, treeish=treeish, _plan_sha256=_plan_sha256,
        )
    except SystemExit:
        return False


def _stage_baseline_for(root: Path, task_id: str) -> str:
    """The tree this task's stage pinned when it opened, or "" if unknowable."""
    if not task_id:
        return ""
    try:
        from forge_cli.stages import stage_baseline
        stage = task_stage_record(root, task_id)
        if not stage:
            return ""
        return stage_baseline(task_state_root(root, task_id), stage) or ""
    except Exception:
        # Never let a baseline lookup decide a gate by crashing it.
        return ""


def effective_review_base(
    root: Path, task_id: str, tip: str = "", state: dict[str, Any] | None = None,
) -> str:
    """Resolve the task base used by both review publication and proof readers."""
    stage = task_stage_record(root, task_id)
    if not stage:
        return ""
    from forge_cli.review import resolve_review_base
    return resolve_review_base(
        root, stage, state if isinstance(state, dict) else raw_run_state(root),
        tip or head_sha(root) or "",
    )


def selected_review_ready_for_functional_check(
    root: Path, state: dict[str, Any] | None = None,
) -> bool:
    """Require current clean proof and reviewed meaning before phase advance."""
    pointer = state if isinstance(state, dict) else raw_run_state(root)
    story = pointer.get("issue_key") or pointer.get("story")
    task_id = pointer.get("task_id")
    if not isinstance(story, str) or not story or not isinstance(task_id, str) or not task_id:
        return False
    try:
        from forge_cli.readiness import review_passed
        from forge_cli.stages import require_current_review_meaning, task_for

        stage = task_stage_record(root, task_id)
        task = task_for(root, task_id)
        review_base = effective_review_base(root, task_id, state=pointer)
        if not stage or not task or not review_base:
            return False
        delta_id = product_delta_digest(root, review_base)
        generation, _selection, problems = read_selected_review_generation(
            root, story, task_id, expected_delta_id=delta_id,
        )
        if problems or not isinstance(generation, dict):
            return False
        lenses = generation.get("lenses")
        if not isinstance(lenses, dict) or not all(
            review_passed(lenses.get(lens))
            for lens in ("quality", "performance", "security")
        ):
            return False
        require_current_review_meaning(root, stage, task, generation)
    except (Exception, SystemExit):
        return False
    return True


_TASK_CONTRACT_FIELDS = (
    "write_scope",
    "required_tests",
    "verify_commands",
    "reviewer_focus",
)


def _task_contract_complete(task: dict) -> bool:
    return all(
        value and (not isinstance(value, str) or value.strip())
        for value in (task.get(field) for field in _TASK_CONTRACT_FIELDS)
    )


def _native_task_approval_recorded(
    root: Path, task: dict, grill: dict, digest: str | None = None,
) -> bool:
    """Whether the task approval matches its immutable consumed-event record."""
    runtime = grill.get("approval_runtime")
    expected_actor = {
        "claude": "human-via-Claude",
        "codex": "human-via-Codex",
    }.get(runtime)
    approved_digest = grill.get("approved_task_plan_sha256")
    task_id = str(task.get("id") or "")
    story = _active_story_key(root)
    valid = bool(
        expected_actor
        and grill.get("approved_by") == expected_actor
        and isinstance(approved_digest, str)
        and re.fullmatch(r"[0-9a-f]{64}", approved_digest)
        and (digest is None or approved_digest == digest)
        and story
        and task_id
        and all(
            isinstance(grill.get(field), str) and grill[field].strip()
            for field in (
                "approved_at", "approval_session_id", "approval_event_id",
            )
        )
    )
    if not valid:
        return False
    session = grill["approval_session_id"]
    event = grill["approval_event_id"]
    replay_key = hashlib.sha256(
        f"{runtime}\0{session}\0{event}".encode("utf-8")
    ).hexdigest()
    try:
        replay = load_json(
            evidence_path(root, story, f"approval-events/{replay_key}.json"),
            default={},
        )
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False
    expected = {
        "approved_plan_sha256": approved_digest,
        "approved_by": expected_actor,
        "approved_at": grill["approved_at"],
        "runtime": runtime,
        "session_id": session,
        "event_id": event,
        "plan_kind": "task",
        "story": story,
        "task": task_id,
    }
    previous = grill.get("previous_approved_task_plan_sha256")
    if isinstance(previous, str) and previous:
        expected["previous_approved_plan_sha256"] = previous
    return replay == expected


def approved_task_plan_predecessors(
    root: Path, task: dict, grill: dict,
) -> tuple[str, ...]:
    """Return the exact authenticated approval ancestry for one task plan."""
    if not _native_task_approval_recorded(root, task, grill):
        return ()
    story = _active_story_key(root)
    task_id = str(task.get("id") or "")
    current = str(grill.get("approved_task_plan_sha256") or "")
    previous = grill.get("previous_approved_task_plan_sha256")
    event_dir = evidence_path(root, story, "approval-events")
    predecessors: list[str] = []
    seen = {current}
    while re.fullmatch(r"[0-9a-f]{64}", previous or "") and previous not in seen:
        matches: list[dict] = []
        for path in event_dir.glob("*.json"):
            try:
                candidate = load_json(path, default={})
            except (OSError, UnicodeError, json.JSONDecodeError):
                continue
            runtime = candidate.get("runtime")
            session = candidate.get("session_id")
            event = candidate.get("event_id")
            actor = {
                "claude": "human-via-Claude",
                "codex": "human-via-Codex",
            }.get(runtime)
            replay_key = hashlib.sha256(
                f"{runtime}\0{session}\0{event}".encode("utf-8")
            ).hexdigest()
            if (
                actor is not None
                and path == event_dir / f"{replay_key}.json"
                and candidate.get("approved_plan_sha256") == previous
                and candidate.get("approved_by") == actor
                and candidate.get("plan_kind") == "task"
                and candidate.get("story") == story
                and candidate.get("task") == task_id
                and all(isinstance(value, str) and value.strip()
                        for value in (candidate.get("approved_at"), session, event))
            ):
                matches.append(candidate)
        if len(matches) != 1:
            break
        predecessors.append(previous)
        seen.add(previous)
        previous = matches[0].get("previous_approved_plan_sha256")
    return tuple(predecessors)


def _task_plan_amendment_preserves_cold_proof(
    root: Path, task: dict, grill: dict,
) -> bool:
    """Preserve one cold read through authenticated human-approved amendments."""
    task_id = str(task.get("id") or "")
    plan = evidence_path(
        root, _active_story_key(root), f"task-plans/{task_id}.md",
    )
    if not plan.is_file():
        return False
    current = plan_digest_without_assumptions(plan)
    cold = grill.get("task_plan_sha256")
    approved = grill.get("approved_task_plan_sha256")
    if (not isinstance(cold, str) or not cold or current == cold
            or not _native_task_approval_recorded(root, task, grill)):
        return False
    return cold == approved or cold in approved_task_plan_predecessors(
        root, task, grill,
    )


def _task_plan_approval_matches_digest(
    root: Path, task: dict, grill: dict, digest: str,
) -> bool:
    """Whether current approval authority binds this task-plan digest."""
    return (
        _native_task_approval_recorded(root, task, grill, digest)
        or _lean_self_bootstrap_task_grill(root, task, grill, digest)
        or _legacy_inflight_task_grill(root, task, grill)
    )


_LEAN_SELF_BOOTSTRAP_STORY = "FORGE-COORD-1"
_LEAN_SELF_BOOTSTRAP_TASK = "LEAN-WORKFLOW"
_LEAN_SELF_BOOTSTRAP_DIGEST = (
    "5129286f00e80ca96d35decccfa9e4aa896d74fe8d05a4d7fe18cf9b1c4a3034"
)
_LEAN_SELF_BOOTSTRAP_FINAL_ARTIFACT_SHA256 = (
    "2f45654a62ae52fb65f92171d0f5dafa73f0b943390725c03f1c837ef70f5162"
)
_LEAN_SELF_BOOTSTRAP_CLAUSE = (
    "then bootstraps the concrete revision once with actual developer "
    "identity/time without claiming a new answer or reread"
)


def _lean_self_bootstrap_actor(root: Path) -> str | None:
    """Read the bootstrap actor from the current authenticated story approval."""
    if _active_story_key(root) != _LEAN_SELF_BOOTSTRAP_STORY:
        return None
    try:
        digest = require_approved_plan_digest(root)
        approval = load_json(
            evidence_path(root, _LEAN_SELF_BOOTSTRAP_STORY, "plan-approval.json"),
            default={},
        )
    except (OSError, UnicodeError, json.JSONDecodeError, SystemExit):
        return None
    if (
        not isinstance(approval, dict)
        or approval.get("approved_plan_sha256") != digest
    ):
        return None
    actor = approval.get("approved_by")
    return actor if isinstance(actor, str) and actor.strip() else None


def _lean_self_bootstrap_task_grill(
    root: Path, task: dict, grill: dict, digest: str,
) -> bool:
    """Recognize Lean's one approved, human-attributed bootstrap record.

    The story plan authorized this exact self-bootstrap before the native-only
    approval path existed.  Keep the exception content-addressed and historical:
    it cannot approve another story, task, plan revision, actor, or record that
    claims a native runtime event.
    """
    actor = _lean_self_bootstrap_actor(root)
    if actor is None:
        return False
    if (
        _active_story_key(root) != _LEAN_SELF_BOOTSTRAP_STORY
        or task.get("id") != _LEAN_SELF_BOOTSTRAP_TASK
        or digest != _LEAN_SELF_BOOTSTRAP_DIGEST
        or grill.get("issue") != _LEAN_SELF_BOOTSTRAP_STORY
        or grill.get("task_id") != _LEAN_SELF_BOOTSTRAP_TASK
        or grill.get("generated_by") != "griller"
        or grill.get("gate") != "task"
        or grill.get("verdict") != "pass"
        or grill.get("final_artifact_sha256")
        != _LEAN_SELF_BOOTSTRAP_FINAL_ARTIFACT_SHA256
        or grill.get("approved_task_plan_sha256") != _LEAN_SELF_BOOTSTRAP_DIGEST
        or grill.get("approved_by") != actor
        or any(field in grill for field in (
            "approval_runtime", "approval_session_id", "approval_event_id",
        ))
    ):
        return False
    approved_at = grill.get("approved_at")
    if not isinstance(approved_at, str) or not approved_at:
        return False
    try:
        timestamp = datetime.fromisoformat(approved_at)
    except ValueError:
        return False
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        return False
    try:
        return task_grill_grounding_matches(root, task, grill)
    except SystemExit:
        return False


def record_lean_self_bootstrap_approval(
    root: Path, task_id: str, approved_by: str,
) -> dict:
    """Consume the exact one-time Lean self-bootstrap authorized by its plan.

    This is deliberately not exposed as a normal-flow CLI after the bootstrap
    is consumed.  It writes the incumbent human-attributed fields and no native
    event identity because no Claude/Codex completion event occurred.
    """
    story = _active_story_key(root)
    actor = _lean_self_bootstrap_actor(root)
    if (
        story != _LEAN_SELF_BOOTSTRAP_STORY
        or task_id != _LEAN_SELF_BOOTSTRAP_TASK
        or actor is None
        or approved_by != actor
    ):
        raise SystemExit("Lean self-bootstrap approval does not match its authority")
    decomposition = load_json(
        protected_decomposition_state_path(root), default={},
    )
    task = next(
        (candidate for candidate in decomposition.get("tasks", [])
         if isinstance(candidate, dict) and candidate.get("id") == task_id),
        None,
    )
    if task is None:
        raise SystemExit("Lean self-bootstrap task is absent from the decomposition")
    approved_story_digest = require_approved_plan_digest(root)
    if decomposition.get("plan_sha256") != approved_story_digest:
        raise SystemExit("Lean self-bootstrap decomposition is not story-plan grounded")
    state = load_json(run_state_path(root), default={})
    plan_file = state.get("plan_file")
    if not isinstance(plan_file, str) or not plan_file:
        raise SystemExit("Lean self-bootstrap story plan is unavailable")
    story_plan = root / plan_file
    try:
        story_text = story_plan.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise SystemExit("Lean self-bootstrap story plan is unreadable") from exc
    if _LEAN_SELF_BOOTSTRAP_CLAUSE not in story_text:
        raise SystemExit("Lean self-bootstrap authority clause is absent")
    task_plan = evidence_path(root, story, f"task-plans/{task_id}.md")
    if (not task_plan.is_file()
            or plan_digest_without_assumptions(task_plan)
            != _LEAN_SELF_BOOTSTRAP_DIGEST):
        raise SystemExit("Lean self-bootstrap task-plan digest does not match")
    if hashlib.sha256(task_plan.read_bytes()).hexdigest() \
            != _LEAN_SELF_BOOTSTRAP_FINAL_ARTIFACT_SHA256:
        raise SystemExit("Lean self-bootstrap final artifact bytes do not match")
    grill_path = evidence_path(
        root, story, f"grills/tasks/{task_id}.json", for_write=True,
    )
    grill = load_json(grill_path, default={})
    approval_fields = (
        "approved_task_plan_sha256", "approved_by", "approved_at",
        "approval_runtime", "approval_session_id", "approval_event_id",
    )
    if any(field in grill for field in approval_fields):
        raise SystemExit("Lean self-bootstrap approval was already consumed")
    require_task_grill(root, task_id, task)
    if grill.get("final_artifact_sha256") \
            != _LEAN_SELF_BOOTSTRAP_FINAL_ARTIFACT_SHA256:
        raise SystemExit("Lean self-bootstrap clean grill does not bind the plan")
    updated = dict(grill)
    updated.update({
        "approved_task_plan_sha256": _LEAN_SELF_BOOTSTRAP_DIGEST,
        "approved_by": actor,
        "approved_at": now_iso(),
    })
    validate_payload(root, "grill", updated)
    dump_json(grill_path, updated)
    return updated


def _legacy_inflight_task_grill(
    root: Path, task: dict, grill: dict, *, treeish: str = "",
) -> bool:
    """Grandfather one exact pre-Lean task authority already in flight.

    These records cannot be upgraded without fabricating cold output fields.
    Pending tasks and partially converted records remain upgrade-only.
    """
    cold_fields = (
        "cold_input_sha256", "final_artifact_sha256", "finding_dispositions",
    )
    if any(field in grill for field in cold_fields):
        return False
    task_id = str(task.get("id") or "")
    stage = task_stage_record(root, task_id)
    if stage.get("status") not in {"active", "done"}:
        return False

    def aware_timestamp(value: object) -> datetime | None:
        if not isinstance(value, str) or not value:
            return None
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
        return parsed if parsed.tzinfo is not None \
            and parsed.utcoffset() is not None else None

    started_at = aware_timestamp(stage.get("started_at"))
    recorded_at = aware_timestamp(grill.get("recorded_at"))
    approved_at = aware_timestamp(grill.get("approved_at"))
    if not (started_at and recorded_at and approved_at
            and recorded_at <= approved_at <= started_at):
        return False
    story = _active_story_key(root)
    plan = evidence_path(root, story, f"task-plans/{task_id}.md")
    if not plan.is_file():
        return False
    digest = plan_digest_without_assumptions(plan)
    current_task_sha256 = task_digest(task)
    stage_task_sha256 = stage.get("task_sha256")
    if stage.get("status") == "done" \
            and stage_task_sha256 != current_task_sha256:
        return False
    if stage.get("status") == "active" \
            and stage_task_sha256 != current_task_sha256 \
            and not _measurement_continuity_matches(root, task, grill):
        return False
    if not (
        grill.get("generated_by") == "griller"
        and grill.get("gate") == "task"
        and grill.get("verdict") == "pass"
        and grill.get("issue") == story
        and grill.get("task_id") == task_id
        and grill.get("task_plan_sha256") == digest
        and grill.get("approved_task_plan_sha256") == digest
        and isinstance(grill.get("approved_by"), str)
        and grill["approved_by"].strip()
        and not any(field in grill for field in (
            "approval_runtime", "approval_session_id", "approval_event_id",
        ))
    ):
        return False
    try:
        return task_grill_grounding_matches(root, task, grill, treeish=treeish)
    except SystemExit:
        return False


def _task_grill_fresh(root: Path, task: dict, grill: dict) -> bool:
    task_id = task.get("id")
    plan = evidence_path(
        root, _active_story_key(root), f"task-plans/{task_id}.md",
    )
    if not plan.is_file():
        return False
    digest = plan_digest_without_assumptions(plan)
    plan_provenance_ok = (
        grill.get("task_plan_sha256") == digest
        or _task_plan_amendment_preserves_cold_proof(root, task, grill)
    )
    try:
        grounded = task_grill_grounding_matches(root, task, grill)
    except SystemExit:
        # The approved story plan is gone — e.g. a shipped or archived story
        # whose plan moved out of plans/active/. A grill cannot be "fresh"
        # against a plan that no longer exists, and read-only callers (the
        # board's /api/state, `forge next`) must degrade, not crash. Gate
        # callers that require the plan call grounding_digest directly and
        # still raise.
        return False
    format_ok = all(field in grill for field in (
        "cold_input_sha256", "final_artifact_sha256", "finding_dispositions",
    )) or _legacy_inflight_task_grill(root, task, grill)
    return bool(
        grill.get("verdict") == "pass"
        and grill.get("commit")
        and grounded
        and plan_provenance_ok
        and format_ok
    )


def _task_plan_state(root: Path, task: dict, grill: dict) -> str:
    """Derive the post-grill task-plan state without storing a status."""
    task_id = task.get("id")
    key = _active_story_key(root)
    plan = evidence_path(root, key, f"task-plans/{task_id}.md")
    if not plan.is_file():
        return "author-task-plan"
    digest = plan_digest_without_assumptions(plan)
    cold_read_matches = grill.get("task_plan_sha256") == digest
    approved = _task_plan_approval_matches_digest(root, task, grill, digest)
    if approved:
        return "approved"
    if _task_plan_amendment_preserves_cold_proof(root, task, grill):
        return "await-approval"
    if cold_read_matches:
        return "await-approval"
    return "grill"


def task_rows(root: Path) -> list[dict]:
    """Derive every live task row from the same inputs as frontier routing."""
    tasks = load_json(
        protected_decomposition_state_path(root), default={}
    ).get("tasks", [])
    stages = load_json(git_control_dir(root) / "stages.json", default={})
    stage_by_id = {
        stage.get("id"): stage
        for stage in stages.get("stages", [])
        if isinstance(stage, dict)
    }
    rows = []
    key = _active_story_key(root)
    # Per-task PRs are the symphony standard when an origin/trunk exists to ship
    # to: a stage-done task reads "done" only once its completion marker is on the
    # trunk, else "await-merge" — mirroring task_frontier_state so the board and
    # `forge next` agree. Without an origin the row keeps its stage status.
    has_origin = _has_origin(root)
    # The board renders every task row per poll and per drawer open. Fetch the
    # trunk ONCE here, then check each done task's marker against that
    # already-fetched ref (refresh=False) instead of a live network fetch per
    # task — the fix for the "very very slow" board (N fetches per render -> 1).
    if has_origin:
        fetch_trunk(root, default_trunk_branch(root), ttl=MARKER_FETCH_TTL)
    for task in tasks:
        task_id = task.get("id")
        stage = stage_by_id.get(task_id, {})
        grill_path = evidence_path(root, key, f"grills/tasks/{task_id}.json")
        grill = load_json(grill_path, default={})
        fresh = _task_grill_fresh(root, task, grill) if grill else False
        status = stage.get("status")
        if status == "done" and has_origin:
            state = (
                "done"
                if task_marker_on_main(root, key, task_id, refresh=False)
                else "await-merge"
            )
        elif status == "done":
            state = "done"
        elif status == "active":
            state = "active"
        elif not _task_contract_complete(task):
            state = "skeleton"
        else:
            plan_state = _task_plan_state(root, task, grill)
            if plan_state == "author-task-plan":
                state = plan_state
            elif not fresh:
                state = "ready"
            else:
                state = "grilled" if plan_state == "approved" else plan_state

        budget = None
        if state == "active":
            from forge_cli.stages import (
                WORKFLOW_PATHS, _changed_line_count, changed_paths,
                review_budget, stage_baseline,
            )

            max_files, max_lines, _reason = review_budget(task)
            base_sha = stage_baseline(root, stage)
            product = [
                path for path in changed_paths(
                    root, base_sha, stage.get("dirty_at_start", {})
                )
                if not path.startswith(WORKFLOW_PATHS)
            ] if base_sha else []
            budget = {
                "used": {
                    "files": len(product),
                    "lines": _changed_line_count(root, base_sha, product)
                    if base_sha else 0,
                },
                "limit": {"files": max_files, "lines": max_lines},
            }
        rows.append({
            "id": task_id,
            "state": state,
            "grill_freshness": (
                "fresh" if fresh else "stale" if grill else "missing"
            ),
            "budget": budget,
        })
    return rows


def linked_worktree_roots(root: Path) -> list[Path]:
    """Every linked worktree of this repo, plus this root.

    Read from git's own bookkeeping -- one `worktrees/<name>/gitdir` file per
    linked worktree -- rather than shelling out to `git worktree list`. Two
    small reads, and no lenient decode policy for process output.
    """
    roots = [root]
    try:
        git_dir = git_control_dir(root).parent
    except SystemExit:
        return roots
    # From inside a linked worktree that git dir is .git/worktrees/<name>;
    # the shared bookkeeping is its grandparent.
    common = (git_dir.parent.parent
              if git_dir.parent.name == "worktrees" else git_dir)
    registry = common / "worktrees"
    if not registry.is_dir():
        return roots
    for entry in sorted(registry.iterdir()):
        try:
            recorded = (entry / "gitdir").read_text(encoding="utf-8").strip()
        except (OSError, UnicodeDecodeError):
            continue
        if not recorded:
            continue
        candidate = Path(recorded).parent  # the .git FILE's parent is the tree
        try:
            if candidate.is_dir() and candidate.resolve() != root.resolve():
                roots.append(candidate)
        except OSError:
            continue
    return roots


def task_state_root(root: Path, task_id: str) -> Path:
    """Where THIS task's stage state actually lives.

    `forge task start` gives each task its own worktree, and a worktree has its
    own git control directory -- so `stages.json` exists once per tree and the
    copies drift the moment one of them closes a stage. A task-scoped command
    then answers differently depending on which directory it happened to run
    in, which is how a legitimately passing grill came to be stamped against
    the wrong basis: `record_grill` saw the task as still active in the main
    repo, ground on the working tree, and `pr-ready` -- run in the worktree,
    where the stage reads done -- verified against the stage baseline instead.
    Neither side was wrong about its own directory. That is the bug.

    A task's own worktree is the authority. Falls back to `root` when the task
    has no worktree (story-level stages, or a worktree already removed), so
    this is only ever more correct than reading the local copy.
    """
    if not task_id:
        return root
    for candidate in linked_worktree_roots(root):
        try:
            pointer = _raw_json_object(git_control_dir(candidate) / "run.json")
        except (OSError, SystemExit):
            continue
        if isinstance(pointer, dict) and pointer.get("task_id") == task_id:
            return candidate
    return root


def task_stage_record(root: Path, task_id: str) -> dict:
    """This task's stage as its OWN worktree records it (see task_state_root)."""
    home = task_state_root(root, task_id)
    stages = load_json(git_control_dir(home) / "stages.json", default={})
    for stage in stages.get("stages", []):
        if isinstance(stage, dict) and stage.get("id") == task_id:
            return stage
    return {}


def _task_schedule(root: Path) -> tuple[list[dict], dict[str, dict], set[str]]:
    """Tasks in declaration order, their stages, and the ids already done."""
    tasks = load_json(
        protected_decomposition_state_path(root), default={}
    ).get("tasks", [])
    stages = load_json(git_control_dir(root) / "stages.json", default={})
    stage_by_id = {
        stage.get("id"): stage
        for stage in stages.get("stages", [])
        if isinstance(stage, dict)
    }
    key = _active_story_key(root)
    is_task_level = run_is_task_level(root, key, [t for t in tasks if isinstance(t, dict)])
    done = {
        candidate.get("id")
        for candidate in tasks
        if (
            task_marker_on_main(root, key, candidate.get("id"))
            if is_task_level else
            stage_by_id.get(candidate.get("id"), {}).get("status") == "done"
        )
    }
    return tasks, stage_by_id, done


def task_dependencies(tasks: list[dict], task_id: str) -> list[str]:
    """A task's effective dependencies: its explicit list, else its predecessor.

    The recorder validates `dependencies` as backward-only (acyclic). A task
    that declares none depends on its immediate predecessor, so a decomposition
    without explicit dependencies keeps today's list order; only tasks with
    explicit dependencies opt into DAG order (symphony-forge #145).
    """
    previous: str | None = None
    for candidate in tasks:
        if candidate.get("id") == task_id:
            explicit = candidate.get("dependencies")
            if isinstance(explicit, list) and explicit:
                return [str(dependency) for dependency in explicit]
            return [previous] if previous else []
        previous = candidate.get("id")
    return []


def ready_task_ids(tasks: list[dict], done: set[str]) -> list[str]:
    """Pending tasks whose every effective dependency is done, in order."""
    return [
        candidate.get("id")
        for candidate in tasks
        if candidate.get("id") not in done
        and all(
            dependency in done
            for dependency in task_dependencies(tasks, candidate.get("id"))
        )
    ]


def task_ready_ids(root: Path) -> list[str]:
    """Pending tasks of the protected decomposition whose dependencies are done."""
    tasks, _stage_by_id, done = _task_schedule(root)
    return ready_task_ids(tasks, done)


def task_done_ids(root: Path) -> set[str]:
    """Tasks that are DONE for gating: marker on the trunk in a task worktree,
    stage done in a story-level tracker (the same rule `task_ready_ids` uses)."""
    return _task_schedule(root)[2]


def task_frontier_items(root: Path) -> list[tuple[str, dict]]:
    """Every task that can be acted on right now, first the one
    `task_frontier_state` would pick: tasks awaiting their merge, stages active
    in any worktree of this story, then every READY task whose write scope is
    disjoint from the active stages. Parallel work is the tail of this list."""
    from forge_cli.stages import active_stages_everywhere, scope_conflicts
    tasks, stage_by_id, done = _task_schedule(root)
    key = _active_story_key(root)
    first = task_frontier_state(root)
    items: list[tuple[str, dict]] = [first] if first else []
    listed = {first[1].get("id")} if first else set()
    active = {stage.get("id") for _root, stage in active_stages_everywhere(root)}
    for candidate in tasks:
        task_id = candidate.get("id")
        if task_id in listed or task_id in done:
            continue
        if _has_origin(root) and (
                stage_by_id.get(task_id, {}).get("status") == "done"
                or task_stage_record(root, task_id).get("status") == "done"
        ) and not task_marker_on_main(root, key, task_id):
            items.append(("await-merge", candidate))
            listed.add(task_id)
    for candidate in tasks:
        task_id = candidate.get("id")
        if task_id in listed or task_id not in active:
            continue
        items.append(("delegate", candidate))  # active in its own worktree
        listed.add(task_id)
    unmerged = {task.get("id") for state, task in items if state == "await-merge"}
    for task_id in ready_task_ids(tasks, done):
        # A dependency that is done but not yet merged has not shipped: the
        # per-task PR flow starts the next task from the trunk that has it.
        if task_id in listed or task_id in active or scope_conflicts(root, task_id) \
                or unmerged & set(task_dependencies(tasks, task_id)):
            continue
        candidate = next(c for c in tasks if c.get("id") == task_id)
        items.append((_task_action_state(root, key, candidate,
                                         stage_by_id.get(task_id, {})), candidate))
        listed.add(task_id)
    return items


def task_frontier_state(root: Path) -> tuple[str, dict] | None:
    """Return the next JIT action and the task to act on, without raising.

    Prefers a stage that is already active; otherwise the earliest READY task
    (dependencies done), falling back to the earliest unfinished task.
    """
    tasks, stage_by_id, done = _task_schedule(root)
    key = _active_story_key(root)

    # Per-task PRs are the symphony standard: every task ships its OWN PR after
    # its local autoreview + `forge stage done`, and merges to the trunk before
    # the next task starts (WORKFLOW.md "Stage Loop"). A stage-done task whose
    # completion marker is not yet on the trunk must surface the per-task PR in
    # BOTH run-pointer modes — task-level (`base_main_sha`) and story-level (a
    # stage running in the story worktree). In story-level mode `_task_schedule`
    # folds stage-done tasks into `done`, so the frontier selection below would
    # skip past this task; this pre-check catches it first, before selection.
    # Only applies when an origin/trunk exists to ship the PR to — a repo without
    # an origin keeps the stage-status frontier (no per-task PR to await).
    if _has_origin(root):
        # A task closed in its OWN worktree is done there, not in this tracker.
        await_merge = next(
            (
                candidate for candidate in tasks
                if (stage_by_id.get(candidate.get("id"), {}).get("status") == "done"
                    or task_stage_record(root, candidate.get("id")).get("status")
                    == "done")
                and not task_marker_on_main(root, key, candidate.get("id"))
            ),
            None,
        )
        if await_merge is not None:
            return "await-merge", await_merge

    ready = set(task_ready_ids(root))
    # A task worktree's frontier is ITS task: with two tasks ready side by
    # side, the earlier one is not this worktree's work. And a task active in
    # a SIBLING worktree is not this checkout's frontier either — it is
    # someone else's; this checkout moves on to the next ready task.
    from forge_cli.stages import active_stages_everywhere
    own = load_json(run_state_path(root), default={}).get("task_id")
    elsewhere = {
        stage.get("id") for wt, stage in active_stages_everywhere(root)
        if wt.resolve() != root.resolve() and stage.get("id") != own
    }

    def local(candidate: dict) -> bool:
        return candidate.get("id") not in done and candidate.get("id") not in elsewhere

    frontier = next(
        (
            candidate for candidate in tasks
            if candidate.get("id") == own and local(candidate)
            and (candidate.get("id") in ready
                 or stage_by_id.get(own, {}).get("status") == "active")
        ),
        None,
    ) or next(
        (
            candidate for candidate in tasks
            if local(candidate)
            and stage_by_id.get(candidate.get("id"), {}).get("status") == "active"
        ),
        None,
    ) or next(
        (candidate for candidate in tasks
         if local(candidate) and candidate.get("id") in ready),
        None,
    ) or next(
        (candidate for candidate in tasks if local(candidate)),
        None,
    ) or next(
        (candidate for candidate in tasks if candidate.get("id") not in done),
        None,
    )
    if frontier is None:
        return None
    return _task_action_state(
        root, key, frontier, stage_by_id.get(frontier.get("id"), {})), frontier


def _proof_problem_action(task_id: object, first: str) -> str:
    prefix = f"{task_id}: "
    groups = {
        "verify": ("no passing verify", "verify proof",
                   "product content changed after verify proof"),
        "tests": ("no passing automated tests", "tests proof",
                  "product content changed after tests proof"),
        "functional": ("user_facing, so a functional check is required",
                       "functional check must be passed"),
    }
    for action, starts in groups.items():
        if first.startswith(tuple(prefix + value for value in starts)):
            return action
    review_starts = tuple(
        prefix + value
        for lens in _PROOF_LENSES
        for value in (f"no {lens} review", f"{lens} review",
                      f"reviews.{lens} proof",
                      f"product content changed after reviews.{lens} proof")
    ) + tuple(prefix + value for value in (
        "selected review", "rejection review", "upgrade review", "review brief",
        "saved review brief", "tests.json review input",
        "cannot render the complete approved-input section",
    )) + ("quality, performance, and security reviews", "review_run_id",
          "branch review is stale")
    return "review" if first.startswith(review_starts) else "inspect-proof"


def proof_problem_action(task_id: object, problem: str) -> str:
    """Classify a task proof problem for the next repair action."""
    return _proof_problem_action(task_id, problem)


def _recorded_failure_action(root: Path, key: str, task_id: str) -> str | None:
    from forge_cli.readiness import tests_passed, verify_passed

    verify = load_json(task_evidence_path(root, key, task_id, "verify.json"), default={})
    tests = load_json(task_evidence_path(root, key, task_id, "tests.json"), default={})
    current_head = head_sha(root)
    if verify and verify.get("commit") == current_head and not verify_passed(verify):
        return "fix-verify"
    for name, action, functional in (
        ("automated", "fix-tests", False),
        ("functional", "fix-functional", True),
    ):
        report = tests.get(name) if isinstance(tests, dict) else None
        if (tests.get("commit") == current_head and isinstance(report, dict)
                and not tests_passed(report, functional=functional)):
            return action
    return None


def _successful_delegation_action(
    root: Path, key: str, task: dict, task_id: str,
) -> str:
    from forge_cli.review import _product_dirty
    from forge_cli.readiness import review_passed

    if _product_dirty(root):
        return "commit"
    failed = _recorded_failure_action(root, key, task_id)
    if failed:
        return failed
    try:
        current_delta = product_delta_digest(
            root, effective_review_base(root, task_id),
        )
        generation, _selection, selected_problems = read_selected_review_generation(
            root, key, task_id, expected_delta_id=current_delta,
        )
    except (Exception, SystemExit):
        return "inspect-proof"
    if not selected_problems and isinstance(generation, dict) and any(
            not review_passed(generation["lenses"].get(lens))
            for lens in _PROOF_LENSES):
        return "fix-review"
    problems = task_proof_problems(root, key, task, preseal=True)
    return "stage-done" if not problems else _proof_problem_action(task_id, problems[0])


def _waiting_delegation_action(
    root: Path, ledger: list[dict], key: str, task_id: object,
    started_at: str, digest: str,
) -> str:
    rows = [
        row for row in ledger
        if row.get("task") == task_id and row.get("story") == key
        and row.get("write") is True and row.get("stage_started_at") == started_at
        and row.get("task_sha256") == digest
    ]
    if not rows:
        return "delegate"
    latest = rows[-1]
    if latest.get("launch_status") not in {"starting", "running"}:
        return "inspect-delegate"
    from forge_cli.codex_status import dead_launches
    dead = {row.get("launch_id") for row in dead_launches(root)}
    return ("inspect-delegate" if latest.get("launch_id") in dead
            else "watch-delegate")


def _task_action_state(root: Path, key: str, task: dict, stage: dict) -> str:
    """The next JIT action for ONE task, given its stage record."""
    task_id = task.get("id")
    if not _task_contract_complete(task):
        return "author-contract"
    grill = load_json(evidence_path(root, key, f"grills/tasks/{task_id}.json"), default={})
    plan_state = _task_plan_state(root, task, grill)
    if plan_state == "author-task-plan":
        return plan_state
    if not _task_grill_fresh(root, task, grill):
        return "grill"
    if plan_state != "approved" or stage.get("status") != "active":
        return plan_state if plan_state != "approved" else "stage-start"

    from forge_cli.delegate import current_delegation, load_delegations
    started_at = str(stage.get("started_at") or "")
    digest = task_digest(task)
    try:
        terminal = current_delegation(
            root, str(task_id), stage_started_at=started_at,
            task_sha256=digest, ignore_lock=True,
        )
        ledger = load_delegations(root)
    except (Exception, SystemExit):
        return "inspect-delegate"
    if terminal and terminal.get("story") == key:
        if terminal.get("launch_status") != "succeeded":
            return "inspect-delegate"
        return _successful_delegation_action(root, key, task, str(task_id))
    return _waiting_delegation_action(
        root, ledger, key, task_id, started_at, digest,
    )


INTERRUPT_REFUSAL = (
    "You are inside an OPEN implementation stage. Questions to the human "
    "belong in PLANNING — the plan is already approved, and from here to the "
    "PR the run is yours.\n\n"
    "Check first whether this is already settled by: the task contract - the "
    "approved plan - the constitution - an accepted decision record - a lesson "
    "in force for these paths. If it is, act on it and CONTINUE.\n\n"
    "Never a question for the human:\n"
    "  - a review budget ceiling: raise it with a recorded reason and continue. "
    "It is measured by `stage done` on a FINISHED diff, which is the only "
    "point splitting can be judged, and changing it no longer re-grills.\n"
    "  - a file the work mechanically implies but write_scope omits (a "
    "lockfile, a module registration, a barrel, a doc reference): extend the "
    "scope, name each file and why the work implies it, continue.\n"
    "  - an environment or sandbox block: take the documented path "
    "(docs/degraded-mode.md, a binding lesson, a pinned mirror).\n\n"
    "If a decision GENUINELY does not exist yet, name it and this stands "
    "down:\n"
    "  ./forge signal escalate --missing-decision \"<what nobody has decided>\" "
    "--checked \"contract,plan,constitution,decisions,lessons\"\n\n"
    "A mid-stage re-grill is allowed the same way: escalate naming the "
    "substantive contract field that changed."
)


def may_interrupt(root: Path, *, spend: bool = False) -> tuple[bool, str]:
    """Whether the agent may stop to involve the human right now.

    The window is the OPEN STAGE — `stage start` follows the human approving
    the task plan, `stage done` follows the review — so from approval to PR the
    run belongs to the agent. The way out is to finish the task; there is no
    proxy for having finished it.

    Asked by BOTH hooks so they cannot disagree. Fails OPEN on unreadable
    state: a missed interruption costs one question, a broken hook costs the
    session.
    """
    try:
        from forge_cli.signal import open_escalation, spend_escalation
        stages = load_json(
            git_control_dir(root) / "stages.json", default={})
        active = any(stage.get("status") == "active"
                     for stage in stages.get("stages", []))
        if not active:
            return True, ""                      # planning: ask freely
        record = open_escalation(root)
        if record:
            # Spent HERE, not by the caller: one escalation authorises one
            # interruption through either door. The Stop hook used to let a
            # turn end without consuming it, so a single genuine question left
            # the gate open for the rest of the stage.
            if spend:
                spend_escalation(root, record)
            return True, ""
        return False, INTERRUPT_REFUSAL
    except Exception:
        return True, ""


def require_task_start_recorded(root: Path, task_id: str, *,
                                trunk: bool = False) -> None:
    """`stage start` is the wrong place to discover `task start` was skipped.

    require_task_worktree returns early when the run pointer has no task_id --
    the very state a skipped `task start` leaves -- so every task-level guard
    silently stopped checking. This asks the question those guards assume has
    already been answered, at the one moment it can still be answered cheaply:
    before the stage opens and pins a baseline.
    """
    state = load_json(run_state_path(root), default={})
    recorded = state.get("task_id")
    if isinstance(recorded, str) and recorded:
        return
    if trunk:
        return
    raise SystemExit(
        f"stage start refused: `./forge task start {task_id}` has not been run "
        f"on this checkout.\n"
        f"  It creates the task branch and its SIBLING WORKTREE and pins "
        f"base_main_sha; without it the work lands on the trunk's own tree and "
        f"the seal cannot measure the diff later.\n"
        f"  Run `./forge task start {task_id}`, then run this from INSIDE the "
        f"worktree it prints.\n"
        f"  Deliberately working on the trunk instead? Say so: "
        f"`./forge stage start {task_id} --trunk`. It is recorded on the "
        f"stage, so a trunk-based run is a choice someone made rather than "
        f"a step someone forgot."
    )


def require_task_worktree(root: Path, *, allow_completed: bool = False) -> None:
    """Bind task-level actions to the worktree recorded by `task start`."""
    state = load_json(run_state_path(root), default={})
    task_id = state.get("task_id")
    # task_id is the task-level marker `forge task start` sets; a story-level run
    # carries `branch` (from intake) but no task_id and must not be gated here.
    if not (isinstance(task_id, str) and task_id):
        return
    branch = state.get("branch")
    if not (isinstance(branch, str) and branch):
        raise SystemExit(
            "task worktree pointer names a task_id without a branch — "
            "re-run `./forge task start`"
        )
    proc = subprocess.run(
        ["git", "symbolic-ref", "--quiet", "--short", "HEAD"],
        cwd=root, capture_output=True, text=True, env=clean_git_env(),
        encoding="utf-8", errors="surrogateescape",
    )
    current_branch = proc.stdout.strip() if proc.returncode == 0 else ""
    frontier = task_frontier_state(root)
    frontier_id = frontier[1].get("id") if frontier else None
    stage = next((stage for stage in load_json(
        git_control_dir(root) / "stages.json", default={}
    ).get("stages", []) if stage.get("id") == task_id), {})
    completed = stage.get("status") == "done"
    task_matches = frontier_id == task_id or (allow_completed and completed)
    if current_branch != branch or not task_matches:
        raise SystemExit(
            "task worktree required: expected "
            f"branch {branch!r} at frontier {task_id!r}, found "
            f"branch {current_branch or '<detached>'!r} at frontier "
            f"{frontier_id or 'none'!r}"
        )


def required_tests_outside_scope(task: dict, root: Path | None = None) -> list[str]:
    """Required-test paths the task is not allowed to write.

    Prefix matching on write_scope entries, which name directories or files:
    "src/" covers "src/a/b.spec.ts", and an entry naming the file covers
    exactly it. An empty scope is not judged here — the contract completeness
    check already refuses that.
    """
    scope = [str(entry).replace("\\", "/").rstrip("/")
             for entry in (task.get("write_scope") or []) if entry]
    if not scope:
        return []
    outside: list[str] = []
    for test in task.get("required_tests") or []:
        path = str((test or {}).get("path") or "").replace("\\", "/").strip()
        if not path:
            continue
        if any(path == entry or path.startswith(entry + "/")
               for entry in scope):
            continue
        # Outside the scope is only a CONTRADICTION when the task has to
        # create the file. A required test that already exists is a proof the
        # task must not break — it needs no write access to it, and refusing
        # that would forbid a perfectly good contract.
        if root is not None and (root / path).exists():
            continue
        outside.append(path)
    return outside


def require_ready_task(
    root: Path, task_id: str, *, require_approval: bool = True,
    allow_completed: bool = False, require_grill: bool = True,
) -> dict:
    """Require the JIT execution contract and its fresh, passing grill."""
    tasks = load_json(
        protected_decomposition_state_path(root), default={}
    ).get("tasks", [])
    task = next(
        (candidate for candidate in tasks if candidate.get("id") == task_id),
        None,
    )
    if task is None:
        raise SystemExit(
            f"{task_id!r} is not a task in the protected decomposition."
        )

    tasks_all, stage_by_id, done = _task_schedule(root)
    stage = stage_by_id.get(task_id, {})
    completed = stage.get("status") == "done"
    if allow_completed and completed:
        # Merge order is the dependency order: a done task seals only once
        # its dependencies are done (their markers on the trunk in a task
        # worktree), never ahead of them.
        waiting = [d for d in task_dependencies(tasks_all, task_id) if d not in done]
        if waiting:
            raise SystemExit(
                f"{task_id} cannot seal before its dependencies ship: waiting on "
                f"{', '.join(waiting)} — merge those task PRs first."
            )
    else:
        # Another active stage is no longer a refusal here: a task is grilled
        # and approved while a sibling runs, and `stage start` is what refuses
        # to OPEN it beside a sibling whose write scope overlaps (scope_conflicts).
        if task_id not in ready_task_ids(tasks_all, done):
            waiting = [
                d for d in task_dependencies(tasks_all, task_id) if d not in done
            ]
            raise SystemExit(
                f"{task_id} is not ready: waiting on "
                f"{', '.join(waiting) or 'nothing'}; tasks start only once their "
                "dependencies are done (a task without explicit dependencies "
                "follows its predecessor)."
            )

    unreachable = required_tests_outside_scope(task, root)
    if unreachable:
        raise SystemExit(
            f"{task_id} cannot produce its own required tests: "
            f"{', '.join(unreachable)} "
            f"{'is' if len(unreachable) == 1 else 'are'} outside write_scope "
            f"({', '.join(task.get('write_scope') or []) or 'empty'}).\n"
            "  The contract asks the task to CREATE a proof it is not allowed "
            "to write (the file does not exist yet). "
            "Fix it in the decomposition NOW — discovering this mid-"
            "implementation costs a paused worker and an interrupted human."
        )

    for field in _TASK_CONTRACT_FIELDS:
        value = task.get(field)
        if not value or (isinstance(value, str) and not value.strip()):
            raise SystemExit(
                f"{task_id} task contract is incomplete: {field} is empty. "
                "Author the JIT contract and re-record it with "
                "`python3 factory/scripts/record_decomposition_from_json.py "
                f"--input <json>`. `forge delegate {task_id} --read-only` "
                "remains available for exploration only."
            )

    treeish = ""
    if allow_completed and completed:
        from forge_cli.stages import stage_baseline
        # Resolve the baseline where the stage that recorded it lives, so the
        # seal and the recorder agree no matter which tree either runs in.
        treeish = stage_baseline(task_state_root(root, task_id), stage)
    key = _active_story_key(root)
    grill = load_json(
        evidence_path(root, key, f"grills/tasks/{task_id}.json"), default={},
    )
    if require_approval and _task_plan_state(root, task, grill) == "author-task-plan":
        raise SystemExit(
            f"Task plan required first: author {task_id} in plan mode, then run "
            f"`./forge task plan save {task_id} --from <path>`."
        )
    if require_grill:
        require_task_grill(root, task_id, task, treeish=treeish)
    if require_approval:
        plan_state = _task_plan_state(root, task, grill)
        if plan_state == "grill":
            raise SystemExit(
                f"the {task_id} task grill is STALE — the task plan changed "
                "before any native approval bound it. Re-grill and record "
                "`python3 factory/scripts/record_grill_from_json.py --gate task "
                f"--task {task_id}` against the current plan."
            )
        if plan_state == "await-approval":
            raise SystemExit(
                f"Task plan approval required: display the exact current {task_id} "
                "plan in native Plan Mode and consume its approval event."
            )
    return task


def task_seal_shared_problems(root: Path, issue_key: str) -> list[str]:
    """Predicates shared by task sealing and story closeout readiness."""
    from forge_cli.assumptions import blocking_for_issue
    from forge_cli.quickfix import _lite_product_files, load_active, profile_of
    from forge_cli.signal import open_signals
    from forge_cli.stages import product_tree_snapshot

    problems: list[str] = []
    signals = open_signals(root)
    if signals:
        ids = ", ".join(f"{signal['id']} ({signal['kind']})" for signal in signals)
        problems.append(
            f"resolution of {len(signals)} open worker signal(s): {ids} — "
            "`forge.py signal resolve <id> --notes ...`"
        )
    window = load_active(root)
    if window:
        profile = profile_of(window)
        closer = "quickfix done" if profile == "quickfix" else "mode done"
        problems.append(
            f"closure of {profile} window {window['id']} ({window['reason']}) — "
            f"`forge.py {closer}`"
        )
    assumptions = blocking_for_issue(root, issue_key) if issue_key else []
    if assumptions:
        ids = ", ".join(f"{row['id']} ({row['status']})" for row in assumptions)
        problems.append(
            f"orchestrator guidance on {len(assumptions)} assumption(s): {ids} — "
            "resolve via `forge.py assumptions resolve <id> "
            "--status confirmed|promoted --notes ...`"
        )
    dirty_product = _lite_product_files(
        root, list(product_tree_snapshot(root).get("dirty", {})),
    )
    if dirty_product:
        problems.append(
            "clean product worktree and index: staged or unstaged product changes "
            f"remain ({', '.join(dirty_product[:5])})"
        )
    return problems


def require_task_sealed(root: Path, task_id: str) -> dict:
    """Require the approved, reviewed, committed seal for one completed task."""
    from forge_cli.stages import _require_reviewed_commit, load_stages

    state = load_json(run_state_path(root), default={})
    bound_task = state.get("task_id")
    if bound_task:
        # `forge task start` mode: the worktree is bound to a specific task_id;
        # enforce that binding and the worktree pointer.
        if bound_task != task_id:
            raise SystemExit(
                f"task worktree required: this worktree is bound to "
                f"{bound_task!r}, not {task_id!r}"
            )
        require_task_worktree(root, allow_completed=True)
    # Stage-based mode (no task_id in the run pointer, e.g. the task ran via
    # `forge stage start` on the story branch): there is no task-bound worktree,
    # so the seal is proven by the done stage + reviewed commit gate below
    # rather than a worktree pointer.
    task = require_ready_task(root, task_id, allow_completed=True)
    stage = next(
        (candidate for candidate in load_stages(root).get("stages", [])
         if candidate.get("id") == task_id),
        None,
    )
    if not stage or stage.get("status") != "done":
        raise SystemExit(f"task {task_id} is not sealed: stage status must be done")
    issue_key = state.get("issue_key") or state.get("story") or ""
    problems = task_seal_shared_problems(root, issue_key)
    if problems:
        raise SystemExit("Task not PR ready:\n- " + "\n- ".join(problems))
    proof_problems = task_proof_problems(root, issue_key, task, preseal=True)
    if proof_problems:
        raise SystemExit("Task proof incomplete:\n- " + "\n- ".join(proof_problems))
    _require_reviewed_commit(root, stage, task)
    return task


def changed_since(root: Path, stamp: str, prefixes: tuple[str, ...]) -> list[str]:
    """Committed files under `prefixes` changed between `stamp` and HEAD.

    Returns ["<unknown commit>"] when the stamp is not in this repo's history,
    so callers treat an unverifiable stamp as stale rather than fresh."""
    head = head_sha(root)
    if not head or not stamp or stamp == head:
        return []
    proc = subprocess.run(
        ["git", "diff", "--name-only", f"{stamp}..{head}"],
        cwd=root, capture_output=True, text=True,
        encoding="utf-8", errors="surrogateescape",
    )
    if proc.returncode != 0:
        return [f"<commit {stamp[:8]} unknown to this repo>"]
    return [f for f in proc.stdout.splitlines() if f.startswith(prefixes)]


def _paths_changed_after(
    root: Path, commit: str, paths: list[str], *, head: str = "HEAD",
) -> tuple[set[str], str]:
    """Return every path touched after commit, including restored rewrites."""
    proc = subprocess.run(
        ["git", "log", "--format=", "--name-only", f"{commit}..{head}", "--", *paths],
        cwd=root, capture_output=True, text=True, env=clean_git_env(),
        encoding="utf-8",
    )
    if proc.returncode != 0:
        return set(), proc.stderr.strip() or "git log failed"
    return {path for path in proc.stdout.splitlines() if path}, ""


def read_hook_input() -> dict[str, Any]:
    raw = read_stdin_utf8().strip()
    if not raw:
        return {}
    return json.loads(raw)


def read_stdin_utf8() -> str:
    """Read process input as strict UTF-8, independent of the host locale."""
    stream = getattr(sys, "stdin")
    buffer = getattr(stream, "buffer", None)
    if buffer is None:
        # Imported/test hosts may supply an already-decoded StringIO. There
        # are no bytes left whose encoding this helper could choose.
        return stream.read()
    wrapper = io.TextIOWrapper(buffer, encoding="utf-8", errors="strict")
    try:
        return wrapper.read()
    finally:
        wrapper.detach()


def branch_name(root: Path | None = None) -> str:
    out = subprocess.run(["git", "branch", "--show-current"], cwd=root or repo_root(), check=True, capture_output=True, text=True, encoding="utf-8")
    return out.stdout.strip()


def infer_issue_key(value: str) -> str | None:
    match = re.search(r"([A-Z][A-Z0-9]+-\d+)", value)
    return match.group(1) if match else None


def ensure_issue_key(explicit: str | None = None, root: Path | None = None) -> str:
    # An explicitly passed key is accepted as-is (GitHub issue numbers, Jira,
    # plain slugs) as long as it is filesystem/branch-safe.
    if explicit and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", explicit.strip()):
        return explicit.strip()
    candidates = [explicit or "", os.environ.get("LINEAR_ISSUE_KEY", ""), branch_name(root)]
    for candidate in candidates:
        key = infer_issue_key(candidate)
        if key:
            return key
    raise SystemExit(
        "Unable to determine an issue key. Pass --issue <key> (e.g. ENG-123, GH-42, 42), "
        "set LINEAR_ISSUE_KEY, or use a branch like feat/ENG-123-slug."
    )


def slugify(text: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip()).strip("-").lower()
    return value or "task"


def run_cmd(command: str, cwd: Path | None = None) -> dict[str, Any]:
    # Decode captured child output as UTF-8 explicitly, matching the UTF-8 the
    # factory scripts now force on their own stdout/stderr. Without this the
    # parent falls back to the ANSI code page (cp1252 on Windows) when invoked
    # directly without PYTHONUTF8, so a check that emits a non-Latin-1 glyph or
    # a non-ASCII repo filename decodes to mojibake — or raises UnicodeDecodeError
    # on a byte cp1252 leaves undefined — aborting verify before evidence lands.
    # errors="replace" degrades a stray byte instead of crashing.
    proc = subprocess.run(command, cwd=cwd or repo_root(), shell=True,
                          capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    return {
        "command": command,
        "exit_code": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }
