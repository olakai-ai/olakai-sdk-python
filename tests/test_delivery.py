"""End-to-end delivery tests against a local stub HTTP server.

Covers the background sender (sync + async callers, flush, atexit),
provider-key exclusion, provider detection, and modelName.
Only fake keys are used.
"""

import asyncio
import json
import os
import subprocess
import sys
import threading
import time
import warnings
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace

import pytest
import requests as real_requests

from src.olakaisdk import (
    OlakaiEventParams,
    instrument_openai,
    olakai_config,
    olakai_event,
    olakai_flush,
    uninstrument_openai,
)
from src.olakaisdk.client import api

SENTINEL = "sk-test-SENTINEL"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

COMPLETION = {
    "id": "chatcmpl-1",
    "object": "chat.completion",
    "created": 0,
    "model": "gpt-4o-mini",
    "choices": [
        {
            "index": 0,
            "message": {"role": "assistant", "content": "hi"},
            "finish_reason": "stop",
        }
    ],
    "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
}
MONITOR_OK = {
    "success": True,
    "totalRequests": 1,
    "successCount": 1,
    "failureCount": 0,
}


class Stub:
    """Fake Olakai monitoring endpoint + fake OpenAI chat endpoint."""

    def __init__(self) -> None:
        self.bodies: list = []
        self.monitor_delay = 0.0
        self.openai_status = 200
        stub = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args: object) -> None:
                pass

            def do_POST(self) -> None:
                raw = self.rfile.read(int(self.headers["Content-Length"]))
                if self.path.startswith("/api/monitoring"):
                    time.sleep(stub.monitor_delay)
                    stub.bodies.append(raw.decode())
                    self._send(200, MONITOR_OK)
                elif stub.openai_status != 200:
                    self._send(stub.openai_status, {"error": {"message": "x"}})
                else:
                    self._send(200, COMPLETION)

            def _send(self, status: int, body: dict) -> None:
                data = json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def events(self) -> list:
        return [json.loads(b) for b in self.bodies]


@pytest.fixture
def stub(monkeypatch):
    monkeypatch.setattr(api, "requests", real_requests)  # undo conftest
    s = Stub()
    olakai_config("olakai-test-key", endpoint=s.url)
    yield s
    olakai_flush(timeout=10)
    s.server.shutdown()
    uninstrument_openai()


def _assert_no_provider_key(stub: Stub) -> None:
    assert stub.bodies
    for body in stub.bodies:
        assert SENTINEL not in body
        assert '"api_key"' not in body
        assert '"apiKey"' not in body


def test_sync_openai_call_is_delivered(stub):
    import openai

    instrument_openai()
    client = openai.OpenAI(api_key=SENTINEL, base_url=stub.url + "/v1")
    client.chat.completions.create(
        model="gpt-4o-mini", messages=[{"role": "user", "content": "hello"}]
    )
    assert olakai_flush(timeout=5)
    [event] = stub.events()
    assert event["prompt"] == "hello"
    assert event["modelName"] == "gpt-4o-mini"
    assert event["customData"]["provider"] == "127.0.0.1"


def test_async_call_does_not_wait_for_slow_endpoint(stub):
    import openai

    stub.monitor_delay = 3.0
    instrument_openai()
    client = openai.AsyncOpenAI(api_key=SENTINEL, base_url=stub.url + "/v1")

    async def call() -> float:
        # Warm up the connection so we time only the SDK overhead.
        await client.chat.completions.create(model="m", messages=[])
        start = time.monotonic()
        await client.chat.completions.create(model="m", messages=[])
        return time.monotonic() - start

    assert asyncio.run(call()) < 0.5
    assert olakai_flush(timeout=10)
    assert len(stub.events()) == 2


def test_event_then_flush_is_delivered(stub):
    olakai_event(OlakaiEventParams(prompt="p", response="r"))
    assert olakai_flush(timeout=5)
    [event] = stub.events()
    assert event["prompt"] == "p"


def test_flush_returns_false_on_timeout(stub):
    stub.monitor_delay = 1.0
    olakai_event(OlakaiEventParams(prompt="p", response="r"))
    assert olakai_flush(timeout=0.1) is False


