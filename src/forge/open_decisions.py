"""Client choices collected from fixed Markdown markers in this checkout."""
from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path
from typing import Any

from forge import records, repo, score

FIELDS = ("Touches", "Why we ask", "Default", "Why this default", "If the default stands", "Due")
MARKER = re.compile(r"^([ \t]*)- Open question:[ \t]*(\S.*?)[ \t]*$")
FIELD = re.compile(r"^[ \t]+(Touches|Why we ask|Default|Why this default|If the default stands|Due):[ \t]*(.*?)[ \t]*$")


def _normal(text: str) -> str:
    return " ".join(text.split())


def _blocks(text: str) -> list[tuple[int, str, list[str]]]:
    # ponytail: skip backtick and tilde fences; no other Markdown parsing.
    lines, fence = [], ""
    for line in text.splitlines():
        found = re.match(r"^[ \t]*(`{3,}|~{3,})(.*)$", line)
        if fence:
            if found and found[1][0] == fence[0] and len(found[1]) >= len(fence) and not found[2].strip():
                fence = ""
            lines.append("")
        elif found:
            fence = found[1]
            lines.append("")
        else:
            lines.append(line)
    starts = [(n, match[2]) for n, line in enumerate(lines) if (match := MARKER.fullmatch(line))]
    return [(n + 1, _normal(question), lines[n + 1:starts[i + 1][0] if i + 1 < len(starts) else len(lines)])
            for i, (n, question) in enumerate(starts)]


def items(top: Path) -> list[dict[str, Any]]:
    """Every open question, its source, fields, scores and missing fields, ranked."""
    screens = records._sections(records._text(top / "docs/design/prototype/SCREENS.md"))
    now = {_normal(name).casefold() for name, body in screens.items()
           if re.search(r"^Build: now[ \t]*$", body, re.M)}
    result = []
    for path in sorted(path for folder in ("docs", "plans") for path in (top / folder).rglob("*.md")):
        for line, question, body in _blocks(path.read_text(encoding="utf-8")):
            fields, scores = {}, None
            for text in body:
                if found := FIELD.fullmatch(text):
                    fields[found[1]] = found[2]
                else:
                    scores = score.parse(text)
                    break
            missing = [name for name in FIELDS if not fields.get(name)]
            if fields.get("Due"):
                try:
                    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", fields["Due"]):
                        raise ValueError
                    date.fromisoformat(fields["Due"])
                except ValueError:
                    missing.append("Due")
            if scores is None:
                missing.append("Gain, Work and Harm")
            result.append(dict(path=path.relative_to(top).as_posix(), line=line, question=question,
                               fields=fields, scores=scores, missing=missing,
                               blocking=_normal(fields.get("Touches", "")).casefold() in now))

    def rank(item: dict[str, Any]) -> tuple:
        if item["missing"]:
            return (len(score.WORDS), item["path"], item["line"])
        gain, work, harm = item["scores"]
        return (list(score.WORDS).index(score.bar(item["scores"])), -harm, -gain, work,
                item["fields"]["Due"], item["path"], item["line"])
    return sorted(result, key=rank)


def blocking(top: Path) -> list[dict[str, Any]]:
    """Complete and incomplete questions that touch a Build now screen."""
    return [item for item in items(top) if item["blocking"]]


def decision_open(args: argparse.Namespace) -> None:
    top = repo.root()
    opened = items(top)
    if not opened:
        print("No open decisions.")
        return
    complete = [item for item in opened if not item["missing"]]
    print(f"{len(complete)} open decisions, highest first:\n")
    prototype = repo.is_prototype(top)
    for number, item in enumerate(complete, 1):
        fields = item["fields"]
        gain, work, harm = item["scores"]
        due = fields["Due"] + (" (passed; the default applies)" if fields["Due"] < repo.now()[:10] else "")
        print(f"{number}. {item['question']}\n"
              f"   Asked in {item['path']}, line {item['line']}. Due {due}. Gain {gain}, Work {work}, Harm {harm}.")
        for name in FIELDS[:-1]:
            print(f"   {name}: {fields[name]}")
        if prototype and item["blocking"]:
            print(f"   Blocks sign-off: {fields['Touches']} is marked Build: now in docs/design/prototype/SCREENS.md.")
        print()
    incomplete = [item for item in opened if item["missing"]]
    if incomplete:
        print("These open questions need every field before they count:")
        for item in incomplete:
            print(f"- {item['path']}, line {item['line']}: {item['question']} needs {', '.join(item['missing'])}.")
        print()
    print('Next: go through the list with the client, then forge decision answer --from <answers file> --by "<name>"')


def due_lines(top: Path) -> list[str]:
    due = [item for item in items(top) if not item["missing"] and item["fields"]["Due"] < repo.now()[:10]]
    if not due:
        return []
    return [f"{len(due)} open decisions passed their due date, so their defaults apply:",
            *(f"- {item['question']}: {item['fields']['Default']} (due {item['fields']['Due']}, {item['path']})" for item in due),
            'Next: forge fix start "Record the defaults of past-due decisions" --done "One decision record holds each default" --kind mechanical',
            "Next: forge decision answer --defaults, then tell the client each default and that a new decision can change it"]


