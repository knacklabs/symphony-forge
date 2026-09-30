STORY = "FORGE-READLOOP-1"
"""The cold read runs in rounds: `forge read` again continues the recorded reader's conversation
with only what changed, starts fresh and says why when it can't, and `forge next` names the round.

Codex readers run the real SDK against the stand-in app-server below, which keeps its
conversations in threads.json beside itself, as Codex keeps them in its home. Claude readers are a
fake `claude` on PATH that keeps each --session-id it starts and refuses to --resume one it doesn't
have. Each says what `<app>-says.md` beside it holds, or `No findings.`.
Each test is named test_<n>_<rule> after the Done-when item of STORY it proves.
"""

import hashlib
import json
import os
import re
import shutil
import sys
from pathlib import Path

import pytest

from conftest import _install
from test_codex_reader import GRILL
from test_codex_worker import _lines, _sent, _toml
from test_codex_worker import sdk_data  # noqa: F401  (a fixture)
from test_phases import _flat
from test_story import DOC, new_story, setup, worktree

CODEX = r'''
import json, os, pathlib, sys

HERE = pathlib.Path(__file__).resolve().parent
STORE, LOG = HERE / "threads.json", HERE / "codex-app-server.jsonl"


def log(**entry):
    with open(LOG, "a", encoding="utf-8") as out:
        out.write(json.dumps(entry) + "\n")


def save(threads):
    (HERE / "threads.tmp").write_text(json.dumps(threads), encoding="utf-8")
    os.replace(HERE / "threads.tmp", STORE)


def send(**message):
    sys.stdout.write(json.dumps(message) + "\n")
    sys.stdout.flush()


def thread(id, saved):
    return {"id": id, "cliVersion": "0.159.2", "createdAt": 0, "updatedAt": 0, "cwd": saved["cwd"],
            "ephemeral": False, "modelProvider": "openai", "preview": "", "sessionId": "stub",
            "source": "appServer", "status": {"type": "idle"}, "turns": []}


def main():
    if sys.argv[1:] == ["--version"]:
        print("codex-cli 0.159.2")
        return
    for line in sys.stdin:
        message = json.loads(line)
        method, params = message.get("method"), message.get("params") or {}
        log(method=method, params=params)
        if method is None or "id" not in message:
            continue
        if method == "initialize":
            send(id=message["id"], result={"userAgent": "codex_app_server/0.159.2",
                                           "serverInfo": {"name": "codex", "version": "0.159.2"}})
            continue
        threads = json.loads(STORE.read_text("utf-8")) if STORE.exists() else {}
        id = params.get("threadId") or f"thr-stub-{len(threads) + 1}"
        saved = threads.setdefault(id, {"cwd": params.get("cwd")}) \
            if method == "thread/start" else threads.get(id)
        if saved is None:
            send(id=message["id"], error={"code": -32600, "message": "no rollout found for " + id})
            continue
        save(threads)
        if method != "turn/start":
            send(id=message["id"], result={
                "approvalPolicy": "never", "approvalsReviewer": "user", "cwd": saved["cwd"],
                "model": "stub-model", "modelProvider": "openai",
                "sandbox": {"type": "readOnly"}, "thread": thread(id, saved)}
                if method in ("thread/start", "thread/resume") else {})
            continue
        turn = f"turn-{id}-{len(_turns(threads)) + 1}"
        send(id=message["id"], result={"turn": {"id": turn, "items": [], "status": "inProgress"}})
        send(method="turn/started", params={"threadId": id, "turn": {
            "id": turn, "items": [], "status": "inProgress"}})
        if os.environ.get("STUB_CODEX_TOUCH"):  # a reader that changes a file
            pathlib.Path(saved["cwd"], os.environ["STUB_CODEX_TOUCH"]).write_text("changed\n")
        says = HERE / "codex-says.md"
        text = says.read_text("utf-8") if says.exists() else "No findings.\n"
        send(method="item/completed", params={"threadId": id, "turnId": turn, "completedAtMs": 2, "item": {
            "type": "agentMessage", "id": "msg-" + turn, "text": text}})
        status = os.environ.get("STUB_CODEX_STATUS", "completed")
        done = {"id": turn, "items": [], "status": status}
        if status == "failed":
            done["error"] = {"message": "stub codex: the model gave up"}
        send(method="turn/completed", params={"threadId": id, "turn": done})


def _turns(threads):
    return [line for line in LOG.read_text("utf-8").splitlines() if '"turn/start"' in line]


main()
'''

