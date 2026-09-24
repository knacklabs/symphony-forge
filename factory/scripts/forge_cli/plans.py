"""forge plan save/assume — approved plans and implementation assumptions."""
from __future__ import annotations

import argparse
import datetime
import os
import re
import tempfile
from pathlib import Path
from typing import Any

import factory_lib
from factory_lib import (
    client_signoff, dump_json, evidence_path, load_json, now_iso,
    plan_digest_without_assumptions, repo_root, require_grill,
    run_state_path, slugify,
)

from .common import fail
from .context import pending_context
from .decisions import active_decision_ids, decision_records
from .signal import open_signals
from .specs import resolve_spec_reference

FRONTMATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.DOTALL)

REQUIRED_PLAN_SECTIONS = (
    "Problem",
    "Scope / Non-goals",
    "Acceptance Criteria",
    "Technical Approach",
    "Decisions",
    "Surface Impact",
    "Task Decomposition",
    "Risks",
    "Verify Plan",
)

BRIEF_PLAN_SECTIONS = (
    "What and why",
    "What changes for you",
    "Done when",
    "Risks",
    "Technical approach",
    "Task decomposition",
    "Verify plan",
)


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    match = FRONTMATTER.match(text)
    if not match:
        return {}, text
    fields: dict[str, Any] = {}
    list_field: str | None = None
    for line in match.group(1).splitlines():
        stripped = line.strip()
        if list_field and stripped.startswith("- "):
            fields[list_field].append(stripped[2:].strip().strip("\"'"))
            continue
        list_field = None
        if ":" not in line:
            continue
        key, _, raw = line.partition(":")
        key = key.strip()
        value = raw.strip()
        if value == "[]":
            fields[key] = []
        elif not value:
            fields[key] = []
            list_field = key
        elif value.startswith("[") and value.endswith("]"):
            fields[key] = [
                item.strip().strip("\"'")
                for item in value[1:-1].split(",") if item.strip()
            ]
        else:
            fields[key] = value.strip("\"'")
    return fields, text[match.end():]


def plan_meta_path(base: Path, story: str) -> Path:
    return factory_lib.story_dir(base, story) / "plan-meta.json"


def plan_metadata_index(base: Path) -> dict[str, dict[str, Any]]:
    """Index protected plan metadata by its recorded plan path."""
    index = {}
    for metadata_path in sorted((base / ".factory" / "stories").glob("*/plan-meta.json")):
        metadata = load_json(metadata_path, default={})
        if isinstance(metadata, dict) and isinstance(metadata.get("plan_file"), str):
            index[metadata["plan_file"]] = metadata
    return index