def decision_answer(args: argparse.Namespace) -> None:
    if bool(args.answers) == bool(args.defaults) or (args.answers and args.by is None):
        repo.refuse(('Use --from <file> with --by "<name>", or --defaults.', "forge decision open"))
    slug = "decided-by-default" if args.defaults else "client-answers"
    top = records._start(args, slug)
    by = "decided by default" if args.defaults else records._name(args, "")
    opened = items(top)
    chosen: list[tuple[dict[str, Any], str]] = []
    if args.defaults:
        chosen = [(item, f"{item['fields']['Default']} (decided by default; due {item['fields']['Due']})")
                  for item in opened if not item["missing"] and item["fields"]["Due"] < repo.now()[:10]]
        if not chosen:
            print("No open decision has passed its due date.")
            return
    else:
        try:
            answers = Path(args.answers).read_text(encoding="utf-8")
        except OSError as exc:
            repo.refuse(("Cannot read {file}: {problem}.", "forge decision open"), file=args.answers, problem=str(exc))
        for _, question, body in _blocks(answers):
            item = next((item for item in opened if item["question"] == question), None)
            next_step = 'forge decision answer --from {file} --by "{by}"'
            if item is None:
                repo.refuse(("{file} answers a question that is not open: {question}.",
                             "copy the question from forge decision open, then " + next_step),
                            file=args.answers, question=question, by=by)
            answer = re.search(r"^[ \t]+Answer:[ \t]*(\S.*?)[ \t]*$", "\n".join(body), re.M)
            if not answer:
                repo.refuse(("{file} has no Answer: line for: {question}.", "add its answer, then " + next_step),
                            file=args.answers, question=question, by=by)
            chosen.append((item, answer[1]))
        if not chosen:
            repo.refuse(("{file} has no open-question answers.", "forge decision open"), file=args.answers)
    number = max(records._decision_numbers(top), default=0) + 1
    name = f"{number:04d}-{slug}"
    rel = f"docs/decisions/{name}.md"
    today = repo.now()[:10]
    context = (f"{len(chosen)} open decisions passed their due date with no answer, so their defaults apply."
               if args.defaults else f"{len(chosen)} open decisions were answered by {by} on {today}.")
    text = (f'---\nstatus: accepted\nconfirmed_by: {json.dumps(by, ensure_ascii=False)}\ndate: {today}\n'
            f'stories: []\nsupersedes: ""\n---\n\n# {"Decided by default" if args.defaults else "Client answers"}\n\n'
            f"## Context\n{context}\n\n## Decision\n")
    for item, answer in chosen:
        text += f"- {item['question']}\n  Answer: {answer}\n  Asked in: {item['path']}\n"
        for field in FIELDS[:-1]:
            if item["fields"].get(field):
                text += f"  {'Default was' if field == 'Default' else field}: {item['fields'][field]}\n"
        text += "\n"
    text += ("## Consequences\nEach question is marked answered where it was asked. A new decision that supersedes this one\n"
             "changes an answer.\n")
    questions = {item["question"] for item, _ in chosen}
    sources = sorted({item["path"] for item in opened if item["question"] in questions})
    for path in (rel, *sources):
        if not (top / path).resolve().is_relative_to(top.resolve()):
            repo.refuse(("Cannot record answers: {path} resolves outside this checkout.",
                         "replace the link with a file inside this checkout, then forge decision open"),
                        path=path)
    records._write(top / rel, text)
    for source in sources:
        lines = (top / source).read_text(encoding="utf-8").splitlines(keepends=True)
        for item in opened:
            if item["path"] == source and item["question"] in questions:
                at = item["line"] - 1
                lines[at] = lines[at].replace("- Open question:", f"- {'Decided by default' if args.defaults else 'Answered'} in {name}:", 1)
        records._write(top / source, "".join(lines))
    repo.commit_state(f"Record {len(chosen)} answers from the client", rel, *sources, top=top)
    print(f"Recorded {len(chosen)} answers in {rel} and marked each where it was asked.")
    if args.defaults:
        for item, answer in chosen:
            print(f"Tell the client: {item['question']}: {answer}. A new decision can change it.")


COMMANDS = [
    {"words": "decision open", "run": "decision_open", "changes_state": False,
     "help": "List open decisions, highest first", "args": [], "position": 224,
     "listing": "| `forge decision open` | Lists open decisions, highest first |"},
    {"words": "decision answer", "run": "decision_answer", "changes_state": True,
     "help": "Record client answers or past-due defaults in one decision",
     "args": [(("--from",), {"dest": "answers", "metavar": "FILE"}),
              (("--by",), {"metavar": "NAME"}), (("--defaults",), {"action": "store_true"})],
     "position": 226,
     "listing": '| `forge decision answer --from <file> --by "<name>"` or `forge decision answer --defaults` | Records client answers or past-due defaults and marks each source |'},
]