CLAUDE = r'''
import io, json, os, pathlib, sys

here = pathlib.Path(__file__).resolve().parent
prompt = io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8").read()
args = sys.argv[1:]
with open(here / "claude-calls.jsonl", "a", encoding="utf-8") as calls:
    calls.write(json.dumps({"args": args, "cwd": os.getcwd(), "prompt": prompt}) + "\n")
store = here / "claude-sessions.json"
sessions = json.loads(store.read_text(encoding="utf-8")) if store.exists() else {}
if "--resume" in args and args[args.index("--resume") + 1] not in sessions:
    print(f"No conversation found with session ID: {args[args.index('--resume') + 1]}",
          file=sys.stderr)
    sys.exit(1)
if "--session-id" in args:
    sessions[args[args.index("--session-id") + 1]] = os.getcwd()
    store.write_text(json.dumps(sessions), encoding="utf-8")
if os.environ.get("STUB_CLAUDE_TOUCH"):  # a reader that changes a file
    pathlib.Path(os.environ["STUB_CLAUDE_TOUCH"]).write_text("changed\n", encoding="utf-8")
if os.environ.get("STUB_CLAUDE_EXIT"):
    print("stub claude: the model gave up", file=sys.stderr)
    sys.exit(int(os.environ["STUB_CLAUDE_EXIT"]))
says = here / "claude-says.md"
sys.stdout.write(says.read_text("utf-8") if says.exists() else "No findings.\n")
'''

FIRST = "Saving needs sign-in first."
SECOND = "The page time has no format."
FRESH = {"codex": "Starting a new Codex conversation, because {}.",
         "claude": "Starting a new Claude session, because {}."}
AMENDED = DOC.replace("2. The basket page says when it was saved.",
                      "2. The basket page says the date it was saved.")


class Reader:
    """A story SHOP read by one app, coordinated from the other."""

    def __init__(self, repo, monkeypatch, app: str):
        self.repo, self.monkeypatch, self.app = repo, monkeypatch, app
        self.shop = worktree(repo, "story/SHOP")
        self.doc, self.notes = self.shop / "plans" / "SHOP.md", self.shop / "plans" / "SHOP.read.md"
        self.log = repo.bin / ("codex-app-server.jsonl" if app == "codex" else "claude-calls.jsonl")
        self.coordinate("claude" if app == "codex" else "codex")

    def coordinate(self, app: str) -> None:
        """Run forge from inside this app, as its commands do."""
        for variable in ("CLAUDECODE", "CODEX_THREAD_ID"):
            self.monkeypatch.delenv(variable, raising=False)
        self.monkeypatch.setenv(*(("CLAUDECODE", "1") if app == "claude" else
                                  ("CODEX_THREAD_ID", "thr-coordinator")))

    def say(self, text: str) -> None:
        (self.repo.bin / f"{self.app}-says.md").write_text(text, encoding="utf-8")

    def read(self):
        return self.repo.forge("read", "SHOP")

    def ok(self, text: str = "No findings.\n") -> str:
        self.say(text)
        done = self.read()
        assert done.returncode == 0, done.stdout + done.stderr
        return done.stdout

    def prompt(self) -> str:
        if self.app == "codex":
            return _sent(self.log, "turn/start")[-1]["input"][0]["text"]
        return json.loads(self.log.read_text("utf-8").splitlines()[-1])["prompt"]

    def calls(self) -> int:
        if self.app == "codex":
            return len(_sent(self.log, "turn/start"))
        return len(self.log.read_text("utf-8").splitlines()) if self.log.exists() else 0

    def continued(self) -> bool:
        """Whether the last round continued the reader's conversation."""
        if self.app == "codex":
            turns = self.repo.path / ".git" / "forge" / "threads" / "read" / "SHOP.log"
            return _lines(turns)[-1]["continued"]
        return "--resume" in json.loads(self.log.read_text("utf-8").splitlines()[-1])["args"]

    def lose(self) -> None:
        """The app forgets every conversation, as when its home is cleared."""
        (self.repo.bin / ("threads.json" if self.app == "codex" else "claude-sessions.json")).unlink()

    def fail(self, on: bool) -> None:
        name, value = (("STUB_CODEX_STATUS", "failed") if self.app == "codex" else
                       ("STUB_CLAUDE_EXIT", "1"))
        self.monkeypatch.setenv(name, value) if on else self.monkeypatch.delenv(name)

    def touch(self, name: str | None) -> None:
        variable = "STUB_CODEX_TOUCH" if self.app == "codex" else "STUB_CLAUDE_TOUCH"
        if name is None:
            self.monkeypatch.delenv(variable)
        else:
            self.monkeypatch.setenv(variable, name if self.app == "codex" else str(self.shop / name))

    def dispose(self, finding: str, disposition: str) -> None:
        text = self.notes.read_text("utf-8")
        line = next(line for line in text.splitlines() if line.endswith(finding))
        self.notes.write_text(text.replace(line, f"{line}\n   Disposition: {disposition}"),
                              encoding="utf-8")

    def text(self) -> str:
        return self.notes.read_text("utf-8")


