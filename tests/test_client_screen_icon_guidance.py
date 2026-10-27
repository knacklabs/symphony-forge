"""The icon rule reaches workers and reviews on new and upgraded clients.

Test-audit: this protects the delivered prompt contract, not model judgement.
Dropping the icon rule from a worker's convention or a review prompt fails it.
Existing React guidance tests cover different rules. Only the worker, GitHub
and Autoreview edges are fake; no production seam is needed.
"""
import re
from pathlib import Path

import pytest

from test_close import CLEAN, GREEN, env  # noqa: F401
from test_score_notes import _client_repo as setup_client
from test_shadcn_only import _commit_main
from test_worker import calls, install_claude

STORY = "FIX-CLIENT-APP-SCREENS-CAN-USE-EMOJI-AS-ICON"

FRONTEND_RULE = (
    "Use no emojis on client app screens, including icons and decoration. Every icon comes "
    "from the starter's icon library, `lucide-react`; shadcn/ui is set to `lucide`. Keyboard "
    "key labels such as the Command key symbol (⌘) are not emojis."
)
REVIEW_RULE = (
    "On client app screens, report an emoji that this change adds as an icon or decoration "
    "as a finding titled `Icons: <the screen>`. Report an icon from outside the starter's "
    "`lucide-react` library the same way; shadcn/ui is set to `lucide`. Keyboard key labels "
    "such as the Command key symbol (⌘) are not emojis. Apply this rule to new and existing "
    "client repos; do not report unchanged screen code."
)
PROTOTYPE_ICON_RULE = (
    "On client app screens, report emoji icons or decoration and icons outside `lucide-react` "
    "as a finding titled `Icons: <the screen>`. Keyboard key labels such as the Command key "
    "symbol (⌘) are not emojis."
)


@pytest.mark.parametrize("adopted,prototype", [(False, False), (True, False), (False, True)],
                         ids=["new-client", "adopted-v1.2.2", "unsigned-prototype"])
def test_1_workers_and_reviews_receive_the_client_screen_icon_rule(env, tmp_path, adopted, prototype):
    setup_client(env, tmp_path, adopted)
    if prototype:
        config = (env.repo.path / "forge.toml").read_text(encoding="utf-8")
        env.repo.write("forge.toml", config + '\nstage = "prototype"\n')
        _commit_main(env.repo, tmp_path, "Review an unsigned prototype")
    env.checks(GREEN)
    item, _ = env.start("screen-icons", "fix/screen-icons", ".factory/fixes/screen-icons.json",
                        {"kind": "fix", "why": "Keep screen icons consistent",
                         "done_when": "Review reports emoji icons on client screens",
                         **({"allow_large": "Prototype before sign-off"} if prototype else {})},
                        {"apps/web/src/pages/home.tsx":
                         "export function Home() { return <main>🚀 Home <kbd>⌘</kbd></main>; }\n"})
    log = install_claude(env.repo)
    worked = env.repo.forge("work", item)
    assert worked.returncode == 0, worked.stdout + worked.stderr
    brief = calls(log)[-1]["brief"]
    match = re.search(r"how-to.*?is in `([^`]+)`", brief, re.S)
    assert match, brief
    frontend = (Path(match[1]) / "frontend.md").read_text(encoding="utf-8")
    assert FRONTEND_RULE in " ".join(frontend.split())

    # The fake does not decide whether the screen violates the rule. This check
    # proves that the real close command gives the rule to the reviewer.
    env.reviews(CLEAN)
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    prompt = " ".join(env.prompt().split())
    if prototype:
        assert "Review this unsigned working prototype." in prompt
        assert PROTOTYPE_ICON_RULE in prompt
    else:
        assert REVIEW_RULE in prompt
