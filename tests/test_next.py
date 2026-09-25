"""`forge next` and the session-start context hook: human touches per item (spec criterion 15)."""
from __future__ import annotations

import json

from test_story import claude_plan, hook, ready, setup


def test_15_human_touches(repo, claude_payload, codex_payload):
    setup(repo)
    shop = ready(repo, "SHOP")
    question = {"questions": [{"question": "Which colour?", "options": [{"label": "Blue"}]}]}

    def ask(cwd, response=None):
        response = response or {"answers": {"Which colour?": "Blue"}}
        assert hook(repo, claude_payload("PostToolUse", "AskUserQuestion", question, response,
                                         cwd=cwd)).returncode == 0

    # In the story's worktree, an answered question and the approval each add one; a question
    # that failed, or whose response has no answer, adds none.
    ask(shop)
    for unanswered in ({"is_error": True}, {"answers": {}}, {"status": "success"}):
        ask(shop, unanswered)
    assert hook(repo, claude_payload("PostToolUse", "AskUserQuestion", question,
                                     cwd=shop)).returncode == 0  # no tool_response at all
    assert hook(repo, claude_plan(claude_payload, (shop / "plans" / "SHOP.md").read_text("utf-8"),
                                  cwd=shop)).returncode == 0

    # On the default branch a question counts for nothing and changes nothing; forge doctor's
    # sample payloads record nothing either.
    main = repo.git("rev-parse", "HEAD")
    ask(repo.path)
    assert hook(repo, claude_payload("PostToolUse", "forge-doctor")).returncode == 0
    assert repo.git("rev-parse", "HEAD") == main and repo.git("status", "--porcelain") == ""

    # In a task's and a fix's worktree, a question counts for that task or fix.
    # ponytail: WORK's `task start` and `fix start` aren't in this branch; these stand in for them.
    task = repo.path.parent / "repo-task-SHOP-SAVE"
    repo.git("worktree", "add", "-q", "-b", "task/SHOP-SAVE", str(task), "story/SHOP")
    (task / ".factory" / "stories" / "SHOP" / "tasks").mkdir(parents=True)
    (task / ".factory" / "stories" / "SHOP" / "tasks" / "SAVE.json").write_text(
        json.dumps({"status": "working"}), encoding="utf-8")
    ask(task)
    fix = repo.path.parent / "repo-fix-tidy-up"
    repo.git("worktree", "add", "-q", "-b", "fix/tidy-up", str(fix), "main")
    (fix / ".factory" / "fixes").mkdir(parents=True)
    (fix / ".factory" / "fixes" / "tidy-up.json").write_text(
        json.dumps({"why": "Tidy up", "done_when": "It is tidy"}), encoding="utf-8")
    asked = codex_payload("PostToolUse", "request_user_input",
                          {"questions": [{"id": "colour", "question": "Which colour?"}]},
                          {"answers": {"colour": {"answers": ["Blue"]}}}, cwd=fix)
    assert hook(repo, asked).returncode == 0

    context = repo.forge("hook", "context",
                         input=json.dumps(claude_payload("SessionStart")))
    assert context.returncode == 0, context.stderr
    assert "Shoppers can save a basket (approved): 3 human touches so far." in context.stdout
    assert "The fix tidy-up (started): 1 human touch so far." in context.stdout
    assert "A worker is building SHOP/SAVE." in context.stdout
    assert context.stdout.startswith(repo.forge("next").stdout.strip())