def _setup(repo, monkeypatch, tmp_path, sdk_data, app: str) -> Reader:  # noqa: F811
    """forge.toml with the grill kind's models for both apps, both apps installed (the Codex SDK
    and the stand-ins), and the story SHOP with its doc written."""
    setup(repo)
    version = repo.forge("--version").stdout.split()[-1]
    repo.write("forge.toml", _toml(version, "claude", GRILL))
    repo.git("commit", "-q", "-am", "Grill on both apps")
    repo.git("push", "-q", "origin", "main")
    _install(repo.bin, "claude", f"#!{sys.executable}\n{CLAUDE}")
    _install(repo.bin, "codex-app-server", f"#!{sys.executable}\n{CODEX}")
    program = repo.bin / ("codex-app-server.cmd" if os.name == "nt" else "codex-app-server")
    monkeypatch.setenv("CODEX_BIN", str(program))
    monkeypatch.setenv("XDG_DATA_HOME", str(sdk_data))
    (tmp_path / "codex-home").mkdir()
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex-home"))
    monkeypatch.setenv("FORGE_NOW", "2026-09-29T10:00:00+00:00")
    new_story(repo, "SHOP")
    reader = Reader(repo, monkeypatch, app)
    reader.doc.write_text(DOC, encoding="utf-8")
    return reader


def _no_codex(monkeypatch, tmp_path) -> None:
    """Codex isn't installed: Forge finds no Codex SDK."""
    (tmp_path / "no-codex").mkdir()
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "no-codex"))


def _no_claude(repo, monkeypatch, tmp_path) -> None:
    """Claude Code isn't installed: no `claude` anywhere on PATH, git still there."""
    for name in ("claude", "claude.cmd"):
        (repo.bin / name).unlink(missing_ok=True)
    git = shutil.which("git")
    kept = [folder for folder in os.environ["PATH"].split(os.pathsep)
            if not any((Path(folder) / name).exists() for name in ("claude", "claude.exe", "claude.cmd"))]
    if git and Path(git).parent.as_posix() not in {Path(folder).as_posix() for folder in kept}:
        tools = tmp_path / "tools"  # git shared a folder with claude: bring git alone
        tools.mkdir()
        (tools / Path(git).name).symlink_to(git)
        kept.append(str(tools))
    monkeypatch.setenv("PATH", os.pathsep.join(kept))
    assert shutil.which("claude") is None and shutil.which("git")


