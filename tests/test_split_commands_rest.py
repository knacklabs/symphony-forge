"""The remaining commands keep their CLI contract when their owners declare them."""
import ast
from pathlib import Path

from test_split_commands import commands_keep_their_help_and_discover_a_new_owner

STORY = "FORGE-SPLIT-1"
SOURCE = Path(__file__).resolve().parents[1] / "src" / "forge"

OWNERS = {
    "approval": {"hook approval"},
    "ask": {"ask"},
    "close": {"close"},
    "deny": {"hook deny"},
    "githooks": {"hook pre-commit", "hook pre-push"},
    "merge": {"merge"},
    "payback": {"spec payback"},
    "prcheck": {"hook pr-check"},
    "records": {"spec save", "spec confirm", "spec measure", "decision new",
                "decision accept", "roadmap add"},
    "story": {"story new", "story done", "read"},
    "task": {"task start", "fix start", "fix allow-large", "fix amend"},
    "worker": {"work"},
}


def _assignments(module):
    tree = ast.parse((SOURCE / f"{module}.py").read_text(encoding="utf-8"))
    return {target.id: node.value for node in tree.body if isinstance(node, ast.Assign)
            for target in node.targets if isinstance(target, ast.Name)}


def test_2_remaining_commands_are_owned_and_keep_their_help(repo, tmp_path, monkeypatch):
    assert "TABLE" not in _assignments("cli")
    for module, words in OWNERS.items():
        declarations = _assignments(module)["COMMANDS"]
        actual = {next(value.value for key, value in zip(item.keys, item.values)
                       if key.value == "words") for item in declarations.elts}
        assert actual == words
        for command in words:
            result = repo.forge(*command.split(), "--help")
            assert result.returncode == 0, (command, result.stderr)
            assert result.stdout.startswith(f"usage: forge {command} ")
    # The existing golden help and new-module checks remain the criterion's CLI proof.
    commands_keep_their_help_and_discover_a_new_owner(repo, tmp_path, monkeypatch)
