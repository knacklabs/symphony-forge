"""Live Postgres version and extension contract."""

from test_soft_delete import psql


def test_the_database_runs_postgres_18_with_the_day_one_extensions() -> None:
    version = psql("SHOW server_version_num")
    assert version.returncode == 0, version.stderr
    version_number = next(
        (
            int(line.strip())
            for line in version.stdout.splitlines()
            if line.strip().isdigit()
        ),
        None,
    )
    assert version_number is not None and version_number >= 180000, version.stdout

    extensions = psql(
        "SELECT string_agg(extname::text, ',' ORDER BY extname) FROM pg_extension "
        "WHERE extname IN ('btree_gin', 'pg_stat_statements', 'pg_trgm')"
    )
    assert extensions.returncode == 0, extensions.stderr
    assert "btree_gin,pg_stat_statements,pg_trgm" in extensions.stdout

    statistics = psql("SELECT count(*) FROM pg_stat_statements")
    assert statistics.returncode == 0, statistics.stderr
