"""Close checks changed client UI files against the shipped design rules."""
from __future__ import annotations

import os

import pytest

from test_close import CLEAN, GREEN, env
from test_score_notes import _client_repo as setup_client


STORY = "FORGE-UISTANDARDS-1"
pytestmark = pytest.mark.platform


def _commit_main(repo, tmp_path, message):
    hooks = tmp_path / "no-hooks"
    hooks.mkdir(exist_ok=True)
    repo.git("add", "-A")
    repo.git("-c", f"core.hooksPath={hooks}", "commit", "-q", "-m", message)
    repo.git("-c", f"core.hooksPath={hooks}", "push", "-q", "origin", "main")


@pytest.mark.parametrize("adopted", [False, True], ids=["new-client", "earlier-adopted-client"])
def test_3_close_checks_only_changed_client_ui_and_reports_design_problems(
    env, tmp_path, monkeypatch, adopted
):
    # Test audit:
    # 1. Protect close's changed-file design checks, waivers and unavailable-checker behavior.
    # 2. A future edit could skip a rule, check an untouched adopted file, or hide a bad waiver.
    # 3. Existing close tests use Forge-source settings; none exercise this client boundary.
    # 4. This calls the real forge close command and the synced pinned launcher; no test seam
    #    decides checker findings.
    setup_client(env, tmp_path, adopted)
    repo = env.repo
    launcher = repo.path / ".codex/skills/impeccable/scripts" / (
        "impeccable.cmd" if os.name == "nt" else "impeccable"
    )
    assert launcher.is_file()
    monkeypatch.setenv("IMPECCABLE_HOME", str(tmp_path / "impeccable-home"))
    monkeypatch.delenv("IMPECCABLE_BIN", raising=False)

    if adopted:
        old = "apps/web/src/old-screen.tsx"
        (repo.path / old).parent.mkdir(parents=True, exist_ok=True)
        (repo.path / old).write_text(
            '<main><h1>Old</h1><div className="p-[13px]">Old spacing</div></main>\n',
            encoding="utf-8",
        )
        _commit_main(repo, tmp_path, "Keep an earlier screen")
        monkeypatch.setenv("IMPECCABLE_LAUNCHER_PROBE", "1")

        ui = "apps/web/src/new-screen.tsx"
        item, where = env.start(
            "ui-guard",
            "fix/ui-guard",
            ".factory/fixes/ui-guard.json",
            {"kind": "fix", "why": "Keep changed screens on the spacing scale",
             "done_when": "Changed screens use the spacing scale"},
            {ui: "<main><h1>New</h1><p>Work</p></main>\n"},
        )

        env.checks(GREEN)
        env.reviews(CLEAN)
        untouched = env.close(item)
        assert untouched.returncode == 0, untouched.stdout + untouched.stderr
        assert "The design checker did not run. The other design checks still ran." in untouched.stdout

        env.commit(where, old,
                   '<main><h1>Old</h1><div className="p-[13px]">Changed old spacing</div></main>\n')
        env.checks(GREEN)
        env.reviews(CLEAN)
        refused = env.close(item)
        output = refused.stdout + refused.stderr
        assert refused.returncode == 1, output
        assert "The design checker did not run. The other design checks still ran." in output
        assert f"{old}:1 spacing-scale" in output
        assert "forge-ui-ignore spacing-scale: <reason>" in output

        env.commit(where, old, (
            "{/* forge-ui-ignore spacing-scale: Keep this existing measurement */}\n"
            '<main><h1>Old</h1><div className="p-[13px]">Changed old spacing</div></main>\n'
        ))
        env.checks(GREEN)
        env.reviews(CLEAN)
        waived = env.close(item)
        assert waived.returncode == 0, waived.stdout + waived.stderr
        assert "The design checker did not run. The other design checks still ran." in waived.stdout
        return

    # The shipped command implementation contains a search role, but it is not the app shell.
    command = repo.path / "libs/shared/ui/src/components/ui/command.tsx"
    command.parent.mkdir(parents=True, exist_ok=True)
    command.write_text("export function CommandDialog() { return <div role=\"search\" />; }\n",
                       encoding="utf-8")
    _commit_main(repo, tmp_path, "Keep the shipped command component")
    monkeypatch.delenv("IMPECCABLE_LAUNCHER_PROBE", raising=False)

    css = "apps/web/src/brand.css"
    shell = "apps/web/src/shell.tsx"
    sidebar = "apps/web/src/components/AppSidebar.tsx"
    ignored_test = "apps/web/src/dashboard.test.tsx"
    ignored_component = "apps/web/src/components/ui/ignored.tsx"
    canvas = "apps/web/src/admin.html"
    item, where = env.start(
        "ui-guard",
        "fix/ui-guard",
        ".factory/fixes/ui-guard.json",
        {"kind": "fix", "why": "Keep client screens on the design rules",
         "done_when": "Changed screens pass the design checks"},
        {
            **{f"apps/web/src/a-{index}.css": ".title { color: inherit; }\n"
               for index in range(50)},
            css: ".title { background: linear-gradient(red, blue); background-clip: text; color: transparent; }\n",
            shell: (
                'import { SidebarProvider } from "./components/ui/sidebar";\n'
                'import { AppSidebar } from "./components/AppSidebar";\n'
                "export function Shell() {\n"
                "  return <SidebarProvider><AppSidebar /><header><h2>Dashboard</h2></header>"
                '<main><h1>Dashboard</h1><div className="p-[13px]">Work</div></main>'
                "</SidebarProvider>;\n}\n"
            ),
            sidebar: (
                'import { Sidebar } from "./components/ui/sidebar";\n'
                "export function AppSidebar() { return <Sidebar />; }\n"
            ),
            ignored_test: '<div className="p-[13px]">Test-only spacing</div>\n',
            ignored_component: '<div className="p-[13px]">Library spacing</div>\n',
        canvas: "<header><input type=\"search\" aria-label=\"Search admin\" /></header>"
                "<aside><button>Menu</button></aside><main><h1>Admin</h1></main>\n",
        },
    )

    def close():
        env.checks(GREEN)
        env.reviews(CLEAN)
        return env.close(item)

    refused = close()
    output = refused.stdout + refused.stderr
    assert refused.returncode == 1, output
    assert f"{shell}:" in output and "spacing-scale" in output
    assert f"{shell}:" in output and "title-twice" in output
    assert f"{shell}:" in output and "shell-fold" in output
    assert f"{shell}:" in output and "shell-search" in output
    assert f"{canvas}:1 shell-fold" in output
    assert f"{css}:1 gradient-text:" in output
    assert ignored_test not in output
    assert ignored_component not in output
    lines = output.splitlines()
    checker = next(index for index, line in enumerate(lines) if f"{css}:1 gradient-text:" in line)
    assert lines[checker + 1].strip() == "/* impeccable-disable gradient-text -- <reason> */"

    # A waiver without a reason must leave all four Forge problems in place.
    env.commit(where, shell, (
        "{/* forge-ui-ignore spacing-scale: */}\n"
        "{/* forge-ui-ignore title-twice: */}\n"
        "{/* forge-ui-ignore shell-fold: */}\n"
        "{/* forge-ui-ignore shell-search: */}\n"
        'import { SidebarProvider } from "./components/ui/sidebar";\n'
        'import { AppSidebar } from "./components/AppSidebar";\n'
        "export function Shell() {\n"
        "  return <SidebarProvider><AppSidebar /><header><h2>Dashboard</h2></header>"
        '<main><h1>Dashboard</h1><div className="p-[13px]">Work</div></main>'
        "</SidebarProvider>;\n}\n"
    ))
    env.commit(where, canvas,
               "<!-- forge-ui-ignore shell-fold: -->\n<header><input type=\"search\" "
               "aria-label=\"Search admin\" /></header><aside><button>Menu</button></aside>"
               "<main><h1>Admin</h1></main>\n")
    still_refused = close()
    output = still_refused.stdout + still_refused.stderr
    assert still_refused.returncode == 1, output
    for rule in ("spacing-scale", "title-twice", "shell-fold", "shell-search"):
        assert rule in output
    assert f"{canvas}:" in output and "shell-fold" in output

    # Reasons waive the Forge checks. The real launcher also accepts its own checker waiver.
    env.commit(where, shell, (
        "{/* forge-ui-ignore spacing-scale: Keep this measured client spacing */}\n"
        "{/* forge-ui-ignore title-twice: The existing navigation repeats its label */}\n"
        "{/* forge-ui-ignore shell-fold: The current sidebar uses a custom layout */}\n"
        "{/* forge-ui-ignore shell-search: Search is supplied by another route */}\n"
        'import { SidebarProvider } from "./components/ui/sidebar";\n'
        'import { AppSidebar } from "./components/AppSidebar";\n'
        "export function Shell() {\n"
        "  return <SidebarProvider><AppSidebar /><header><h2>Dashboard</h2></header>"
        '<main><h1>Dashboard</h1><div className="p-[13px]">Work</div></main>'
        "</SidebarProvider>;\n}\n"
    ))
    env.commit(where, canvas,
               "<!-- forge-ui-ignore shell-fold: This canvas keeps its legacy sidebar -->\n"
               "<header><input type=\"search\" aria-label=\"Search admin\" /></header>"
               "<aside><button>Menu</button></aside><main><h1>Admin</h1></main>\n")
    env.commit(where, css,
               ".title { background: linear-gradient(red, blue); background-clip: text; color: transparent; }\n"
               "/* impeccable-disable gradient-text -- Keep the client's brand colors */\n")
    waived = close()
    assert waived.returncode == 0, waived.stdout + waived.stderr

    # A clean imported shell passes when its component supplies folding and search.
    env.commit(where, shell, (
        'import { SidebarProvider } from "./components/ui/sidebar";\n'
        'import { AppSidebar } from "./components/AppSidebar";\n'
        "export function Shell() {\n"
        '  return <SidebarProvider><AppSidebar /><header><h2>Navigation</h2></header>'
        '<main><h1>Dashboard</h1><div className="p-4">Work</div></main>'
        "</SidebarProvider>;\n}\n"
    ))
    env.commit(where, sidebar,
               'import { Sidebar } from "./components/ui/sidebar";\n'
               'export function AppSidebar() { return <><Sidebar collapsible="icon" />'
               '<input type="search" aria-label="Search" /></>; }\n')
    env.commit(where, css, ".title { color: navy; }\n")
    env.commit(where, canvas,
               '<header><input type="search" aria-label="Search admin" /></header>'
               '<aside data-collapsible="icon"><button>Menu</button></aside>'
               "<main><h1>Admin</h1></main>\n")
    clean = close()
    assert clean.returncode == 0, clean.stdout + clean.stderr

    # Removing the imported fold control brings the shell refusal back.
    env.commit(where, sidebar,
               'import { Sidebar } from "./components/ui/sidebar";\n'
               'export function AppSidebar() { return <><Sidebar /><input type="search" '
               'aria-label="Search" /></>; }\n')
    missing_fold = close()
    output = missing_fold.stdout + missing_fold.stderr
    assert missing_fold.returncode == 1, output
    assert f"{shell}:" in output and "shell-fold" in output

    # With an empty checker cache, the remaining code check still refuses bad spacing.
    env.commit(where, sidebar,
               'import { Sidebar } from "./components/ui/sidebar";\n'
               'export function AppSidebar() { return <><Sidebar collapsible="icon" />'
               '<input type="search" aria-label="Search" /></>; }\n')
    monkeypatch.setenv("IMPECCABLE_LAUNCHER_PROBE", "1")
    monkeypatch.setenv("IMPECCABLE_HOME", str(tmp_path / "offline-impeccable-home"))
    offline = "apps/web/src/offline.tsx"
    env.commit(where, offline,
               '<main><h1>Offline</h1><div className="p-[13px]">Work</div></main>\n')
    skipped = close()
    output = skipped.stdout + skipped.stderr
    assert skipped.returncode == 1, output
    assert "The design checker did not run. The other design checks still ran." in output
    assert f"{offline}:1 spacing-scale" in output
