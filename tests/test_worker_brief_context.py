"""A resumed worker gets the full completion target and grep map for changed functions."""
from __future__ import annotations

from pathlib import Path

import pytest

from test_fix_claude_workers_start_a_fresh_session_eve import _started
from test_worker import calls

STORY = "FIX-FULL-BRIEF-AND-PROOF"
FIX = "fix-the-login-typo"
DONE = "The login page says Log in"


@pytest.mark.parametrize("source, caller, test, original, function, unchanged, removed", [
    ("validator.py", "service.py", "tests/test_verify_credentials.py",
     "def verify_credentials():\n    return False\n", "verify_credentials", "", ""),
    ("validator.ts", "service.ts", "tests/credentials.spec.ts",
     "export const verify_credentials = (): boolean => {\n    return false;\n};\n",
     "verify_credentials", "", ""),
    ("src/testimonials/controller.ts", "src/api.ts", "tests/test_testimonials.py",
     "export class TestimonialsController {\n"
     "  createTestimonial(\n    input: unknown,\n  ): boolean {\n"
     "    return false;\n  }\n}\n", "createTestimonial", "", ""),
    ("auth/service.py", "auth/routes.py", "tests/test_auth_service.py",
     "class AuthService:\n"
     "    def authenticate(self):\n        return False\n\n"
     "    def unchanged_archive_sessions(self):\n        return True\n",
     "authenticate", "unchanged_archive_sessions", ""),
    ("projects/projects.controller.ts", "projects/projects.service.ts",
     "tests/projects.controller.spec.ts",
     "export class ProjectsController {\n"
     "  create(\n    input: unknown,\n  ): boolean {\n"
     "    this.audit(input);\n    return false;\n  }\n\n"
     "  unchanged(): boolean {\n    return true;\n  }\n}\n",
     "create", "unchanged", "this.audit(input);"),
], ids=["python-function", "typed-typescript-arrow", "multiline-typescript-method",
        "changed-method-with-unchanged-sibling", "deleted-line-in-multiline-method"])
def test_2_worker_round_brief_shows_done_when_and_changed_function_context(
        repo, source, caller, test, original, function, unchanged, removed):
    # The grep map must work for both Python and the typed TypeScript client stack.
    repo.write(source, original)
    repo.write(caller, f"service.{function}()\n")
    repo.write(test, f"service.{function}()\n")
    repo.git("add", source, caller, test)
    repo.git("commit", "-q", "-m", "Seed the sign-in check",
             "-m", "Proof list:\n- Sign-in check: manual check passed")
    repo.git("push", "-q", "origin", "main")

    log = _started(repo)
    first = repo.forge("work", FIX)
    assert first.returncode == 0, first.stdout + first.stderr
    folder = Path(calls(log)[-1]["cwd"])

    # The body-only edit must resolve to this function's caller and test.
    if removed:
        changed = original.replace(f"    {removed}\n", "")
    else:
        changed = original.replace("False", "True").replace("false", "true")
    (folder / source).write_text(changed, encoding="utf-8")
    repo.git("add", source, cwd=folder)
    repo.git("commit", "-q", "-m", "Accept valid credentials", "-m",
             "Proof list:\n- Sign-in check: manual check passed", cwd=folder)

    resumed = repo.forge("work", FIX)
    assert resumed.returncode == 0, resumed.stdout + resumed.stderr
    brief = calls(log)[-1]["brief"]

    assert f"Done when: {DONE}" in brief
    assert "Complete the full Done-when for this item" in brief
    changed_functions = brief.split("## Changed functions at round start\n", 1)[1].split("\n\n", 1)[0]
    assert function in changed_functions
    assert not unchanged or unchanged not in changed_functions
    assert caller in changed_functions
    assert test in changed_functions
