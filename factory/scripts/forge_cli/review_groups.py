"""A big diff is reviewed in parallel groups, each retried on its own (0078).

The reviewer tool splits any prompt over 512 KB into chunks and runs them one
after another inside one call. WF-1A T1 (2026-09-14): a 900 KB diff, four
chunks of 20-40 minutes each, over an hour per review round, and one chunk
that came back truncated cost the whole hour. Nothing in that call could be
retried alone, and the lockfile alone was a chunk's worth of noise.

Forge now does the splitting itself, before the call, and only when the tool
would split anyway: the diff's product files are dealt into the fewest chunks
whose prompt fits, each chunk gets its own review worktree and its own
three-lens Codex run, all released together and joined. A chunk whose result
is refused is re-run alone, up to twice, with the refusal's cause written into
its brief. Scope-only rejections are retained as untrusted leads and sent to
the unique owning chunk for a fresh review. The accepted results are merged
into the exact shape the tool uses for its own chunks, so the recorder, the
projection and every reader stay unchanged.

What a chunk sees. Its bundle is only its files' diff, but its tree is the
whole task tip: the group's base is a synthetic commit with the group's files
put back to the task base and everything else at the tip, so `base...HEAD`
is the group's diff and HEAD is the tree that ships. Every finding, including
a contract verdict, must be anchored to one of this chunk's changed paths.
Other HEAD files are context only. Contracts wholly owned by other chunks are
omitted; the final union still requires every contract and keeps the worst
supported verdict.

A diff that fits in one prompt is one group: the same single call as before.
`FORGE_REVIEW_SPLIT_BYTES` lowers the split point for probes and tests.
"""
from __future__ import annotations

import contextlib
import copy
import io
import json
import os
import subprocess
import time
import unicodedata
from pathlib import Path

from .common import fail
from .tasks import _git, _require_git

# The reviewer tool's MAX_REVIEW_PROMPT_BYTES is 512,000; forge splits a
# little under it so the tool never has to split what forge already split.
REVIEW_SPLIT_BYTES = 480_000
SPLIT_ENV = "FORGE_REVIEW_SPLIT_BYTES"
# Prompt bytes the tool adds around the brief, dataset and bundle.
PROMPT_SLACK = 8_000
# Files that add bytes to a bundle and nothing to a review. Put back to the
# task base in every review tip; they still ship in the PR and stay in scope.
REVIEW_NOISE_NAMES = frozenset({
    "pnpm-lock.yaml", "package-lock.json", "yarn.lock", "npm-shrinkwrap.json",
    "Cargo.lock", "poetry.lock", "uv.lock", "Pipfile.lock", "Gemfile.lock",
    "composer.lock", "go.sum", "flake.lock",
})
REVIEW_NOISE_SUFFIXES = (".min.js", ".min.css", ".map", ".snap", ".lock")
REVIEW_NOISE_DIRS = ("__snapshots__/", "generated/", "__generated__/")
MAX_GROUP_RETRIES = 2
LISTED_PATHS = 60


def review_split_bytes() -> int:
    raw = os.environ.get(SPLIT_ENV, "").strip()
    if raw.isdigit() and int(raw) > 0:
        return int(raw)
    return REVIEW_SPLIT_BYTES


