"""The deny hook blocks destructive commands, skipped git hooks and merges on both hosts."""
from __future__ import annotations

import json

DESTROY, HOOKS, MERGE = "destroy work", "the git hooks must run", "only a human merges"
BLOCKED = {
    # The carried-over list, in every spelling of its options.
    "rm -rf build": DESTROY,
    "rm -fr build": DESTROY,
    "rm -r -f build": DESTROY,
    "rm --recursive --force build": DESTROY,
    "rm --force --recursive build": DESTROY,
    "rm -Rf build": DESTROY,
    "sudo /bin/rm -f -R build": DESTROY,
    "find . -name '*.tmp' -exec rm -rf {} +": DESTROY,
    "git reset --hard HEAD~1": DESTROY,
    "git -C web reset --hard": DESTROY,
    "git push --force origin fix/a": DESTROY,
    "git push -f origin fix/a": DESTROY,
    "git push -uf origin fix/a": DESTROY,
    "git push --force-with-lease origin fix/a": DESTROY,
    "git push origin +fix/a": DESTROY,
    "terraform destroy -auto-approve": DESTROY,
    "kubectl delete pod web": DESTROY,
    # Inside another command, a shell script or a substitution.
    "npm test; git push -f": DESTROY,
    "bash -lc 'rm -fr build'": DESTROY,
    'echo "$(git reset --hard)"': DESTROY,
    "echo `rm -fr build`": DESTROY,
    "git commit --no-verify -m 'Fix it'": HOOKS,
    "git push --no-verify origin fix/a": HOOKS,
    "git add -A && git commit -nm 'Fix it'": HOOKS,
    "git -c core.hooksPath=/dev/null push origin HEAD:main": HOOKS,
    "git -c core.hooksPath=/tmp commit -m 'Fix it'": HOOKS,
    "gh pr merge 12 --squash": MERGE,
}
ALLOWED = ["ls -la", "git status", "git commit -m 'Remove the rm -rf step'",
           "git commit -m 'Turn off -n mode'", "git push origin fix/a", "git push -u origin fix/a",
           "git add -f notes.txt", "gh pr view 12", "rm build/old.txt", "rm -r build",
           "grep -rf patterns.txt src", "echo 'git push -f is refused'", "pytest -q"]


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
