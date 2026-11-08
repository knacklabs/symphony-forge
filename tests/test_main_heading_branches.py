"""Source-file checks do not refuse conditional main headings."""
import pytest

from test_close import CLEAN, GREEN, env  # noqa: F401
from test_score_notes import _client_repo

STORY = "FIX-UI-CHECK-CONDITIONAL-HEADINGS"
pytestmark = pytest.mark.platform


@pytest.mark.parametrize("adopted", [False, True], ids=["new-client", "earlier-adopted-client"])
def test_1_conditional_main_headings_do_not_block_close(env, tmp_path, adopted):
    # Audit: real close must accept conditional headings after init and upgrade sync.
    # The source scanner rejects if/else branches; the old test covered only ternaries.
    # The owner removed source heading counts. No production test seam is needed.
    _client_repo(env, tmp_path, adopted)
    screen = "apps/web/src/screen.tsx"
    item, _ = env.start(
        "heading-branches", "fix/heading-branches", ".factory/fixes/heading-branches.json",
        {"kind": "fix", "why": "Keep conditional headings",
         "done_when": "Source heading counts do not block close"},
        {screen: 'export function Screen({ready}) {\n'
                 '  if (ready) return <main><h1>Orders</h1></main>;\n'
                 '  else return <main><h1>Loading</h1></main>;\n}\n'},
    )
    env.checks(GREEN)
    env.reviews(CLEAN)
    passed = env.close(item)
    assert passed.returncode == 0, passed.stdout + passed.stderr
