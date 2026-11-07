"""The main-heading check counts headings that can appear together."""
import pytest

from test_close import CLEAN, GREEN, env  # noqa: F401
from test_score_notes import _client_repo

STORY = "FIX-UI-CHECK-CONDITIONAL-HEADINGS"
pytestmark = pytest.mark.platform


@pytest.mark.parametrize("adopted", [False, True], ids=["new-client", "earlier-adopted-client"])
def test_1_exclusive_main_headings_pass_and_simultaneous_headings_fail(env, tmp_path, adopted):
    # Audit: real close protects exclusive versus simultaneous headings. Raw tag counting
    # rejects the exclusive case; existing close coverage has only unconditional headings.
    # Init and earlier-adoption sync deliver the checker. No test-only production seam.
    _client_repo(env, tmp_path, adopted)
    screen = "apps/web/src/screen.tsx"
    item, where = env.start(
        "heading-branches", "fix/heading-branches", ".factory/fixes/heading-branches.json",
        {"kind": "fix", "why": "Check headings that appear together",
         "done_when": "Exclusive headings pass and simultaneous headings fail"},
        {screen: 'export function Screen({ready}) { return <main>{ready ? '
                 '(<h1>Orders</h1>) : (<h1>Loading</h1>)}</main>; }\n'},
    )

    def close():
        env.checks(GREEN)
        env.reviews(CLEAN)
        return env.close(item)

    passed = close()
    assert passed.returncode == 0, passed.stdout + passed.stderr
    cases = [
        ('<main>{ready ? <><h1>Orders</h1><h1>Extra</h1></> : <h1>Loading</h1>}</main>', False),
        ('<main><h1>Always</h1>{ready ? <h1>Orders</h1> : <h1>Loading</h1>}</main>', False),
        ('<main>{ready ? <h1>Orders</h1> : other ? <h1>Empty</h1> : <h1>Loading</h1>}</main>', True),
        ('<main>{ready ? <h1>Orders</h1> : null}{other ? <h1>Extra</h1> : null}</main>', False),
    ]
    # One upgraded-client witness is enough; the full case table belongs to new clients.
    for markup, allowed in (cases[:1] if adopted else cases):
        env.commit(where, screen, f'export function Screen({{ready, other}}) {{ return {markup}; }}\n')
        result = close()
        output = result.stdout + result.stderr
        assert result.returncode == (0 if allowed else 1), output
        if not allowed:
            assert f"{screen}:1 title-twice: Show the page title once." in output