def read_plan_metadata(
    base: Path, path: Path, metadata_index: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Prefer protected metadata, then the matching run pointer, then frontmatter."""
    fields, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
    index = metadata_index if metadata_index is not None else plan_metadata_index(base)
    metadata = index.get(path.relative_to(base).as_posix())
    if metadata is None:
        matches = [
            entry for entry in index.values()
            if Path(str(entry.get("plan_file", ""))).name == path.name
        ]
        metadata = matches[0] if len(matches) == 1 else None
    if metadata is None:
        state = load_json(run_state_path(base), default={})
        relative = path.relative_to(base).as_posix()
        if not isinstance(state, dict):
            state = {}
        story = state.get("story") or state.get("issue_key")
        if not isinstance(story, str) or not story:
            story = None
        metadata_path = plan_meta_path(base, story) if story else None
        if (state.get("plan_file") == relative and metadata_path is not None
                and not metadata_path.exists()):
            metadata = {
                "issue": state.get("issue_key"),
                "story": story,
                "status": state.get("plan_status"),
                "plan_file": relative,
            }
    return {**fields, **metadata} if metadata else fields


def write_plan_metadata(base: Path, story: str, metadata: dict[str, Any]) -> None:
    """Atomically publish plan metadata using the shared JSON serializer."""
    destination = plan_meta_path(base, story)
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent,
    )
    os.close(descriptor)
    temporary = Path(name)
    try:
        dump_json(temporary, metadata)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def _require_decision_attestation(
    base: Path, fields: dict[str, Any], *, has_frontmatter: bool,
) -> list[str]:
    if not has_frontmatter:
        return []
    active_ids = active_decision_ids(base)
    if "decisions_reviewed" not in fields or not isinstance(
        fields["decisions_reviewed"], list
    ):
        fail(
            "plan frontmatter must include decisions_reviewed as a list of every "
            "active decision id (`./forge decision list --active`)."
        )
    reviewed = set(fields["decisions_reviewed"])
    active = set(active_ids)
    missing = sorted(active - reviewed)
    inactive = sorted(reviewed - active)
    if missing:
        fail("decisions_reviewed is missing active decisions: " + ", ".join(missing))
    if inactive:
        known = {str(record["id"]) for record in decision_records(base)}
        labels = [
            decision if decision not in known else f"{decision} (inactive)"
            for decision in inactive
        ]
        fail("decisions_reviewed contains unknown or inactive decisions: "
             + ", ".join(labels))
    return sorted(reviewed)


def _require_matching_plan_grill(
    base: Path, plan: Path, issue: str, *, awaiting: bool = False,
    check_decisions_in_force: bool = False,
) -> tuple[dict[str, Any], list[str]]:
    grill = load_json(evidence_path(base, issue, "grills/plan.json"), default={})
    decisions_in_force = []
    if (check_decisions_in_force and isinstance(grill, dict)
            and grill.get("issue") == issue
            and grill.get("input_sha256") == plan_digest_without_assumptions(plan)):
        decisions_in_force = _require_decisions_in_force_at_grill(base, grill)
    require_grill(
        base, "plan",
        ("docs/product/", "docs/decisions/", "docs/architecture/"),
        ignore_names=("client-signoff", "epics-approved"),
    )
    if grill.get("issue") != issue:
        fail(f"the recorded plan grill is for {grill.get('issue')!r}, not "
             f"{issue!r} — re-grill the current plan, then approve it")
    if grill.get("input_sha256") != plan_digest_without_assumptions(plan):
        if awaiting:
            fail("plan approval refused: the plan grill does not match the awaiting "
                 "plan. Re-grill the awaiting plan, then approve it again.")
        fail(f"the plan grill was not recorded against THIS input ({plan.name}) — "
             "re-grill the current version, then approve it again")
    return grill, decisions_in_force


def _require_decisions_in_force_at_grill(
    base: Path, grill: dict[str, Any],
) -> list[str]:
    """Return active decisions present before the matching grill was recorded."""
    issue = str(grill.get("issue") or "")
    try:
        grill_stamp = evidence_path(base, issue, "grills/plan.json").stat().st_mtime_ns
    except OSError:
        fail("could not establish the plan grill time; re-grill")
    active = []
    for record in decision_records(base):
        if record["status"] != "accepted":
            continue
        try:
            changed_at = record["path"].stat().st_mtime_ns
        except OSError:
            fail("could not establish decision timing against the plan grill; re-grill")
        if changed_at > grill_stamp:
            fail("a decision was accepted after the plan grill; re-grill")
        active.append(str(record["id"]))
    return active


def _stages_progress(base: Path, issue: str, location: str) -> str:
    path = evidence_path(base, issue, "stages.json")
    stages = load_json(path, default={}).get("stages", [])
    if not stages:
        return "-"
    done = sum(1 for stage in stages if stage.get("status") == "done")
    return f"{done}/{len(stages)}"


def cmd_save(args: argparse.Namespace) -> None:
    base = Path(args.repo).resolve() if args.repo else repo_root()
    state = load_json(run_state_path(base), default={})
    # Sign-off FIRST, and deliberately: it is derived from committed
    # harness.yaml, so it holds even with no run state at all — deleting
    # .factory/run.json cannot bypass the gate (autoreview r6).
    ok, why = client_signoff(base)
    if not ok:
        fail(f"plan approval requires client sign-off. {why}")
    if not state:
        fail("plan approval requires an initialized run. Run intake first.")
    pending = pending_context(base)
    if pending:
        fail(
            f"{len(pending)} docs/context/ file(s) are unharvested: {', '.join(pending[:5])}"
            f"{'…' if len(pending) > 5 else ''}. Plans must not be approved over pending "
            "context — run `forge.py context scan`, harvest per factory/prompts/harvester.md "
            "or mark irrelevant ones `forge.py context mark <file> --ignored`, then save."
        )
    issue = args.issue or state.get("issue_key")
    if not issue:
        fail("no --issue given and no issue_key in .factory/run.json (run intake first)")
    source = Path(args.source).expanduser()
    if not source.is_file():
        fail(f"plan source {source} not found — pass the approved plan file via --from")
    story = args.story or issue
    current_story = state.get("story") or state.get("issue_key")
    title = args.title or state.get("title") or issue
    dest_dir = base / "plans" / "active"
    dest = dest_dir / f"{issue}-{slugify(title)}.md"
    dest_relative = dest.relative_to(base).as_posix()
    previous_metadata = load_json(plan_meta_path(base, story), default={})
    previous_plan_file = (
        previous_metadata.get("plan_file")
        if isinstance(previous_metadata, dict) else None
    )
    previous_plan_approved = (
        isinstance(previous_metadata, dict)
        and previous_metadata.get("status") == "approved"
    )
    if (previous_plan_approved and isinstance(previous_plan_file, str)
            and previous_plan_file != dest_relative):
        fail(f"plan save refused: an approved plan exists at {previous_plan_file}; "
             "amend it rather than saving a new title")
    if (
        (state.get("plan_status") == "approved" and current_story == story)
        or (previous_plan_approved and previous_plan_file == dest_relative)
    ):
        fail(f"plan save refused: {story} already has an approved current plan. "
             "Keep the approved contract stable; use the governed amendment "
             "path when its meaning must change.")
    roadmap_items = load_json(base / "plans" / "roadmap.json", default={}).get("items", [])
    item = next((i for i in roadmap_items if i.get("key") == story), None)
    if item is None:
        fail(f"--story {story!r} is not in plans/roadmap.json")
    if story != issue:
        fail(f"plan save refused: --story must match --issue ({issue!r}); "
             "intake owns the issue/story key used by downstream stages.")
    # Capture is not build authorization: `roadmap add --no-spec` exists so an
    # ad-hoc ask is visible rather than smuggled in, and this is where that debt
    # comes due — decision 0014 still governs what may be BUILT. Stories from
    # the PM handoff (`roadmap import`) are unaffected; only the escape hatch is.
    if item.get("spec_debt_reason") and not item.get("spec"):
        fail(f"{story} was captured without a spec ({item['spec_debt_reason']}) — "
             "capture is not authorization (decision 0014). Draft and confirm the "
             f"capability spec, then: ./forge roadmap link-spec {story} "
             "--spec docs/specs/<slug>.md")
    spec_ref = item.get("spec")
    if not isinstance(spec_ref, str) or not spec_ref.strip():
        fail(f"{story} has no confirmed spec — link a confirmed spec before planning")
    spec = resolve_spec_reference(base, spec_ref, confirmed=True)
    # Approval requires the plan to have been GRILLED (grill-me / griller.md
    # --gate plan): fresh, passing, for THIS task, and bound by digest to
    # THIS draft — grilling one version never approves an edited one.
    source_text = source.read_text(encoding="utf-8")
    fields, body = parse_frontmatter(source_text)
    has_frontmatter = bool(FRONTMATTER.match(source_text))
    _, decisions_in_force = _require_matching_plan_grill(
        base, source, issue, check_decisions_in_force=not has_frontmatter,
    )
    contradictions = [
        signal for signal in open_signals(base) if signal.get("kind") == "contradiction"
    ]
    if contradictions:
        fail(
            "plan save refused while an open contradiction signal exists: "
            + ", ".join(signal["id"] for signal in contradictions)
            + ". Resolve the contradiction before approving the plan."
        )
    reviewed = _require_decision_attestation(
        base, fields, has_frontmatter=has_frontmatter,
    )
    sections = factory_lib.parse_sections(body)
    has_new_brief = all(sections.get(section) for section in BRIEF_PLAN_SECTIONS)
    has_legacy_plan = all(sections.get(section) for section in REQUIRED_PLAN_SECTIONS)
    if not has_new_brief and not has_legacy_plan:
        required_sections = (
            REQUIRED_PLAN_SECTIONS if has_frontmatter else BRIEF_PLAN_SECTIONS
        )
        missing_sections = [
            section for section in required_sections if not sections.get(section)
        ]
        fail("the plan is missing required sections: " + ", ".join(missing_sections))
    status = "awaiting-approval"
    saved = now_iso()
    header = ""
    if has_frontmatter:
        decisions = "\n".join(f"  - {decision}" for decision in reviewed)
        decisions_value = f"\n{decisions}" if decisions else " []"
        header = (
            f"---\nissue: {issue}\ntitle: {title}\nstatus: {status}\n"
            f"saved: {saved}\nstory: {story}\n"
            f"decisions_reviewed:{decisions_value}\n---\n"
        )
        if factory_lib._plan_body_digest_bytes((header + body).encode("utf-8")) \
                != plan_digest_without_assumptions(source):
            fail("plan save refused: frontmatter must use the canonical Forge save "
                 "form, with decisions_reviewed as a block list (one `- <id>` per "
                 "line), so the saved plan retains the semantic digest.")
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest.write_text(body, encoding="utf-8")
    metadata = {
        "issue": issue,
        "story": story,
        "title": title,
        "status": status,
        "saved": saved,
        "plan_file": dest.relative_to(base).as_posix(),
    }
    if has_frontmatter:
        metadata["decisions_reviewed"] = reviewed
    else:
        metadata["decisions_in_force"] = decisions_in_force
    write_plan_metadata(base, story, metadata)
    previous_path = Path(previous_plan_file) if isinstance(previous_plan_file, str) else None
    if (previous_path and previous_plan_file != dest_relative
            and previous_path.parent == Path("plans/active")
            and previous_path.name.startswith(f"{issue}-")
            and previous_path.suffix == ".md"):
        (base / previous_path).unlink(missing_ok=True)
    if state:
        state["plan_status"] = status
        state["issue_key"] = issue
        state["plan_file"] = dest.relative_to(base).as_posix()
        state["story"] = story
        state.pop("approved_plan_sha256", None)
        state["updated_at"] = now_iso()
        dump_json(run_state_path(base), state)
    semantic_digest = plan_digest_without_assumptions(dest)
    question_id = f"approve_plan_{semantic_digest}"
    question = "Approve this plan?"
    print(
        f"Plan saved to {dest.relative_to(base)} (plan_status: awaiting-approval). "
        f"Semantic digest: {semantic_digest}. Codex request_user_input: "
        f'id="{question_id}", header="Approve plan", question="{question}". '
        "Display these exact bytes in native Plan Mode; successful native "
        "approval records and advances this plan automatically."
    )


def cmd_list(args: argparse.Namespace) -> None:
    base = Path(args.repo).resolve() if args.repo else repo_root()
    roadmap = {
        item.get("key"): item
        for item in load_json(base / "plans" / "roadmap.json", default={}).get("items", [])
    }
    rows = []
    metadata_index = plan_metadata_index(base)
    for location in ("active", "completed"):
        for path in sorted((base / "plans" / location).glob("*.md")):
            fields = read_plan_metadata(base, path, metadata_index)
            issue = str(fields.get("issue", "-"))
            story = str(fields.get("story", "-"))
            rows.append((
                location,
                issue,
                story,
                str(fields.get("status", "-")),
                str(roadmap.get(story, {}).get("status", "-")),
                _stages_progress(base, issue, location),
                path.relative_to(base).as_posix(),
            ))
    if not rows:
        print("No active or completed plans.")
        return
    print("LOCATION  ISSUE  STORY  PLAN      ROADMAP  STAGES  FILE")
    for row in rows:
        print(f"{row[0]:<9} {row[1]:<6} {row[2]:<6} {row[3]:<9} "
              f"{row[4]:<8} {row[5]:<6} {row[6]}")


def cmd_assume(args: argparse.Namespace) -> None:
    base = Path(args.repo).resolve() if args.repo else repo_root()
    state = load_json(run_state_path(base), default={})
    issue = args.issue or state.get("issue_key")
    if not issue:
        fail("no --issue given and no issue_key in .factory/run.json (run intake first)")
    plans = sorted((base / "plans" / "active").glob(f"{issue}-*.md"))
    if not plans:
        fail(
            f"no active plan for {issue} (plans/active/{issue}-*.md). Save the approved "
            "plan first with `forge.py plan save` — assumptions attach to a plan."
        )
    plan = plans[-1]
    text = plan.read_text(encoding="utf-8")
    heading = "## Implementation Assumptions"
    entry = f"- {datetime.date.today().isoformat()}: {args.text.strip()}\n"
    if heading in text:
        text = text.rstrip("\n") + "\n" + entry
    else:
        text = (
            text.rstrip("\n")
            + f"\n\n{heading}\n\n"
            "<!-- Made during implementation, NOT part of the approved plan. "
            "Dev: review these before merge; promote any that matter to docs/decisions/. -->\n"
            + entry
        )
    plan.write_text(text, encoding="utf-8")
    from .assumptions import append_row
    entry_id = append_row(base, issue, args.text)
    print(f"Assumption recorded in {plan.relative_to(base)} and ledgered as {entry_id} "
          "(plans/assumptions.md)")
