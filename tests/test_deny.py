"""The deny hook blocks destructive commands, skipped git hooks and merges on both hosts."""
from __future__ import annotations

import json

BLOCKED = {
    "rm -rf build": "destroy work",
    "git reset --hard HEAD~1": "destroy work",
    "git push --force origin fix/a": "destroy work",
    "terraform destroy -auto-approve": "destroy work",
    "kubectl delete pod web": "destroy work",
    "git commit --no-verify -m 'Fix it'": "the git hooks must run",
    "git push --no-verify origin fix/a": "the git hooks must run",
    "git add -A && git commit -nm 'Fix it'": "the git hooks must run",
    "gh pr merge 12 --squash": "only a human merges",
}
ALLOWED = ["ls -la", "git status", "git commit -m 'Remove the old page'", "git push origin fix/a",
           "gh pr view 12", "rm build/old.txt", "pytest -q"]


def test_23_deny_hook(repo, claude_payload, codex_payload):
    for build in (claude_payload, codex_payload):
        for command, reason in BLOCKED.items():
            payload = build("PreToolUse", "Bash", {"command": command})
            blocked = repo.forge("hook", "deny", input=json.dumps(payload))
            assert blocked.returncode == 2, command
            assert blocked.stderr.startswith('Forge blocks "') and reason in blocked.stderr, command
            assert "\nNext: " in blocked.stderr
        for command in ALLOWED:
            allowed = repo.forge("hook", "deny", input=json.dumps(build("PreToolUse", "Bash",
                                                                        {"command": command})))
            assert (allowed.returncode, allowed.stdout, allowed.stderr) == (0, "", ""), command

    unreadable = repo.forge("hook", "deny", input="not json")
    assert unreadable.returncode == 2
    assert unreadable.stderr == ("The hook input is not a JSON object, so Forge cannot check the "
                                 "command.\nNext: forge doctor\n")
