"""Check Forge's tools, generated files, hooks, CI and Codex trust; repair safe drift with --fix."""
from __future__ import annotations
import argparse
import io
import json
import os
import re
import shutil
import subprocess
import tomllib
from pathlib import Path
from typing import Any

from forge import __version__, codex, init, machine, quicktest, repo, review, story, sync, task

COMMANDS = [{"words": "doctor", "run": "doctor", "changes_state": False,
    "help": "Check tools, versions, hooks, adapter drift and the named CI checks", "args": [(('--fix',), {"action": "store_true", "help":
              "repair what doctor safely can: the pinned Forge, the Codex SDK, the git hooks, "
              "the folders of finished work and the files forge sync writes"})], "position": 30,
    "listing": "| `forge doctor` | Checks tools, versions, hooks, generated-file drift and CI; one row per problem, each with a fix; `--fix` repairs what it safely can |",
}]
REFUSALS = {"problems": ("forge doctor found {count} problem(s); each row above gives its fix.", "forge doctor")}
INSTALL = {"git": "install git from https://git-scm.com/downloads", "gh": "install gh from https://cli.github.com",
    "uv": "curl -LsSf https://astral.sh/uv/install.sh | sh", "claude": "npm install -g @anthropic-ai/claude-code",
    "impeccable": "npx skills add pbakaus/impeccable -g", "emil-design-eng": "install emil-design-eng where the worker reads skills",
    "autoreview": (f"install skills/autoreview from https://github.com/openclaw/agent-skills at "
                   f"{review.AUTOREVIEW_PIN} into {review.HELPERS[0].parents[1]} or " f"{review.HELPERS[1].parents[1]}")}
CACHES = {".venv", "node_modules", "__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache"}
REPAIR = "forge doctor --fix"
WHY = "Bring the files Forge writes for Claude Code and Codex up to date"
DONE = "The files match what forge sync writes for the pinned Forge"
HAND = "move your change out of this file, since forge sync rewrites it, then forge doctor --fix"
SAMPLES = {"SessionStart": {"source": "startup"}, "PreToolUse": {"tool_name": "Bash", "tool_input": {"command": "git status"}},
    "PostToolUse": {"tool_name": "forge-doctor", "tool_input": {}, "tool_response": {}}}
BARE_PATH = "/usr/bin:/bin"
def _forge_hooks(text: str) -> list[tuple[str, str]]:
    try:
        hooks = json.loads(text or "{}").get("hooks", {})
        return [(event, hook["command"]) for event, groups in hooks.items() for group in groups
                for hook in group.get("hooks", []) if sync.FORGE_COMMAND.search(hook.get("command", ""))]
    except (ValueError, AttributeError, TypeError, KeyError): return []
def _codex_trusts(top: Path, config: Path) -> bool:
    common = Path(repo.git("rev-parse", "--path-format=absolute", "--git-common-dir", cwd=top))
    roots = {top.resolve(), common.resolve().parent}
    try:
        projects = tomllib.loads(sync.read(config)).get("projects", {})
        return any(Path(path).resolve() in roots and project.get("trust_level") == "trusted" for path, project in projects.items())
    except (tomllib.TOMLDecodeError, AttributeError): return False
def _last(done: subprocess.CompletedProcess[str] | Exception) -> str:
    if not isinstance(done, (subprocess.CompletedProcess, subprocess.CalledProcessError)): return str(done).partition("\nNext: ")[0]
    return ((done.stderr or "").strip() or (done.stdout or "").strip() or f"exit code {done.returncode}").splitlines()[-1]
def _prs(top: Path, branch: str, *options: str) -> Any:
    done = repo.run("gh", "pr", "list", "--head", branch, "--state", "all", *options, cwd=top)
    try: return json.loads(done.stdout) if done.returncode == 0 else None
    except ValueError: return None
def _files_fix_finished(top: Path, branch: str) -> bool:
    prs = _prs(top, branch, "--json", "state") if shutil.which("gh") else None
    return isinstance(prs, list) and any(isinstance(pr, dict) and pr.get("state") in ("MERGED", "CLOSED") for pr in prs)
