"""Database guidance reaches both hosts without migrating an adopted app."""
import json
import shutil

import pytest

from conftest import ROOT
from test_setup import _fresh_client

STORY = "FORGE-DATABASE-1"


@pytest.mark.platform
@pytest.mark.parametrize("adoption", ["new init", "earlier adopted"])
def test_1_new_and_existing_repos_get_the_database_skill(repo, gh, tmp_path, adoption):
    # Audit: init/sync must ship the database contract to both agents and preserve old data code.
    # Omitting the ship entry or copying starter files on upgrade breaks this contract.
    # Existing guide checks cover neither this skill nor an older database and money schema.
    # Real Forge commands exercise the owner boundary without a production test seam.
    if adoption == "new init":
        client, initialized = _fresh_client(repo, gh, tmp_path)
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    else:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
        client = repo.path
        config = client / "forge.toml"
        version = repo.forge("--version").stdout.split()[-1]
        config.write_text(config.read_text("utf-8").replace('"v1.2.2"', json.dumps(version)),
                          encoding="utf-8")
        schema = client / "apps/api/prisma/schema/shop.prisma"
        schema.parent.mkdir(parents=True)
        schema.write_text("model Shop {\n  id Int @id\n  totalInCents Int\n}\n", encoding="utf-8")
        compose = client / "compose.test.yml"
        compose.write_text("services:\n  database:\n    image: postgres:16-alpine\n", encoding="utf-8")
        before = {path.relative_to(client).as_posix(): path.read_bytes()
                  for path in (client / "apps").rglob("*") if path.is_file()}
        compose_before = compose.read_bytes()
        repo.git("checkout", "-b", "fix/database-guidance")
        synced = repo.forge("sync")
        assert synced.returncode == 0, synced.stdout + synced.stderr
        assert {path.relative_to(client).as_posix(): path.read_bytes()
                for path in (client / "apps").rglob("*") if path.is_file()} == before
        assert compose.read_bytes() == compose_before

    for host in (".claude", ".codex"):
        target = client / host / "skills/database/SKILL.md"
        assert target.is_file(), f"{host} did not receive database guidance"
        source = (ROOT / "src/forge/templates/skills/database/SKILL.md").read_bytes()
        assert target.read_bytes() == source
        skill = target.read_text("utf-8")
        headings = [line for line in skill.splitlines() if line.startswith("## ")]
        assert headings == [f"## {heading}" for heading in (
            "Columns by kind of data", "Keys and constraints", "Migrations", "Indexes for lists", "List paging",
            "Dashboards and reports", "Change history", "Job tables", "jsonb", "Extensions",
            "Speed without a cache", "Prisma and SQLAlchemy")]
        assert ("pgvector, ltree, pg_trgm, unaccent, fuzzystrmatch, citext, PostGIS, "
                "btree_gist, btree_gin, pg_partman, pg_cron, pg_stat_statements, pgcrypto") in skill
        for term in ("Postgres 17 or older", "@default(uuid(7))", "default=uuid7",
                     "no database default", "Postgres extension <name>: the owner allows it on <date> (<why>)"):
            assert term in skill
