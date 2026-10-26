# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""One claimed cloud run, executed in the process the worker starts for it."""

from __future__ import annotations

import asyncio
import io
import json
import os
import signal
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import httpx
import pytest

from hackagent.interfaces import worker_run
from hackagent.models import ModelConfig, build_model
from hackagent.orchestrator.execution.execute import ExecutionOutcome

RUN_ID = str(uuid4())


@pytest.fixture(autouse=True)
def _process(monkeypatch):
    monkeypatch.setattr(os, "environ", dict(os.environ))
    monkeypatch.setenv("HACKAGENT_BASE_URL", "https://api.example")
    monkeypatch.setattr(worker_run, "setup_package_logging", lambda **_: None)
    before = signal.getsignal(signal.SIGTERM)
    yield
    signal.signal(signal.SIGTERM, before)


def _stdin() -> io.StringIO:
    return io.StringIO(
        json.dumps(
            {
                "run": {"id": RUN_ID},
                "run_token": "hart_x",
                "claimed_by": "cloud-worker:h",
            }
        )
    )


def _main(execute) -> tuple[int, MagicMock, MagicMock]:
    store = MagicMock(name="run_store")
    connect = MagicMock(return_value=store)
    with (
        patch.object(worker_run.RemoteBackend, "connect", connect),
        patch.object(worker_run, "execute_run", execute),
    ):
        code = worker_run.main(_stdin())
    return code, connect, store


def test_the_claim_is_executed_with_its_run_token():
    execute = MagicMock(return_value=ExecutionOutcome("COMPLETED", ""))
    code, connect, store = _main(execute)
    assert code == worker_run.EXIT_COMPLETED
    connect.assert_called_once_with("https://api.example", "hart_x")
    args, kwargs = execute.call_args
    assert args == (store, UUID(RUN_ID))
    assert kwargs["base_url"] == "https://api.example"
    assert kwargs["gateway_key"] == "hart_x"
    assert kwargs["claimed_by"] == "cloud-worker:h"
    assert kwargs["claim"].run == {"id": RUN_ID}
    assert kwargs["claim"].run_token == "hart_x"
    # Stopping the worker mid-run fails the run rather than cancelling it.
    assert kwargs["interrupted_as"] == ("FAILED", worker_run.STOPPED_NOTE)
    store.close.assert_called_once_with(close_client=True)


@pytest.mark.parametrize("status", ["FAILED", "CANCELLED"])
def test_a_run_that_ended_otherwise_exits_ended(status):
    code, _, _ = _main(MagicMock(return_value=ExecutionOutcome(status, "x")))
    assert code == worker_run.EXIT_ENDED


def test_sigterm_ends_the_run_and_exits_ended():
    def execute(*args, **kwargs):
        os.kill(os.getpid(), signal.SIGTERM)
        raise AssertionError("SIGTERM should have interrupted the run")

    code, _, store = _main(MagicMock(side_effect=execute))
    assert code == worker_run.EXIT_ENDED
    store.close.assert_called_once_with(close_client=True)


def test_an_error_escapes_so_the_worker_finishes_the_run():
    with pytest.raises(RuntimeError):
        _main(MagicMock(side_effect=RuntimeError("boom")))


def test_no_redirect_is_followed_during_the_run():
    seen = {}

    def execute(*args, **kwargs):
        seen["send"] = (httpx.Client.send, httpx.AsyncClient.send)
        return ExecutionOutcome("COMPLETED", "")

    originals = (httpx.Client.send, httpx.AsyncClient.send)
    _main(MagicMock(side_effect=execute))
    assert seen["send"] != originals
    assert (httpx.Client.send, httpx.AsyncClient.send) == originals


REPLY = json.dumps(
    {
        "id": "x",
        "object": "chat.completion",
        "created": 0,
        "model": "m",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "hi"},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }
).encode()


def _server(hits: list, tag: str, redirect_to=None) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            self.rfile.read(int(self.headers.get("content-length") or 0))
            hits.append(tag)
            if redirect_to is not None:
                self.send_response(307)
                self.send_header("Location", redirect_to() + self.path)
                self.send_header("content-length", "0")
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(REPLY)))
            self.end_headers()
            self.wfile.write(REPLY)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


# LiteLLM's own logger warns when the sync call finds no event loop.
@pytest.mark.filterwarnings("ignore:There is no current event loop:DeprecationWarning")
@pytest.mark.parametrize(
    ("name", "model_type", "path"),
    [
        ("gpt-4o", "OPENAI", "/v1"),
        ("hosted_vllm/m", "LITELLM", "/v1"),
        ("llama3", "OLLAMA", ""),
    ],
)
def test_a_redirecting_endpoint_is_a_model_error(name, model_type, path):
    hits: list[str] = []
    other = _server(hits, "other")
    endpoint = _server(
        hits, "endpoint", redirect_to=lambda: f"http://127.0.0.1:{other.server_port}"
    )
    try:
        model = build_model(
            ModelConfig.model_validate(
                {
                    "name": name,
                    "connection": {
                        "provider": "p",
                        "type": model_type,
                        "endpoint": f"http://127.0.0.1:{endpoint.server_port}{path}",
                        "api_key": "test-key",
                    },
                }
            )
        )
        messages = [{"role": "user", "content": "x"}]
        with worker_run.redirects_refused():
            reply = model.complete(messages)
            areply = asyncio.run(model.acomplete(messages))
    finally:
        endpoint.shutdown()
        other.shutdown()
    assert reply.error is not None
    assert areply.error is not None
    assert hits and set(hits) == {"endpoint"}
