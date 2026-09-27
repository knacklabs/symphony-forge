"""Planning records: specs, decisions and the roadmap. They ship through the fix lane.

Every command here runs only on a fix or story branch that Forge started (its state file is
in the checkout), and commits what it wrote there, so the change reaches main by `forge close`.

A spec's cold read, written by `forge read <slug>`, lives in the notes file beside the spec,
`docs/specs/<slug>.read.md`:

    ---
    reader: <who read it>
    read_at: <when>
    read_hash: <git hash-object of the spec as read>
    amended_hash: <git hash-object after the one amendment, recorded by --amended>
    ---
    1. <finding>
       Disposition: cut | defer | keep <one-line reason>

Each finding is a numbered item at the start of a line; its disposition follows it.
`spec confirm` stores the SHA-256 of the confirmed body (the text after the frontmatter) as
`confirmed_hash`, and `roadmap add` reads a spec only while its body still matches it.

A spec's `## Success measure` holds `- Metric:`, `- Baseline:`, `- Target:` and
`- Check date: YYYY-MM-DD` lines, each of which may wrap onto indented lines. `spec measure`
appends a `- Result: <text> (YYYY-MM-DD)` line and refreshes `confirmed_hash`.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import date
from pathlib import Path

from forge import repo

REFUSALS = {
    "bad_slug": ("{slug!r} is not a slug; a slug is lowercase words joined by hyphens.", "{next}"),
    "not_lane": ("{branch} is not a fix or story branch that Forge started, and planning records "
                 "ship through the fix lane.", 'forge fix start "<why>" --done "<done when>"'),
    "bad_name": ("--by needs the name of the human who confirmed, on one line.",
                 'forge {words} {slug} --by "<name>"'),
    "no_spec": ("docs/specs/{slug}.md does not exist; write the spec there first.",
                "forge spec save {slug}"),
    "incomplete": ("docs/specs/{slug}.md is missing {missing}.", "forge spec save {slug}"),
    "spec_confirmed": ("docs/specs/{slug}.md is confirmed and unchanged since; saving it again "
                       "would undo the human's confirmation.", "forge roadmap add {slug}"),
    "not_draft": ("docs/specs/{slug}.md is not a saved draft (status: {status}).",
                  "forge spec save {slug}"),
    "no_read": ("docs/specs/{slug}.md has no cold read.", "forge read {slug}"),
    "changed": ("docs/specs/{slug}.md changed after its cold read.", "forge read {slug} --amended"),
    "changed_again": ("docs/specs/{slug}.md changed after its one recorded amendment.",
                      "git diff -- docs/specs/{slug}.md"),
    "no_disposition": ("Finding {number} in docs/specs/{slug}.read.md has no disposition: cut, "
                       "defer, or keep with a reason.", 'forge spec confirm {slug} --by "{by}"'),
    "unconfirmed": ("docs/specs/{slug}.md is not confirmed (status: {status}); only a confirmed "
                    "spec adds roadmap items.", 'forge spec confirm {slug} --by "<name>"'),
    "not_confirmed_text": ("docs/specs/{slug}.md is not the text that was confirmed; it needs a new "
                           "cold read and confirmation.", "forge spec save {slug}"),
    "no_measure": ("docs/specs/{slug}.md needs a ## Success measure section with {missing} "
                   "filled in.", "forge spec save {slug}"),
    "measure_unconfirmed": ("docs/specs/{slug}.md is not confirmed (status: {status}); only a "
                            "confirmed spec records a result.",
                            'forge spec confirm {slug} --by "<name>"'),
    "bad_result": ("--result needs the measured result, on one line.",
                   'forge spec measure {slug} --result "<measured result>"'),
    "roadmap_section": ("The Roadmap section of docs/specs/{slug}.md needs one `- KEY: title` line "
                        "per story: {problem}.", "forge spec save {slug}"),
    "decision_exists": ("{rel} already exists.", 'forge decision accept {slug} --by "<name>"'),
    "no_decision": ("There is no decision docs/decisions/NNNN-{slug}.md.", "forge decision new {slug}"),
    "ambiguous": ("{name} matches more than one decision ({found}); name one as NNNN-slug.",
                  "{next}"),
    "not_proposed": ("{rel} is {status}, so it cannot be accepted.", "forge decision new <new-slug>"),
    "unfilled": ("{rel} has only the template's comments in {sections}; fill them in first.",
                 'forge decision accept {slug} --by "{by}"'),
    "no_superseded": ("{rel} supersedes {old}, but there is no such decision.",
                      'forge decision accept {slug} --by "{by}"'),
}

SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
LANE = re.compile(r"fix/(?P<fix>[a-z0-9][a-z0-9-]*)|story/(?P<key>[A-Z][A-Z0-9-]*)")
FRONTMATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.S)
SPEC_SECTIONS = ("Why", "Behaviour", "Acceptance criteria")
DECISION_SECTIONS = ("Context", "Decision", "Consequences")
FINDING = re.compile(r"^(\d+)\.[ \t]", re.M)
DISPOSITION = re.compile(r"^[ \t]*(?:[-*][ \t]+)?\**disposition:\**[ \t]*(cut|defer|keep)\b"
                         r"[ \t:\u2014\u2013-]*(\S?)", re.I | re.M)
MEASURE_LINE = re.compile(r"^-[ \t]*(Metric|Baseline|Target|Check date|Result):(.*(?:\n[ \t]+\S.*)*)",
                          re.M)  # a field wraps onto indented lines
MEASURE_FIELDS = {"Metric": "- Metric:", "Baseline": "- Baseline:", "Target": "- Target:",
                  "Check date": "- Check date: YYYY-MM-DD"}
ROADMAP_LINE = re.compile(r"- ([A-Z][A-Z0-9-]*): (\S.*)")
ROADMAP = "plans/roadmap.json"
DECISION = """---
status: proposed
confirmed_by: ""
date: {date}
stories: []
supersedes: ""
---

