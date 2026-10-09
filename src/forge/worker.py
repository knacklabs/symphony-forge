"""forge work: build the worker's brief and run the worker on a task or fix in its own checkout."""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from string import Template
from typing import Any

from forge import codex, doctor, machine, repo, story, task
from forge.repo import git, refuse

HERE = Path(__file__).parent
# The shipped how-to per concern of the client stack; the brief names it and the worker may read it.
CONVENTIONS = (HERE / "templates" / "conventions").resolve()
TEST_PATHS = repo.TEST_PATHS
SERIOUS = ("P0", "P1")
REVIEW_LOOP = (
    "Close holds the fourth review after three consecutive rounds blocked by serious findings, "
    "whatever files they were in. The existing same-file stop still applies from the third round. "
    "Wait for the coordinator to record the human's narrow, split or accept choice before continuing.")
# The bytes of change a continued conversation is shown in full; a larger one is listed by file.
LARGE = 200 * 1024
NUDGING = "The worker left changes uncommitted, so Forge asks it once to commit, test and commit any fixes."
SETTINGS = ("Workers never edit `forge.toml`. It belongs to the coordinator, through a settings "
            "fix the owner asked for. Report a needed settings change in your last message instead.")
# Sent once, in the same conversation, when a round ends with changes left uncommitted.
COMMIT_NUDGE = ("Your turn ended with changes left uncommitted, so the review can't see them. "
                "Commit your work on this branch first. Run "
                "the change's related tests through `forge test` in the foreground and wait for them to finish; never "
                "leave them running in the background. Then commit any fixes on this branch, and end "
                "your turn only once nothing is left uncommitted.\n")

REFUSALS = {
    "no_checkout": ("{item} has no checkout here, so it hasn't been started.", "forge next"),
    "failed": ("The worker stopped with exit code {status}; its log is {log}.", "forge work {item}"),
    "sdk": ("{problem}", "forge doctor --fix"),
    "turn": ("The Codex turn didn't complete: {why}; its log is {log}.", "forge work {item}"),
    "brief": ('"What changes for you" or "Done when" in the story doc of {item}\'s checkout isn\'t '
              "what story {key} approved, so Forge sends no brief from it.",
              "git -C {top} checkout {base} -- {doc}, commit it, then forge work {item}"),
    "empty_note": ("The --note text is empty.", 'forge work {item} --note "<text>"'),
    "question": ("The worker is waiting for an answer:\n{question}",
                 'forge work {item} --note "<answer>"'),
}


