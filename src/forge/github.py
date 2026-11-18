"""Wait for explicit GitHub quota refusals at the shared command edge."""
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone

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
                r"\brate limit\b.*\bexceeded\b|\bexceeded\b.*\brate limit\b|\bHTTP\s+429\b", said, re.I | re.S):
            return done
        quota = repo.run("gh", "api", "rate_limit", cwd=cwd)
        resume = time.time() + 60
        try:
            resources = json.loads(quota.stdout)["resources"]
            resource = resources["graphql" if args[1:3] == ("api", "graphql") else "core"]
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


def read(args: tuple[str, ...], execute) -> subprocess.CompletedProcess[str]:
    """Retry reads only: replaying a write after an unreadable receipt could duplicate it."""
    from forge import repo

    api = args[1:2] == ("api",)
    read = (args[1:3] in (("pr", "list"), ("pr", "view"), ("pr", "checks"),
                         ("run", "list"), ("run", "view"),
                         ("release", "list"), ("release", "view")))
    if api:
        # gh infers POST from fields; our GraphQL query is a read despite that POST.
        read = (not any(flag in args for flag in ("-f", "-F", "--field", "--raw-field", "--input"))
                or ("graphql" in args and any(re.match(r"query=\s*(?:\{|query\b)", arg)
                                              for arg in args)))
        if "--method" in args or "-X" in args:
            flag = "--method" if "--method" in args else "-X"
            read = args[args.index(flag) + 1].upper() == "GET"
    if not read:
        return execute()
    jq = args[args.index("--jq") + 1] if "--jq" in args else None
    structured = api or "--json" in args
    for pause in (1, 2, 4, None):
        done = execute()
        said = done.stderr + done.stdout
        if done.returncode and re.search(r"\bHTTP\s+(?:401|403|404)\b", said, re.I):
            return done
        unreadable = False
        if structured and done.returncode == 0:
            text = done.stdout.strip()
            try:
                if ((jq is None and api and "--paginate" in args and "--slurp" not in args)
                        or (jq is not None and jq.endswith("[]"))):
                    decoder = json.JSONDecoder()
                    while text:
                        _, end = decoder.raw_decode(text)
                        text = text[end:].lstrip()
                elif jq is None:
                    json.loads(text)
                else:
                    unreadable = text.startswith("<")
            except ValueError:
                unreadable = True
        transient = unreadable or (structured and (done.stdout.lstrip().startswith("<")
                                                   or done.stderr.lstrip().startswith("<"))) or (done.returncode and (
            re.search(r"\bHTTP\s+5\d\d\b", said, re.I)
            or re.search(r"\bunexpected EOF\b|\binvalid character\b", said, re.I)
            or "looking for beginning of value" in said
            or "unexpected end of JSON input" in said
            or any(text in said for text in repo.NETWORK)))
        if not transient:
            return done
        if pause is None:
            return subprocess.CompletedProcess(done.args, 1, "",
                                               repo.REFUSALS["no_github"][0] + "\n")
        time.sleep(pause)
