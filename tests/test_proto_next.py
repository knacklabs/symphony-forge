"""The open prototype answers reported by the real forge next command."""

STORY = "FORGE-PROTO-1"

MUST = ("Sign-off person", "Demo workflow", "Users and roles", "Existing systems",
        "Sign-in", "Personal data", "Production host")


def test_6_next_lists_open_must_answer_topics_before_signoff(repo):
    version = repo.forge("--version").stdout.split()[-1]
    repo.write("forge.toml", f'version = "{version}"\nrepo = "client"\n')
    page = repo.write("docs/product/BRIEF.md", "# Product brief\n\n## Answers\n"
                      "- Sign-off person: Sam Lee, director (client, 2026-09-28)\n"
                      "- Demo workflow: ask the client (salesperson, 2026-09-28)\n"
                      "- Users and roles: later, when the team is chosen\n"
                      "- Existing systems: none (client, 2026-09-28)\n"
                      "- Existing systems: CRM (client, 2026-09-28)\n"
                      "- Sign-in: email and password (client, yesterday)\n"
                      "- Personal data: none (client, 2026-09-28)\n"
                      "- Data import: later, when migration begins\n\n## Out of scope\n"
                      "- Production host: our platform (client, 2026-09-28)\n")

    shown = repo.forge("next")
    assert shown.returncode == 0, shown.stderr
    for topic in ("Demo workflow", "Users and roles", "Existing systems", "Sign-in",
                  "Production host"):
        assert f"- {topic}" in shown.stdout
    for topic in ("Sign-off person", "Personal data", "Data import"):
        assert f"- {topic}" not in shown.stdout
    assert "docs/product/BRIEF.md" in shown.stdout

    page.write_text("# Product brief\n\n## Answers\n" + "".join(
        f"- {topic}: settled (client, 2026-09-28)\n" for topic in MUST), encoding="utf-8")
    settled = repo.forge("next")
    assert settled.returncode == 0, settled.stderr
    assert "Open before sign-off" not in settled.stdout

    page.write_text("# Product brief\n\n## Answers\n", encoding="utf-8")
    repo.write("docs/decisions/0001-client-signoff.md", "---\nstatus: accepted\n---\n")
    signed = repo.forge("next")
    assert signed.returncode == 0, signed.stderr
    assert "Open before sign-off" not in signed.stdout