def _open_files_fix(top: Path) -> str: return next((branch for branch in repo.git("for-each-ref", "--format=%(refname:short)",
                 "refs/heads/fix/forge-files-*", cwd=top).splitlines() if not _files_fix_finished(top, branch)), "")
def _finished(top: Path, main: Path) -> list[tuple[Path, str, str]]:
    if not shutil.which("gh"): return []
    open_fix = _open_files_fix(top)
    found = []
    for branch, path in story.worktrees(top).items():
        if (not branch.startswith(("story/", "task/", "fix/", "forge/")) or branch == open_fix or path.resolve() in (main, top.resolve())
                or (path / ".gitmodules").exists()): continue
        prs = _prs(top, branch, "--limit", "100", "--json", "headRefOid,state")
        if not isinstance(prs, list) or len(prs) >= 100 or not all(isinstance(pr, dict) for pr in prs): continue
        head = repo.git("rev-parse", f"refs/heads/{branch}", cwd=top)
        states = {pr.get("state") for pr in prs if pr.get("headRefOid") == head}
        state = "merged" if "MERGED" in states else "closed" if "CLOSED" in states else ""
        if not state or any(pr.get("state") == "OPEN" for pr in prs): continue
        status = repo.run("git", "status", "--porcelain", "--ignored", "--untracked-files=normal", cwd=path)
        if status.returncode == 0 and all(line[3:] == "uv.lock" or (
                line[:2] == "!!" and line.endswith("/") and Path(line[3:]).name in CACHES)
                for line in status.stdout.splitlines()): found.append((path, branch, state))
    return found
def _pin_changes(top: Path, commits: set[str]) -> set[str]:
    if not commits: return set()
    specs = [f"{commit}{parent}:forge.toml" for commit in sorted(commits) for parent in ("", "^")]
    done = subprocess.run([shutil.which("git") or "git", "cat-file", "--batch"], cwd=top,
                          input=("\n".join(specs) + "\n").encode("utf-8"), capture_output=True, check=True,
                          env={**os.environ, "FORGE_WORKER": "1"})
    contents = io.BytesIO(done.stdout)
    pins = {}
    for spec in specs:
        header = contents.readline()
        if header.endswith(b" missing\n"): pins[spec] = ""
        else:
            size = int(header.split()[-1])
            text = contents.read(size).decode("utf-8", errors="replace")
            contents.read(1)  # cat-file adds a newline after each blob's bytes.
            pins[spec] = repo._pin(text)  # pyright: ignore[reportPrivateUsage]
    return {commit for commit in commits if pins[f"{commit}:forge.toml"] != pins[f"{commit}^:forge.toml"]}
def _history(top: Path, wanted: dict[str, str], ref: str) -> dict[str, str]:
    history = repo.git("log", "--format=commit %H%x00%P%x00%s", "-z", "--raw", "--no-renames",
                       "--no-abbrev", "--full-history", "--sparse", "--diff-merges=first-parent",
                       ref, "--", *wanted, cwd=top)
    parents: dict[str, list[str]] = {}
    subjects: dict[str, str] = {}
    changes: dict[tuple[str, str], tuple[str, str]] = {}
    fields = iter(history.split("\0"))
    commit = ""
    for field in fields:
        field = field.lstrip("\n")
        if field.startswith("commit "):
            commit = field.removeprefix("commit ")
            parents[commit] = next(fields).split()
            subjects[commit] = next(fields)
        elif field.startswith(":"):
            _, mode, _, blob, _ = field.split()
            rel = next(fields)
            changes[commit, rel] = (mode, blob) if mode != "000000" else ("", "")
    def entry(at: str, rel: str) -> tuple[str, str]:
        trail = []
        while at and (at, rel) not in changes:
            trail.append(at)
            at = next(iter(parents[at]), "")
        value = changes.get((at, rel), ("", ""))
        for ancestor in trail: changes[ancestor, rel] = value
        return value
    latest = {}
    for rel in wanted:
        at = next(iter(parents), "")
        while at:
            value = entry(at, rel)
            # Like log -- <one path>, follow the first parent with the same file.
            same = next((parent for parent in parents[at] if entry(parent, rel) == value), "")
            if same: at = same
            else:
                if parents[at] or value != ("", ""): latest[rel] = f"{at} {subjects[at]}"
                break
    return latest

