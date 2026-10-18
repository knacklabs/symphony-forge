"""A saturated land queue lends a running-check wait's place to independent work.

The real commands own admission, close, checks and merges. GitHub holds the oldest
change's checks until an independent change reaches review; existing queue coverage
does not hold checks while all local places are occupied. No production seam is used.
"""

import json

from conftest import machine_cores
from test_close import env  # noqa: F401
from test_queue_land_all import _edit, _fix, client  # noqa: F401

STORY = "land-frees-ci-slots"


HELD_CHECKS = '''if args[:4] == ["api", "--paginate", "--jq", ".check_runs[]"]:
    branch = subprocess.run(["git", "branch", "--show-current"], capture_output=True,
                            text=True).stdout.strip()
    if branch == "fix/base":
        history = here / "held-checks.jsonl"
        reviews = here.parent / "review-starts.jsonl"
        released = reviews.exists() and any(
            json.loads(line)["fix"] == "independent" for line in reviews.read_text("utf-8").splitlines())
        status = "completed" if released else "in_progress" if history.exists() else "queued"
        append_json(history, {"state": status, "at": time.time()})
        if released:
            (here / "base-green").touch()
        answer("\\n".join(json.dumps(row) for row in [
            {"name": "tests", "status": status,
             "conclusion": "success" if released else None},
            {"name": "forge-pr-check", "status": "completed", "conclusion": "success"}]))

'''


def test_1_a_check_wait_admits_independent_close_but_keeps_order_and_backpressure(client, monkeypatch):
    env = client
    machine_cores(env.repo, 2)  # one place, so a waiting child would fill the queue
    monkeypatch.setenv("FORGE_CHECKS_WAIT", "45")
    base = _fix(env, monkeypatch, "base", 1, {"shared.py": _edit(1, "base")})
    main = env.repo.path
    try:
        env.repo.path = base
        _fix(env, monkeypatch, "child", 2, {"child.py": "CHILD = True\n"})
    finally:
        env.repo.path = main
    _fix(env, monkeypatch, "shared", 3, {"shared.py": _edit(7, "shared")})
    _fix(env, monkeypatch, "independent", 4, {"independent.py": "READY = True\n"})
    # Keep the borrowed place busy until base requests it back. Base must wait for
    # independent to finish, even though its checks are now green.
    (env.tmp / "wait-independent").write_text(
        (env.repo.bin / "base-green").as_posix(), encoding="utf-8")
    gh = env.repo.bin / "gh"
    text = gh.read_text("utf-8")
    gh.write_text(text.replace('if args[:4] == ["api", "--paginate", "--jq", ".check_runs[]"]:',
                               HELD_CHECKS + 'if args[:4] == ["api", "--paginate", "--jq", ".check_runs[]"]:',
                               1), encoding="utf-8")

    done = env.repo.forge("land", "--all", timeout=240)

    assert done.returncode == 0, done.stdout + done.stderr
    lines = done.stdout.splitlines()
    assert lines.index("Starting independent.") < lines.index("base merged."), done.stdout
    assert lines.index("independent merged.") < lines.index("base merged."), done.stdout
    assert lines.index("base merged.") < lines.index("Starting child."), done.stdout
    assert lines.index("base merged.") < lines.index("Starting shared."), done.stdout
    probes = [json.loads(line) for line in (env.repo.bin / "held-checks.jsonl")
              .read_text("utf-8").splitlines()]
    reviews = [json.loads(line) for line in (env.tmp / "review-starts.jsonl")
               .read_text("utf-8").splitlines()]
    independent = next(row["at"] for row in reviews if row["fix"] == "independent")
    # Queued CI keeps backpressure; running CI frees the place until checks complete.
    assert probes[0]["state"] == "queued", probes
    running = next(row["at"] for row in probes if row["state"] == "in_progress")
    green = next(row["at"] for row in probes if row["state"] == "completed")
    assert running < independent < green, (probes, reviews)
    assert "Merged (4):" in done.stdout, done.stdout