# {title}

## Context
<!-- Why this decision was needed; the forces at play. -->

## Decision
<!-- What was decided, in one or two sentences. -->

## Consequences
<!-- What follows: tradeoffs accepted, doors closed, work implied. -->
"""


# --- specs -----------------------------------------------------------------------------


def spec_save(args: argparse.Namespace) -> None:
    top = _start(args, args.slug)
    rel, text, fields, body = _spec(top, args.slug)
    if not text:
        repo.refuse(REFUSALS["no_spec"], slug=args.slug)
    # A confirmed spec whose body changed goes back to a draft for a new read and confirm.
    if fields.get("status") == "confirmed" and fields.get("confirmed_hash") == _digest(body):
        repo.refuse(REFUSALS["spec_confirmed"], slug=args.slug)
    title = re.search(r"^# +(.+?)(?:[ \t]+#+)?[ \t]*$", body, re.M)
    sections = _sections(body)
    missing = [f"## {name}" for name in SPEC_SECTIONS if not sections.get(name, "").strip()]
    if not title or missing:
        repo.refuse(REFUSALS["incomplete"], slug=args.slug,
                    missing=", ".join(([] if title else ["a # title"]) + missing))
    _check_measure(args.slug, body)
    _roadmap_items(args.slug, body)  # a malformed Roadmap section fails here, before the read
    _write(top, rel, _set(text, slug=args.slug, title=title[1], status="draft", saved=repo.now(),
                          confirmed_by=None, confirmed_hash=None))
    repo.commit_state(f"Save the {args.slug} spec as a draft", rel, top=top)
    print(f"Saved {rel} as a draft. Next: forge read {args.slug}")


def spec_confirm(args: argparse.Namespace) -> None:
    top = _start(args, args.slug)
    by = _name(args, args.slug)
    rel, text, fields, body = _spec(top, args.slug)
    status = fields.get("status") or "none"
    if status == "confirmed":
        print(f"{rel} is already confirmed.")
        return
    if status != "draft":
        repo.refuse(REFUSALS["not_draft"], slug=args.slug, status=status)
    _check_measure(args.slug, body)
    notes = f"docs/specs/{args.slug}.read.md"
    record, findings = _front(_text(top, notes))
    if not record.get("read_hash"):
        repo.refuse(REFUSALS["no_read"], slug=args.slug)
    amended = record.get("amended_hash")
    if repo.git("hash-object", "--", rel, cwd=top) != (amended or record["read_hash"]):
        repo.refuse(REFUSALS["changed_again" if amended else "changed"], slug=args.slug)
    parts = FINDING.split(findings)
    for number, finding in zip(parts[1::2], parts[2::2]):
        found = DISPOSITION.search(finding)
        if not found or (found[1].lower() == "keep" and not found[2]):
            repo.refuse(REFUSALS["no_disposition"], number=number, slug=args.slug, by=by)
    _write(top, rel, _set(text, status="confirmed", confirmed_by=f'"{by}"',
                          confirmed_hash=_digest(body)))
    repo.commit_state(f"Confirm the {args.slug} spec", rel, notes, top=top)
    print(f"{rel} is confirmed by {by}. Next: forge roadmap add {args.slug}")


def spec_measure(args: argparse.Namespace) -> None:
    top = _start(args, args.slug)
    result = args.result.strip()
    if not result or not result.isprintable():
        repo.refuse(REFUSALS["bad_result"], slug=args.slug)
    rel, text, fields, body = _spec(top, args.slug)
    if not text:
        repo.refuse(REFUSALS["no_spec"], slug=args.slug)
    if fields.get("status") != "confirmed":
        repo.refuse(REFUSALS["measure_unconfirmed"], slug=args.slug,
                    status=fields.get("status") or "none")
    if fields.get("confirmed_hash") != _digest(body):
        repo.refuse(REFUSALS["not_confirmed_text"], slug=args.slug)
    _check_measure(args.slug, body)
    front = text[:len(text) - len(body)]
    heading = list(re.finditer(r"^## +(.+?)(?:[ \t]+#+)?[ \t]*$", body, re.M))
    at = max(n for n, found in enumerate(heading) if found[1] == "Success measure")  # as _sections
    end = heading[at + 1].start() if at + 1 < len(heading) else len(body)
    cut = heading[at].end() + len(body[heading[at].end():end].rstrip())
    body = body[:cut] + f"\n- Result: {result} ({repo.now()[:10]})" + body[cut:]
    _write(top, rel, _set(front + body, confirmed_hash=_digest(body)))
    repo.commit_state(f"Record the result of the {args.slug} spec's success measure", rel, top=top)
    print(f"Added the result to the Success measure of {rel}; it stays confirmed.")


def due_check(text: str, today: str) -> tuple[str, str] | None:
    """A confirmed spec's title and metric when its check date has come and it has no result yet.

    Whether its stories are done is the caller's to check.
    """
    fields, body = _front(text)
    measure = success_measure(body)
    if (fields.get("status") != "confirmed" or _measure_gaps(measure) or "Result" in measure
            or measure["Check date"] > today):
        return None
    return fields.get("title") or "", measure["Metric"].rstrip(".")


def success_measure(body: str) -> dict[str, str]:
    """The fields of a spec's Success measure, each on one line; {} when it has none."""
    return {match[1]: " ".join(match[2].split())
            for match in MEASURE_LINE.finditer(_sections(body).get("Success measure", ""))}