def _changes(top: Path, cfg: dict[str, Any], wanted: dict[str, str],
             ref: str) -> tuple[set[str], dict[str, str]]:
    if not wanted: return set(), {}
    status = repo.git("status", "--porcelain=v2", "-z", "--no-renames", "--untracked-files=all",
                      "--ignored", "--", *wanted, cwd=top)
    dirty, staged = set(), set()
    for entry in status.split("\0"):
        if entry.startswith("1 "):
            _, xy, *_, rel = entry.split(" ", 8)
            dirty.add(rel)
            if xy[0] != ".": staged.add(rel)
        elif entry.startswith(("? ", "! ")): dirty.add(entry[2:])
        elif entry.startswith("u "):
            rel = entry.split(" ", 10)[-1]
            dirty.add(rel)
            staged.add(rel)
    latest = _history(top, wanted, ref)
    landed = (set(repo.git("rev-list", story.landed_ref(top), cwd=top).splitlines())
              if cfg["repo"] != "forge-source" else set())
    owned = {commit for last in latest.values() for commit, _, subject in [last.partition(" ")]
             if commit in landed and subject.startswith(WHY)}
    commits = {last.partition(" ")[0] for last in latest.values()} & landed
    free = owned | _pin_changes(top, commits - owned)
    held: dict[str, str] = {}
    for rel in wanted:
        if rel in dirty:
            held[rel] = "has changes not committed yet, so doctor won't overwrite it"
        else:
            last = latest.get(rel, "")
            commit, _, subject = last.partition(" ")
            held[rel] = ("" if not last or cfg["repo"] == "forge-source" or commit in free
                         else f"was changed by hand ({subject}), so doctor won't overwrite it")
    return staged, held

def _split(folder: Path, wanted: dict[str, str], staged: set[str],
           held: dict[str, str]) -> tuple[list[str], list[tuple[str, str]], frozenset[str]]:
    differing = set(sync.differing(folder, wanted))
    reasons = {rel: held.get(rel, "") for rel in wanted if rel in differing or rel in staged}
    free = [rel for rel, reason in reasons.items() if not reason]
    keep = {rel for rel, reason in reasons.items() if reason}
    rows = [(f"{rel} {reason}.", HAND) for rel, reason in reasons.items() if reason]
    if "AGENTS.md" in keep and "CLAUDE.md" in free:  # sync moves CLAUDE.md's lines into AGENTS.md
        free.remove("CLAUDE.md")
        keep.add("CLAUDE.md")
        rows.append(("CLAUDE.md stays until doctor can write AGENTS.md, since sync moves its lines " "there.", HAND))
    return free, rows, frozenset(keep)
def _linked(folder: Path, wanted: dict[str, str]) -> list[tuple[str, str]]:
    for rel in [*wanted, "AGENTS.md", "CLAUDE.md"]:
        path = folder / rel
        if any(part.is_symlink() for part in [path, *path.parents] if part.is_relative_to(folder) and part != folder):
            return [(f"{rel} is a link, so doctor repaired none of Forge's files.", f"replace the link with a regular file, then {REPAIR}")]
    return []
def _unfinished(name: str, branch: str, path: Path | None) -> tuple[str, str]:
    remove = (f'git worktree remove --force --force "{path}" and ' if path else "")
    return (f"Doctor's fix {name} isn't merged yet, so doctor started no new one.",
            f"finish it with forge close {name}, or remove it with {remove}git branch " f"-D {branch}, then {REPAIR}")