def _continues(repo, monkeypatch, tmp_path, sdk_data, app):  # noqa: F811
    reader = _setup(repo, monkeypatch, tmp_path, sdk_data, app)
    first = reader.ok(f"1. {FIRST}\n2. {SECOND}\n")
    assert first.endswith("Next: give every finding a disposition, amend the doc, then forge read SHOP\n")
    notes = reader.text()
    for fact in ("round: 1\n", "passed: no\n", f"## Round 1\n\n1. {FIRST}\n2. {SECOND}\n"):
        assert fact in notes, notes
    assert not _sent(reader.log, "thread/archive")  # a round with findings keeps its conversation

    # forge next names the round, and a round waits for every disposition.
    assert repo.forge("next").stdout.splitlines()[-2:] == [
        "Planning Shoppers can save a basket: round 1 of its cold read had findings, so round 2 is "
        "next.",
        "Next: give finding 1 in plans/SHOP.read.md a disposition, then forge read SHOP"]
    calls = reader.calls()
    refused = reader.read()
    assert (refused.returncode, refused.stderr) == (1, (
        "Finding 1 in plans/SHOP.read.md has no disposition: cut, defer, or keep with a reason.\n"
        "Next: edit plans/SHOP.read.md, then forge next\n"))
    assert reader.calls() == calls and reader.text() == notes

    # Between rounds: dispositions, a doc edit, a trap learned on the default branch after the
    # story branch was made, and a changed answers page.
    reader.dispose(FIRST, "keep because shoppers asked for it")
    reader.dispose(SECOND, "cut")
    reader.doc.write_text(AMENDED, encoding="utf-8")
    repo.write("AGENTS.md", "# Agents\n\n## Known traps\n\n- Fixture paths break on Windows.\n")
    repo.git("add", "AGENTS.md")
    repo.git("commit", "-q", "-m", "Learn a trap")
    repo.git("push", "-q", "origin", "main")
    brief = reader.shop / "docs" / "product" / "BRIEF.md"
    brief.parent.mkdir(parents=True)
    brief.write_text("# Brief\n\n## Answers\n\n- Hosting: the client's own servers\n", encoding="utf-8")

    # The reader restarts its numbering at 1; Forge numbers it after round 1's findings.
    reader.ok("1. Disputed keep 1: shoppers without an account lose baskets too.\n")
    assert reader.continued()
    prompt = reader.prompt()
    flat = _flat(prompt)
    assert "Round 2 of your cold read of `plans/SHOP.md`" in prompt
    assert ("-2. The basket page says when it was saved.\n"
            "+2. The basket page says the date it was saved.") in prompt
    assert (f"1. {FIRST}\n   Disposition: keep because shoppers asked for it\n"
            f"2. {SECOND}\n   Disposition: cut") in prompt
    assert "a numbered list starting at 3" in flat
    assert "- Fixture paths break on Windows." in prompt
    assert "Re-read the `## Answers` section of `docs/product/BRIEF.md` from the checkout" in flat
    # Never the first round's instructions, the whole doc or what the reader re-reads itself.
    for resent in ("You are doing the one cold read", "Shoppers can save a basket and come back",
                   "the client's own servers"):
        assert resent not in prompt, resent
    notes = reader.text()
    assert "round: 2\n" in notes and "## Round 2\n\n3. Disputed keep 1:" in notes
    assert f"## Round 1\n\n1. {FIRST}\n   Disposition: keep because" in notes

    # The human settles the dispute; the kept finding and the dispute both cite the decision.
    decided = "Decided: sign-in first: saving needs an account (owner, 2026-09-29)"
    reader.doc.write_text(AMENDED + f"\n{decided}\n", encoding="utf-8")
    text = reader.text().replace("keep because shoppers asked for it", f"keep per {decided}")
    reader.notes.write_text(text, encoding="utf-8")
    reader.dispose("lose baskets too.", f"keep per {decided}")
    reader.ok()
    assert reader.continued()
    prompt = reader.prompt()
    assert "Round 3 of your cold read" in prompt and f"+{decided}" in prompt
    # The last round's findings, and the older one whose disposition changed; not the unchanged one.
    assert f"3. Disputed keep 1: shoppers without an account lose baskets too.\n   Disposition: keep per {decided}" in prompt
    assert f"1. {FIRST}\n   Disposition: keep per {decided}" in prompt
    assert SECOND not in prompt
    assert "a numbered list starting at 4" in _flat(prompt)

    # Only exactly "No findings." passes; the conversation is archived once it does.
    notes = reader.text()
    assert "round: 3\n" in notes and "passed: yes\n" in notes and "## Round 3\n\nNo findings.\n" in notes
    if app == "codex":
        assert [call["threadId"] for call in _sent(reader.log, "thread/archive")] == ["thr-stub-1"]
    assert "Next: in Claude Code, show plans/SHOP.md in Plan Mode" in repo.forge("next").stdout


