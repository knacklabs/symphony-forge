"""Ask Codex one read-only question in the current checkout."""
from __future__ import annotations

import argparse

from forge import codex, repo, story

REFUSALS = {
    "empty": ("The question is empty.", 'forge ask "<question>"'),
    "sdk": ("{problem}", "forge doctor --fix"),
    "discarded": ("A file changed while Codex answered, so its answer was discarded.",
                  'git status, then forge ask "<question>"'),
    "failed": ("Codex did not complete the answer.", 'forge ask "<question>"'),
}


def ask(args: argparse.Namespace) -> None:
    question = args.question
    if not question.strip():
        repo.refuse(REFUSALS["empty"])
    top = repo.root()
    problem = codex.sdk_problem()
    if problem:
        repo.refuse(REFUSALS["sdk"], problem=problem)
    codex.settings(repo.config(top), "Ask")
    prompt = ("Answer this question about the code in this checkout. Read files as needed. "
              "Do not change any file.\n\n" + question)
    before = story._snapshot(top)
    with codex.hold(top, "ask", "Ask"):
        result = codex.run(top, "ask", "Ask", "Ask · this checkout", prompt, "read-only",
                           echo=False, model=args.model, effort=args.effort)
    if story._snapshot(top) != before:
        repo.refuse(REFUSALS["discarded"])
    if result["status"] != "completed" or not (result["text"] or "").strip():
        repo.refuse(REFUSALS["failed"])
    print(result["text"].strip())


COMMANDS = [{
    "words": "ask", "run": "ask", "changes_state": False,
    "help": "Ask Codex a read-only question about this checkout",
    "args": [(('question',), {}),
             (('--model',), {"metavar": "MODEL", "help": "Codex model for this answer"}),
             (('--effort',), {"metavar": "EFFORT", "help": "reasoning effort for this answer"})],
    "position": 140,
    "listing": '| `forge ask "<question>"` | Asks Codex a read-only question about the code without starting a fix (`--model` and `--effort` override `[models.lite]`) |',
}]
