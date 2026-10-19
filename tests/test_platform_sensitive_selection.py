"""Platform-sensitive tests cannot silently leave the Windows CI subset."""
import ast
import re
from pathlib import Path

STORY = "FIX-WINDOWS-PLATFORM-SUBSET"


def test_2_platform_sensitive_tests_are_marked():
    # This is a test-policy guard, not a list of today's selected tests. New files,
    # imported platform helpers and OS-specific branches must opt in too.
    areas = re.compile(r"install|hooks?|quot|cmd|paths?|crlf|windows|process|locking|shell|launcher|line_endings|worktree|shim|shlex|fcntl|msvcrt", re.I)
    branches = re.compile(r"sys\.platform|os\.(?:name|linesep|sep)|platform\.(?:system|win32)|sys\.getwindowsversion|\.cmd\b|cmd\.exe|CRLF|crlf|killpg|SIGKILL|flock|msvcrt")
    missing = []
    for path in sorted(Path(__file__).parent.glob("test_*.py")):
        if path == Path(__file__):
            continue
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        tests = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                 and node.name.startswith("test_")]
        # pathlib and generic command-fixture installation are ordinary setup;
        # imports of platform-specific test modules and helpers are a signal.
        imports = " ".join(
            name for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))
            for name in ([node.module or ""] if isinstance(node, ast.ImportFrom)
                         else [alias.name for alias in node.names])
            if name.startswith("test_") or name in {"shlex", "fcntl", "msvcrt"})
        shared = "\n".join(ast.get_source_segment(source, node) or "" for node in tree.body
                            if node not in tests and not isinstance(node, (ast.Import, ast.ImportFrom)))
        whole_file = bool(areas.search(path.stem) or areas.search(imports) or branches.search(shared))
        module_mark = any(isinstance(node, ast.Assign)
                          and any(isinstance(target, ast.Name) and target.id == "pytestmark"
                                  for target in node.targets)
                          and "pytest.mark.platform" in (ast.get_source_segment(source, node) or "")
                          for node in tree.body)
        for node in tests:
            text = (ast.get_source_segment(source, node) or "") + "\n" + "\n".join(
                ast.unparse(mark) for mark in node.decorator_list)
            sensitive = whole_file or areas.search(node.name) or branches.search(text)
            marked = module_mark or any(ast.unparse(mark) == "pytest.mark.platform"
                                        for mark in node.decorator_list)
            if sensitive and not marked:
                missing.append(f"{path.name}::{node.name}")
    assert not missing, "Platform-sensitive tests need @pytest.mark.platform:\n" + "\n".join(missing)