# --- decisions -------------------------------------------------------------------------


def decision_new(args: argparse.Namespace) -> None:
    top = _start(args, args.slug)
    existing = _decision(top, args.slug, "forge decision new <new-slug>")
    if existing:
        repo.refuse(REFUSALS["decision_exists"], rel=existing, slug=args.slug)
    number = max(_decision_numbers(top), default=0) + 1
    rel = f"docs/decisions/{number:04d}-{args.slug}.md"
    _write(top, rel, DECISION.format(date=repo.now()[:10],
                                     title=args.slug.replace("-", " ").capitalize()))
    repo.commit_state(f"Propose the {args.slug} decision", rel, top=top)
    print(f"Wrote {rel}; no branch has a higher decision number. Fill it in, then once the human "
          f'confirms in chat: forge decision accept {args.slug} --by "<name>"')


def decision_accept(args: argparse.Namespace) -> None:
    top = _start(args, args.slug)
    by = _name(args, args.slug)
    rel = _decision(top, args.slug, f'forge decision accept NNNN-{args.slug} --by "{by}"')
    if not rel:
        repo.refuse(REFUSALS["no_decision"], slug=args.slug)
    text = _text(top, rel)
    fields, body = _front(text)
    status = fields.get("status") or "proposed"
    if status == "accepted":
        print(f"{rel} is already accepted.")
        return
    if status != "proposed":
        repo.refuse(REFUSALS["not_proposed"], rel=rel, status=status)
    sections = _sections(body)
    unfilled = [name for name in DECISION_SECTIONS
                if not re.sub(r"<!--.*?-->", "", sections.get(name, ""), flags=re.S).strip()]
    if unfilled:
        repo.refuse(REFUSALS["unfilled"], rel=rel, sections=", ".join(unfilled), slug=args.slug,
                    by=by)
    changed = [rel]
    old = fields.get("supersedes")
    if old:
        old_rel = _decision(top, old, f'forge decision accept {args.slug} --by "{by}"',
                            f"supersedes: {old} in {rel}")
        if not old_rel or old_rel == rel:
            repo.refuse(REFUSALS["no_superseded"], rel=rel, old=old, slug=args.slug, by=by)
        _write(top, old_rel, _set(_text(top, old_rel), status="superseded",
                                  superseded_by=Path(rel).stem))
        changed.append(old_rel)
    _write(top, rel, _set(text, status="accepted", confirmed_by=f'"{by}"'))
    repo.commit_state(f"Accept the {args.slug} decision", *changed, top=top)
    also = f"; {changed[1]} is now superseded" if old else ""
    print(f"Accepted {rel}, confirmed by {by}{also}.")


