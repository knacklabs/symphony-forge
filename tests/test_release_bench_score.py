"""The release score: model-free checks on a built app, saved by release and compared with the last one."""
import json
import re
import socket
import subprocess
import sys
import tomllib
from pathlib import Path

STORY = "FORGE-BENCH-1"
ROOT = Path(__file__).resolve().parents[1]
PY = f'"{sys.executable}"'
LAUNCHER = ".claude/skills/impeccable/scripts/impeccable"


def _score(app, checks, release, results, usage=None):
    """Start the script the way the maintainer guide does."""
    command = ["uv", "run", "--frozen", "--python", "3.11", "python", "scripts/bench_score.py",
               str(app), "--checks", str(checks), "--release", release, "--results", str(results)]
    if usage is not None:
        usage_file = Path(results).parent / "usage.json"
        usage_file.write_text(json.dumps(usage), encoding="utf-8")
        command += ["--usage", str(usage_file)]
    return subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=120)


def _checks(path, checks, app_section="", baseline="", extra=""):
    lines = [baseline, app_section, extra]
    for name, command, kind, app in checks:
        lines.append(f'[[check]]\nname = "{name}"\ncommand = {json.dumps(command)}\nkind = "{kind}"\n'
                     f'app = {"true" if app else "false"}\n')
    path.write_text("\n".join(lines), encoding="utf-8")


def _free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def _closed(port):
    with socket.socket() as probe:
        return probe.connect_ex(("127.0.0.1", port)) != 0


def _fake_app(folder, port):
    folder.mkdir()
    (folder / "server.py").write_text(
        "import http.server, os, sys\n"
        "open('server.pid', 'w').write(str(os.getpid()))\n"
        "http.server.HTTPServer(('127.0.0.1', int(sys.argv[1])), http.server.SimpleHTTPRequestHandler).serve_forever()\n",
        encoding="utf-8")
    (folder / "stop.py").write_text(
        "import os, pathlib, signal, socket, time\n"
        "pathlib.Path('stopped').write_text('yes')\n"
        "pid = pathlib.Path('server.pid')\n"
        "if pid.exists():\n"
        "    os.kill(int(pid.read_text()), signal.SIGTERM)\n"
        f"    for _ in range(100):\n"
        f"        if socket.socket().connect_ex(('127.0.0.1', {port})):\n"
        "            break\n"
        "        time.sleep(0.05)\n",
        encoding="utf-8")


def test_2_the_score_counts_each_check_and_names_the_ones_that_did_not_run(tmp_path):
    port = _free_port()
    fetch = (f'{PY} -c "import urllib.request; '
             f'urllib.request.urlopen(\'http://127.0.0.1:{port}/\')"')
    checks = [("build", "exit 0", "pass", False), ("tests", "exit 1", "pass", False),
              ("design", "echo 3", "count", False), ("sign-in", "echo 0", "count", True),
              ("list", "no-such-command-for-the-score", "pass", True), ("form", fetch, "pass", True),
              ("dashboard", "exit 0", "pass", True), ("job", "exit 0", "pass", True)]
    app = tmp_path / "app"
    _fake_app(app, port)
    app_section = (f'[app]\nstart = {json.dumps(f"{PY} server.py {port}")}\n'
                   f'ready = "http://127.0.0.1:{port}/"\nready_timeout = 30\n'
                   f'stop = {json.dumps(f"{PY} stop.py")}\n')
    _checks(tmp_path / "checks.toml", checks, app_section)

    made = _score(app, tmp_path / "checks.toml", "v1.0.0", tmp_path / "results")
    assert made.returncode == 0, made.stdout + made.stderr
    saved = json.loads((tmp_path / "results/v1.0.0.json").read_text(encoding="utf-8"))
    assert (saved["passed"], saved["total"]) == (5, 8)
    assert "5 of 8 checks pass" in made.stdout
    by_name = {check["name"]: check for check in saved["checks"]}
    assert [(n, by_name[n]["status"], by_name[n]["number"]) for n in by_name] == [
        ("build", "pass", 0), ("tests", "fail", 1), ("design", "fail", 3), ("sign-in", "pass", 0),
        ("list", "did not run", None), ("form", "pass", 0), ("dashboard", "pass", 0), ("job", "pass", 0)]
    assert "did not run" in made.stdout
    assert _closed(port)

    # The app never starts: its 5 checks fail with a reason, stop still runs, the rest keep their own result.
    checks[1] = ("tests", "exit 0", "pass", False)
    checks[2] = ("design", "echo The design checks did not run because Node is not installed.", "count", False)
    broken = tmp_path / "broken"
    _fake_app(broken, port)
    never = (f'[app]\nstart = {json.dumps(f"{PY} -c pass")}\nready = "http://127.0.0.1:{port}/"\n'
             f'ready_timeout = 2\nstop = {json.dumps(f"{PY} stop.py")}\n')
    _checks(tmp_path / "broken.toml", checks, never)
    made = _score(broken, tmp_path / "broken.toml", "v1.0.1", tmp_path / "results")
    assert made.returncode == 0, made.stdout + made.stderr
    saved = json.loads((tmp_path / "results/v1.0.1.json").read_text(encoding="utf-8"))
    by_name = {check["name"]: check for check in saved["checks"]}
    assert (saved["passed"], saved["total"]) == (2, 8)
    assert [by_name[n]["reason"] for n in ("sign-in", "list", "form", "dashboard", "job")] == ["the app did not start"] * 5
    assert (by_name["design"]["status"], by_name["design"]["number"]) == ("did not run", None)
    assert by_name["build"]["status"] == by_name["tests"]["status"] == "pass"
    assert (broken / "stopped").exists()


