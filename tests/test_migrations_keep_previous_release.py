"""Close checks only new migrations that can break the previous release."""
from __future__ import annotations

from pathlib import Path

import pytest

from test_close import CLEAN, GREEN, env  # noqa: F401 (env is a fixture)
from test_score_notes import _client_repo as setup_client
from test_worker import calls, install_claude

STORY = "FORGE-EXPAND-1"


@pytest.mark.parametrize(
    "case",
    ["new-client-prisma", "new-client-alembic", "adopted-v1.2.2-prisma"],
    ids=["new-client-prisma", "new-client-alembic", "adopted-v1.2.2-prisma"],
)
def test_1_close_holds_a_migration_the_previous_release_cannot_run(
    env, tmp_path, case
):
    # Audit: protect the close command's live-release migration boundary, including its
    # Contract exception, the independent SQL and Alembic formats, and guidance delivered by
    # work/init/sync. A parser regression could miss one destructive statement or read old files.
    # The adopted app uses root-level Prisma migrations, which the starter-path cases cannot
    # cover: a path matcher that requires a parent directory silently skips the adopted layout.
    # No existing test exercises close against newly added migrations; database guide tests only
    # check delivery. The real Forge work and close commands are the boundary; Claude, review and
    # GitHub use the repository's existing edge stubs. No production test seam is needed.
    setup_client(env, tmp_path, case == "adopted-v1.2.2-prisma")
    repo = env.repo
    env.checks(GREEN)

    # The newly initialized starter is a prototype until sign-off. This test covers the live
    # release contract, so mark its client stage live before starting work.
    config = repo.path / "forge.toml"
    settings = config.read_text(encoding="utf-8")
    if 'stage = "prototype"' in settings:
        config.write_text(settings.replace('stage = "prototype"', 'stage = "live"'),
                          encoding="utf-8")
        hooks = tmp_path / "fixture-no-hooks"
        hooks.mkdir(exist_ok=True)
        repo.git("add", "forge.toml")
        repo.git("-c", f"core.hooksPath={hooks}", "commit", "-q", "-m", "Set the client live")
        repo.git("-c", f"core.hooksPath={hooks}", "push", "-q", "origin", "main")

    migration_path = Path(
        "apps/api/migrations/versions/0011_notes.py"
        if case == "new-client-alembic"
        else ("prisma/migrations/20261101000100_notes/migration.sql"
              if case == "adopted-v1.2.2-prisma"
              else "apps/api/prisma/migrations/20261101000100_notes/migration.sql")
    ).as_posix()
    if case == "new-client-alembic":
        migration = (
            "from alembic import op\nimport sqlalchemy as sa\n\n"
            "def upgrade():\n"
            "    op.add_column('project', sa.Column('note', sa.Text()))\n"
            "    op.drop_constraint('fk', 'project', type_='foreignkey')\n"
            "    op.alter_column('project', 'status', existing_type=sa.INTEGER(), type_=sa.Text())\n"
            "    op.rename_table('note', 'memo')\n"
            "    op.execute(f\"ALTER TABLE {schema}.project RENAME COLUMN name TO title\")\n\n"
            "def downgrade():\n"
            "    op.drop_column('project', 'note')\n"
            "    op.drop_table('memo')\n"
        )
        destructive = (
            "op.alter_column('project', 'status'",
            "op.rename_table('note', 'memo')",
            "op.execute(f\"ALTER TABLE {schema}.project RENAME COLUMN name TO title\")",
        )
        allowed_mentions = ("op.drop_constraint", "op.drop_column", "op.drop_table", "downgrade()")
        contract = "# Contract: the live release no longer reads project.status.\n"
    elif case == "adopted-v1.2.2-prisma":
        migration = 'ALTER TABLE "Project" RENAME COLUMN "name" TO "title";\n'
        destructive = ('ALTER TABLE "Project" RENAME COLUMN "name" TO "title"',)
        allowed_mentions = ("DROP INDEX", "ALTER INDEX", "downgrade()")
        contract = '-- Contract: the live release no longer reads "Project"."name".\n'
    else:
        migration = (
            'ALTER TABLE "Project" ADD COLUMN "title" TEXT;\n'
            'DROP INDEX "idx_Old";\n'
            'ALTER INDEX "a" RENAME TO "b";\n'
            'ALTER TABLE "Project" DROP COLUMN "legacyName";\n'
            'DROP TABLE "LegacyNote";\n'
            'ALTER TABLE "Project" ALTER COLUMN "title" TYPE VARCHAR(200);\n'
            'ALTER TABLE "Project" RENAME TO "ArchivedProject";\n'
        )
        destructive = (
            'ALTER TABLE "Project" DROP COLUMN "legacyName"',
            'DROP TABLE "LegacyNote"',
            'ALTER TABLE "Project" ALTER COLUMN "title" TYPE VARCHAR(200)',
            'ALTER TABLE "Project" RENAME TO "ArchivedProject"',
        )
        allowed_mentions = ('DROP INDEX "idx_Old"', 'ALTER INDEX "a"', "downgrade()")
        contract = '-- Contract: the live release no longer reads "Project"."legacyName".\n'

    log = install_claude(repo)
    if case == "new-client-prisma":
        # An additive migration closes without a Contract comment. It is a separate fix so the
        # unsafe migration below remains the only added migration at its close boundary.
        additive_path = "apps/api/prisma/migrations/20261101000000_tags/migration.sql"
        additive_item, _ = env.start(
            "migration-additive",
            "fix/migration-additive",
            ".factory/fixes/migration-additive.json",
            {"kind": "fix", "why": "Add tags safely", "done_when": "Tags can be stored"},
            {additive_path: 'CREATE TABLE "Tag" ("id" UUID PRIMARY KEY);\n'
                            'ALTER TABLE "Project" ADD COLUMN "tagId" UUID;\n'},
        )
        worked = repo.forge("work", additive_item)
        assert worked.returncode == 0, worked.stdout + worked.stderr
        brief = " ".join(calls(log)[-1]["brief"].split())
        assert "Every migration must work with the previous release: expand, then contract." in brief
        env.reviews(CLEAN)
        additive_close = env.close(additive_item)
        assert additive_close.returncode == 0, additive_close.stdout + additive_close.stderr

    item, where = env.start(
        "migration-contract",
        "fix/migration-contract",
        ".factory/fixes/migration-contract.json",
        {"kind": "fix", "why": "Keep rollback working", "done_when": "The previous release can still run"},
        {migration_path: migration},
    )
    if case != "new-client-prisma":
        worked = repo.forge("work", item)
        assert worked.returncode == 0, worked.stdout + worked.stderr
        brief = " ".join(calls(log)[-1]["brief"].split())
        assert "Every migration must work with the previous release: expand, then contract." in brief

    env.reviews(CLEAN)
    refused = env.close(item)
    output = refused.stdout + refused.stderr
    assert refused.returncode == 1, output
    assert migration_path in output
    for statement in destructive:
        assert statement in output, statement
    assert "Contract:" in output
    assert f"then forge close {item}" in output
    for statement in allowed_mentions:
        assert statement not in output, statement

    # These checks follow the runtime refusal so the first red result identifies a missing gate.
    for host in (".claude", ".codex"):
        database = " ".join((repo.path / host / "skills/database/SKILL.md").read_text("utf-8").split())
        forge_skill = " ".join((repo.path / host / "skills/forge/SKILL.md").read_text("utf-8").split())
        assert "Expand, then contract." in database
        assert "Migrations work with the previous release still running: expand, then contract." in forge_skill

    current = (where / migration_path).read_text(encoding="utf-8")
    env.commit(where, migration_path, current.rstrip() + "\n" + contract,
               "Explain the migration contract")
    env.reviews(CLEAN)
    allowed = env.close(item)
    assert allowed.returncode == 0, allowed.stdout + allowed.stderr
