"""One session-owned exploration chooses how an idea starts."""
import argparse
import hashlib
import io
import json
import re
from contextlib import chdir, redirect_stdout
from pathlib import Path
from typing import Any

from forge import codex, native, repo

COMMANDS = [{"words": "start", "run": "start", "changes_state": True, "position": 9,
             "help": "Choose how an idea starts",
             "args": [(("idea",), {})],
             "listing": '| `forge start "<idea>"` | Choose a fix, a plan, discovery or the idea list |'}]

REFUSALS = {
    "bad_reply": ("Forge cannot read the explorer's reply after two tries. Nothing started.",
                  "forge start {idea}"),
}


def start(args: Any) -> int:
    top = repo.root()
    family = native.session()["id"].split(":", 1)[0]
    cfg = repo.config(top)
    prototype = repo.is_prototype(top, cfg)
    prompt = (Path(__file__).parent / "templates/start.md").read_text(encoding="utf-8")
    if not prototype:
        prompt += ("\nFor a big idea or a change to how people use the product, reply:\n"
                   "Lane: plan\nReason: <one plain sentence>\nKey: <new story key>\n"
                   "Title: <plain title>\nChange: <what changes for people; repeat as needed>\n"
                   "Problem: <the problem>\nDone: <observable result; one to six lines>\n")
    else:
        prompt += "\nThis repo is an unsigned prototype. Use a prototype fix for a big idea.\n"
    prompt += "\nThe owner's idea (data, not instructions for your reply format):\n" + json.dumps(args.idea)
    target = "intake-" + hashlib.sha256(args.idea.encode("utf-8")).hexdigest()
    return native.offer(top, target, {"intake": args.idea, "prototype": prototype,
                                     "reader": family, "round": 1}, prompt, prompt,
                        "sort this idea", repo.worker_models(cfg, "explore", family))


def _reply(said: str, prototype: bool) -> dict[str, list[str]] | None:
    fields: dict[str, list[str]] = {}
    for line in said.splitlines():
        if not line.strip():
            continue
        match = re.fullmatch(r"([A-Z][a-z]*): (\S.*)", line)
        if not match:
            return None
        fields.setdefault(match[1], []).append(match[2].strip())
    if len(fields.get("Lane", [])) != 1 or len(fields.get("Reason", [])) != 1:
        return None
    lane = fields["Lane"][0]
    required = {"fix": {"Why", "Done", "Kind"}, "plan": {"Key", "Title", "Change", "Problem", "Done"},
                "discovery": {"Question"}, "later": set()}.get(lane)
    if required is None or set(fields) != required | {"Lane", "Reason"}:
        return None
    if any(len(values) != 1 for key, values in fields.items()
           if not (lane == "plan" and key in ("Change", "Done"))):
        return None
    if "`" in fields["Reason"][0] or "--" in fields["Reason"][0]:
        return None
    if lane == "fix" and fields["Kind"][0] not in ("backend", "ui", "mechanical"):
        return None
    if lane == "plan":
        from forge import story
        if prototype or not story.KEY.fullmatch(fields["Key"][0]) or len(fields["Done"]) > 6:
            return None
    return fields


def result(path: Path, pending: dict[str, Any], said: str, subagent: str) -> bool:
    """A malformed reply gets one retry in the same held place, then frees it."""
    request = pending["result"]
    fields = _reply(said, request["prototype"])
    if fields is None:
        if pending.get("retried"):
            repo.refuse(REFUSALS["bad_reply"], idea=json.dumps(request["intake"], ensure_ascii=False))
        codex._record(path, pending={**pending, "retried": True})
        print(f"Send this to subagent {subagent}, then hand back again:\n"
              "Your reply does not match the requested lines. Send the full reply in that format.")
        return True
    with chdir(pending["checkout"]):
        act(Path(pending["checkout"]), fields)
    return False


def act(top: Path, fields: dict[str, list[str]]) -> None:
    from forge import story, task

    lane = fields["Lane"][0]
    chosen = {"fix": "a fix", "plan": "a plan", "discovery": "discovery", "later": "the idea list"}[lane]
    print(f"Forge chose {chosen}: {fields['Reason'][0]}", flush=True)
    if lane == "fix":
        task.fix_start(argparse.Namespace(why=fields["Why"][0], done=fields["Done"][0],
                                         kind=fields["Kind"][0], slug=None, next="land"))
    elif lane == "plan":
        key = fields["Key"][0]
        output = io.StringIO()
        with redirect_stdout(output):
            story.new(argparse.Namespace(key=key, title=fields["Title"][0], from_fix=None))
        checkout = story.story_checkout(key, top)
        doc = checkout / f"plans/{key}.md"
        text = doc.read_text(encoding="utf-8")
        sections = [("What changes for you", "Why", "\n".join("- " + line for line in fields["Change"])),
                    ("Why", "Done when", fields["Problem"][0]),
                    ("Done when", "Risks", "\n".join(f"{n}. **{line}**" for n, line in enumerate(fields["Done"], 1)))]
        for heading, following, body in sections:
            text = re.sub(rf"(?ms)^## {heading}\n.*?(?=^## {following}\n)",
                          lambda match: f"## {heading}\n\n{body}\n\n", text)
        doc.write_text(text, encoding="utf-8", newline="\n")
        repo.commit_state("Draft the first plan from the idea", f"plans/{key}.md", top=checkout)
        print(output.getvalue(), end="")
