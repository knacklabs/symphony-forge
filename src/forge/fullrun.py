"""Full tests on the latest default-branch commit, with GitHub as the result's one home."""
import json
import os
import re
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from forge import repo, review

STATUS = "forge-full-suite"


def next_run(top: Path) -> str:
    if repo.test_place(repo.config(top)) == "ci":
        return f"gh workflow run forge.yml --ref {repo.default_branch(top)}"
    return "forge test --full in the main checkout"


def latest(top: Path) -> str:
    """Refresh the default branch once before a full run or a gate reads its commit."""
    default = repo.default_branch(top)
    fetched = repo.run("git", "fetch", "--quiet", "origin",
                       f"refs/heads/{default}:refs/remotes/origin/{default}", cwd=top)
    if fetched.returncode:
        raise repo.Refused(f"Forge cannot fetch the latest commit on {default}.",
                           "git fetch origin, then try again")
    return repo.git("rev-parse", f"origin/{default}", cwd=top)


def green(top: Path) -> str:
    sha = latest(top)
    done = repo.run("gh", "api", f"repos/{{owner}}/{{repo}}/commits/{sha}/statuses", cwd=top)
    try:
        statuses = json.loads(done.stdout) if not done.returncode else []
        status = next((row for row in statuses if row.get("context") == STATUS), None)
    except (ValueError, TypeError, AttributeError):
        status = None
    default = repo.default_branch(top)
    if status and status.get("state") == "success":
        return ""
    if status and status.get("state") == "failure":
        return f"The full test run on the latest commit on {default} failed."
    return f"The latest commit on {default} has no green full test run."


def run(top: Path) -> int:
    command = repo.config(top)["test"]
    if not command:
        print("forge.toml names no test command, so forge test ran none.")
        return 0
    sha = latest(top)
    default = repo.default_branch(top)
    if repo.git("rev-parse", "HEAD", cwd=top) != sha:
        raise repo.Refused(
            f"The full run must use the latest commit on {default}. Next: "
            f"git switch {default} && git pull, then forge test --full.", "")
    if repo.git("status", "--porcelain", cwd=top):
        raise repo.Refused(
            "The full run must use only committed files. Next: commit or set aside the changes, "
            "then forge test --full.", "")
    status, report = review.test_run(top, command, sha, always=True)
    print(report)
    # The workflow publishes one result after every matrix group, including timed-out jobs.
    if os.environ.get("GITHUB_RUN_ID") and "FORGE_GROUP" in os.environ:
        return status
    fields = ["-f", f"context={STATUS}", "-f", f"state={'failure' if status else 'success'}",
              "-f", f"description=The full test run {'failed' if status else 'passed'}."]
    if os.environ.get("GITHUB_RUN_ID"):
        url = (f"{os.environ.get('GITHUB_SERVER_URL', 'https://github.com')}/"
               f"{os.environ['GITHUB_REPOSITORY']}/actions/runs/{os.environ['GITHUB_RUN_ID']}")
        fields += ["-f", f"target_url={url}"]
    posted = repo.run("gh", "api", "--method", "POST",
                      f"repos/{{owner}}/{{repo}}/statuses/{sha}", *fields, cwd=top)
    if status and repo.test_place(repo.config(top)) == "local":
        results = review.results_path(top)
        evidence = results.read_text("utf-8") if results.is_file() else ""
        failed = sorted(set(re.findall(r"^(?:failed|error) (.+)$", evidence, re.M)))
        why = "The full test run on main failed" + (": " + ", ".join(failed) if failed else "")
        if failed:
            print("Failing tests: " + ", ".join(failed))
        print(f"Next: forge fix start {repo.quote(why)} "
              f"--done {repo.quote('The full test run passes on main')}")
    if posted.returncode:
        print("Forge could not record the full test run on GitHub. "
              "Next: check GitHub access, then run forge test --full again.")
    return status


def notices(top: Path) -> list[str]:
    try:
        place = repo.test_place(repo.config(top))
    except repo.Refused:
        # Optional advice must not hide next's setup and unreadable-worktree reports.
        return []
    if place != "local" or not shutil.which("gh"):
        return []
    query = """query($owner:String!,$repo:String!,$branch:String!) {
      repository(owner:$owner,name:$repo) {
        ref(qualifiedName:$branch) { target { ... on Commit {
          history(first:30) { nodes { status { contexts { context state createdAt } } } }
        } } }
      }
    }"""
    done = repo.run("gh", "api", "graphql", "-F", "owner={owner}", "-F", "repo={repo}",
                    "-f", f"branch=refs/heads/{repo.default_branch(top)}",
                    "-f", "query=" + " ".join(query.split()), cwd=top)
    if done.returncode:
        return []
    try:
        data = json.loads(done.stdout)
        if data.get("errors"):
            return []
        nodes = data["data"]["repository"]["ref"]["target"]["history"]["nodes"]
        dates = [datetime.fromisoformat(row["createdAt"].replace("Z", "+00:00"))
                 for node in nodes for row in (node.get("status") or {}).get("contexts", [])
                 if row.get("context") == STATUS]
        if dates and datetime.fromisoformat(repo.now()) - max(dates) <= timedelta(hours=24):
            return []
    except (ValueError, KeyError, TypeError, AttributeError):
        return []
    return ["The daily full run on main is due. When this machine is quiet, "
            "run forge test --full in the main checkout."]
