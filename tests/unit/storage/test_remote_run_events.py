# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""RemoteBackend.send_run_events: the executor's POST /run/{id}/events."""

from __future__ import annotations

import json
from uuid import uuid4

import httpx
import pytest

from hackagent.storage._http.client import AuthenticatedClient
from hackagent.storage.remote import (
    ExecutorRejected,
    RemoteBackend,
    RunAlreadyFinished,
    RunEventsUnsupported,
)

EVENT = {
    "seq": 1,
    "time": "2026-11-11T10:00:00+00:00",
    "level": "info",
    "kind": "goal",
    "attack": "pair",
    "attack_run": None,
    "goal_index": 0,
    "message": "pair · goal 1/1 · 1 attempt · 0 successful",
    "data": {},
}


def backend(status: int, body: object, seen: list[httpx.Request]) -> RemoteBackend:
    def answer(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(status, json=body)

    client = AuthenticatedClient(
        base_url="https://api.example/api",
        token="run-token",
        prefix="Bearer",
        httpx_args={"transport": httpx.MockTransport(answer)},
    )
    return RemoteBackend(client)


def test_sends_the_batch_with_the_executor_s_key():
    seen: list[httpx.Request] = []
    run_id = uuid4()
    store = backend(
        200, {"accepted": 1, "duplicates": 0, "dropped": 0, "last_seq": 1}, seen
    )
    try:
        result = store.send_run_events(run_id, [EVENT])
    finally:
        store.close(close_client=True)

    [request] = seen
    assert request.method == "POST"
    assert request.url.path == f"/api/run/{run_id}/events"
    assert request.headers["Authorization"] == "Bearer run-token"
    assert json.loads(request.content) == {"events": [EVENT]}
    assert result["accepted"] == 1


@pytest.mark.parametrize(
    ("status", "error"),
    [
        (401, ExecutorRejected),
        (403, ExecutorRejected),
        (409, RunAlreadyFinished),
        (404, RunEventsUnsupported),
        (405, RunEventsUnsupported),
        (400, ValueError),
        (502, RuntimeError),
    ],
)
def test_each_refusal_has_its_own_error(status, error):
    store = backend(status, {"events": {"0": {"level": ["not valid"]}}}, [])
    try:
        with pytest.raises(error):
            store.send_run_events(uuid4(), [EVENT])
    finally:
        store.close(close_client=True)
