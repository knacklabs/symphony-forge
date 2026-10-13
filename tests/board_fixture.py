"""A client-sized board fixture for browser proof: 44 roadmap stories (30 planned with 4 parts each,
14 with no plan yet), 10 open fixes, 50 finished fixes and six weeks of merges, written as git history
in a new folder. Generated on demand, never checked in.

Usage: python tests/board_fixture.py <empty folder> <forge version>
Then run `forge board --out <page>` in <folder>/client.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

WHO = ["Shoppers", "Store managers", "Couriers", "Support staff", "Buyers", "Finance"]
WHAT = ["save a basket", "track a parcel", "return an order", "split a payment", "see stock levels",
        "print a packing slip", "reorder last week's shop", "share a wish list", "book a delivery slot",
        "apply a voucher", "export the month's sales", "answer a refund request"]
PARTS = ["Store the record", "Show it on the page", "Send a notice", "Add the report line"]


def build(folder: Path, version: str) -> Path:
    remote, client = folder / "origin.git", folder / "client"
    now = datetime.now(timezone.utc).replace(microsecond=0)
    env = {**os.environ, "GIT_AUTHOR_NAME": "Asha Rao", "GIT_AUTHOR_EMAIL": "asha@example.com",
           "GIT_COMMITTER_NAME": "Asha Rao", "GIT_COMMITTER_EMAIL": "asha@example.com"}

    def git(*args: str, at: datetime | None = None) -> None:
        dated = {**env, "GIT_AUTHOR_DATE": at.isoformat(), "GIT_COMMITTER_DATE": at.isoformat()} if at else env
        subprocess.run(["git", *args], cwd=client, env=dated, check=True, capture_output=True)

    def write(rel: str, data: object) -> None:
        path = client / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data if isinstance(data, str) else json.dumps(data, indent=2), encoding="utf-8")

    def commit(message: str, at: datetime) -> None:
        git("add", "-A")
        git("commit", "-qm", message, at=at)

    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    client.mkdir()
    git("init", "-q", "-b", "main")
    git("remote", "add", "origin", str(remote))
    stories = [(f"SHOP-{n + 1}", f"{WHO[n % len(WHO)]} can {WHAT[n % len(WHAT)]}"
                + (f", round {n // len(WHAT) + 1}" if n >= len(WHAT) else "")) for n in range(44)]
    write("forge.toml", f'version = "{version}"\nrepo = "client"\n')
    write("plans/roadmap.json", {"items": [{"key": key, "title": title} for key, title in stories]})
    start = now - timedelta(weeks=6)
    commit("Set up the shop", start)

    def step(name: str, at: datetime) -> dict:
        return {"step": name, "at": at.isoformat()}

    # 30 planned stories: 20 done, 6 building, 2 approved and not started, 2 still planning.
    for n, (key, title) in enumerate(stories[:30]):
        begun = start + timedelta(hours=6 + n * 30)
        rows = "\n".join(f"| T{p + 1} | {PARTS[p]} | {PARTS[p]} for {title.lower()} | 1 | `src/{key.lower()}-{p}.py` "
                         f"| `tests/test_{key.lower()}_{p}.py` | {f'T{p}' if p else (f'SHOP-{n}/T4' if n and n % 5 == 0 else 'none')} | no |"
                         for p in range(4))
        write(f"plans/{key}.md", f"# {title}\n\n## What changes for you\n\n{title}.\n\n## Why\n\nAsked for.\n\n"
              "## Done when\n\n1. It works.\n\n## Tasks\n\n| ID | Name | What it delivers | Covers | Scope | Tests | "
              f"After | User-facing |\n|---|---|---|---|---|---|---|---|\n{rows}\n\nNew moving parts: none\n\n"
              "## Risks\n\nRisks: none\n")
        state = {"doc": f"plans/{key}.md", "title": title, "status": "planning", "steps": [step("start", begun)]}
        if n < 28:
            state.update(status="approved", approval={"at": (begun + timedelta(hours=2)).isoformat()})
        write(f".factory/stories/{key}/story.json", state)
        commit(f"Plan {title}", begun + timedelta(hours=2))
        merged = 4 if n < 20 else (n % 3) + 1 if n < 26 else 0
        for p in range(merged):
            at = begun + timedelta(hours=8 + p * 20)
            write(f".factory/stories/{key}/tasks/T{p + 1}.json", {
                "branch": f"task/{key}-T{p + 1}", "status": "ready", "touches": 1,
                "steps": [step("start", at - timedelta(hours=5)), step("review", at - timedelta(hours=1))]})
            commit(f"{PARTS[p]} for {title.lower()}", min(at, now - timedelta(hours=1)))
        if n < 20:
            state.update(status="done", finished=(begun + timedelta(hours=80)).isoformat())
            write(f".factory/stories/{key}/story.json", state)
            commit(f"Finish {title}", min(begun + timedelta(hours=80), now - timedelta(hours=1)))
    # 50 finished fixes across the six weeks.
    for n in range(50):
        at = start + timedelta(hours=10 + n * 20)
        write(f".factory/fixes/fix-{n + 1}.json", {
            "kind": "fix", "branch": f"fix/fix-{n + 1}", "status": "ready",
            "why": f"{WHO[n % len(WHO)]} see the right total on page {n + 1}", "done_when": "It shows",
            "steps": [step("start", at - timedelta(hours=3)), step("review", at - timedelta(hours=1))]})
        commit(f"Fix page {n + 1}", min(at, now - timedelta(hours=1)))
    git("push", "-q", "origin", "main")
    # In-progress parts of the building stories and 10 open fixes, each on its own pushed branch.
    branches = [(f"task/{key}-T{(n % 3) + 2}", f".factory/stories/{key}/tasks/T{(n % 3) + 2}.json", {})
                for n, (key, _) in enumerate(stories[:30]) if 20 <= n < 26]
    branches += [(f"fix/open-{n + 1}", f".factory/fixes/open-{n + 1}.json",
                  {"kind": "fix", "why": f"The {WHAT[n].split()[-1]} page loads faster", "done_when": "It is fast"})
                 for n in range(10)]
    for n, (branch, rel, extra) in enumerate(branches):
        git("switch", "-qc", branch, "main")
        at = now - timedelta(hours=4 + n * 7)
        write(rel, {"branch": branch, "status": "working", **extra, "steps": [step("start", at)]})
        commit("Start the work", at)
        git("push", "-q", "origin", branch)
        git("switch", "-q", "main")
    return client


if __name__ == "__main__":
    print(build(Path(sys.argv[1]), sys.argv[2]))