def is_review_noise(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    return (name in REVIEW_NOISE_NAMES
            or name.endswith(REVIEW_NOISE_SUFFIXES)
            or any(f"/{marker}" in f"/{path}" for marker in REVIEW_NOISE_DIRS))


def restore_paths_to_base(worktree: Path, base_sha: str, paths: list[str],
                          message: str) -> str:
    """Put `paths` back to the task base in the detached worktree and commit;
    return the new tip. A path that did not exist at the base is dropped."""
    for rel in paths:
        at_base = _git(worktree, "cat-file", "-e", f"{base_sha}:{rel}").returncode == 0
        if at_base:
            _require_git(worktree, f"restoring {rel} to the task base",
                         "checkout", base_sha, "--", rel)
        else:
            _require_git(worktree, f"dropping {rel} from the review tip",
                         "rm", "-q", "--cached", "--", rel)
            path = worktree / rel
            if path.is_file():
                path.unlink()
    _require_git(worktree, "committing the review tip",
                 "-c", "user.name=forge-review", "-c", "user.email=forge-review@local",
                 "commit", "-q", "--no-verify", "--allow-empty", "-m", message)
    return _require_git(worktree, "resolving the review tip", "rev-parse", "HEAD")


def diff_bytes_by_path(worktree: Path, base_sha: str) -> dict[str, int]:
    """Patch bytes per changed path, base..HEAD, in git's own order."""
    paths_proc = _git(worktree, "diff", "--no-renames", "--name-only", "-z",
                      f"{base_sha}..HEAD")
    if paths_proc.returncode != 0:
        fail("listing review paths failed: " + (paths_proc.stderr.strip() or "git diff"))
    paths = paths_proc.stdout.split("\0")
    if paths[-1] == "":
        paths.pop()
    proc = _git(worktree, "-c", "core.pager=cat", "diff", "--no-color",
                "--no-ext-diff", "--no-renames", f"{base_sha}..HEAD")
    if proc.returncode != 0:
        fail("listing the review diff failed: " + (proc.stderr.strip() or "git diff"))
    sizes: dict[str, int] = {}
    current = None
    section = 0
    for line in proc.stdout.split("\n"):
        if line.startswith("diff --git "):
            if section >= len(paths):
                fail("review diff path and patch section counts differ")
            current = paths[section]
            section += 1
            sizes[current] = 0
        if current is not None:
            sizes[current] += len(line.encode("utf-8", "surrogateescape")) + 1
    if section != len(paths):
        fail("review diff path and patch section counts differ")
    return sizes


def plan_groups(sizes: dict[str, int], capacity: int) -> list[list[str]]:
    """Deal paths into the fewest groups whose patch bytes fit `capacity`,
    keeping git's order so neighbouring files stay together. A single path
    larger than the capacity is a group of its own (the tool chunks it)."""
    capacity = max(capacity, 1)
    groups: list[list[str]] = []
    current: list[str] = []
    used = 0
    for path, size in sizes.items():
        if current and used + size > capacity:
            groups.append(current)
            current, used = [], 0
        current.append(path)
        used += size
    if current:
        groups.append(current)
    return groups


def group_commits(worktree: Path, base_sha: str, review_tip: str,
                  group_paths: list[str], index_file: Path) -> tuple[str, str]:
    """Two commits for one group: a base whose tree is the review tip with the
    group's files put back to the task base, and a tip carrying the review
    tip's whole tree on top of it. `base...tip` is exactly the group's diff;
    the tree at the tip is the whole task, as it ships."""
    from factory_lib import clean_git_env
    env = {**clean_git_env(), "GIT_INDEX_FILE": str(index_file),
           "GIT_AUTHOR_NAME": "forge-review", "GIT_AUTHOR_EMAIL": "forge-review@local",
           "GIT_COMMITTER_NAME": "forge-review",
           "GIT_COMMITTER_EMAIL": "forge-review@local"}

    def run(description: str, *args: str) -> str:
        proc = subprocess.run(["git", *args], cwd=worktree, capture_output=True,
                              text=True, env=env, encoding="utf-8")
        if proc.returncode != 0:
            fail(f"{description} failed: {proc.stderr.strip() or proc.stdout.strip()}")
        return proc.stdout.strip()

    run("reading the review tip", "read-tree", review_tip)
    for rel in group_paths:
        entry = _git(worktree, "--literal-pathspecs", "ls-tree", base_sha,
                     "--", rel).stdout.strip()
        if entry:
            mode, _kind, sha = entry.split("\t", 1)[0].split()
            run(f"putting {rel} at the task base", "update-index", "--add",
                "--cacheinfo", f"{mode},{sha},{rel}")
        else:
            run(f"dropping {rel} from the group base", "update-index",
                "--force-remove", "--", rel)
    tree = run("writing the group base tree", "write-tree")
    group_base = run("committing the group base", "commit-tree", tree, "-p", base_sha,
                     "-m", f"review group base: {len(group_paths)} path(s) at task "
                           f"base {base_sha[:12]}")
    group_tip = run("committing the group tip", "commit-tree", f"{review_tip}^{{tree}}",
                    "-p", group_base, "-m", "review group tip: the whole task tree")
    return group_base, group_tip


def group_note(index: int, total: int, paths: list[str], others: list[str],
               repo_readable: bool) -> str:
    def listed(items: list[str]) -> str:
        shown = "\n".join(f"- {item}" for item in items[:LISTED_PATHS])
        more = len(items) - LISTED_PATHS
        return shown + (f"\n- ... and {more} more" if more > 0 else "")

    lines = [
        f"REVIEW GROUP {index} OF {total}. The task's diff was too large for one "
        "pass, so this bundle carries only these changed files:", listed(paths), "",
    ]
    if repo_readable:
        lines += [
            f"The task's other changed files ({len(others)}) are reviewed by the "
            "other groups. They ARE in the tree at HEAD, your working folder, "
            "exactly as they will ship:", listed(others), "",
            "Review this chunk's changed files through all three lenses. A defect "
            "finding must use a file_path from this chunk's changed-file list. "
            "Record a verdict for every contract you can prove from a line you "
            "read, with that line as its location, wherever the line is; a verdict "
            "record located outside this chunk is set aside by the review tool and "
            "counted by the harness. Omit a contract you cannot prove, and never "
            "invent an implemented verdict or a local anchor.",
        ]
    else:
        lines += [
            f"The task's other changed files ({len(others)}) are not visible to "
            "you:", listed(others), "",
            "Review this chunk's changed files through all three lenses. Every "
            "emitted finding, including VERDICT, must use a file_path from this "
            "chunk's changed-file list. Omit a contract wholly owned by another "
            "chunk; never invent an implemented verdict or a local anchor.",
        ]
    lines += ["", "Every chunk's accepted result is merged. The final union requires "
              "every task contract, the worst supported verdict per contract wins, "
              "and a contract no group records is partial, fail-closed."]
    return "\n".join(lines)


def diagnose_refusal(problem: str, parsed: dict | None = None,
                     paths: list[str] | None = None) -> str:
    """Turn a refusal into the one instruction the retry needs."""
    text = problem.lower()
    quoted = problem.strip().rstrip(".")
    rejected = parsed.get("scope_rejected_findings") if isinstance(parsed, dict) else None
    if isinstance(rejected, list):
        from .review import _is_verdict_record
        defects = [finding for finding in rejected if not _is_verdict_record(finding)]
        if defects:
            named = [
                f"{finding.get('title', '?')} @ "
                f"{(finding.get('code_location') or {}).get('file_path', '?')}"
                for finding in defects if isinstance(finding, dict)
            ]
            return ("Your previous pass was refused: the review tool set aside "
                    f"{len(rejected)} finding(s) located outside this chunk and at "
                    "least one is not a verdict record: " + "; ".join(named[:6])
                    + ". A defect finding must be located in one of this chunk's "
                    "files: " + ", ".join(paths or []) + ". Move it there or drop it.")
    if "within 3000 characters" in text:
        return ("Your previous pass overflowed overall_explanation (the tool caps it "
                "at 3000 characters). Keep each of the three assessments to a few "
                "sentences; verdicts are finding records, never lines in "
                "overall_explanation.")
    if "marker" in text or "assessment is empty" in text or "order" in text \
            or "copied one lens" in text:
        return (f"Your previous pass was refused: {quoted}. Write the six marker "
                "lines exactly once each, in the order quality, performance, "
                "security, each pair with its own non-empty assessment between "
                "them, and no VERDICT line in overall_explanation.")
    if "verdict" in text:
        return (f"Your previous pass was refused: {quoted}. Every plan contract "
                "needs exactly one finding titled `[quality] VERDICT <id>: "
                "implemented|partial|missing`; no VERDICT under any other lens tag "
                "and none in overall_explanation.")
    if "lens title tag" in text or "invalid" in text or "duplicate" in text:
        return (f"Your previous pass was refused: {quoted}. Every finding needs "
                "exactly one of [quality] , [performance] , [security] at the start "
                "of its title, a file_path and line, one of the five categories, a "
                "P0-P3 priority and null source_attribution.")
    if "json" in text or "exited" in text:
        return (f"Your previous pass produced no usable result ({quoted}). Return "
                "exactly one JSON object matching the schema and nothing else.")
    return f"Your previous pass was refused: {quoted}. Correct exactly that."


def _bounded(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    suffix = "\n\n[truncated]"
    return text[:max(0, limit - len(suffix))] + suffix


def flatten_passes(report: dict) -> list[dict]:
    """The chunk wrappers inside one group result: the group's single pass,
    or, when the tool chunked the group internally, each of its passes. Each
    carries the report fields plus provider_report, as `_actual_passes`
    expects of a chunk."""
    if "pass_reports" in report:
        return [copy.deepcopy(entry["report"]) for entry in report["pass_reports"]]
    return [{key: copy.deepcopy(value) for key, value in report.items()
             if key != "review_status"}]


def merge_group_reports(wrappers: list[dict]) -> dict:
    """Merge chunk wrappers the way the reviewer tool merges its own chunks
    (merge_chunk_reports): one finding per (path, line, category, title), its
    body prefixed with the chunk label, aggregate correctness, the minimum
    confidence, every pass preserved under pass_reports."""
    labelled = [(f"chunk {index}/{len(wrappers)}", wrapper)
                for index, wrapper in enumerate(wrappers, 1)]
    findings: list[dict] = []
    seen: set[tuple[str, int, str, str]] = set()
    for label, wrapper in labelled:
        for finding in wrapper["findings"]:
            location = finding["code_location"]
            key = (location["file_path"], location["line"], finding["category"],
                   " ".join(finding["title"].lower().split()))
            if key in seen:
                continue
            seen.add(key)
            merged = copy.deepcopy(finding)
            merged["body"] = _bounded(f"{label}:\n\n{merged['body']}", 2000)
            findings.append(merged)
    summary = ", ".join(f"{label}: {len(wrapper['findings'])} finding(s)"
                        for label, wrapper in labelled)
    incorrect = bool(findings) or any(
        wrapper["overall_correctness"] == "patch is incorrect" for _, wrapper in labelled)
    report = {
        "findings": findings,
        "overall_correctness": "patch is incorrect" if incorrect else "patch is correct",
        "overall_explanation": _bounded(
            f"Review passes returned. {summary}. See preserved pass reports for "
            "provider conclusions.", 3000),
        "overall_confidence": min(wrapper["overall_confidence"] for _, wrapper in labelled),
        "pass_reports": [{"label": label, "report": copy.deepcopy(wrapper)}
                         for label, wrapper in labelled],
    }
    if len(labelled) == 1:
        report.update(copy.deepcopy(labelled[0][1]))
        report["findings"] = findings
    for field in ("scope_rejected_findings", "priority_filtered_findings",
                  "attribution_rejected_findings"):
        retained = [copy.deepcopy(finding) for _, wrapper in labelled
                    for finding in wrapper.get(field) or []]
        if retained:
            report[field] = retained
    incomplete = any(report.get(field) for field in (
        "scope_rejected_findings", "missing_required_findings",
        "attribution_rejected_findings"))
    report["review_status"] = (
        "incomplete" if incomplete else "findings" if findings
        else "filtered" if report.get("priority_filtered_findings")
        else "incorrect" if report["overall_correctness"] == "patch is incorrect"
        else "scoped-clean")
    return report


def _run_group_batch(pending: list[dict], *, prompt_rel: str, log_dir: Path,
                     ledger_root: Path, argv_for,
                     heartbeat_every: float) -> dict[str, dict]:
    """Launch one attempt for each pending group and join the processes."""
    from .review import _close_codex_run, _record_codex_run, _stamp_codex_run

    launched: dict[str, dict] = {}
    try:
        for group in pending:
            group["attempts"] += 1
            stem = f"{group['label']}.attempt{group['attempts']}"
            json_out = log_dir / f"{stem}.json"
            json_out.unlink(missing_ok=True)
            argv = argv_for(group, json_out, group["extra_prompt"])
            log = (log_dir / f"{stem}.log").open("wb")
            run_id = _record_codex_run(
                ledger_root, f"{prompt_rel} [{group['label']}]", argv,
            )
            process = subprocess.Popen(
                argv, cwd=group["worktree"], stdout=log,
                stderr=subprocess.STDOUT,
                env={**os.environ, "PYTHONUTF8": "1"},
            )
            _stamp_codex_run(ledger_root, run_id, pid=process.pid)
            launched[group["label"]] = {
                "group": group, "process": process, "run_id": run_id, "log": log,
                "json": json_out, "started": time.monotonic(), "returncode": None,
            }
        print(f"review groups released together: {', '.join(launched)} (pids "
              f"{', '.join(str(item['process'].pid) for item in launched.values())}); "
              f"each group's output is {log_dir.as_posix()}/<group>.attemptN.log",
              flush=True)
        last_beat = time.monotonic()
        while any(item["returncode"] is None for item in launched.values()):
            for label, item in launched.items():
                if item["returncode"] is not None:
                    continue
                code = item["process"].poll()
                if code is None:
                    continue
                item["returncode"] = code
                _close_codex_run(ledger_root, item["run_id"], code)
                item["log"].close()
                took = int(time.monotonic() - item["started"])
                item["group"]["seconds"] += took
                print(f"== {label} finished (exit {code}, {took}s) ==", flush=True)
            now = time.monotonic()
            if now - last_beat >= heartbeat_every:
                last_beat = now
                running = " · ".join(
                    f"{label} {int(now - item['started'])}s"
                    for label, item in launched.items()
                    if item["returncode"] is None
                )
                print(f"review still running: {running}", flush=True)
            time.sleep(0.25)
    finally:
        for item in launched.values():
            if item["returncode"] is None:
                try:
                    item["process"].terminate()
                except OSError:
                    pass
                _close_codex_run(ledger_root, item["run_id"], None)
            try:
                item["log"].close()
            except OSError:
                pass
    return launched


def _group_result(item: dict, validate) -> tuple[str, object, bytes, object]:
    """Read and certify one completed group attempt."""
    from .review import _scope_only_rejected_findings

    problem = ""
    parsed = None
    raw = b""
    scope_findings = None
    if not item["json"].is_file():
        problem = "the review tool produced no JSON"
    else:
        raw = item["json"].read_bytes()
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            problem = f"the review tool produced invalid JSON: {exc}"
    if not problem and item["returncode"] == 2:
        certifying_problem = _refusal(validate, parsed)
        if certifying_problem:
            scope_problem = _refusal(_scope_only_rejected_findings, parsed)
            if scope_problem:
                problem = ("the review tool exit 2 was not a valid scope-only "
                           f"rejection: {scope_problem}")
            else:
                scope_findings = _scope_only_rejected_findings(copy.deepcopy(parsed))
    elif not problem and item["returncode"] not in (0, 1):
        problem = f"the review tool exited {item['returncode']}"
    if not problem and scope_findings is None:
        problem = _refusal(validate, parsed)
    return problem, parsed, raw, scope_findings


def _route_scope_findings(group: dict, retained_local: list[dict],
                          scope_rejected: list[dict], owners: dict[str, list[dict]],
                          schedule) -> None:
    """Route scope-only claims to the one group that owns each changed path."""
    from .review import VERDICT_RECORD, _tagged_finding

    group_paths = {
        unicodedata.normalize("NFC", item) for item in group.get("paths", [])
    }

    def add_lead(owner: dict, finding: dict) -> None:
        _lens, clean, _fingerprint, _merge_key = _tagged_finding(finding)
        if VERDICT_RECORD.match(clean["title"]):
            return
        key = json.dumps(finding, sort_keys=True, ensure_ascii=False)
        if key in owner["lead_keys"]:
            return
        owner["lead_keys"].add(key)
        owner["lead_findings"].append(copy.deepcopy(finding))
        schedule(owner)

    for finding in retained_local:
        path = finding["code_location"]["file_path"]
        if unicodedata.normalize("NFC", path) not in group_paths:
            fail(f"{group['label']} retained a local finding outside its assigned "
                 f"paths: {path}")
        add_lead(group, finding)
    for finding in scope_rejected:
        path = finding["code_location"]["file_path"]
        normalized_path = unicodedata.normalize("NFC", path)
        if normalized_path in group_paths:
            fail(f"{group['label']} returned contradictory scope metadata for its "
                 f"own path {path}")
        matches = owners.get(normalized_path, [])
        if len(matches) != 1:
            detail = "outside the full group union" if not matches else "ambiguous"
            fail(f"{group['label']} rejected finding path {path} is {detail}; "
                 "refusing cross-group routing")
        add_lead(matches[0], finding)


def run_groups(*, groups: list[dict], prompt_rel: str, log_dir: Path,
               ledger_root: Path, argv_for, validate,
               heartbeat_every: float = 60.0) -> list[dict]:
    """Release one three-lens run per group, all together; join them; re-run
    alone every group whose result is refused, with the cause in its brief;
    scope-only rejected findings are reassessed by their unique owning group.

    `groups` entries carry `label` and `worktree`. `argv_for(group, json_out,
    extra_prompt)` builds the argv. `validate(parsed)` raises SystemExit (via
    `fail`, which prints the reason) when the result would be refused at
    record time. Each group returns with every `accepted_reports` entry plus
    its latest `report`, `raw`, `attempts` and `seconds`. Every attempt's
    output and JSON stay under `log_dir`.
    """
    log_dir.mkdir(parents=True, exist_ok=True)
    pending = list(groups)
    owners: dict[str, list[dict]] = {}
    for group in groups:
        group.update({
            "attempts": 0, "extra_prompt": None, "seconds": 0,
            "accepted_reports": [], "lead_findings": [], "lead_keys": set(),
            "scope_correction": False, "retry_cause": "", "retry_parsed": None,
        })
        for path in group.get("paths", []):
            owners.setdefault(unicodedata.normalize("NFC", path), []).append(group)

    def schedule(targets: dict[str, dict], group: dict) -> None:
        if group["attempts"] >= MAX_GROUP_RETRIES + 1:
            fail(f"{group['label']} cannot reassess routed scope leads: its three-attempt "
                 "maximum is exhausted")
        targets[group["label"]] = group

    def retry_prompt(group: dict) -> str:
        parts = []
        if group["retry_cause"]:
            parts.append(diagnose_refusal(
                group["retry_cause"], group["retry_parsed"], group.get("paths") or []))
        if group["scope_correction"]:
            allowed = "\n".join(f"- {path}" for path in group.get("paths", []))
            parts.append(
                "SCOPE CORRECTION: emit findings only on these assigned changed paths:\n"
                f"{allowed}\nOther HEAD files are context only. Omit cross-chunk "
                "VERDICT records and never fabricate a local anchor.")
        if group["lead_findings"]:
            leads = json.dumps(group["lead_findings"], sort_keys=True, ensure_ascii=False)
            parts.append(
                "UNTRUSTED REVIEW LEADS: reassess these retained local or routed "
                "cross-group claims through the normal "
                "review of your assigned changed paths. Do not copy or promote a lead "
                f"without independently supporting it. LEADS_JSON={leads}")
        return f"RETRY {group['attempts'] + 1}: " + "\n\n".join(parts)
    started_all = time.monotonic()
    while pending:
        launched = _run_group_batch(
            pending, prompt_rel=prompt_rel, log_dir=log_dir,
            ledger_root=ledger_root, argv_for=argv_for,
            heartbeat_every=heartbeat_every,
        )

        retrying: dict[str, dict] = {}
        for label, item in launched.items():
            group = item["group"]
            problem, parsed, raw, scope_findings = _group_result(item, validate)
            if not problem:
                if scope_findings is not None:
                    retained_local, scope_rejected = scope_findings
                    group["scope_correction"] = True
                    group["retry_cause"] = ""
                    group["retry_parsed"] = None
                    if group["attempts"] > MAX_GROUP_RETRIES:
                        fail(f"{label} was scope-refused {group['attempts']} times; its "
                             f"attempts are kept under {log_dir.as_posix()}; fix the "
                             "scope cause and rerun the review.")
                    schedule(retrying, group)

                    _route_scope_findings(
                        group, retained_local, scope_rejected, owners,
                        lambda owner: schedule(retrying, owner),
                    )
                    print(f"== {label} scope-only rejection retained; retrying its scope "
                          "and reassessing routed owner leads ==", flush=True)
                else:
                    group["accepted_reports"].append(copy.deepcopy(parsed))
                    group["report"], group["raw"] = parsed, raw
                    group["retry_cause"] = ""
                    group["retry_parsed"] = None
                continue
            if group["attempts"] > MAX_GROUP_RETRIES:
                fail(f"{label} was refused {group['attempts']} times; last cause: "
                     f"{problem}. Its attempts are kept under {log_dir.as_posix()} "
                     f"({label}.attempt*.log and .json); read them, fix the cause, "
                     "rerun the review.")
            group["retry_cause"] = problem
            group["retry_parsed"] = copy.deepcopy(parsed)
            schedule(retrying, group)
            print(f"== {label} refused ({problem}); retrying it alone with the cause "
                  f"in its brief (attempt {group['attempts'] + 1}) ==", flush=True)
        pending = list(retrying.values())
        for group in pending:
            group["extra_prompt"] = retry_prompt(group)
    total = int(time.monotonic() - started_all)
    timing = ", ".join(f"{group['label']} {group['seconds']}s"
                       + (f" x{group['attempts']}" if group["attempts"] > 1 else "")
                       for group in groups)
    print(f"review groups done in {total}s wall ({timing})", flush=True)
    for group in groups:
        if not group["accepted_reports"]:
            fail(f"{group['label']} produced no accepted review pass")
    return groups


def _refusal(validate, parsed: dict) -> str:
    """The reason `validate` refuses `parsed`, or '' when it accepts it.
    `fail` prints `ERROR: <reason>` and exits; the reason is captured here so
    it can be handed back to the reviewer."""
    captured = io.StringIO()
    try:
        with contextlib.redirect_stdout(captured):
            validate(copy.deepcopy(parsed))
    except SystemExit as exc:
        reason = captured.getvalue().strip()
        reason = reason.split("ERROR: ", 1)[-1].strip() if reason else ""
        return reason or (str(exc.code) if not isinstance(exc.code, int) else "refused")
    return ""
