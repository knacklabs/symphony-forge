"""Zod guidance reaches new and earlier-adopted clients through work and close.

Test-audit: these protect convention and prompt contracts, not model judgement.
Dropping guidance during setup, upgrade, work or review must fail; existing React
and module tests do not own Zod guidance. Only external tools are faked, with no
production seam. The adopted case also guards app-owned file preservation.
"""
import json
import re
from pathlib import Path

import pytest

from test_close import CLEAN, GREEN, blocked, env, finding  # noqa: F401
from test_score_notes import _client_repo as setup_client
from test_shadcn_only import _commit_main
from test_worker import calls, install_claude


REQUEST_RULE = (
    "Request input is a zod schema in `@app/shared`: one for each body and one for each list "
    "query, and the web form uses the same schema. Check it with "
    "`@Body(new ZodValidationPipe(schema))` or `@Query(new ZodValidationPipe(schema))`, and "
    "document it with `@ApiZodBody(schema)` or `@ApiZodQuery(schema)`. Each schema is "
    "`.strict()`, gives every string a maximum length, and gives every field "
    "`.meta({ description, example })`. A request schema has no `.transform()`, because the "
    "documentation cannot show one."
)
MODULE_RULE = (
    "Request input is checked by zod schemas from `@app/shared`, as api.md says; the app has "
    "no global ValidationPipe."
)
REVIEW_RULE = (
    "In a TypeScript app with `zod` in a `package.json`, report a request body or query that "
    "this change adds and that no zod schema checks as a P1 finding titled `Zod: <the endpoint>`. "
    "Request input has one zod schema in the app's shared package, which the web form and the "
    "API both use, and the API documentation comes from that schema. A class-validator rule or "
    "an `@ApiProperty` on request input that this change adds is a finding. Input the default "
    "branch already has is not a finding, and neither is a path parameter that a Nest parse "
    "pipe checks."
)
WORKER_RULE = (
    "In a TypeScript app with zod in a package.json, check each request body and query that "
    "you add with a zod schema in the shared package, through ZodValidationPipe, and document "
    "it from the same schema, as the API convention says. Do not add class-validator rules or "
    "@ApiProperty to request input. Review flags new request input that no zod schema checks."
)
EXISTING_APP = (
    "An app's current request DTOs and its global ValidationPipe stay as they are, and the "
    "review does not flag them. In an app with zod, new request input follows this page. An app "
    "without zod keeps its own validation for new code too."
)


def _fix(env, name, changes):
    state = {"kind": "fix", "why": "Use shared request schemas",
             "done_when": "New request input follows the API convention"}
    return env.start(name, f"fix/{name}", f".factory/fixes/{name}.json", state, changes)


def _worker_brief(env, item):
    log = install_claude(env.repo)
    worked = env.repo.forge("work", item)
    assert worked.returncode == 0, worked.stdout + worked.stderr
    return calls(log)[-1]["brief"]


def _conventions(brief):
    match = re.search(r"how-to.*?is in `([^`]+)`", brief, re.S)
    assert match, brief
    return Path(match[1])


@pytest.mark.parametrize("adopted", [False, True], ids=["new-client", "adopted-v1.2.2"])
def test_4_the_api_and_backend_pages_name_zod_for_request_input(env, tmp_path, adopted):
    setup_client(env, tmp_path, adopted)
    item, _ = _fix(env, "request-guidance", {"app.py": "print('guidance')\n"})
    pages = _conventions(_worker_brief(env, item))
    api = " ".join((pages / "api.md").read_text(encoding="utf-8").split())
    backend = " ".join((pages / "backend.md").read_text(encoding="utf-8").split())
    security = " ".join((pages / "security.md").read_text(encoding="utf-8").split())
    assert REQUEST_RULE in api
    assert "class-validator rules" not in api
    assert "new ValidationPipe(" not in api
    assert "export const listQuerySchema = z.object({" in api
    assert "z.coerce.number().int().min(1).default(1)" in api
    assert "z.coerce.number().int().min(1).max(100).default(20)" in api
    assert "ApiZodBody(schema: z.ZodType): MethodDecorator" in api
    assert "ApiZodQuery(schema: z.ZodObject): MethodDecorator" in api
    assert "io: 'input', target: 'openapi-3.0'" in api
    assert "every request schema field and response DTO field has a description and an example" in api
    assert "path and query param" in api
    assert MODULE_RULE in backend
    assert "Name request schemas `createXSchema` and `updateXSchema`" in backend
    assert "list queries `xListQuerySchema`, in `@app/shared`; name response DTOs `XResponseDto`." in backend
    assert "zod schemas for request input, and shared types" in backend
    assert "start-up: validation" not in backend
    assert "Each request schema is `.strict()`, so `ZodValidationPipe` from api.md rejects unknown fields." in security


@pytest.mark.parametrize("adopted", [False, True], ids=["new-client", "adopted-v1.2.2"])
def test_5_review_flags_new_request_input_that_zod_does_not_check(env, tmp_path, adopted):
    setup_client(env, tmp_path, adopted)
    env.repo.write("package.json", json.dumps({"dependencies": {"zod": "4.1.12"}}))
    _commit_main(env.repo, tmp_path, "Use Zod")
    env.checks(GREEN)
    path = "libs/orders/src/orders.dto.ts"
    item, _ = _fix(env, "request-input", {path:
        "import { IsString } from 'class-validator';\n"
        "export class CreateOrderDto { @IsString() name!: string; }\n"})
    assert WORKER_RULE in " ".join(_worker_brief(env, item).split())
    title = "Zod: POST /api/v1/orders"
    issue = {**finding("P1", title, path),
             "body": "Gain 4, Work 1, Harm 1\nRaise: Functional\n"
                     "Case: normal use - the new order body has no shared zod schema."}
    env.reviews(blocked(issue))
    closed = env.close(item)
    output = closed.stdout + closed.stderr
    assert closed.returncode == 1, output
    # Fixes now ask the owner at round one rather than start another worker round.
    assert "reached the round limit with open findings" in output
    assert "One more round, split or accept?" in output
    assert title in output
    assert "Gain 4, Work 1, Harm 1" in output
    assert REVIEW_RULE in " ".join(env.prompt().split())


def test_6_an_existing_app_keeps_its_current_validation(env, tmp_path):
    # Supply exact bytes: text writes translate LF to CRLF on Windows before adoption.
    # This keeps the existing byte-preservation contract independent of host newlines.
    originals = {
        "package.json": json.dumps({"dependencies": {
            "class-validator": "0.14.2", "class-transformer": "0.5.1", "zod": "4.1.12"}}).encode("utf-8"),
        "apps/api/src/main.ts": b"app.useGlobalPipes(new ValidationPipe());\n",
        "libs/projects/src/projects.dto.ts":
            b"import { IsInt } from 'class-validator';\n"
            b"export class ProjectListQueryDto { @IsInt() page = 1; }\n",
    }
    for path, content in originals.items():
        target = env.repo.path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    setup_client(env, tmp_path, True)
    for path, content in originals.items():
        assert (env.repo.path / path).read_bytes() == content
    env.checks(GREEN)
    item, where = _fix(env, "keep-validation", {"app.py": "print('updated')\n"})
    pages = _conventions(_worker_brief(env, item))
    api = (pages / "api.md").read_text(encoding="utf-8")
    assert "## In an app set up before this release" in api
    assert EXISTING_APP in " ".join(api.split())
    env.reviews(CLEAN)
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert REVIEW_RULE in " ".join(env.prompt().split())
    for path, content in originals.items():
        assert (env.repo.path / path).read_bytes() == content
        assert (where / path).read_bytes() == content