def work(args: argparse.Namespace) -> None:
    item = args.item
    note = getattr(args, "note", None)
    if note is not None and not note.strip():
        refuse(REFUSALS["empty_note"], item=item)
    match = repo.ITEM.fullmatch(item)
    if not match or not (match["task"] or match["fix"]):
        refuse(repo.REFUSALS["bad_item"], item=item)
    branches = [f"task/{match['key']}-{match['task']}"] if match["task"] else [f"fix/{item}", f"forge/{item}"]
    trees = story.worktrees(Path.cwd())
    top = next((trees[branch] for branch in branches if branch in trees), None)
    if top is None:
        refuse(REFUSALS["no_checkout"], item=item)
    config = repo.config(top)  # the item's own forge.toml, not the caller's
    state = repo.read_state(item, top) or {}
    if match["task"]:
        doc = f"plans/{match['key']}.md"
        story._parsed(story._text(top / doc), doc)  # pyright: ignore[reportPrivateUsage]
        sections = task.sections((top / doc).read_text(encoding="utf-8"))
        row = task.rows(sections).get(match["task"], {})
        design = repo.user_facing(config, row)
    else:
        design = state.get("allow_large") == "Prototype before sign-off" and repo.is_prototype(top)
    family = repo.worker(config, "build", design)[0]
    on_codex = family == "codex"
    # The item's state records the worker each round used. A round continues a conversation only
    # when the round before used the same worker; otherwise it starts fresh with the whole brief.
    last = state.get("worker")
    previous = state.get("status", "started") != "started"
    moved = (f"its last round ran on {last.title()}" if last else
             "Forge has no record of which worker its last round ran on")
    if note is None and (question := codex.record(top, item).get("question")):
        refuse(REFUSALS["question"], item=item, question=question)
    # On Codex, any forge work after the item's first turn, here or on another machine, is a fix
    # round: it continues the item's conversation.
    later = (on_codex or design) and bool(codex.record(top, item).get("start") or
                                           state.get("status", "started") != "started")
    kind = "Fix" if later else "Build" if match["task"] else "Lite"
    # Every check refuses before the status commit, so a refused call changes nothing.
    approval = _approval(match["key"], item, top) if match["task"] else None
    claude = [] if design and not on_codex else ready(top, config, kind, on_codex, design=design)
    _, chosen, why = repo.worker(config, kind.lower(), design)
    print(f"Building {item} with {family.title()} ({chosen['model']}, {chosen['effort']}) "
          f"because {why}", flush=True)
    # Every worker takes the item's lock, so one round at a time reads and updates its record. Codex
    # workers also stop a leftover Codex process and read back a turn it left before the status
    # commit, and leave none running when this ends, whether it succeeds, fails or is interrupted.
    # The round then waits for one of the machine's agent slots.
    with codex.hold(top, item, kind), machine.agent_slot(top, "work", item,
            chosen.get("model"), chosen.get("effort")):
        if on_codex:
            codex.recover(top, item)
        question = codex.record(top, item).get("question")
        if question and note is None:
            refuse(REFUSALS["question"], item=item, question=question)
        if previous and last != family:  # a failed start leaves nothing of the other to resume
            codex._record(codex._item_file(top, item, ".json", kind), conversation=None,
                          start=None, head=None, claude=None)
        thread, fresh = (codex.conversation(top, item, approval) if on_codex and later
                         and last == family else (None, "first turn"))
        # A Claude worker, design ones too, continues the session its item's last round ran in, in
        # this checkout. Without one, a round after the first starts fresh and says why.
        session = None if on_codex else codex.record(top, item).get("claude")
        if last != family:
            fresh = moved if previous else fresh
        elif session and session["checkout"] != str(top):
            fresh = f"its session was started in another checkout, {session['checkout']}"
        elif session:
            thread = session["id"]
        elif not on_codex and previous:
            fresh = "Forge has no record of its Claude session on this machine"
        state = repo.read_state(item, top) or {}
        findings, failing = _fix_round(state)
        if "round" in state:
            round_number = state["round"] + 1
        elif session:
            round_number = session["rounds"] + 1
        else:
            turns = codex._item_file(top, item, ".log", kind)
            round_number = 1 + len({(entry["conversation"], entry["turn"])
                                    for line in turns.read_text(encoding="utf-8").splitlines()
                                    if "turn" in (entry := json.loads(line))}) if turns.exists() else 1
        brief, subject = _brief(match, top, state, findings, failing, note, question, round_number,
                                continued=bool(thread))
        fresh_brief = None
        if thread:
            saved = session or codex.record(top, item)
            brief += _changes(top, saved.get("head") or saved["start"])
            fresh_brief, _ = _brief(match, top, state, findings, failing, note, question,
                                   round_number)
        state["status"] = "fixing" if findings or failing else "working"
        state["worker"] = family
        state["round"] = round_number
        repo.commit_state(f"{item} is {state['status']}", repo.write_state(item, state, top),
                          top=top)
        start, clock = repo.now(), time.monotonic()
        nudge = COMMIT_NUDGE
        outcome = "failed"
        final = None
        nudged = ""
        try:
            if not on_codex:
                before = story._snapshot(top) if design else None  # pyright: ignore[reportPrivateUsage]
                if design:
                    claude = ["--model", chosen["model"], "--effort", chosen["effort"]]
                try:
                    final = _claude(item, top, brief, fresh_brief, claude,
                            session, thread, None if fresh == "first turn" else fresh)
                except (repo.Refused, OSError) as error:
                    # Only split falls back: workers = claude means Claude, even when it fails.
                    if (not design or config["workers"] != "split" or
                            story._snapshot(top) != before):  # pyright: ignore[reportPrivateUsage]
                        raise
                    reason = ("claude command missing" if shutil.which("claude") is None else
                              str(error).split("\n", 1)[0].removeprefix("The worker "))
                    chosen = repo.design_models(config, "codex")
                    message = (f"Claude {reason}; fell back to Codex with "
                               f"{chosen['model']} at {chosen['effort']} effort.")
                    print(message, flush=True)
                    with repo.work_log(top, item).open("a", encoding="utf-8") as out:
                        out.write(message + "\n")
                    ready(top, config, kind, True, design=True)
                    codex.recover(top, item)
                    if previous and last != "codex":
                        codex._record(codex._item_file(top, item, ".json", kind), conversation=None,
                                      start=None, head=None, claude=None)
                    thread, fresh = (codex.conversation(top, item, approval)
                                     if later and last == "codex" else
                                     (None, moved if previous else "first turn"))
                    state["worker"] = "codex"
                    repo.commit_state(f"{item} fell back to Codex",
                                      repo.write_state(item, state, top), top=top)
                    brief, fresh_brief = fresh_brief or brief, None
                    if thread:
                        saved = codex.record(top, item)
                        fresh_brief = brief
                        brief, _ = _brief(match, top, state, findings, failing, note, question,
                                          round_number, continued=True)
                        brief += _changes(top, saved.get("head") or saved["start"])
                    on_codex = True
                else:
                    if git("status", "--porcelain", "-uall", cwd=top):
                        print(NUDGING, flush=True)
                        saved = codex.record(top, item)["claude"]
                        try:
                            nudged = _run(item, top, nudge, claude, ["--resume", saved["id"]])
                        finally:
                            codex._record(codex._item_file(top, item, ".json", kind),
                                claude={**saved, "head": git("rev-parse", "HEAD", cwd=top)})
                    outcome = "completed"
                    return
            name = f"{match['key']} · {subject}" if match["task"] else f"Fix · {subject}"
            if len(name) > 60:
                prefix = name[:59]
                name = (prefix.rstrip() if name[59].isspace() else
                        prefix.rsplit(" ", 1)[0] or prefix) + "…"
            result = codex.run(top, item, kind, name, brief, "full-access",
                               thread, fresh, approval, note=note, fresh_prompt=fresh_brief,
                               design=design)
            outcome = "completed" if result["status"] == "completed" else "failed"
            final = (result.get("text") or "") if outcome == "completed" else None
            if outcome == "completed" and git("status", "--porcelain", "-uall", cwd=top):
                print(NUDGING, flush=True)
                again = codex.run(top, item, kind, name, nudge, "full-access",
                                  result["conversation"], "", approval, design=design)
                if again["status"] != "completed":
                    result, outcome = again, "failed"
                else:
                    nudged = (again.get("text") or "").strip()
        finally:
            if final is not None:
                asked = "\n\n".join(dict.fromkeys(match[1] for answer in (final, nudged)
                    if (match := re.search(r"(?:\A|\n\s*\n)(Question:.*)\Z", answer.strip(), re.S))))
                identity = repo.record_event(top, item, "worker question", question=asked) if asked else None
                codex._record(codex._item_file(top, item, ".json", kind),
                              question=asked or None, question_id=identity)
                if asked:
                    print(f"{asked}\nNext: forge work {item} --note \"<answer>\"")
            repo.record_timing(top, item, "worker round", start, clock, outcome, chosen)
            if left := git("status", "--porcelain", "-uall", cwd=top).splitlines():
                print("Warning: the worker ended its round with changes left uncommitted, so the review "
                      f"won't see them: {', '.join(line.split(maxsplit=1)[1] for line in left)}.")
        if result["status"] != "completed":
            why = (f"Codex reported it {result['status']}" if result["status"]
                   else "Codex never reported its end")
            refuse(REFUSALS["turn"], why=why, log=repo.work_log(top, item), item=item)


