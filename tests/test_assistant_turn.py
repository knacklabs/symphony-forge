"""The copied TypeScript assistant handles turns through its HTTP API."""
from __future__ import annotations

import json
import re
import shutil
import sys
import threading
import uuid
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from test_assistant_chats import _assistant_client, _run_assistant_app
from test_mcp import _adopted_files_after_sync
from test_starter_tree import LIVE, _require_cases

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "src/forge/templates/skills/agents/assistant-module/typescript"
TURN_SPEC = Path("apps/api/test/assistant-turn.e2e-spec.ts")
STORY = "FORGE-ASSIST-1-TSTURN"
TURN_SETTINGS = {
    "ASSISTANT_AI_KEY": "test-key",
    "ASSISTANT_MODEL": "test-model",
    "ASSISTANT_SPEND_CAP_USD": "10",
    "ASSISTANT_PRICE_INPUT_USD_PER_MTOK": "1",
    "ASSISTANT_PRICE_OUTPUT_USD_PER_MTOK": "1",
}
TURN_CASES = {
    1: (
        "a question about projects streams text and a table block of the person's own projects",
        "a question about one project streams its detail card",
        "a stand-in report tool streams a chart block and stat tiles",
        "a tool with no display entry streams its summary text only",
        "the stream never carries markup that the model wrote",
        "a message over 4000 characters gets 400 VALIDATION_ERROR",
        "a password or a card number is refused and reaches no model call or checkpoint",
    ),
    2: (
        "a write stops at a confirm card and changes nothing",
        "confirm makes the change once",
        "confirm sent twice makes one change",
        "a message sent again with the same Idempotency-Key runs one turn",
        "cancel changes nothing and tells the model",
        "a confirm after 15 minutes runs nothing",
        "a second message while a turn runs gets 409",
        "two changes asked at once give one card at a time: confirm the first, cancel the second, and only the first is saved",
        "a confirmId that is not the open one gets 409 and runs nothing",
    ),
    3: (
        "the assistant lists only what the person's role allows",
        "a person without the permission gets the tool's plain refusal",
        "a change made through the assistant is in the history as the person, via the assistant",
        "the model cannot choose another user",
    ),
    4: (
        "another person's chat id on the message endpoint gets 404 before any model call",
        "another person's chat id and confirmId on the confirm endpoint get 404 and the pending write does not run",
    ),
    5: (
        "a used-up cap streams the limit line and the app's other routes work",
        "each turn writes one usage row for the person with its cost",
        "each turn logs one line with the prompt version and a hashed account id and no message text",
    ),
}
_TURN_RUN = None
_TURN_CLIENT = None
_TURN_PREPARED = False
_SECRET = re.compile(r"(?i)\b(password|passcode|card number)\b|(?:\d[ -]*?){13,19}")
_CASE = re.compile(r"\bcase:([a-z0-9-]+)", re.IGNORECASE)


