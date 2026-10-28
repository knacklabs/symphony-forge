"""The feature command builds database values from one shared field-kind table."""

import json
import re
import shutil
import tomllib
from pathlib import Path

import pytest

from conftest import ROOT
from test_feature_command import SHELLS, _run_line, _written_paths, require_feature_cases
from test_setup import _fresh_client
from test_starter_tree import LIVE, _run_live_starter

STORY = "FORGE-DATABASE-1"

ADOPTED = ROOT / "tests/fixtures/adopted-v1.2.2/client"
CUSTOMERS_LINE = "forge task feature customers --one customer --field 'name:text'"
INVOICES_LINE = (
    "forge task feature invoices --one invoice --field 'title:text' "
    "--field 'notes?:long-text' --field 'total:money' --field 'dueDate:date' "
    "--field 'paid:yes-no' --field 'state:status(draft|sent|void)' "
    "--field 'customer:link(customers)' --field 'adjustment?:number'"
)

EXPECTED = {
    "text": ("text", "String", "Text"),
    "long-text": ("text", "String", "Text"),
    "number": ("numeric(19,4)", "Decimal @db.Decimal(19, 4)", "Numeric(19, 4)"),
    "money": ("numeric(19,4)", "Decimal @db.Decimal(19, 4)", "Numeric(19, 4)"),
    "date": ("date", "DateTime @db.Date", "Date"),
    "yes-no": ("boolean DEFAULT false", "Boolean @default(false)", "Boolean, server_default=false()"),
    "email": ("text", "String", "Text"),
    "status": ("text DEFAULT '{first}'", 'String @default("{first}")', 'Text, server_default="{first}"'),
    "link": ("uuid", "String @db.Uuid", "Uuid"),
}
SKILL_ROWS = {
    kind: (f"`{sql}`", f"`{prisma}`", f"`{sqlalchemy}`")
    for kind, (sql, prisma, sqlalchemy) in EXPECTED.items()
}
SKILL_ROWS["money"] = (
    "`numeric(19,4)`; currency `text`",
    "`Decimal @db.Decimal(19, 4)`; currency `String`",
    "`Numeric(19, 4)`; currency `Text`",
)


def _assert_skill_rows(path: Path) -> None:
    rows = {}
    for line in path.read_text("utf-8").splitlines():
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) >= 4 and cells[0] in EXPECTED:
            rows[cells[0]] = tuple(cells[1:4])
    assert {kind: rows.get(kind) for kind in EXPECTED} == SKILL_ROWS


def _assert_kind_values(client: Path) -> None:
    kinds = tomllib.loads((ROOT / "src/forge/templates/feature/kinds.toml").read_text("utf-8"))
    for name, expected in EXPECTED.items():
        kind = kinds["kinds"][name]
        assert (kind["sql"], kind["prisma"], kind["sqlalchemy"]) == expected
    for host in (".codex", ".claude"):
        _assert_skill_rows(client / host / "skills/database/SKILL.md")

    for name in ("number", "money"):
        kind = kinds["kinds"][name]
        assert kind["pydantic"] == "str"
        assert kind["zod"] == r"z.string().regex(/^-?\d{1,15}(?:\.\d{1,4})?$/)"
    assert kinds["kinds"]["number"]["sample"] == "-42.5000"
    money = kinds["kinds"]["money"]
    assert (money["currency_sql"], money["currency_prisma"], money["currency_sqlalchemy"]) == ("text", "String", "Text")
    assert money["currency_check"] == 'CONSTRAINT "{table}_{currency}_code" CHECK ("{currency}" ~ \'^[A-Z]{3}$\')'
    assert money["input"] == "money"
    assert money["cell"] == money["csv"] == "formatMoney(row.{name}, row.{name}Currency)"
    assert (money["sample"], money["changed"], money["bad"]) == ("1250.0000", "1800.0000", "not-money")