def ready(top: Path, config: dict[str, Any], kind: str, on_codex: bool,
          design: bool = False) -> list[str]:
    """Refuse unless this kind of work can start in the checkout: its [models] entry and, on Codex,
    the SDK with the declining handler's place and the project's trust. Returns
    claude's --model and --effort, or [] on Codex. The cold read (Grill) runs these checks too."""
    if not on_codex:
        # A worker always names its models; a cold read with no entry runs on Claude's own.
        chosen = (repo.models if kind == "Grill" else repo.worker_models)(config, kind.lower(),
                                                                           "claude")
        if "subagents" in chosen:
            refuse(repo.REFUSALS["models"], problem=f"Claude workers take model and effort, so "
                                                     f"[models.{kind.lower()}] can't set subagents")
        return ["--model", chosen["model"], "--effort", chosen["effort"]] if chosen else []
    problem = codex.sdk_problem()  # includes the declining handler's place in the SDK
    if problem:
        refuse(REFUSALS["sdk"], problem=problem)
    if not design:  # a design round's Codex models are design_models', which never refuse
        codex.settings(config, kind)
    codex.require_trust(top)  # before the status commit, so a refusal changes nothing
    return []


def _approval(key: str, item: str, top: Path) -> str:
    """The story's approval, read from its own branch, where approvals are committed, else from the
    default branch once that branch is gone; refused when the story's record has none, when the
    approved part of the story doc changed since, until it is approved again, and when the
    checkout's own story doc, which the brief is made from, isn't the approved one."""
    doc = f"plans/{key}.md"
    base = f"story/{key}"
    # Only a gone branch falls back: a doc deleted on the branch refuses below as a change.
    if repo.run("git", "rev-parse", "--verify", "-q", f"{base}^{{commit}}").returncode:
        base = task.main_ref()
    state = task.show(base, repo.state_path(key))
    approved = (json.loads(state or "{}").get("approval") or {}).get("hash")
    if not approved:
        refuse(task.REFUSALS["not_approved"], key=key)
    if approved != task.approval_hash(task.show(base, doc) or ""):
        refuse(task.REFUSALS["changed"], key=key)
    # The story's own worktree holds the doc its next approval reads, uncommitted edits included.
    planning = story.stories_here(top).get(key)
    if planning and approved != task.approval_hash(story._text(planning / doc)):  # pyright: ignore[reportPrivateUsage]
        refuse(task.REFUSALS["changed"], key=key)
    if approved != task.approval_hash(story._text(top / doc)):  # pyright: ignore[reportPrivateUsage]
        refuse(REFUSALS["brief"], item=item, key=key, top=top, base=base, doc=doc)
    return approved