def _starts_fresh(repo, monkeypatch, tmp_path, sdk_data, app):  # noqa: F811
    reader = _setup(repo, monkeypatch, tmp_path, sdk_data, app)
    reader.ok(f"1. {FIRST}\n")
    reader.dispose(FIRST, "keep because shoppers asked for it")
    notes = reader.text()

    def fresh(why: str, says: str = "No findings.\n") -> str:
        """A round that starts a new conversation with the first round's instructions, the whole
        doc and every earlier finding with its disposition, and says why."""
        out = reader.ok(says)
        assert FRESH[app].format(why) in out, out
        assert not reader.continued()
        prompt = reader.prompt()
        for sent in ("You are doing the one cold read", "Shoppers can save a basket and come back",
                     "Disposition: keep because shoppers asked for it"):
            assert sent in prompt, sent
        return prompt

    # A failed round records nothing and drops its conversation, so the retry starts fresh.
    reader.fail(True)
    calls = reader.calls()
    failed = reader.read()
    # Only a conversation the app no longer has starts fresh in the same run; this failure doesn't.
    assert reader.calls() == calls + 1
    problem = ("Codex reported the turn failed." if app == "codex" else "stub claude: the model gave up")
    assert (failed.returncode, failed.stderr) == (1, f"The cold read of plans/SHOP.md failed: {problem}\n"
                                                     "Next: forge read SHOP\n")
    assert reader.text() == notes
    reader.fail(False)
    no_record = ("Forge has no record of its conversation on this machine" if app == "codex" else
                 "Forge has no record of its Claude session on this machine")
    # A reply with no numbered finding becomes one, numbered after the earlier rounds'.
    prompt = fresh(no_record, "The totals are unclear.\n")
    assert "Round 2 of your cold read" in prompt and "a numbered list starting at 2" in _flat(prompt)
    assert "## Round 2\n\n2. The totals are unclear.\n" in reader.text()
    assert "passed: no" in reader.text()
    refused = reader.read()
    assert refused.stderr.startswith("Finding 2 in plans/SHOP.read.md has no disposition")
    reader.dispose("The totals are unclear.", "cut")

    # A discarded round too.
    notes = reader.text()
    reader.touch("scratch.txt")
    discarded = reader.read()
    assert discarded.stderr == ("A file changed during the cold read of plans/SHOP.md, so the read "
                                "was discarded.\nNext: git status, then forge read SHOP\n")
    assert reader.text() == notes
    reader.touch(None)
    (reader.shop / "scratch.txt").unlink()
    fresh(no_record, "1. Nothing saves offline.\n")
    assert "## Round 3\n\n3. Nothing saves offline.\n" in reader.text()
    reader.dispose("Nothing saves offline.", "cut")

    # The app lost the conversation.
    session = (json.loads((repo.path / ".git" / "forge" / "threads" / "read" / "SHOP.json")
                         .read_text("utf-8")).get("claude") or {}).get("id")
    reader.lose()
    fresh("Codex couldn't resume its conversation: no rollout found for thr-stub-3" if app == "codex"
          else f"Claude couldn't continue session {session}", "4. Totals need tax.\n")
    reader.dispose("Totals need tax.", "cut")

    # Notes written before rounds: no round number and no copy of what was read. That is round 1,
    # and the next round starts fresh with no diff.
    old = re.sub(r"^(round|passed|doc_seen|spec_seen|notes_seen):.*\n", "", reader.text(), flags=re.M)
    reader.notes.write_text(re.sub(r"^## Round \d+\n\n", "", old, flags=re.M), encoding="utf-8")
    prompt = fresh("Forge has no copy of what its last round read")
    assert "Round 2 of your cold read" in prompt and "(not available)" in prompt
    assert "a numbered list starting at 5" in _flat(prompt)
    assert "round: 2\n" in reader.text() and "## Round 2\n\nNo findings.\n" in reader.text()


