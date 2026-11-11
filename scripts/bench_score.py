"""Score a built app with model-free checks, save the score by release and compare it with the last one."""
import argparse
import hashlib
import json
import os
import re
import subprocess
import time
import tomllib
import urllib.error
import urllib.request
from pathlib import Path

LAUNCHER = ".claude/skills/impeccable/scripts/impeccable"
USAGE_KEYS = ("input_tokens", "output_tokens", "turns", "minutes")
NOT_FOUND = {127, 9009}  # the shell's "command not found" on POSIX and Windows


def release_number(name):
    found = re.fullmatch(r"v(\d+(?:\.\d+)*)", name)
    return tuple(int(part) for part in found[1].split(".")) if found else None


def run_check(check, app, env):
    """One check: pass or fail, the number behind it, and a reason when it did not run."""
    try:
        done = subprocess.run(check["command"], shell=True, cwd=app, env=env, capture_output=True, text=True)
    except OSError as error:
        return {"status": "did not run", "number": None, "reason": str(error)}
    if done.returncode in NOT_FOUND:
        return {"status": "did not run", "number": None, "reason": "the command was not found"}
    if check["kind"] == "pass":
        return {"status": "pass" if done.returncode == 0 else "fail", "number": done.returncode, "reason": ""}
    words = done.stdout.split()
    if "did not run" in done.stdout or not words or not words[-1].isdigit():
        return {"status": "did not run", "number": None, "reason": (done.stdout or done.stderr).strip()[:200]}
    return {"status": "pass" if int(words[-1]) == 0 else "fail", "number": int(words[-1]), "reason": ""}


def start_app(app_entry, app, env):
    """Start the app and wait for its address; False when it never answers."""
    try:
        launch = subprocess.Popen(app_entry["start"], shell=True, cwd=app, env=env,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        return False
    deadline = time.monotonic() + app_entry.get("ready_timeout", 300)
    while time.monotonic() < deadline:
        if launch.poll() not in (None, 0):
            return False
        try:
            urllib.request.urlopen(app_entry["ready"], timeout=2)
            return True
        except urllib.error.HTTPError:
            return True  # any answer means the app is up
        except OSError:
            time.sleep(1)
    return False


def fingerprint(base, paths):
    """Bytes of the listed files (folders walk in name order), so a changed check shows up."""
    digest = hashlib.sha256()
    for entry in paths:
        path = base / entry
        for file in sorted(path.rglob("*")) if path.is_dir() else [path]:
            digest.update(file.relative_to(base).as_posix().encode())
            if file.is_file():
                digest.update(file.read_bytes())
    return digest


def engine_line(app):
    try:
        probe = subprocess.run([str(app / LAUNCHER), "engine-probe"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    lines = [line for line in probe.stdout.splitlines() if line.startswith("impeccable-engine")]
    return lines[0] if lines else "unknown"


def previous_score(results, release):
    """The saved score with the highest release number below this one; odd files are passed over."""
    wanted = release_number(release)
    found = []
    for file in results.glob("v*.json"):
        number = release_number(file.stem)
        if number and number < wanted:
            found.append((number, file))
    for _, file in sorted(found, reverse=True):
        try:
            saved = json.loads(file.read_text(encoding="utf-8"))
            if isinstance(saved["passed"], int) and isinstance(saved["total"], int):
                return file.stem, saved
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return None, None


def usage_lines(path):
    if not path:
        return None, ["Usage: not given"]
    try:
        usage = json.loads(Path(path).read_text(encoding="utf-8"))
        missing = [key for key in USAGE_KEYS if key not in usage]
    except (OSError, ValueError, TypeError):
        return None, ["Usage: the usage file could not be read"]
    if missing:
        return None, [f"Usage: the usage file is missing {', '.join(missing)}"]
    show = lambda value: "not reported" if value is None else value
    return usage, [f"Build took {show(usage['minutes'])} minutes",
                   f"Tokens: input {show(usage['input_tokens'])}, output {show(usage['output_tokens'])}, "
                   f"turns {show(usage['turns'])}"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("app")
    parser.add_argument("--checks", required=True)
    parser.add_argument("--release", required=True)
    parser.add_argument("--usage")
    parser.add_argument("--results", required=True)
    args = parser.parse_args()
    if not release_number(args.release):
        parser.error("--release must look like v1.2.36")
    app, checks_file, results = Path(args.app), Path(args.checks), Path(args.results)
    config = tomllib.loads(checks_file.read_text(encoding="utf-8"))
    env = {**os.environ, "CHECKS_DIR": str(checks_file.parent.resolve() / "checks")}

    # Build, tests and design checks first, then the app is started for the checks that need it.
    done = {}
    for check in (c for c in config["check"] if not c.get("app")):
        done[check["name"]] = run_check(check, app, env)
    wanted = [c for c in config["check"] if c.get("app")]
    if wanted:
        entry = config["app"]
        env["APP_URL"] = entry["ready"]
        up = start_app(entry, app, env)
        for check in wanted:
            done[check["name"]] = run_check(check, app, env) if up else {
                "status": "fail", "number": None, "reason": "the app did not start"}
        subprocess.run(entry["stop"], shell=True, cwd=app, env=env, capture_output=True)
    listed = [{"name": c["name"], **done[c["name"]]} for c in config["check"]]
    passed = sum(c["status"] == "pass" for c in listed)

    engine = engine_line(app)
    base = hashlib.sha256()
    base.update(fingerprint(checks_file.parent, config.get("baseline", [])).digest())
    base.update(fingerprint(app, config.get("app_baseline", [])).digest())
    base.update(engine.encode())
    baseline = base.hexdigest()[:12]
    usage, usage_text = usage_lines(args.usage)

    before, saved = previous_score(results, args.release)
    results.mkdir(parents=True, exist_ok=True)
    (results / f"{args.release}.json").write_text(json.dumps(
        {"release": args.release, "passed": passed, "total": len(listed), "checks": listed,
         "baseline": baseline, "engine": engine, "usage": usage}, indent=2), encoding="utf-8")

    print(f"{args.release}: {passed} of {len(listed)} checks pass")
    for check in listed:
        number = "" if check["number"] is None else f" ({check['number']})"
        reason = f": {check['reason']}" if check["reason"] else ""
        print(f"  {check['name']}: {check['status']}{number}{reason}")
    if not saved:
        print("No earlier score to compare with.")
    elif saved.get("baseline") != baseline:
        print(f"This is a new baseline: the notes, checks or design checker changed since {before}, so there is no direction.")
        print(f"  Design checker before: {saved.get('engine', 'unknown')}; now: {engine}")
        print(f"  {before}: {saved['passed']} of {saved['total']} checks pass")
    else:
        change = passed - saved["passed"]
        word = "same" if change == 0 else f"up {change}" if change > 0 else f"down {-change}"
        print(f"Compared with {before} ({saved['passed']} of {saved['total']} checks pass): {word}")
    print("\n".join(usage_text))


if __name__ == "__main__":
    main()
