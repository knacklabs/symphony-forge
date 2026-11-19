"""Audit: continued secondary limits must back off after a cached primary reset.

The reset tests end after one refusal, so they miss retries against an expired
snapshot. Only GitHub and the existing child clock are fake. Real close and its
shared cache own the retries; no new production seam is needed.
"""
import pytest

from test_close import env  # noqa: F401

STORY = "check-waits-by-quota"
pytestmark = pytest.mark.platform


def test_5_close_backs_off_after_a_cached_reset_passes(env, fake_clock):
    item, where = env.start_fix()
    clock = env.tmp / "clock" / "sitecustomize.py"
    clock.write_text(clock.read_text("utf-8") +
                     '\nreal_time = time.time\ntime.time = lambda: real_time() + float(offset.read_text("utf-8"))\n',
                     encoding="utf-8")
    stub = env.repo.bin / "gh"
    first, rest = stub.read_text("utf-8").split("\n", 1)
    stub.write_text(first + "\n" + '''import json, pathlib, sys, time
here = pathlib.Path(__file__).resolve().parent
args = sys.argv[1:]
attempts = here / "secondary-attempts"
rows = attempts.read_text("utf-8").splitlines() if attempts.exists() else []
if args[:2] == ["pr", "edit"]:
    with attempts.open("a", encoding="utf-8") as stream:
        stream.write(str(time.monotonic()) + "\\n")
    if len(rows) < 3:
        print("HTTP 429: You have exceeded a secondary rate limit.", file=sys.stderr)
        sys.exit(1)
if args[:2] == ["api", "rate_limit"]:
    reset = here / "primary-reset"
    if not reset.exists(): reset.write_text(str(int(time.time()) + 10), encoding="utf-8")
    remaining = 5000 if len(rows) >= 3 else 0
    print(json.dumps({"resources": {name: {"remaining": remaining,
        "reset": int(time.time()) + 3600 if remaining else int(reset.read_text("utf-8"))}
        for name in ("core", "graphql")}}))
    sys.exit(0)
''' + rest, encoding="utf-8")
    done = env.repo.forge("close", item, cwd=where)
    assert done.returncode == 0, done.stdout + done.stderr
    attempts = [float(row) for row in (env.repo.bin / "secondary-attempts").read_text("utf-8").splitlines()]
    assert len(attempts) >= 4
    assert 12 <= attempts[1] - attempts[0] < 18
    assert all(after - before >= 60 for before, after in zip(attempts[1:3], attempts[2:4]))
