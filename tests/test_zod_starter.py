"""New starters ship one input validator and schema-derived request documentation."""
import json
import re
from pathlib import Path

STORY = "FORGE-ZOD-1"

STARTER = Path(__file__).resolve().parents[1] / "src" / "forge" / "templates" / "starter"


def test_1_a_new_app_has_no_class_validator():
    package = json.loads((STARTER / "package.json").read_text(encoding="utf-8"))
    forbidden = {"class-validator", "class-transformer"}
    for group in ("dependencies", "devDependencies", "optionalDependencies", "peerDependencies"):
        assert not forbidden.intersection(package.get(group, {}))
    lock = (STARTER / "pnpm-lock.yaml").read_text(encoding="utf-8")
    assert not re.search(r"class-(?:validator|transformer)@", lock)
    for path in STARTER.rglob("*"):
        if path.is_file() and path.name != "pnpm-lock.yaml":
            assert not any(name in path.read_text(encoding="utf-8") for name in forbidden), path
    assert "ValidationPipe(" not in (STARTER / "apps/api/src/main.ts").read_text(encoding="utf-8")


def test_3_the_request_docs_come_from_the_shared_zod_schemas():
    decorator = STARTER / "libs/core/server/src/common/api-zod.decorator.ts"
    assert decorator.is_file()
    assert "z.toJSONSchema" in decorator.read_text(encoding="utf-8")
    assert "projectListQuerySchema" in (STARTER / "libs/projects/contracts/src/index.ts").read_text(encoding="utf-8")
    for folder in (STARTER / "libs", STARTER / "apps/api/src"):
        for path in folder.rglob("*.ts"):
            if path != decorator:
                text = path.read_text(encoding="utf-8")
                assert not re.search(r"ApiQuery\(|ApiPropertyOptional|ApiBody\(\{ type", text), path