def _assert_invoice_migration(sql: str, starter: str) -> None:
    if starter == "typescript":
        table, schema = "Invoice", "invoices"
        names = {"due": "dueDate", "paid": "paid", "state": "state", "currency": "totalCurrency",
                 "customer": "customerId", "org": "organisationId", "updated": "updatedAtUtc",
                 "deleted": "deletedAtUtc"}
    else:
        table, schema = "invoice", "invoices"
        names = {"due": "due_date", "paid": "paid", "state": "state", "currency": "total_currency",
                 "customer": "customer_id", "org": "organisation_id", "updated": "updated_at_utc",
                 "deleted": "deleted_at_utc"}
    for column, sql_type, required in (
        ("title", "text", True), ("notes", "text", False), ("total", "numeric(19,4)", True),
        (names["currency"], "text", True), (names["due"], "date", True),
        (names["paid"], "boolean DEFAULT false", True), (names["state"], "text DEFAULT 'draft'", True),
        (names["customer"], "uuid", True), ("adjustment", "numeric(19,4)", False),
    ):
        match = re.search(rf'^\s*"{re.escape(column)}"\s+([^\n]+)', sql, re.M)
        assert match and sql_type in match[1], (column, match[1] if match else sql)
        assert ("NOT NULL" in match[1]) is required, match[1]

    constraints = (
        f'CONSTRAINT "{table}_title_length" CHECK (char_length("title") BETWEEN 1 AND 200)',
        f'CONSTRAINT "{table}_notes_length" CHECK (char_length("notes") <= 10000)',
        f'CONSTRAINT "{table}_state_allowed" CHECK ("state" IN (\'draft\', \'sent\', \'void\'))',
        f'CONSTRAINT "{table}_{names["currency"]}_code" CHECK ("{names["currency"]}" ~ \'^[A-Z]{{3}}$\')',
    )
    assert all(constraint in sql for constraint in constraints)
    assert f'CONSTRAINT "{table}_adjustment' not in sql
    assert f'FOREIGN KEY ("{names["customer"]}")' not in sql

    index_source = f'ON "{schema}"."{table}"'
    assert f'CREATE INDEX "idx_{table}_list" {index_source} ("{names["org"]}", "{names["updated"]}" DESC, "id" DESC) WHERE "{names["deleted"]}" IS NULL;' in sql
    for column in (names["paid"], names["state"], names["customer"]):
        assert f'CREATE INDEX "idx_{table}_{column}" {index_source} ("{names["org"]}", "{column}", "{names["updated"]}" DESC, "id" DESC) WHERE "{names["deleted"]}" IS NULL;' in sql
    assert f'CREATE INDEX "idx_{table}_title_search" {index_source} USING gin ("{names["org"]}", "title" gin_trgm_ops) WHERE "{names["deleted"]}" IS NULL;' in sql
    assert f'CREATE INDEX "idx_{table}_{names["customer"]}_fk" {index_source} ("{names["customer"]}");' in sql
    assert f'CREATE TRIGGER "{table}_set_updated_at" BEFORE UPDATE ON "{table}" FOR EACH ROW EXECUTE FUNCTION set_updated_at();' in sql


def _file_snapshot(root: Path) -> dict[Path, bytes]:
    return {path.relative_to(root): path.read_bytes() for path in root.rglob("*")
            if path.is_file() and ".git" not in path.relative_to(root).parts}


def _assert_adopted_stays_unchanged(repo) -> None:
    shutil.copytree(ADOPTED, repo.path, dirs_exist_ok=True)
    config = repo.path / "forge.toml"
    version = repo.forge("--version").stdout.split()[-1]
    config.write_text(config.read_text("utf-8").replace('"v1.2.2"', json.dumps(version)), encoding="utf-8")
    repo.git("checkout", "-q", "-b", "fix/database-kinds-adopted")
    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stdout + synced.stderr
    for host in (".codex", ".claude"):
        _assert_skill_rows(repo.path / host / "skills/database/SKILL.md")
    before = _file_snapshot(repo.path)
    before_status = repo.git("status", "--porcelain=v1", "-uall")
    refused = _run_line(repo, repo.path, SHELLS[0], CUSTOMERS_LINE)
    assert refused.returncode != 0, refused.stdout + refused.stderr
    assert "Wrote " not in refused.stdout
    assert _file_snapshot(repo.path) == before
    assert repo.git("status", "--porcelain=v1", "-uall") == before_status