class _AssistantProviderHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, _format, *_args):
        pass

    def do_GET(self):
        parsed = urlsplit(self.path)
        if parsed.path != "/calls":
            self.send_error(404)
            return
        case = parse_qs(parsed.query).get("case", [""])[0]
        with self.server.state_lock:
            count = self.server.calls[case]
        self._json(200, {"count": count})

    def do_POST(self):
        parsed = urlsplit(self.path)
        if parsed.path == "/release":
            case = parse_qs(parsed.query).get("case", [""])[0]
            with self.server.state_lock:
                self.server.releases.setdefault(case, threading.Event()).set()
            self._json(200, {"released": True})
            return
        if parsed.path != "/v1/chat/completions":
            self.send_error(404)
            return

        length = int(self.headers.get("Content-Length", "0"))
        try:
            body = json.loads(self.rfile.read(length))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self.send_error(400)
            return
        messages = body.get("messages", [])
        user_text = _last_user_text(messages)
        case, arguments = _case_and_arguments(user_text)
        with self.server.state_lock:
            self.server.calls[case] += 1
            call_number = self.server.calls[case]
            release = self.server.releases.setdefault(case, threading.Event())
        if case == "concurrent" and call_number == 1:
            release.wait(120)

        tool_calls = _model_tool_calls(case, arguments, messages)
        if tool_calls:
            self._stream(body, {"tool_calls": tool_calls}, "tool_calls", 30, 10)
        else:
            answer = _model_answer(case, messages) or {
                "projects": "Here are your projects.",
                "report": "The report shows three projects.",
                "summary": "This tool has no display entry.",
                "detail": "Here are the project details.",
                "markup": '<script>alert("xss")</script>',
                "write": "The change has been handled.",
                "cancel": "The person cancelled this change.",
                "two-writes": "The requested changes have been handled.",
                "permission": "The project was not changed.",
                "other-user": "Here are your projects.",
                "usage": "Usage recorded.",
                "limit": "This answer should not be requested.",
                "concurrent": "The delayed answer is ready.",
            }.get(case, "I could not answer that request.")
            self._stream(body, {"content": answer}, "stop", 30, 10)

    def _json(self, status, value):
        data = json.dumps(value).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(data)

    def _stream(self, request, delta, finish_reason, input_tokens, output_tokens):
        model = request.get("model", "test-model")
        completion_id = f"chatcmpl-{uuid.uuid4().hex}"
        created = 1_800_000_000
        chunks = [
            {"id": completion_id, "object": "chat.completion.chunk", "created": created,
             "model": model, "choices": [{"index": 0, "delta": delta,
                                             "finish_reason": finish_reason}]},
            {"id": completion_id, "object": "chat.completion.chunk", "created": created,
             "model": model, "choices": [], "usage": {
                 "prompt_tokens": input_tokens, "completion_tokens": output_tokens,
                 "total_tokens": input_tokens + output_tokens,
             }},
        ]
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()
        for chunk in chunks:
            self.wfile.write(f"data: {json.dumps(chunk, separators=(',', ':'))}\n\n".encode())
            self.wfile.flush()
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()
        self.close_connection = True


class _AssistantProvider:
    def __init__(self):
        self.server = ThreadingHTTPServer(("0.0.0.0", 0), _AssistantProviderHandler)
        self.server.daemon_threads = True
        self.server.calls = Counter()
        self.server.releases = {}
        self.server.state_lock = threading.Lock()
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    @property
    def url(self):
        return f"http://127.0.0.1:{self.server.server_port}"

    @property
    def container_url(self):
        return f"http://host.docker.internal:{self.server.server_port}/v1"

    def close(self):
        with self.server.state_lock:
            for event in self.server.releases.values():
                event.set()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        assert not self.thread.is_alive(), "assistant test provider did not stop"


@pytest.fixture(scope="module")
def assistant_test_provider():
    provider = _AssistantProvider()
    try:
        yield provider
    finally:
        provider.close()