def _stays_pinned(repo, monkeypatch, tmp_path, sdk_data, app):  # noqa: F811
    reader = _setup(repo, monkeypatch, tmp_path, sdk_data, "claude")
    reader.ok(f"1. {FIRST}\n")
    assert "reader: claude (opus)\n" in reader.text()
    reader.dispose(FIRST, "cut")

    # Started from the app that is itself the reader, while the other app is installed: refused.
    notes = reader.text()
    reader.coordinate("claude")
    refused = reader.read()
    assert (refused.returncode, refused.stderr) == (1, (
        "Claude Code is the cold reader of plans/SHOP.md, so its next round can't start from "
        "Claude Code.\nNext: run forge read SHOP from Codex\n"))
    assert reader.text() == notes and not (repo.bin / "codex-app-server.jsonl").exists()

    # The recorded reader's app is gone: from that same app, the round is no longer refused but
    # starts fresh on the reader Forge picks now, says so, and records it.
    _no_claude(repo, monkeypatch, tmp_path)
    moved = repo.forge("read", "SHOP")
    assert moved.returncode == 0, moved.stdout + moved.stderr
    assert FRESH["codex"].format("its reader, Claude Code, is no longer installed") in moved.stdout
    assert "reader: codex (gpt-6-sol)\n" in reader.text()
    turn = _sent(repo.bin / "codex-app-server.jsonl", "turn/start")[-1]["input"][0]["text"]
    assert "Round 2 of your cold read" in turn and "You are doing the one cold read" in turn


def _wrong_app(repo, monkeypatch, tmp_path, sdk_data, app):  # noqa: F811
    reader = _setup(repo, monkeypatch, tmp_path, sdk_data, "codex")
    reader.ok(f"1. {FIRST}\n")
    assert "reader: codex (gpt-6-sol)\n" in reader.text()
    reader.dispose(FIRST, "cut")
    reader.coordinate("codex")
    refused = reader.read()
    assert refused.stderr == ("Codex is the cold reader of plans/SHOP.md, so its next round can't "
                              "start from Codex.\nNext: run forge read SHOP from Claude Code\n")


def _one_app(repo, monkeypatch, tmp_path, sdk_data, app):  # noqa: F811
    # Only Claude Code: under Claude Code, a separate Claude conversation reads, and continues.
    reader = _setup(repo, monkeypatch, tmp_path, sdk_data, "claude")
    reader.coordinate("claude")
    _no_codex(monkeypatch, tmp_path)
    reader.ok(f"1. {FIRST}\n")
    assert ("reader: claude (opus), a separate Claude Code conversation because Codex isn't "
            "installed\n") in reader.text()
    reader.dispose(FIRST, "cut")
    reader.ok()
    assert reader.continued() and "Round 2 of your cold read" in reader.prompt()

    # Only Codex: under Codex, a separate Codex conversation reads.
    monkeypatch.setenv("XDG_DATA_HOME", str(sdk_data))
    _no_claude(repo, monkeypatch, tmp_path)
    codex = Reader(repo, monkeypatch, "codex")
    codex.coordinate("codex")
    codex.notes.unlink()
    codex.ok(f"1. {FIRST}\n")
    assert ("reader: codex (gpt-6-sol), a separate Codex conversation because Claude Code isn't "
            "installed\n") in codex.text()
    codex.dispose(FIRST, "cut")
    codex.ok()
    assert codex.continued() and "Round 2 of your cold read" in codex.prompt()