def _add_live_money_case(client: Path, starter: str) -> None:
    path = (client / "apps/api/test/invoices.e2e-spec.ts" if starter == "typescript"
            else client / "apps/api/tests/test_invoices.py")
    source = path.read_text("utf-8")
    if starter == "typescript":
        imports = "import { apiBaseUrl, credentials, csrfToken, invite } from './helpers';"
        assert imports in source
        source = source.replace(imports, "import { apiBaseUrl, credentials, csrfToken, invite, psql } from './helpers';", 1)
        anchor = "describe('invoices API', () => {"
        case = r'''  it('keeps exact decimal strings and the stored currency', async () => {
    const { client, csrf } = await sharedSignedIn();
    const input = await featureInput(client, csrf, randomUUID(), 'sample');
    input.total = '12345678901234.5650';
    input.adjustment = '-42.5000';
    await client.post('/api/v1/invoices').set('x-csrf-token', csrf)
      .send({ ...input, total: 1250 }).expect(400);
    await client.post('/api/v1/invoices').set('x-csrf-token', csrf)
      .send({ ...input, adjustment: -42.5 }).expect(400);
    await client.post('/api/v1/invoices').set('x-csrf-token', csrf)
      .send({ ...input, totalCurrency: 'USD' }).expect(400);
    const created = await client.post('/api/v1/invoices').set('x-csrf-token', csrf).send(input).expect(201);
    const id = created.body.data.id as string;
    expect(created.body.data.totalCurrency).toBe('INR');
    expect(typeof created.body.data.total).toBe('string');
    expect(created.body.data.total).toMatch(/^12345678901234\.5650?$/);
    expect(typeof created.body.data.adjustment).toBe('string');
    expect(created.body.data.adjustment).toMatch(/^-42\.5(?:0{0,3})?$/);
    const setExistingCurrency = psql(`UPDATE invoices."Invoice" SET "totalCurrency" = 'USD' WHERE id = '${id}'`);
    expect(setExistingCurrency.status, setExistingCurrency.output).toBe(0);
    const invalidCurrency = psql(`UPDATE invoices."Invoice" SET "totalCurrency" = 'usd' WHERE id = '${id}'`);
    expect(invalidCurrency.status).not.toBe(0);
    expect(invalidCurrency.output).toContain('Invoice_totalCurrency_code');
    const changed = { ...input, total: '-0.0500' };
    const updated = await client.put(`/api/v1/invoices/${id}`).set('x-csrf-token', csrf).send(changed).expect(200);
    expect(updated.body.data.totalCurrency).toBe('USD');
    expect(typeof updated.body.data.total).toBe('string');
    expect(updated.body.data.total).toMatch(/^-0\.05(?:0{0,2})?$/);
  });
'''
        assert source.count(anchor) == 1
        path.write_text(source.replace(anchor, anchor + "\n" + case, 1), encoding="utf-8")
    else:
        imports = "from test_invites import invite"
        assert imports in source
        source = source.replace(imports, imports + "\nfrom test_soft_delete import psql", 1)
        case = r'''

def test_keeps_exact_decimal_strings_and_the_stored_currency(
    client: httpx.Client,
) -> None:
    _, csrf = sign_up(client)
    headers = {"x-csrf-token": csrf}
    customer = client.post(
        "/api/v1/customers", headers=headers, json={"name": "Currency customer"}
    )
    assert customer.status_code == 201, customer.text
    body = {
        "title": "Currency invoice",
        "total": "12345678901234.5650",
        "adjustment": "-42.5000",
        "dueDate": "2026-10-28",
        "paid": False,
        "state": "draft",
        "customerId": customer.json()["data"]["id"],
    }
    bad_number = client.post(
        "/api/v1/invoices", headers=headers, json={**body, "total": 12345678901234.565}
    )
    assert bad_number.status_code == 400, bad_number.text
    bad_adjustment = client.post(
        "/api/v1/invoices", headers=headers, json={**body, "adjustment": -42.5}
    )
    assert bad_adjustment.status_code == 400, bad_adjustment.text
    bad_currency = client.post(
        "/api/v1/invoices", headers=headers, json={**body, "totalCurrency": "USD"}
    )
    assert bad_currency.status_code == 400, bad_currency.text
    created = client.post("/api/v1/invoices", headers=headers, json=body)
    assert created.status_code == 201, created.text
    data = created.json()["data"]
    invoice_id = data["id"]
    assert data["totalCurrency"] == "INR"
    assert isinstance(data["total"], str) and Decimal(data["total"]) == Decimal(
        "12345678901234.5650"
    )
    assert isinstance(data["adjustment"], str) and Decimal(
        data["adjustment"]
    ) == Decimal("-42.5000")
    changed_currency = psql(
        f"UPDATE invoices.invoice SET total_currency = 'USD' WHERE id = '{invoice_id}'"
    )
    assert changed_currency.returncode == 0, (
        changed_currency.stdout + changed_currency.stderr
    )
    invalid_currency = psql(
        f"UPDATE invoices.invoice SET total_currency = 'usd' WHERE id = '{invoice_id}'"
    )
    assert invalid_currency.returncode != 0
    assert (
        "invoice_total_currency_code"
        in invalid_currency.stdout + invalid_currency.stderr
    )
    updated = client.put(
        f"/api/v1/invoices/{invoice_id}",
        headers=headers,
        json={**body, "total": "-0.0500"},
    )
    assert updated.status_code == 200, updated.text
    data = updated.json()["data"]
    assert data["totalCurrency"] == "USD"
    assert isinstance(data["total"], str) and Decimal(data["total"]) == Decimal(
        "-0.0500"
    )
'''
        path.write_text(source + case, encoding="utf-8")