def _in_fix(top: Path, cfg: dict[str, Any], wanted: dict[str, str]) -> list[tuple[str, str]]:
    ref, default = story.landed_ref(top), repo.default_branch(top)
    if branch := _open_files_fix(top): return [_unfinished(branch.removeprefix("fix/"), branch, story.worktrees(top).get(branch))]
    staged, changes = _changes(top, cfg, wanted, ref)
    free, held, _ = _split(top, wanted, staged, changes)
    heads = repo.git("rev-parse", "HEAD", ref, cwd=top).splitlines()
    if (len(set(heads)) != 1 or repo.git("status", "--porcelain", "--untracked-files=all", cwd=top)):
        return [(f"Doctor needs a clean checkout at origin/{default} before it makes a fix for "
                 "Forge's files.", f"commit or discard your changes first, bring this checkout "
                 f"to origin/{default}, then {REPAIR}"), *_rows(free), *held]
    if not free: return held
    name = "forge-files-" + repo.now()[:16].replace("-", "").replace(":", "").replace("T", "-")
    branch = f"fix/{name}"
    if (_files_fix_finished(top, branch) or story.show(top, ref, repo.state_path(name)) is not None
            or repo.run("git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}", cwd=top).returncode == 0):
        return [(f"Doctor already used fix {name}, so doctor started no new one.",
                 f"run {REPAIR} again in the next minute"), *_rows(free), *held]
    who = repo.git("var", "GIT_AUTHOR_IDENT", cwd=top).split("<")[0].strip()
    state = {"kind": "fix", "why": WHY, "done_when": DONE, "base": repo.git("rev-parse", ref, cwd=top),
             "allow_large": "Doctor brings every file forge sync writes up to date in one change; "
                            f"{who} allowed it by running forge doctor --fix."}
    path = task._folder(f"fix-{name}")  # pyright: ignore[reportPrivateUsage]
    try:
        task._new_checkout(name, branch, f"fix-{name}", ref, state, f"Start the fix: {WHY}")  # pyright: ignore[reportPrivateUsage]
        fixed = repo.config(path)
        fixed_wanted = sync.files(path, fixed)
        if linked := _linked(path, fixed_wanted): return [(problem, _unfinished(name, branch, path)[1]) for problem, _ in linked]
        free, held, keep = _split(path, fixed_wanted, staged, changes)
        if free:
            free = sync.write(path, fixed, keep)
            repo.git("add", "-A", "-f", "--", *free, cwd=path)
            repo.git("commit", "-q", "-m", WHY, "--", *free, cwd=path)
    except (repo.Refused, OSError, subprocess.CalledProcessError) as failed:
        return [(f"Doctor couldn't bring Forge's files up to date in fix {name}: "
                        f"{_last(failed)}", _unfinished(name, branch, path)[1]), *held]
    if not free: return [_unfinished(name, branch, path), *held]
    print(f"- Fixed: wrote {len(free)} of Forge's files in fix {name}.")
    return [(f"Doctor's fix {name} holds Forge's files and isn't merged yet.", f"forge close {name}"), *held]

def _rows(free: list[str]) -> list[tuple[str, str]]:
    return [(f"{rel} differs from what forge sync writes for the installed Forge v{__version__}.", REPAIR) for rel in free]

def _files(top: Path, cfg: dict[str, Any], wanted: dict[str, str], fix: bool) -> list[tuple[str, str]]:
    if linked := _linked(top, wanted): return linked
    default = repo.default_branch(top)
    on_default, failed = repo.current_branch(top) == default, []
    if fix and on_default:
        fetched = repo.run("git", "fetch", "-q", "origin", cwd=top)
        if not fetched.returncode: return _in_fix(top, cfg, wanted)
        failed = [(f"doctor couldn't fetch {default} from origin, so it started no fix for " f"Forge's files: {_last(fetched)}",
                   f"check your network and GitHub access, then {REPAIR}")]
    staged, changes = _changes(top, cfg, wanted, story.landed_ref(top) if on_default else "HEAD")
    free, rows, keep = _split(top, wanted, staged, changes)
    if not fix or not free or failed: return failed + _rows(free) + rows
    try:  # forge sync's own write, so deletions and links behave exactly as there
        written = sync.write(top, cfg, keep)
    except (repo.Refused, OSError) as error:  # what is written stays, as forge sync leaves it
        still = [rel for rel in sync.differing(top, sync.files(top, cfg)) if rel not in keep]
        written = [rel for rel in free if rel not in still]
        if isinstance(error, repo.Refused) and error.entry is repo.REFUSALS["default_branch"]:
            problem, _, next_step = str(error).partition("\nNext: ")
            failure = (problem, next_step)  # a detached HEAD: sync's own refusal
        else: failure = (f"doctor couldn't write Forge's files: {_last(error)}", REPAIR)
        rows = [failure, *_rows(still), *rows]
    for rel in written: print(f"- Fixed: {'wrote' if (top / rel).exists() else 'removed'} {rel}.")
    return rows

