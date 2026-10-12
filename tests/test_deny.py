"""The deny hook blocks destructive commands, skipped git hooks and merges on both hosts."""
from __future__ import annotations

import json

DESTROY = '" because it can destroy work that cannot be recovered.'
HOOKS = '" because the git hooks must run on every commit and push.'
MERGE = '" because only a human merges a pull request.'
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
    "uv run pytest -n 2 && git commit -m 'Fix it' -n": HOOKS,
    "bash <<'EOF'\ngit commit -n -m 'Fix it'\nEOF": HOOKS,
    "cat <<'EOF' | bash\ngit commit -n\nEOF": HOOKS,
    "cat <<EOF | bash\ngit commit --no-verify\nEOF": HOOKS,
    "git commit -F - <<EOF\n$(git commit -n)\nEOF": HOOKS,
    "git commit -m --no-verify -n": HOOKS,
    "git commit -m x --no-verify": HOOKS,
    "echo '<<EOF'\ngit commit -n": HOOKS,
    "# don't\necho '<<EOF'\ngit commit -n": HOOKS,
    "echo a#b; git commit -n": HOOKS,
    "echo $((1 << 2))\ngit commit -n\n2": HOOKS,
    "cat <<E\"OF\"\nx\nEOF\ngit commit -n\nE": HOOKS,
    "bash -c \"$(cat <<'EOF'\ngit commit -n\nEOF\n)\"": HOOKS,
    "cat > script.sh <<'EOF'\ngit commit -n\nEOF\nbash script.sh": HOOKS,
    "echo x\\ #note; git commit -n": HOOKS,
    "echo x\\\n#note; git commit -n": HOOKS,
    # An unquoted heredoc message is scanned in full: it fails closed.
    "git commit -F - <<EOF\nProof list: git commit -n --no-verify\nEOF": HOOKS,
    "git commit -F - <<EOF\nFix it\nE\\\nOF\ngit commit -n\nEOF": HOOKS,
    "git -c core.hooksPath=/dev/null push origin HEAD:main": HOOKS,
    "git -c core.hooksPath=/tmp commit -m 'Fix it'": HOOKS,
    "gh pr merge 12 --squash": MERGE,
}
ALLOWED = ["ls -la", "git status", "git commit -m 'Remove the rm -rf step'",
           "git commit -m 'Turn off -n mode'", "git push origin fix/a", "git push -u origin fix/a",
           "git add -f notes.txt", "gh pr view 12", "rm build/old.txt", "rm -r build",
           "grep -rf patterns.txt src", "echo 'git push -f is refused'", "pytest -q",
           # Only git commit's own options count: not another command's, a message, or a heredoc.
           "uv run pytest -n 2 tests/x.py && git commit -m 'Fix it'",
           'uv run pytest -n 2 && git commit -m "-n 2 runs two workers"', "git commit -uno -m x",
           "pytest -n 2 && git commit -F - <<'EOF'\nTests don't need git commit -n\nEOF",
           "git commit -m --no-verify", "git commit --message --no-verify",
           "git commit -F- <<\\EOF\nProof list: git commit -n --no-verify\nEOF",
           "git commit --file - <<\"EOF\"\nNo git commit -n here\nEOF",
           "bash -c true && git commit -F - <<'EOF'\nNo git commit -n here\nEOF",
           "git -C web commit --file=- <<'EOF'\nNo git commit -n here\nEOF",
           "env GIT_EDITOR=: git commit --file=- <<'EOF'\nNo git commit -n here\nEOF"]


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
