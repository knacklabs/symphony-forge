"""Wait for explicit GitHub quota refusals at the shared command edge."""
import json
import re
import sys
import time
from datetime import datetime, timezone

NETWORK = ("Could not resolve host", "i/o timeout", "Connection timed out", "Connection reset",
           "error connecting to")
wait_for_reset = False  # Shared command setup enables this only for close, merge and land.


def run(args, execute, cwd):
    from forge import repo

    if not wait_for_reset or args[1:3] == ("api", "rate_limit"):
        return execute()
    announced = False
    while True:
        done = execute()
        said = done.stderr + done.stdout
        if not done.returncode or not re.search(
                r"\bAPI rate limit exceeded\b|\bsecondary rate limit\b|\bHTTP\s+429\b", said, re.I):
            return done
        resume = time.time() + 60
        retry = re.search(r"retry-after:\s*(\d+)", said, re.I)
        header = re.search(r"x-ratelimit-reset:\s*(\d+)", said, re.I)
        if retry:
            resume = time.time() + int(retry[1]) + 3
        elif header and "secondary rate limit" not in said.lower():
            resume = int(header[1]) + 3
        elif "secondary rate limit" not in said.lower():
            quota = repo.run("gh", "api", "rate_limit", cwd=cwd)
            resume = time.time() + 60
            try:
                resources = json.loads(quota.stdout)["resources"]
                graphql = args[1:3] == ("api", "graphql") or "graphql" in said.lower()
                resource = resources["graphql" if graphql else "core"]
                if quota.returncode == 0 and resource["remaining"] == 0:
                    resume = int(resource["reset"]) + 3
            except (ValueError, KeyError, TypeError, AttributeError):
                pass  # An unavailable quota lookup still permits the documented one-minute retry.
        if not announced:
            when = datetime.fromtimestamp(resume, timezone.utc).strftime("%H:%M:%S UTC")
            print(f"GitHub rate limit reached. Wait until {when}, then continue.",
                  file=sys.stderr, flush=True)
            announced = True
        time.sleep(max(0, resume - time.time()))