def _last_user_text(messages):
    for message in reversed(messages):
        if message.get("role") != "user":
            continue
        content = message.get("content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "".join(part.get("text", "") for part in content if isinstance(part, dict))
    return ""


def _case_and_arguments(text):
    if _SECRET.search(text) and not _CASE.search(text):
        return "secret", {}
    match = _CASE.search(text)
    if not match:
        return "unknown", {}
    suffix = text[match.end():].strip()
    if suffix.startswith("{"):
        try:
            return match.group(1).lower(), json.loads(suffix)
        except json.JSONDecodeError:
            pass
    if match.group(1).lower() == "detail":
        return "detail", {"project_id": suffix.split()[0] if suffix else ""}
    return match.group(1).lower(), {}


def _model_tool_calls(case, arguments, messages):
    turn_messages = _messages_after_last_user(messages)
    tool_messages = [message for message in turn_messages if message.get("role") == "tool"]
    if case == "two-writes" and tool_messages:
        # The initial reply has a deferred call and the first real result. A
        # third receipt means the reissued second action has also finished.
        if len(tool_messages) > 2:
            return []
        deferred = next((message for message in tool_messages
                         if "This action has not run. Request it separately" in str(message.get("content", ""))), None)
        if deferred:
            call_id = deferred.get("tool_call_id")
            original = next((call for message in turn_messages
                             if message.get("role") == "assistant"
                             for call in message.get("tool_calls", []) if call.get("id") == call_id), None)
            if original:
                function = original.get("function", {})
                try:
                    args = json.loads(function.get("arguments", "{}"))
                except json.JSONDecodeError:
                    return []
                return [_tool_call(function.get("name", "projects_create"), args)]
        return []
    if tool_messages:
        return []
    if case == "projects":
        return [_tool_call("projects_search", _with_response_format(arguments))]
    if case == "report":
        return [_tool_call("demo_report", {})]
    if case == "summary":
        return [_tool_call("demo_summary", {})]
    if case == "detail":
        return [_tool_call("projects_get", {
            "project_id": arguments.get("project_id", ""), "response_format": "concise",
        })]
    if case in ("write", "cancel"):
        return [_tool_call("projects_create", _with_response_format(arguments))]
    if case == "identity":
        return [_tool_call("projects_search", _with_response_format({
            **arguments, "account_id": arguments.get("account_id", "another-account-id"),
        }))]
    if case == "other-user":
        if "name" in arguments:
            return [_tool_call("projects_create", _with_response_format(arguments))]
        return [_tool_call("projects_search", _with_response_format({
            **arguments, "account_id": arguments.get("account_id", "another-account-id"),
        }))]
    if case == "two-writes":
        first = arguments.get("firstName", arguments.get("first_name", arguments.get("first", "Assistant first")))
        second = arguments.get("secondName", arguments.get("second_name", arguments.get("second", "Assistant second")))
        return [
            _tool_call("projects_create", {"name": first, "status": "active", "response_format": "concise"}, 0),
            _tool_call("projects_create", {"name": second, "status": "active", "response_format": "concise"}, 1),
        ]
    if case == "permission":
        return [_tool_call("projects_update", _with_response_format(arguments))]
    return []


def _messages_after_last_user(messages):
    last_user = max((index for index, message in enumerate(messages)
                     if message.get("role") == "user"), default=-1)
    return messages[last_user + 1:]


def _model_answer(case, messages):
    tool_text = "\n".join(str(message.get("content", "")) for message in
                          _messages_after_last_user(messages) if message.get("role") == "tool")
    if case == "cancel" and "cancelled" in tool_text.lower():
        return "I left the project unchanged."
    if case == "permission" and "Your agent account's role cannot use projects_update." in tool_text:
        return ("Your agent account's role cannot use projects_update. An admin can change its role "
                "on the Members screen.")
    if case == "other-user" and "Received tool input did not match expected schema" in tool_text:
        return "Received tool input did not match expected schema"
    return None


def _with_response_format(arguments):
    return {**arguments, "response_format": "concise"}


def _tool_call(name, arguments, index=0):
    return {"index": index, "id": f"call_{uuid.uuid4().hex}", "type": "function",
            "function": {"name": name, "arguments": json.dumps(arguments, separators=(",", ":"))}}


def _replace_once(path: Path, old: str, new: str):
    source = path.read_text(encoding="utf-8")
    if source.count(old) != 1:
        raise AssertionError(f"copy setup did not match one location in {path}")
    path.write_text(source.replace(old, new), encoding="utf-8")


def _turn_app(client: Path, provider: _AssistantProvider):
    shutil.copyfile(TEMPLATE / TURN_SPEC, client / TURN_SPEC)
    test_tools = client / "apps/api/src/assistant-test-tools.ts"
    test_tools.write_text(
        """import { defineTool } from '@app/core-server';
import { z } from 'zod';

defineTool({
  name: 'demo_report', feature: 'projects', permission: 'projects.view',
  description: 'Read the stand-in project report for the assistant test.',
  input: z.object({}),
  output: z.object({
    months: z.array(z.object({ month: z.string(), total: z.number() })), total: z.number(),
  }),
  annotations: {
    title: 'Read project report', readOnlyHint: true, destructiveHint: false,
    idempotentHint: true, openWorldHint: false,
  },
  call: async () => ({ summary: 'The report is ready.', data: { months: [{ month: 'Nov', total: 3 }], total: 3 } }),
});

defineTool({
  name: 'demo_summary', feature: 'projects', permission: 'projects.view',
  description: 'Read the stand-in summary without a display block.',
  input: z.object({}), output: z.object({}),
  annotations: {
    title: 'Read summary', readOnlyHint: true, destructiveHint: false,
    idempotentHint: true, openWorldHint: false,
  },
  call: async () => ({ summary: 'This tool has no display entry.', data: {} }),
});
""",
        encoding="utf-8",
    )
    app_module = client / "apps/api/src/app.module.ts"
    _replace_once(app_module, "import { McpModule } from '@app/mcp-server';\n", (
        "import { McpModule } from '@app/mcp-server';\n"
        "import './assistant-test-tools';\n"
    ))
    display = client / "libs/assistant/server/src/assistant.display.ts"
    _replace_once(display, "  projects_restore: detail,\n", """  projects_restore: detail,
  demo_report: (data) => {
    const report = z.object({
      months: z.array(z.object({ month: z.string(), total: z.number() })),
      total: z.number(),
    }).parse(data);
    return [
      { kind: 'chart', props: { type: 'line', xKey: 'month', series: [{ key: 'total', label: 'Total' }],
        rows: report.months, unit: 'projects' } },
      { kind: 'stats', props: { tiles: [{ label: 'Total projects', value: report.total, unit: 'projects' }] } },
    ];
  },
""")

    package = client / "package.json"
    data = json.loads(package.read_text(encoding="utf-8"))
    data["scripts"]["test:api"] = (
        "vitest run --config apps/api/vitest.config.ts apps/api/test/assistant-turn.e2e-spec.ts"
    )
    package.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    compose = client / "compose.test.yml"
    source = compose.read_text(encoding="utf-8")
    port_marker = '      PORT: "3000"\n'
    if source.count(port_marker) != 3:
        raise AssertionError(f"copy setup did not match all API services in {compose}")
    source = source.replace(port_marker, port_marker + f"      ASSISTANT_AI_URL: {provider.container_url}\n")
    if sys.platform == "linux":
        for service in ("api", "one-company-api", "production-api"):
            marker = f"  {service}:\n    build: .\n"
            if source.count(marker) != 1:
                raise AssertionError(f"copy setup did not match the {service} service in {compose}")
            source = source.replace(marker, marker + '    extra_hosts:\n      - "host.docker.internal:host-gateway"\n')
    compose.write_text(source, encoding="utf-8")


@pytest.fixture
def assistant_turn_run(repo, gh, tmp_path, tmp_path_factory, monkeypatch, assistant_test_provider):
    """Own one copied-app run per pytest process, shared by all five boundary tests."""
    global _TURN_RUN, _TURN_CLIENT, _TURN_PREPARED
    if not LIVE:
        return None
    if _TURN_RUN is None:
        if _TURN_CLIENT is None:
            _TURN_CLIENT = _assistant_client(repo, gh, tmp_path)
        client = _TURN_CLIENT
        if not _TURN_PREPARED:
            _turn_app(client, assistant_test_provider)
            _TURN_PREPARED = True
        monkeypatch.setenv("ASSISTANT_TEST_PROVIDER_URL", assistant_test_provider.url)
        _TURN_RUN = _run_assistant_app(
            client, tmp_path_factory, monkeypatch, settings=TURN_SETTINGS,
        )
    return _TURN_RUN


_COPIED_TURN_FILES = (
        "libs/assistant/server/src/assistant.agent.ts",
        "libs/assistant/server/src/assistant.turn.ts",
        "libs/assistant/server/src/assistant.display.ts",
        "libs/assistant/server/src/assistant.turn.controller.ts",
        "libs/assistant/server/src/assistant.module.ts",
        "libs/assistant/server/src/index.ts",
        "apps/api/test/assistant-turn.e2e-spec.ts",
)


@pytest.mark.platform
@pytest.mark.timeout(1800)
@pytest.mark.parametrize("app", ["typescript", "earlier adopted"])
def test_1_a_person_asks_and_reads_text_and_blocks(repo, gh, tmp_path, app, request):
    # Audit: protects the real stream and copy/upgrade boundaries. Existing model and chat cases
    # cover configuration and storage, not text, typed blocks, or copied turn endpoints. The
    # live test uses a fake only at the model-provider edge and real MCP tools and Postgres.
    # No test-only production seam is added; report tools live only in the throwaway test app.
    if app == "earlier adopted":
        before, after = _adopted_files_after_sync(repo)
        assert after == before
        for host in (".codex", ".claude"):
            delivered = repo.path / host / "skills/agents/assistant-module/typescript"
            assert (delivered / "apps/api/test/assistant-turn.e2e-spec.ts").is_file()
        return

    global _TURN_CLIENT, _TURN_PREPARED
    _TURN_CLIENT = _assistant_client(repo, gh, tmp_path)
    shutil.copyfile(TEMPLATE / TURN_SPEC, _TURN_CLIENT / TURN_SPEC)
    for relative in _COPIED_TURN_FILES:
        assert (_TURN_CLIENT / relative).is_file(), f"copied app is missing {relative}"
    if not LIVE:
        return
    result = request.getfixturevalue("assistant_turn_run")
    _require_cases(result["api"], TURN_CASES[1])


@pytest.mark.platform
@pytest.mark.timeout(1800)
def test_2_every_write_waits_for_a_confirm(request):
    # Audit: protects the HTTP confirmation lifecycle, retry key and single-card rule. Existing
    # chat cases seed a pending card but do not execute writes through confirmation. The app's
    # real projects service and database own the result; the provider stub only returns model calls.
    # No test-only production seam is added.
    if not LIVE:
        pytest.skip("Set FORGE_STARTER_LIVE=1 to run the assistant API and Postgres cases")
    _require_cases(request.getfixturevalue("assistant_turn_run")["api"], TURN_CASES[2])


@pytest.mark.platform
@pytest.mark.timeout(1800)
def test_3_the_assistant_acts_as_the_person(request):
    # Audit: protects permission checks, identity binding and change history over a real turn.
    # Existing MCP and history cases do not cover an assistant turn. The copied app uses its own
    # signed-in users and real history service; no test-only production seam is added.
    if not LIVE:
        pytest.skip("Set FORGE_STARTER_LIVE=1 to run the assistant API and Postgres cases")
    _require_cases(request.getfixturevalue("assistant_turn_run")["api"], TURN_CASES[3])


@pytest.mark.platform
@pytest.mark.timeout(1800)
def test_4_other_peoples_chats_cannot_be_written_to(request):
    # Audit: protects the chat owner check at both turn entry points. Existing chat tests prove
    # private reads, but not that a foreign chat id stops model calls and pending writes.
    # The test uses real HTTP ownership checks, Postgres and tools; no test-only production seam.
    if not LIVE:
        pytest.skip("Set FORGE_STARTER_LIVE=1 to run the assistant API and Postgres cases")
    _require_cases(request.getfixturevalue("assistant_turn_run")["api"], TURN_CASES[4])


@pytest.mark.platform
@pytest.mark.timeout(1800)
def test_5_a_used_up_cap_shows_one_line(request):
    # Audit: protects the full turn's cap stop, usage row and safe trace. Model tests cover
    # settings and arithmetic but not the live turn path or the app's continued availability.
    # The copied app records usage through AssistantUsage; the provider stub does not decide it.
    # No test-only production seam is added.
    if not LIVE:
        pytest.skip("Set FORGE_STARTER_LIVE=1 to run the assistant API and Postgres cases")
    _require_cases(request.getfixturevalue("assistant_turn_run")["api"], TURN_CASES[5])