# --- the roadmap -----------------------------------------------------------------------


def roadmap_add(args: argparse.Namespace) -> None:
    slug = args.spec
    top = _start(args, slug)
    rel, _, fields, body = _spec(top, slug)
    if fields.get("status") != "confirmed":
        repo.refuse(REFUSALS["unconfirmed"], slug=slug, status=fields.get("status") or "none")
    if fields.get("confirmed_hash") != _digest(body):
        repo.refuse(REFUSALS["not_confirmed_text"], slug=slug)
    wanted = _roadmap_items(slug, body)
    if not wanted:
        repo.refuse(REFUSALS["roadmap_section"], slug=slug, problem="it has none")
    items = repo.roadmap(top)  # refuses a roadmap it can't read
    taken = {item["key"]: item.get("spec") for item in items}
    for key in wanted:
        if key in taken and taken[key] != rel:
            repo.refuse(REFUSALS["roadmap_section"], slug=slug,
                        problem=f"{key} is already on the roadmap for {taken[key] or 'no spec'}")
    new = [key for key in wanted if key not in taken]
    if not new:
        print(f"{ROADMAP} already has every item in {rel}.")
        return
    data = json.loads(_text(top, ROADMAP) or "{}")  # the other top-level keys stay as they are
    last = max((item["order"] for item in items if isinstance(item.get("order"), int)), default=0)
    data["items"] = items + [{"key": key, "title": wanted[key], "spec": rel, "status": "pending",
                              "order": last + n} for n, key in enumerate(new, 1)]
    _write(top, ROADMAP, json.dumps(data, indent=2) + "\n")
    repo.commit_state(f"Add {', '.join(new)} to the roadmap from the {slug} spec", ROADMAP, top=top)
    print(f"Added {', '.join(new)} to {ROADMAP} from {rel}.")


# --- helpers ---------------------------------------------------------------------------


def _start(args: argparse.Namespace, slug: str) -> Path:
    """The checkout's top, once the slug is sound and the branch is a Forge fix or story."""
    if not SLUG.fullmatch(slug):  # also keeps every path under docs/
        fixed = "-".join(re.findall(r"[a-z0-9]+", slug.lower())) or "my-slug"
        by = f' --by "{args.by}"' if getattr(args, "by", None) else ""
        repo.refuse(REFUSALS["bad_slug"], slug=slug, next=f"forge {args.words} {fixed}{by}")
    top = repo.root()
    # ponytail: reuse CORE's branch rule, checked before any write so main never changes.
    branch = repo._work_branch(top)  # pyright: ignore[reportPrivateUsage]
    lane = LANE.fullmatch(branch)
    if not lane or repo.read_state(lane["fix"] or lane["key"], top) is None:
        repo.refuse(REFUSALS["not_lane"], branch=branch)
    return top


def _name(args: argparse.Namespace, slug: str) -> str:
    by = args.by.strip()
    if not by or not by.isprintable():
        repo.refuse(REFUSALS["bad_name"], words=args.words, slug=slug)
    return by


def _spec(top: Path, slug: str) -> tuple[str, str, dict[str, str], str]:
    """A spec's path, text, frontmatter and body; the text is empty when there is no spec."""
    rel = f"docs/specs/{slug}.md"
    text = _text(top, rel)
    return (rel, text, *_front(text))


