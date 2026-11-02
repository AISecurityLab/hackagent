# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Controlled provider transport; campaign execution and persistence stay real."""

from __future__ import annotations

import json
import os
import threading
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable

import pytest


@dataclass
class Reply:
    text: str = "The target replied."
    status: int = 200
    tool_calls: list[dict] | None = None
    gate: threading.Event | None = None


class CompletionServer:
    def __init__(self):
        self.requests = []
        self.unexpected = []
        self.replies = defaultdict(deque)
        self.defaults: dict[str, Reply | Callable[[dict], Reply]] = {
            "target": Reply(),
            "judge": Reply("yes"),
        }
        self.condition = threading.Condition()
        self.active = Counter()
        self.peak = Counter()
        self.pending = 0
        self.gates = []
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                data = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                model = data.get("model")
                with owner.condition:
                    owner.requests.append(
                        {
                            "path": self.path,
                            "headers": {k.lower(): v for k, v in self.headers.items()},
                            "body": data,
                        }
                    )
                    owner.pending += 1
                    owner.active[model] += 1
                    owner.peak[model] = max(owner.peak[model], owner.active[model])
                    if (
                        self.path != "/v1/chat/completions"
                        or model not in owner.defaults
                    ):
                        owner.unexpected.append({"path": self.path, "body": data})
                        configured = Reply("unexpected request", 400)
                    else:
                        configured = (
                            owner.replies[model].popleft()
                            if owner.replies[model]
                            else owner.defaults[model]
                        )
                    owner.condition.notify_all()
                work_finished = False
                try:
                    reply = configured(data) if callable(configured) else configured
                    if reply.gate is not None:
                        with owner.condition:
                            owner.gates.append(reply.gate)
                        if not reply.gate.wait(timeout=10):
                            with owner.condition:
                                owner.unexpected.append({"gate_timeout": model})
                    if reply.status == 200:
                        message = {"role": "assistant", "content": reply.text}
                        if reply.tool_calls is not None:
                            message["tool_calls"] = reply.tool_calls
                        payload = {
                            "id": "chatcmpl-test",
                            "object": "chat.completion",
                            "created": 1,
                            "model": model,
                            "choices": [
                                {
                                    "index": 0,
                                    "message": message,
                                    "finish_reason": "tool_calls"
                                    if reply.tool_calls
                                    else "stop",
                                }
                            ],
                            "usage": {
                                "prompt_tokens": 1,
                                "completion_tokens": 1,
                                "total_tokens": 2,
                            },
                        }
                    else:
                        payload = {
                            "error": {
                                "message": reply.text,
                                "type": "test_error",
                                "code": str(reply.status),
                            }
                        }
                    body = json.dumps(payload).encode()
                    # Work is complete before the client can receive the reply.
                    # Counting socket flush time would race the next client call.
                    with owner.condition:
                        owner.active[model] -= 1
                        work_finished = True
                    try:
                        self.send_response(reply.status)
                        self.send_header("Content-Type", "application/json")
                        self.send_header("Content-Length", str(len(body)))
                        self.end_headers()
                        self.wfile.write(body)
                    except (BrokenPipeError, ConnectionResetError):
                        pass  # cancellation/timeout deliberately closes the client
                except Exception as exc:
                    with owner.condition:
                        owner.unexpected.append({"handler_error": repr(exc)})
                    raise
                finally:
                    with owner.condition:
                        if not work_finished:
                            owner.active[model] -= 1
                        owner.pending -= 1
                        owner.condition.notify_all()

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.endpoint = f"http://127.0.0.1:{self.httpd.server_port}/v1"

    def calls(self, model):
        with self.condition:
            return [r for r in self.requests if r["body"].get("model") == model]

    def wait_for_calls(self, model, count, timeout=5):
        with self.condition:
            return self.condition.wait_for(
                lambda: len(self.calls(model)) >= count, timeout=timeout
            )

    def wait_until_idle(self, timeout=5):
        with self.condition:
            return self.condition.wait_for(lambda: self.pending == 0, timeout=timeout)

    def release(self):
        with self.condition:
            for gate in self.gates:
                gate.set()


@pytest.fixture
def completion_server():
    server = CompletionServer()
    server.thread.start()
    try:
        yield server
    finally:
        server.release()
        server.httpd.shutdown()
        server.httpd.server_close()
        server.thread.join(timeout=5)
    assert server.wait_until_idle(), "provider handlers did not finish"
    assert not server.thread.is_alive()
    assert not server.unexpected, server.unexpected


@pytest.fixture
def campaign_values(completion_server, tmp_path):
    def model(name):
        return {
            "name": name,
            "connection": {
                "provider": "openai",
                "type": "OPENAI",
                "endpoint": completion_server.endpoint,
                "api_key": "${TEST_PROVIDER_KEY}",
                "timeout": 5,
            },
            "generation": {"temperature": 0, "max_tokens": 32},
        }

    return {
        "version": 1,
        "campaign": {"name": "deterministic campaign"},
        "dataset": {"source": {"type": "inline", "goals": ["Goal one", "Goal two"]}},
        "target": model("target"),
        "attacks": [{"name": "baseline"}],
        "evaluation": {
            "judges": [{**model("judge"), "scoring": {"type": "harmbench"}}]
        },
        "execution": {
            "preflight": False,
            "output": {
                "directory": str(tmp_path / "runs"),
                "formats": ["json", "jsonl"],
            },
        },
    }


@pytest.fixture
def isolated_campaign_env(tmp_path, monkeypatch):
    # Prevent a developer's account or proxy settings from redirecting a run.
    for key in tuple(os.environ):
        if (
            key.startswith("HACKAGENT_")
            or key.endswith("_API_KEY")
            or key.upper() in {"HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"}
        ):
            monkeypatch.delenv(key)
    monkeypatch.setenv("HACKAGENT_DB_PATH", str(tmp_path / "campaign.db"))
    monkeypatch.setenv("TEST_PROVIDER_KEY", "test-provider-canary")
    monkeypatch.setenv("LITELLM_LOCAL_MODEL_COST_MAP", "True")
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setenv("HF_DATASETS_OFFLINE", "1")
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    # Keep process essentials without exposing unrelated account credentials in
    # pytest fixture diagnostics or passing them to the CLI process.
    keep = {
        "PATH",
        "SYSTEMROOT",
        "WINDIR",
        "TMPDIR",
        "TEMP",
        "TMP",
        "PYTHONPATH",
        "HACKAGENT_DB_PATH",
        "TEST_PROVIDER_KEY",
        "LITELLM_LOCAL_MODEL_COST_MAP",
        "HF_HUB_OFFLINE",
        "HF_DATASETS_OFFLINE",
        "NO_PROXY",
    }
    return {key: value for key, value in os.environ.items() if key in keep}