def _assert_live_run(client: Path, starter: str, tmp_path_factory) -> None:
    _add_live_money_case(client, starter)
    live = _run_live_starter(tmp_path_factory, ((client, Path(".")),), ("GET /health returned 200",))
    if starter == "typescript":
        require_feature_cases(live["api"], "invoices.e2e-spec.ts", (
            "keeps exact decimal strings and the stored currency",
            "creates, lists, reads, updates, soft-deletes, and restores",
            "pages forward and backward by every sortable field",
            "searches and filters the feature list",
            "rejects bad fields, unknown inputs, and unknown list parameters",
        ))
        require_feature_cases(live["api"], "database.e2e-spec.ts", (
            "each module keeps its tables in its own schema",
        ))
    else:
        require_feature_cases(live["api"], "test_invoices", (
            "test_keeps_exact_decimal_strings_and_the_stored_currency",
            "test_creates_lists_reads_updates_and_deletes_a_invoice",
            "test_pages_invoices_with_next_and_previous_cursors",
            "test_filters_invoices_by_search_and_filters",
            "test_rejects_bad_fields_unknown_inputs_and_unknown_list_parameters",
        ))
        require_feature_cases(live["api"], "test_module_schemas", (
            "test_each_module_keeps_its_tables_in_its_own_schema",
        ))


@pytest.mark.platform
@pytest.mark.timeout(1800)
@pytest.mark.parametrize("starter", ["typescript", "python"])
def test_5_feature_columns_come_from_the_kind_table(repo, gh, tmp_path, tmp_path_factory, starter):
    # Audit: a changed kind value must reach generated migrations and both shipped skill copies;
    # command tests that read the kind table cannot detect a table and skill drifting together.
    # The command is the owner boundary; no test-only production seam is needed.
    client, initialized = _fresh_client(repo, gh, tmp_path, "--starter", "react" if starter == "typescript" else "python")
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    _assert_kind_values(client)
    if starter == "typescript":
        # Audit: an existing Prisma preview must survive feature generation in one valid array.
        # Fresh-generator coverage cannot catch duplicate properties. Exercise the same CLI,
        # including a second feature, without a new production seam.
        base = client / "apps/api/prisma/schema/base.prisma"
        # Prisma rejects multiline generator arrays; keep this existing preview valid.
        base.write_text(base.read_text("utf-8").replace(
            "generator client {",
            'generator client {\n  previewFeatures = ["relationJoins"]',
            1,
        ), encoding="utf-8")
    written = set()
    for index, line in enumerate((CUSTOMERS_LINE, INVOICES_LINE)):
        result = _run_line(repo, client, SHELLS[index % len(SHELLS)], line)
        assert result.returncode == 0, result.stdout + result.stderr
        written |= _written_paths(result, client)
        if starter == "typescript":
            previews = re.findall(r"\bpreviewFeatures\s*=\s*\[([^\]]*)\]", base.read_text("utf-8"))
            assert len(previews) == 1, previews
            assert sorted(re.findall(r'"([^"\n]+)"', previews[0])) == ["partialIndexes", "relationJoins"]

    if starter == "typescript":
        migration_paths = [path for path in written if "_invoices/" in path and path.endswith("migration.sql")]
    else:
        migration_paths = [path for path in written
                           if re.fullmatch(r"apps/api/migrations/versions/\d{4}_invoices\.py", path)]
    assert len(migration_paths) == 1
    migration = (client / migration_paths[0]).read_text("utf-8")
    _assert_invoice_migration(migration, starter)

    if LIVE:
        _assert_live_run(client, starter, tmp_path_factory)
    if starter == "typescript":
        _assert_adopted_stays_unchanged(repo)