def doctor(args: argparse.Namespace) -> int:
    top = repo.root()
    cfg = repo.config(top)
    install = sync.install_line(cfg["version"])
    rows: list[tuple[str, str]] = []
    def add(problem: str, fix: str = REPAIR) -> None: rows.append((problem, fix))
    pinned = "v" + cfg["version"].removeprefix("v")
    if pinned != f"v{__version__}":
        problem = repo.REFUSALS["pin"][0].format(installed=f"v{__version__}", pinned=pinned)
        release, installed = (re.match(r"v?(\d+)\.(\d+)\.(\d+)", v) for v in (pinned, __version__))
        repairs = bool(release and installed and tuple(map(int, release.groups())) >
                       tuple(map(int, installed.groups()))) and os.environ.get("FORGE_PINNED_RUN") != pinned
        if repairs and args.fix and shutil.which("uv"):
            done = repo.run(*install.split())
            forge = shutil.which("forge")
            if done.returncode == 0 and forge:
                print(f"- Fixed: installed Forge {pinned}, the version this repo pins.", flush=True)
                return subprocess.run([forge, "doctor", "--fix"], env={**os.environ, "FORGE_PINNED_RUN": pinned}).returncode
            said = _last(done) if done.returncode else "no forge is on PATH after uv installed it"
            add(f"{problem} Installing it failed: {said}", install)
        else: add(problem, REPAIR if repairs and not args.fix else install)
    on_codex = cfg["workers"] != "claude"  # split runs Codex and Claude
    needs_sdk = on_codex or bool(os.environ.get("CLAUDECODE") and shutil.which(os.environ.get("CODEX_BIN") or "codex"))
    sdk_failed = ""
    if args.fix and needs_sdk and shutil.which("uv") and codex.sdk_problem():
        try: codex.install()
        except repo.Refused as refused: sdk_failed = str(refused).partition("\nNext: ")[0]
    for tool in ("git", "gh", "uv") if cfg["workers"] == "codex" else ("git", "gh", "uv", "claude"):
        if not shutil.which(tool): add(f"{tool} is not installed or not on PATH.", INSTALL[tool])
    if shutil.which("gh") and repo.run("gh", "auth", "status", cwd=top).returncode: add("gh is not signed in to GitHub.", "gh auth login")
    if needs_sdk and (problem := sdk_failed or codex.sdk_problem()): add(problem)
    try:  # the reviewer close runs, at the version Forge pins
        review.helper()
    except repo.Refused as refused: add(str(refused).partition("\nNext: ")[0], INSTALL["autoreview"])
    try:
        wanted = sync.files(top, cfg)
        compared = ("- Note: doctor compared the synced files with the installed Forge " f"v{__version__}")
        compared += "." if pinned == f"v{__version__}" else (
            f", not the pinned {pinned}.\n  To check with {pinned}: {install}, then run forge " "doctor again.")
    except repo.Refused as refused:
        problem, _, fix = str(refused).partition("\nNext: ")
        add(f"doctor couldn't compare the synced files with what forge sync writes: " f"{problem}", fix)
        wanted, compared = {}, ""
    driver = repo.run("git", "config", "--get", "merge.forge-roadmap.driver", cwd=top).stdout.strip()
    attributes = sync.read(Path(repo.git("rev-parse", "--path-format=absolute", "--git-path", "info/attributes", cwd=top)))
    merge_drift = driver != sync.MERGE_DRIVER or sync.merge_attributes(attributes) != attributes
    hooks_drift = any(sync.read(path) != text for path, text in sync.shims(top, cfg).items())
    if hooks_drift or merge_drift:
        if not args.fix: add("The git hooks that check each commit and push aren't installed."
                         if hooks_drift else "The roadmap and spotted-list merge rule doesn't " "match the installed Forge.")
        else:
            try:  # never committed, so this repair runs on the default branch too
                if hooks_drift: sync.install_shims(top, cfg)
                else: sync.install_merge_rules(top)
                print("- Fixed: installed the git hooks that check each commit and push."
                      if hooks_drift else "- Fixed: installed the roadmap and spotted-list merge rule.")
            except repo.Refused as refused:
                problem, _, fix = str(refused).partition("\nNext: ")
                add(problem, fix)
    main = Path(repo.git("rev-parse", "--path-format=absolute", "--git-common-dir", cwd=top)).resolve().parent
    finished = _finished(top, main)
    if finished and not args.fix: add(f"{len(finished)} folders hold finished work: " f"{', '.join(str(path) for path, _, _ in finished)}.")
    for path, branch, state in finished if args.fix else []:
        removed = repo.run("git", "worktree", "remove", "--force", str(path), cwd=main)
        if removed.returncode:
            add(f"Forge couldn't remove {path}: {_last(removed)}", f"unlock it or close programs using it, then {REPAIR}")
            continue
        deleted = repo.run("git", "branch", "-D", branch, cwd=main)
        if deleted.returncode: add(f"Removed {path}, but its branch {branch} is still here: "
                         f"{_last(deleted).rstrip('.')}.", f"git branch -D {branch}")
        else: print(f"- Fixed: removed {path}, whose pull request is {state}.")
    rows += _files(top, cfg, wanted, args.fix and pinned == f"v{__version__}")
    if not shutil.which("sh"): add("sh isn't on PATH, so no host hook can run.", "install Git, which brings sh, and put it on PATH")
    elif wanted and sync.read(top / sync.LAUNCHER) != wanted.get(sync.LAUNCHER):
        add(f"doctor didn't run the host hooks, because {sync.LAUNCHER} differs from what " "forge sync writes.")
    else:
        env = {**os.environ, "PATH": BARE_PATH} if os.name != "nt" else None  # Windows has no /usr/bin
        bare = f" when run with PATH={BARE_PATH}" if env else ""
        checked: dict[tuple[str, str], subprocess.CompletedProcess[str]] = {}
        for rel in sync.HOSTS:
            generated = set(_forge_hooks(wanted.get(rel, "")))
            for event, command in _forge_hooks(sync.read(top / rel)):
                if (event, command) not in generated: continue
                key = (event, command)
                if key not in checked:
                    payload = {"session_id": "forge-doctor", "cwd": str(top), "hook_event_name": event, **SAMPLES.get(event, {})}
                    checked[key] = subprocess.run( [shutil.which("sh") or "sh", "-c", command], cwd=top,
                        input=json.dumps(payload), capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
                done = checked[key]
                if done.returncode:
                    said = (done.stderr.strip() or "it printed nothing").splitlines()
                    fix = next((line[6:] for line in said if line.startswith("Next: ")), install)
                    add(f"The {event} hook in {rel} fails with exit code " f"{done.returncode}{bare}: {said[0]}", fix)
    if not cfg["checks"]: add("forge.toml names no checks, so close has nothing to wait for.", "ask your agent to set checks in forge.toml")
    protection = (repo.run("gh", "api", f"repos/{{owner}}/{{repo}}/branches/" f"{repo.default_branch(top)}/protection", cwd=top)
                  if shutil.which("gh") else None)
    plan_note = (init.skipped(repo.default_branch(top), cfg["checks"]) if protection and init.no_protection_plan(protection) else "")
    if protection and (protection.returncode == 0 or "Branch not protected" in protection.stdout + protection.stderr):
        try:
            required = json.loads(protection.stdout).get("required_status_checks") or {}
            protected = {entry["context"] for entry in required.get("checks") or []
                         if isinstance(entry, dict) and isinstance(entry.get("context"), str)}
            protected.update(name for name in required.get("contexts") or [] if isinstance(name, str))
        except (ValueError, AttributeError): protected = set()
        if protected != set(cfg["checks"]): add("forge.toml checks differ from branch protection's required checks: "
                         f"Forge names {', '.join(sorted(cfg['checks'])) or 'none'}; protection "
                         f"requires {', '.join(sorted(protected)) or 'none'}.", "ask your agent to reconcile checks in forge.toml with branch protection")
    if "python -m forge.fasttest" in cfg["fast_test"]:
        add("fast_test still runs python -m forge.fasttest in the client's environment.",
            'replace it with fast_test = "forge test --pytest {base}" in forge.toml')
    if not cfg["test"]: add("forge.toml has no test command.", "ask your agent to set test in forge.toml, then run forge sync")
    elif "tests" in cfg["checks"] and f"run: {json.dumps(cfg['test'])}" not in sync.read( top / sync.WORKFLOW_PATH):
        add(f"The tests check in {sync.WORKFLOW_PATH} doesn't run forge.toml's test " "command.")
    codex_config = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex") / "config.toml"
    trusted = _codex_trusts(top, codex_config)
    trust = ("open Codex here and trust the project, or add " f'[projects."{top}"] with trust_level = "trusted" to {codex_config}')
    if on_codex and not trusted: add("Codex doesn't trust this project, so it would skip Forge's hooks and the "
                     "project's Codex settings.", trust)
    skills = {"claude": [Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude"), top / ".claude"],
              "codex": [codex_config.parent, Path.home() / ".agents", top / ".codex", top / ".agents"]}
    package = top / "package.json"
    packages = json.loads(sync.read(package)) if package.is_file() else {}
    dependencies = {**packages.get("dependencies", {}), **packages.get("devDependencies", {})}
    has_frontend = (any((top / path / "package.json").is_file() for path in ("frontend", "web", "apps/web"))
                    or any(name in dependencies for name in ("react", "react-dom", "vue", "svelte", "@angular/core", "next", "vite")))
    if has_frontend:
        for host in (host for host in skills if cfg["workers"] in (host, "split") or shutil.which(host)):
            for skill in ("impeccable", "emil-design-eng"):
                if not any((folder / "skills" / skill / "SKILL.md").is_file() for folder in skills[host]):
                    add(f"{skill} is required for UI work but isn't installed where the " f"{host} worker reads skills.", INSTALL[skill])
    for line in codex.tidy(top): print(f"- {line}")
    for problem, fix in rows: print(f"- {problem}\n  Fix: {fix}")
    if plan_note: print(f"- Note: {plan_note}")
    quicktest.suggest(top, cfg)
    if cfg["fast_test"]: print(f"- Note: close runs fast_test ({cfg['fast_test']}) instead of test, with {{base}} as "
              "the merge base with the default branch; the pull request's tests check still runs " "the full test command.")
    if on_codex: print("- Note: when Codex asks you to approve Forge's hooks, approve them; Forge can't see " "whether you did.")
    elif not trusted: print("- Note: Codex runs this repo's hooks only in a project it trusts, and it doesn't "
              f"trust this one yet.\n  Fix: {trust}")
    if rows:
        if compared: print(compared)
    else:
        print(f"Everything {'checks' if trusted else 'else checks'} out for Forge {cfg['version']}.")
        print(compared)
    cores = getattr(os, "process_cpu_count", os.cpu_count)() or 2
    budget = machine.half_cores()
    print(f"This machine: {cores} cores, so {budget} agents at once and test runs on {budget} cores.")
    if rows: repo.refuse(REFUSALS["problems"], count=len(rows))
    return 0