def _changes(top: Path, start: str) -> str:
    """For a continued conversation: the commits since its last turn ended, and every change git
    sees in the checkout since then, untracked files included through a temporary index, so git's
    own index stays as it is. A very large change is listed by file."""
    commits = git("log", "--oneline", f"{start}..HEAD", cwd=top) or "None."
    with tempfile.TemporaryDirectory() as folder:
        env = {**os.environ, "GIT_INDEX_FILE": str(Path(folder) / "index")}
        shutil.copy(git("rev-parse", "--path-format=absolute", "--git-path", "index", cwd=top),
                    env["GIT_INDEX_FILE"])

        def cached(*args: str) -> str:
            return subprocess.run(["git", *args], cwd=top, env=env, capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", check=True).stdout
        cached("add", "-A")
        diff = cached("diff", "--cached", start)
        if len(diff.encode("utf-8")) > LARGE:
            diff = ("The change is over 200 KB, so here are the files it touches:\n"
                    + cached("diff", "--cached", "--name-status", start))
    return (f"\n## Since your last turn\n\nThe new commits:\n\n{commits}\n\nEvery change in "
            "the checkout since your last turn ended, new files included:\n\n"
            f"```diff\n{diff}```\n")


def _fix_round(state: dict[str, Any]) -> tuple[list[dict[str, Any]], list[tuple[str, str]]]:
    """The open serious findings and the failing checks, close's own test run among them, once
    close has run."""
    tests = [("Tests on the close run", state["tests"])] if state.get("tests") else []
    review = state.get("review")
    if not review:  # no review yet: no pull request to read checks from
        return [], tests
    dismissed = {entry.get("finding") for entry in review.get("dismissals") or []}
    findings = [finding for n, finding in enumerate(review.get("findings") or [], 1)
                if finding.get("priority") in SERIOUS and n not in dismissed]
    return findings, tests + _failing(state.get("branch", ""))


def _failing(branch: str) -> list[tuple[str, str]]:
    """Each failing check on the branch's pull request, with the tail of its log."""
    try:  # gh exits non-zero when a check fails, so read what it printed either way
        checks = json.loads(repo.run("gh", "pr", "checks", branch, "--json", "name,bucket,link").stdout)
    except ValueError:  # no pull request yet
        return []
    failing = []
    for check in checks if isinstance(checks, list) else []:
        if check.get("bucket") == "fail":
            job = re.search(r"/job/(\d+)", check.get("link") or "")
            log = repo.run("gh", "run", "view", "--job", job[1], "--log-failed").stdout if job else ""
            failing.append((check.get("name", "a check"), "\n".join(log.splitlines()[-30:])))
    return failing


def _brief(match: re.Match[str], top: Path, state: dict[str, Any],
           findings: list[dict[str, Any]], failing: list[tuple[str, str]],
           note: str | None = None, question: str | None = None,
           round_number: int = 1, continued: bool = False) -> tuple[str, str]:
    """The brief from templates/brief.md, where `<!-- if NAME -->` blocks stay only when NAME is
    on, and its subject: the task's name, or the fix's why."""
    on: set[str] = set()
    values: dict[str, str] = {
        "settings": SETTINGS,
        "review_loop": REVIEW_LOOP,
        "delegation": (HERE / "templates" / "delegation.md").read_text(encoding="utf-8").strip()}
    if note is not None:
        on.add("coordinator")
        values["coordinator"] = note
    if question:
        on.add("answer")
        values.update(question=question, answer=note or "")
    if match["task"]:
        text = (top / "plans" / f"{match['key']}.md").read_text(encoding="utf-8")
        doc, parsed = task.sections(text), story.parse(text)
        row = task.rows(doc).get(match["task"], {})
        covers = {int(n) for n in re.findall(r"\d+", row.get("Covers", ""))}
        subject = row.get("Name", "")
        moving = re.search(r"^New moving parts:.*", doc.get("Tasks", ""), re.M | re.S)
        on |= {"task"} | ({"user-facing"} if row.get("User-facing", "").lower() in ("yes", "true")
                          else set())
        values.update(
            title=doc["#"], what=doc.get("What changes for you", ""), why=doc.get("Why", ""),
            done="\n".join(story.item(parsed, n, n in covers) for n in parsed["done"]),
            risks=doc.get("Risks", ""), notes=doc.get("Notes", ""),
            moving=moving[0].strip() if moving else "New moving parts: none",
            row="\n".join(f"| {' | '.join(cells)} |" for cells in (
                list(row), ["---"] * len(row), list(row.values()))),
            covers=row.get("Covers", ""), scope=row.get("Scope", ""), tests=row.get("Tests", ""),
            existing_tests=_existing_tests(top, task.cell_list(row.get("Scope", ""))))
    else:
        on.add("fix")
        subject = state.get("why", "")
        values.update(why=subject, done=state.get("done_when", ""),
                      interfaces=", ".join(f"`{pattern}`" for pattern in
                                           repo.config(top)["interfaces"]) or "none",
                      allowance=state.get("allow_large") or "No recorded allowance")
    values["summary"] = (f"Fix round {round_number} on {subject}." if round_number > 1 else
                         f"Build {subject} for {match['key']}." if match["task"] else
                         f"Fix: {subject}.")
    if findings or failing:
        on.add("fix-round")
        values["findings"] = "\n".join(
            f"- {f.get('priority')} {f.get('title', '')} "
            f"({':'.join(str(p) for p in (f.get('file'), f.get('line')) if p) or 'no file'}): "
            f"{f.get('body', '')}"
            for f in findings) or "None."
        values["checks"] = "\n\n".join(
            f"### {name}\n\n```\n{tail}\n```" for name, tail in failing) or "None."
    if continued:
        brief = values["summary"] + "\n\nThe earlier brief in this conversation still applies.\n"
        brief += "\n" + values["delegation"] + "\n"
        brief += "\n" + SETTINGS + "\n"
        brief += "\nNever run `forge stop`: only a person can stop a run, after confirmation in the host.\n"
        brief += "\n" + REVIEW_LOOP + "\n"
        brief += ("\nCommit your work on this branch first. Run the change's related tests through `forge test`, "
                  "then commit any fixes before you stop. "
                  "This replaces any earlier full-suite instruction; CI runs the full suite.\n")
        brief += ("\n`forge close` pushes the committed branch and runs CI on every platform. "
                  "CI output reaches you in your next round. If you need CI evidence, commit and "
                  "stop instead of asking the coordinator to push or run CI. CI is the merge gate. "
                  "Commit your local proof in the `Proof list:` without waiting for CI results or timings.\n")
        if note is not None:
            brief += f"\n## From the coordinator\n\n{note}\n"
        if question:
            brief += f"\n## Your pending question\n\n{question}\n\nThe coordinator answered: {note or ''}\n"
        if findings or failing:
            brief += (f"\n## Fix round\n\n### Open serious findings\n\n{values['findings']}\n"
                      f"\n### Failing checks\n\n{values['checks']}\n")
        return brief, subject
    on.add("standards")
    values["standards"] = (HERE / "standards.md").read_text(encoding="utf-8").strip()
    values["conventions"] = str(CONVENTIONS)
    text = (HERE / "templates" / "brief.md").read_text(encoding="utf-8")
    text = re.sub(r"<!-- if ([\w-]+) -->\n(.*?)<!-- end -->\n",
                  lambda block: block[2] if block[1] in on else "", text, flags=re.S)
    return Template(text).safe_substitute(values), subject


def _existing_tests(top: Path, scope: list[str]) -> str:
    """The checkout's test files that name a Scope file or folder, listed for the brief."""
    # ponytail: a whole-word match on each entry's last plain name (`board` for `web/board.py`), so
    # a common name such as `index` lists more tests than it should; match imports if that's noisy.
    names = sorted({Path(plain[-1]).stem for entry in scope
                    if (plain := [p for p in Path(entry).parts if not set(p) & set("*?[")])})
    patterns = [arg for name in names for arg in ("-e", name)]
    found = repo.run("git", "grep", "-l", "-w", "-F", *patterns, "--", *TEST_PATHS,
                     cwd=top).stdout.splitlines() if names else []
    return ", ".join(f"`{path}`" for path in found) or "none found"


def _claude(item: str, top: Path, brief: str, fresh_brief: str | None, models: list[str],
            session: dict[str, Any] | None, resume: str | None, why: str | None) -> str:
    """A Claude worker's round: continue session `resume` with the short brief, else start a new
    session with the whole brief and say why when there was one to continue. When Claude says it
    has no such session, the same round starts fresh; any other failure fails the round and keeps
    the session, so the next forge work continues it. The session, its checkout, the item's rounds
    and HEAD when a round ends go in the item's record on this machine."""
    path = codex._item_file(top, item, ".json", "Fix")
    log = repo.work_log(top, item)
    rounds = session["rounds"] if session else 0
    try:
        if resume:
            size = log.stat().st_size if log.exists() else 0
            try:
                return _run(item, top, brief, models, ["--resume", resume])
            except repo.Refused:
                # Claude refuses a session it doesn't have before the turn starts, with this line.
                output = log.read_bytes()[size:].decode("utf-8", "replace").split("\n", 1)[-1]
                if not output.startswith("No conversation found"):
                    raise
            why = f"Claude no longer has session {resume}"
        if why:
            message = f"Starting a new Claude session with the whole brief, because {why}."
            print(message, flush=True)
            with log.open("a", encoding="utf-8") as out:
                out.write(message + "\n")
        # A replaced session keeps the item's round count.
        session = {"id": str(uuid.uuid4()), "checkout": str(top),
                   "start": git("rev-parse", "HEAD", cwd=top), "rounds": rounds}
        codex._record(path, claude=session)
        return _run(item, top, fresh_brief or brief, models, ["--session-id", session["id"]])
    finally:
        if session:
            codex._record(path, claude={**session, "rounds": rounds + 1,
                                        "head": git("rev-parse", "HEAD", cwd=top)})


def _run(item: str, top: Path, brief: str, models: list[str],
         session: list[str] | None = None) -> str:
    """Run Claude Code headless in the checkout; its output goes to the terminal and the log."""
    exe = shutil.which("claude")
    if exe is None:
        refuse(repo.REFUSALS["missing_tool"], tool="claude")
    log = repo.work_log(top, item)
    # Full access, like Codex workers: the checkout's synced deny hook is the guard, in every mode.
    command = [exe, "-p", *models, "--permission-mode", "bypassPermissions",
               "--output-format", "stream-json", "--verbose",
               "--add-dir", str(CONVENTIONS), *(session or [])]
    lines, final_result = [], None
    with repo.record_run(top, item, "worker", family="claude",
                         model=models[models.index("--model") + 1],
                         effort=models[models.index("--effort") + 1]) as ran, \
            log.open("a", encoding="utf-8", buffering=1) as out, subprocess.Popen(
            command, cwd=top, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
            env={**os.environ, "FORGE_WORKER": "1"}, **codex.GROUP) as worker, \
            machine.agent_process(worker, log):
        out.write(f"--- forge work {item} at {repo.now()}\n")
        worker._stdin_write(brief)
        for line in worker.stdout:
            try:
                event = json.loads(line)
            except ValueError:
                event = None
            if isinstance(event, dict):
                line = repo.claude_output(top, item, ran["run_id"], event)
                if event.get("type") == "result":
                    final_result = line.rstrip("\n")
            if line:
                if not isinstance(event, dict) or event.get("type") == "result":
                    print(line, end="", flush=True)
                out.write(line)
                lines.append(line)
        worker.wait()
        ran["outcome"] = "completed" if worker.returncode == 0 else "failed"
    if worker.returncode:
        refuse(REFUSALS["failed"], status=worker.returncode, log=log, item=item)
    return final_result if final_result is not None else "".join(lines)


COMMANDS = [{
    "words": "work", "run": "work", "changes_state": True,
    "help": "Run the configured worker on a task or fix",
    "args": [(('item',), {}), (('--note',), {"metavar": "TEXT", "help": "guide this round of work"})],
    "position": 130,
    "listing": '| `forge work <item>` | Runs the worker on a task or fix: the first build, or a fix round (`--note "<text>"` guides that round) |',
}]