def test_atexit_delivers_on_process_exit(stub):
    code = (
        "from olakaisdk import olakai_config, olakai_event, "
        "OlakaiEventParams\n"
        f"olakai_config('k', endpoint='{stub.url}')\n"
        "olakai_event(OlakaiEventParams(prompt='exit', response='r'))\n"
    )
    env = dict(os.environ, PYTHONPATH=os.path.join(ROOT, "src"))
    subprocess.run([sys.executable, "-c", code], env=env, check=True)
    assert [e["prompt"] for e in stub.events()] == ["exit"]


def test_model_name_present_when_set_absent_when_none(stub):
    olakai_event(OlakaiEventParams(prompt="a", response="r", modelName="m1"))
    olakai_event(OlakaiEventParams(prompt="b", response="r"))
    assert olakai_flush(timeout=5)
    by_prompt = {e["prompt"]: e for e in stub.events()}
    assert by_prompt["a"]["modelName"] == "m1"
    assert "modelName" not in by_prompt["b"]


@pytest.mark.parametrize("capture", [True, False])
def test_openai_never_sends_provider_key(stub, capture):
    import openai

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        instrument_openai(capture_api_keys=capture)
    assert (
        any(issubclass(w.category, DeprecationWarning) for w in caught)
        is capture
    )

    client = openai.OpenAI(
        api_key=SENTINEL, base_url=stub.url + "/v1", max_retries=0
    )
    client.chat.completions.create(model="m", messages=[])
    stub.openai_status = 400
    with pytest.raises(openai.BadRequestError):
        client.chat.completions.create(model="m", messages=[])
    assert olakai_flush(timeout=5)
    assert len(stub.events()) == 2
    _assert_no_provider_key(stub)


def _keyed_client() -> SimpleNamespace:
    inner = SimpleNamespace(api_key=SENTINEL, _api_key=SENTINEL)
    return SimpleNamespace(
        api_key=SENTINEL, _api_key=SENTINEL, _client=inner, model_name="g"
    )


ANTHROPIC_RESPONSE = SimpleNamespace(
    content=[SimpleNamespace(text="hi", type="text")],
    model="claude",
    usage=SimpleNamespace(input_tokens=1, output_tokens=1),
)
GOOGLE_RESPONSE = SimpleNamespace(
    text="hi",
    candidates=[],
    usage_metadata=SimpleNamespace(
        prompt_token_count=1, candidates_token_count=1, total_token_count=2
    ),
)


@pytest.mark.parametrize("capture", [True, False])
@pytest.mark.parametrize(
    "module,trace,args,kwargs,response",
    [
        (
            "anthropic",
            "_trace_anthropic_call_sync",
            (),
            {"model": "claude", "messages": []},
            ANTHROPIC_RESPONSE,
        ),
        ("google", "_trace_google_call_sync", ("hi",), {}, GOOGLE_RESPONSE),
    ],
)
def test_other_providers_never_send_provider_key(
    stub, capture, module, trace, args, kwargs, response
):
    import importlib

    mod = importlib.import_module(f"src.olakaisdk.instrumentation.{module}")
    fn = getattr(mod, trace)

    def fail(*a: object, **k: object) -> None:
        raise ValueError("boom")

    fn(
        _keyed_client(),
        lambda *a, **k: response,
        args,
        kwargs,
        True,
        True,
        capture,
    )
    with pytest.raises(ValueError):
        fn(_keyed_client(), fail, args, kwargs, True, True, capture)
    assert olakai_flush(timeout=5)
    assert len(stub.events()) == 2
    _assert_no_provider_key(stub)


@pytest.mark.parametrize(
    "base_url,expected",
    [
        ("https://openrouter.ai/api/v1", "openrouter"),
        ("https://my-res.openai.azure.com/openai/", "azure"),
        ("https://api.openai.com/v1", "openai"),
        ("http://localhost:11434/v1", "localhost"),
    ],
)
def test_provider_detected_from_base_url(base_url, expected):
    import openai

    from src.olakaisdk.extractors.openai_extractor import (
        detect_openai_provider,
    )

    client = openai.OpenAI(api_key=SENTINEL, base_url=base_url)
    assert detect_openai_provider(client.chat.completions) == expected
    assert detect_openai_provider(object()) == "openai"
