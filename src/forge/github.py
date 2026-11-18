"""Wait for explicit GitHub quota refusals at the shared command edge."""
import json
import re
import sys
import time
from datetime import datetime, timezone


def run(args, execute, cwd):
    from forge import repo

    announced = False
    while True:
        done = execute()
        said = done.stderr + done.stdout
        if not done.returncode or not re.search(r"rate[ -]?limit|HTTP\s+429", said, re.I):
            return done
        header = re.search(r"x-ratelimit-reset:\s*(\d+)", said, re.I)
        if header:
            reset = int(header[1])
        else:
            # The quota endpoint is free of the primary limit. Do not recurse on its own refusal.
            if args[1:3] == ("api", "rate_limit"):
                return done
            quota = repo.run("gh", "api", "rate_limit", cwd=cwd)
            try:
                resources = json.loads(quota.stdout)["resources"]
                resource = resources["graphql" if "graphql" in said.lower() else "core"]
                reset = int(resource["reset"])
            except (ValueError, KeyError, TypeError, AttributeError):
                return done
        resume = reset + 3
        if not announced:
            when = datetime.fromtimestamp(resume, timezone.utc).strftime("%H:%M:%S UTC")
            print(f"GitHub rate limit reached. Wait until {when}, then continue.",
                  file=sys.stderr, flush=True)
            announced = True
        time.sleep(max(0, resume - time.time()))