def test_3_the_score_is_saved_by_release_and_compared_with_the_previous_saved_score(tmp_path):
    app = tmp_path / "app"
    (app / LAUNCHER).parent.mkdir(parents=True)
    (app / LAUNCHER).write_text("#!/bin/sh\necho 'impeccable-engine 1.0'\n", encoding="utf-8")
    (app / LAUNCHER).chmod(0o755)
    (app / "marker.txt").write_text("one", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("one", encoding="utf-8")
    results = tmp_path / "results"

    def go(release, passing, usage=None):
        steps = [(f"check {i}", "exit 0" if i < passing else "exit 1", "pass", False) for i in range(3)]
        _checks(tmp_path / "checks.toml", steps, baseline='baseline = ["notes.txt"]\napp_baseline = ["marker.txt"]\n')
        made = _score(app, tmp_path / "checks.toml", release, results, usage)
        assert made.returncode == 0, made.stdout + made.stderr
        return made.stdout

    assert "no earlier score" in go("v1.2.11", 2).lower()
    assert (results / "v1.2.11.json").exists()
    (results / "v1.2.11.json").unlink()

    go("v1.2.9", 1)
    go("v1.2.10", 2)
    (results / "other.json").write_text("{}", encoding="utf-8")
    (results / "v1.2.8.json").write_text("", encoding="utf-8")
    (results / "v1.2.7.json").write_text("{not json", encoding="utf-8")
    text = go("v1.2.11", 3)  # v1.2.10 is the previous score by number, though v1.2.9 sorts after it as text
    assert "Compared with v1.2.10" in text and "up 1" in text
    assert "2 of 3 checks pass" in text and "3 of 3 checks pass" in text
    go("v1.2.37", 0)
    assert "Compared with v1.2.11" in (down := go("v1.2.36", 1)) and "down 2" in down
    assert "same" in go("v1.2.12", 3)
    go("v1.2.11", 0)  # the same release again replaces its file
    assert json.loads((results / "v1.2.11.json").read_text(encoding="utf-8"))["passed"] == 0

    # Another check list, another design checker file or another engine: no direction.
    (tmp_path / "notes.txt").write_text("two", encoding="utf-8")
    assert "new baseline" in (text := go("v1.2.13", 3)) and "Compared with" not in text
    (app / "marker.txt").write_text("two", encoding="utf-8")
    assert "new baseline" in (text := go("v1.2.14", 3)) and "Compared with" not in text
    (app / LAUNCHER).write_text("#!/bin/sh\necho 'impeccable-engine 2.0'\n", encoding="utf-8")
    text = go("v1.2.15", 3)
    assert "new baseline" in text and "Compared with" not in text
    assert "impeccable-engine 1.0" in text and "impeccable-engine 2.0" in text

    # The usage file: minutes and tokens are printed, a null says so, missing keys are named.
    text = go("v1.2.16", 3, {"input_tokens": 1234, "output_tokens": None, "turns": None, "minutes": 42.5})
    assert "42.5" in text and "1234" in text and text.count("not reported") == 2
    text = go("v1.2.17", 3, {"minutes": 3})
    assert "input_tokens" in text and (results / "v1.2.17.json").exists()


def test_4_each_required_part_has_a_note_and_an_expected_check():
    notes = (ROOT / "benchmark/notes.md").read_text(encoding="utf-8").lower()
    for word in ("sign in", "list", "form", "dashboard", "job", "/api/jobs/mark-late-orders"):
        assert word in notes, f"the notes do not mention {word}"
    checks = tomllib.loads((ROOT / "benchmark/checks.toml").read_text(encoding="utf-8"))
    assert {"start", "ready", "stop"} <= set(checks["app"])
    names = {check["name"] for check in checks["check"] if check.get("app")}
    assert names == {"sign-in", "list", "form", "dashboard", "job"}
    assert {check["name"] for check in checks["check"]} >= {"build", "tests", "design"}
    for check in checks["check"]:
        script = re.search(r"CHECKS_DIR/([\w-]+\.mjs)", check["command"])
        assert script is None or (ROOT / "benchmark/checks" / script[1]).is_file(), check["name"]