def _spec_diff(repo, monkeypatch, tmp_path, sdk_data, app):  # noqa: F811
    setup(repo)
    _install(repo.bin, "claude", f"#!{sys.executable}\n{CLAUDE}")
    assert repo.forge("fix", "start", "Recover the saved basket", "--done",
                      "Saved baskets return").returncode == 0
    fix = worktree(repo, "fix/recover-the-saved-basket")

    def confirm(why: str) -> None:
        body = f"# Basket spec\n\n## Why\n\n{why}\n\n## Roadmap\n\n- BASKET: Recover baskets\n"
        digest = hashlib.sha256(body.encode()).hexdigest()
        path = fix / "docs" / "specs" / "baskets.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f'---\nstatus: confirmed\nconfirmed_hash: "{digest}"\n---\n{body}',
                        encoding="utf-8")
        repo.git("add", "-A", cwd=fix)
        repo.git("commit", "-q", "-m", "Confirm the basket spec", cwd=fix)

    confirm("A saved basket gets lost.")
    assert repo.forge("story", "new", "BASKET", "Recover baskets", "--from-fix",
                      "recover-the-saved-basket").returncode == 0
    story = worktree(repo, "story/BASKET")
    (story / "plans" / "BASKET.md").write_text(DOC, encoding="utf-8")
    calls, notes = repo.bin / "claude-calls.jsonl", story / "plans" / "BASKET.read.md"
    (repo.bin / "claude-says.md").write_text(f"1. {FIRST}\n", encoding="utf-8")
    assert repo.forge("read", "BASKET").returncode == 0

    def next_round(finding: str) -> str:
        text = notes.read_text("utf-8")
        notes.write_text(text.replace(finding, f"{finding}\n   Disposition: cut"), encoding="utf-8")
        read = repo.forge("read", "BASKET")
        assert read.returncode == 0, read.stdout + read.stderr
        return json.loads(calls.read_text("utf-8").splitlines()[-1])["prompt"]

    confirm("A saved basket gets lost, and shoppers leave.")
    (repo.bin / "claude-says.md").write_text("2. Leaving is not measured.\n", encoding="utf-8")
    prompt = next_round(FIRST)
    assert "-A saved basket gets lost.\n+A saved basket gets lost, and shoppers leave." in prompt
    assert "- BASKET: Recover baskets" not in prompt  # the diff, not the whole spec
    # Unchanged since the last round: an empty spec diff.
    (repo.bin / "claude-says.md").write_text("No findings.\n", encoding="utf-8")
    prompt = next_round("Leaving is not measured.")
    assert "empty when it is unchanged:\n\n\n\nWhen that diff" in prompt


@pytest.mark.parametrize("walk, app", [
    (_continues, "codex"), (_continues, "claude"), (_starts_fresh, "codex"),
    (_starts_fresh, "claude"), (_stays_pinned, "claude"), (_wrong_app, "codex"),
    (_one_app, "both"), (_spec_diff, "claude")], ids=lambda value: getattr(value, "__name__", value))
def test_1_the_same_reader_reads_again(repo, monkeypatch, tmp_path, sdk_data, walk, app):  # noqa: F811
    walk(repo, monkeypatch, tmp_path, sdk_data, app)


def test_6_forge_next_nudges_a_read_that_doesnt_converge(repo, monkeypatch, tmp_path, sdk_data):  # noqa: F811
    reader = _setup(repo, monkeypatch, tmp_path, sdk_data, "claude")
    for number in range(1, 4):
        reader.ok(f"{number}. Gap number {number}.\n")
        reader.dispose(f"Gap number {number}.", "cut")
        said = repo.forge("next").stdout.splitlines()[-2:]
        assert said[0].startswith(f"Planning Shoppers can save a basket: round {number} of its "
                                  f"cold read had findings, so round {number + 1} is next.")
        assert said[1] == "Next: forge read SHOP"
        nudged = said[0].endswith(" It isn't converging: ask the human whether to split the story "
                                  "instead of reading on.")
        assert nudged == (number + 1 >= 4)
    reader.ok()
    assert "Next: in Claude Code, show plans/SHOP.md in Plan Mode" in repo.forge("next").stdout
