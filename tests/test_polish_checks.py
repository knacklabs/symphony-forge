"""Close refuses a changed UI file that animates all properties; existing apps get the rules."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from test_noscreens_starters import _earlier_app
from test_polish_parts import _new_app, _read

STORY = "FORGE-POLISH-1"
pytestmark = pytest.mark.platform
SWITCH = "libs/shared/ui/src/components/ui/switch.tsx"
BAD = 'export const A = () => <i className="transition-all duration-150" />;\n'


def _check(client: Path, *files: str) -> list[str]:
    done = subprocess.run([shutil.which("node"), ".forge/design/ui-checks.js"], cwd=client,
                          input=json.dumps(list(files)), capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)["problems"]


@pytest.mark.parametrize("adopted", [False, True], ids=["new-client", "earlier-adopted-client"])
def test_4_motion_all_refuses_a_changed_file_and_a_reason_sets_it_aside(repo, gh, tmp_path, adopted):
    if adopted:
        # Sync leaves the old part with transition-all; only a file the change touches is checked.
        client = _earlier_app(repo, gh, tmp_path)
        old = "libs/shared/ui/src/components/ui/button.tsx"
        assert not _check(client)
        assert "transition-all" in _read(client / old)
        # Sync gave the old app the check and the written rules in both hosts, and no app file.
        for host in (".claude", ".codex"):
            assert "motion-all" in _read(client / host / "skills/forge/SKILL.md")
        (problem,) = [p for p in _check(client, old) if "motion-all" in p]
        assert problem.startswith(f"{old}:")
        return
    client = _new_app(repo, gh, tmp_path, ("--starter",))
    # The freshly made app has no problem, so the rule refuses nothing correct.
    starter = [str(p.relative_to(client)) for root in ("libs/shared/ui", "apps/web/src")
               for p in (client / root).rglob("*") if p.is_file()]
    assert not [p for p in _check(client, *starter) if "motion-all" in p]
    for rel, text in ((SWITCH, BAD), ("apps/web/src/a.css", ".a { transition: all 1s; }\n"),
                      ("apps/web/src/b.css", ".b { transition-property: all; }\n")):
        (client / rel).write_text(text, encoding="utf-8")
        (problem,) = [p for p in _check(client, rel) if "motion-all" in p]
        assert problem.startswith(f"{rel}:1 motion-all: ")
        assert "List the properties" in problem and "forge-ui-ignore motion-all: <reason>" in problem
    # Only the comment with a reason sets it aside, and a stripped comment hides nothing.
    (client / SWITCH).write_text("{/* forge-ui-ignore motion-all: */}\n" + BAD, encoding="utf-8")
    assert _check(client, SWITCH)
    (client / SWITCH).write_text("{/* forge-ui-ignore motion-all: Fades the whole card */}\n" + BAD,
                                 encoding="utf-8")
    assert not _check(client, SWITCH)
    (client / SWITCH).write_text("{/* transition-all */}\nexport const A = 1;\n", encoding="utf-8")
    assert not _check(client, SWITCH)
    # A // comment at the end of a code line counts as a comment and can carry the waiver.
    ok = ('export const A = () => <i className="transition-opacity" />; // replaced transition-all\n',
          BAD.rstrip() + " // forge-ui-ignore motion-all: Fades the whole card\n")
    # Only the text after // is set aside: a URL, a quoted // or a real class before it still counts.
    bad = (BAD.rstrip() + " // forge-ui-ignore motion-all:\n",
           'export const A = () => <a href="https://x.dev" className="transition-all" />;\n',
           'export const A = () => <i title="a // b" className="transition-all" />;\n',
           'export const A = () => <p>https://x.dev</p>;\nexport const B = <i className="transition-all" />;\n',
           "export const A = { transition: 'all 150ms ease' };\n",
           'export const A = { transitionProperty: "all" };\n')
    for text in ok:
        (client / SWITCH).write_text(text, encoding="utf-8")
        assert not _check(client, SWITCH), text
    for text in bad:
        (client / SWITCH).write_text(text, encoding="utf-8")
        assert [p for p in _check(client, SWITCH) if "motion-all" in p], text
    # The other rules keep their reading: an end-of-line waiver does not set them aside.
    other = "apps/web/src/c.tsx"
    (client / other).write_text('export const A = () => <i className="p-[13px]" />; '
                                "// forge-ui-ignore spacing-scale: Odd gap\n", encoding="utf-8")
    assert [p for p in _check(client, other) if "spacing-scale" in p]