def _digest(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _measure_gaps(measure: dict[str, str]) -> list[str]:
    """The Success measure lines that are missing, empty or (the check date) not a real date."""
    gaps = [line for name, line in MEASURE_FIELDS.items() if not measure.get(name)]
    when = measure.get("Check date")
    if when:
        try:
            date.fromisoformat(when if re.fullmatch(r"\d{4}-\d{2}-\d{2}", when) else "")
        except ValueError:
            gaps.append(MEASURE_FIELDS["Check date"])
    return gaps


def _check_measure(slug: str, body: str) -> None:
    gaps = _measure_gaps(success_measure(body))
    if gaps:
        repo.refuse(REFUSALS["no_measure"], slug=slug, missing=", ".join(gaps))


def _roadmap_items(slug: str, body: str) -> dict[str, str]:
    """The `- KEY: title` lines of a spec's Roadmap section, by key; refuses any other line."""
    items: dict[str, str] = {}
    for line in _sections(body).get("Roadmap", "").strip().splitlines():
        match = ROADMAP_LINE.fullmatch(line.strip())
        if not match or match[1] in items:
            problem = f"{match[1]} is listed twice" if match else f"{line.strip()!r} is not one"
            repo.refuse(REFUSALS["roadmap_section"], slug=slug, problem=problem)
        items[match[1]] = match[2]
    return items


def _decision(top: Path, name: str, next_step: str, called: str = "") -> str:
    """The one decision named NNNN-slug (that exact file) or slug, or "" when there is none."""
    folder = top / "docs" / "decisions"
    if not SLUG.fullmatch(name):
        return ""
    if re.match(r"\d{4}-", name) and (folder / f"{name}.md").is_file():
        return f"docs/decisions/{name}.md"
    found = sorted(f"docs/decisions/{path.name}"
                   for path in folder.glob(f"[0-9][0-9][0-9][0-9]-{name}.md"))
    if len(found) > 1:
        repo.refuse(REFUSALS["ambiguous"], name=called or name, found=", ".join(found),
                    next=next_step)
    return found[0] if found else ""


def _decision_numbers(top: Path) -> set[int]:
    """Decision numbers in this checkout or ever on any branch, local or fetched."""
    # ponytail: one walk of all history; per-ref `git ls-tree` if that gets slow.
    names = repo.git("log", "--all", "--format=", "--name-only", "--", "docs/decisions/",
                     cwd=top).splitlines()
    names += [path.name for path in (top / "docs" / "decisions").glob("*.md")]
    return {int(match[1]) for name in names if (match := re.match(r"(\d{4})-", Path(name).name))}


def _front(text: str) -> tuple[dict[str, str], str]:
    """A doc's frontmatter fields and the body after them."""
    match = FRONTMATTER.match(text)
    if not match:
        return {}, text
    fields = {}
    for line in match[1].splitlines():
        key, colon, value = line.partition(":")
        if colon:
            fields[key.strip()] = value.strip().strip("\"'")
    return fields, text[match.end():]


def _set(text: str, **changes: str | None) -> str:
    """The doc with these frontmatter fields set (None removes one); other lines stay as they are."""
    match = FRONTMATTER.match(text)
    lines = match[1].splitlines() if match else []
    for key, value in changes.items():
        keys = [line.partition(":")[0].strip() for line in lines]
        line = [] if value is None else [f"{key}: {value}"]
        if key in keys:
            lines[keys.index(key):keys.index(key) + 1] = line
        else:
            lines += line
    body = text[match.end():] if match else "\n" + text
    return "---\n" + "\n".join(lines) + "\n---\n" + body


def _sections(body: str) -> dict[str, str]:
    """A Markdown body's `## ` sections, by title."""
    # ponytail: fenced code isn't skipped, so a `## ` line inside a code block starts a section.
    parts = re.split(r"^## +(.+?)(?:[ \t]+#+)?[ \t]*$", body, flags=re.M)
    return dict(zip(parts[1::2], parts[2::2]))


def _text(top: Path, rel: str) -> str:
    path = top / rel
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def _write(top: Path, rel: str, text: str) -> None:
    path = top / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))  # bytes, so Windows writes the same LF file
