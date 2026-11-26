# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""RemoteBackend over a connection the server may drop: its client sends
safe requests again, results carry a client-chosen id so their creation is
safe too once the server honours it, and a lost write does not keep a failed
run from being recorded as FAILED."""

import json
import unittest
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import httpx

from hackagent.storage._http.api.result import result_create
from hackagent.storage._http.retry import RetryingTransport
from hackagent.storage.remote import RemoteBackend

BASE = "https://api.example.com"


def _response(status_code, parsed=None, content=b"{}"):
    resp = MagicMock()
    resp.status_code = status_code
    resp.parsed = parsed
    resp.content = content
    return resp


def _created(result_id):
    parsed = MagicMock()
    parsed.id = result_id
    return parsed


def _sent_id(mock_create) -> UUID:
    kwargs = dict(mock_create.sync_detailed.call_args.kwargs)
    kwargs.pop("client")
    return UUID(result_create._get_kwargs(**kwargs)["json"]["id"])


def _create(backend):
    return backend.create_result(
        run_id=uuid4(),
        goal="g",
        goal_index=0,
        request_payload={},
        agent_specific_data={},
    )


def _post_result():
    return httpx.Request("POST", BASE + "/result", content=b"{}")


class TestConnect(unittest.TestCase):
    def test_the_client_sends_dropped_requests_again(self):
        backend = RemoteBackend.connect(BASE, "key", verify=False)
        try:
            transport = backend.client.httpx_args["transport"]
            self.assertIsInstance(transport, RetryingTransport)
            # The retry sits under httpx: it applies to every call the
            # generated endpoints make through this client.
            self.assertIs(backend.client.get_httpx_client()._transport, transport)
        finally:
            backend.close(close_client=True)

    def test_a_dropped_read_is_sent_again(self):
        calls = []

        def server(request):
            calls.append(request)
            if len(calls) == 1:
                raise httpx.RemoteProtocolError("Server disconnected")
            return httpx.Response(200, json={"count": 0, "results": []})

        backend = RemoteBackend.connect(BASE, "key")
        try:
            backend.client.get_httpx_client()._transport._inner = httpx.MockTransport(
                server
            )
            backend.client.get_httpx_client()._transport._sleep = lambda s: None
            self.assertEqual(backend.check_connection(), 200)
            self.assertEqual(len(calls), 2)
        finally:
            backend.close(close_client=True)


class TestClientChosenResultIds(unittest.TestCase):
    def setUp(self):
        self.backend = RemoteBackend(MagicMock())

    def tearDown(self):
        self.backend.close()

    def test_a_result_is_created_with_an_id_of_the_clients(self):
        with patch("hackagent.storage.remote.result_create") as mock_create:
            mock_create.sync_detailed.side_effect = lambda **kw: _response(
                201, parsed=_created(_sent_id(mock_create))
            )
            record = _create(self.backend)

        self.assertEqual(record.id, _sent_id(mock_create))

    def test_creation_is_repeatable_once_the_server_keeps_the_id(self):
        self.assertFalse(self.backend._repeatable(_post_result()))

        with patch("hackagent.storage.remote.result_create") as mock_create:
            mock_create.sync_detailed.side_effect = lambda **kw: _response(
                201, parsed=_created(_sent_id(mock_create))
            )
            _create(self.backend)

        self.assertTrue(self.backend._repeatable(_post_result()))

    def test_a_server_that_picks_its_own_id_keeps_creation_unrepeatable(self):
        server_id = uuid4()
        with patch("hackagent.storage.remote.result_create") as mock_create:
            mock_create.sync_detailed.return_value = _response(
                201, parsed=_created(server_id)
            )
            record = _create(self.backend)

        self.assertEqual(record.id, server_id)
        self.assertFalse(self.backend._repeatable(_post_result()))

    def test_a_result_stored_by_an_earlier_try_is_accepted(self):
        with patch("hackagent.storage.remote.result_create") as mock_create:
            mock_create.sync_detailed.side_effect = lambda **kw: _response(
                200, parsed=_created(_sent_id(mock_create))
            )
            record = _create(self.backend)

        self.assertEqual(record.id, _sent_id(mock_create))

    def test_the_generated_endpoint_parses_a_200(self):
        result_id = uuid4()
        body = {"id": str(result_id), "run": str(uuid4()), "run_id": str(uuid4())}
        body.update(timestamp="2026-11-26T14:27:00Z", traces=[])
        parsed = result_create._parse_response(
            client=MagicMock(raise_on_unexpected_status=False),
            response=httpx.Response(200, content=json.dumps(body).encode()),
        )
        self.assertEqual(parsed.id, result_id)

    def test_other_calls_keep_the_default_policy(self):
        self.assertTrue(
            self.backend._repeatable(httpx.Request("GET", BASE + "/run/r1"))
        )
        self.assertFalse(
            self.backend._repeatable(httpx.Request("POST", BASE + "/run/r1/finish"))
        )


class TestTraceSteps(unittest.TestCase):
    def test_a_step_stored_by_an_earlier_try_is_accepted(self):
        backend = RemoteBackend(MagicMock())
        try:
            with patch("hackagent.storage.remote.result_trace_create") as mock_trace:
                mock_trace.sync_detailed.return_value = _response(200)
                backend._create_trace_remote(uuid4(), 0, "OTHER", {})
            mock_trace.sync_detailed.assert_called_once()
        finally:
            backend.close()


class TestLostWritesAndTheRunsEnd(unittest.TestCase):
    def setUp(self):
        self.backend = RemoteBackend(MagicMock())
        self.backend._count_failure()

    def tearDown(self):
        self.backend.close()

    def test_a_failed_run_is_still_recorded_as_failed(self):
        run_id = uuid4()
        with (
            patch("hackagent.storage.remote.run_finish_create") as mock_finish,
            patch("hackagent.storage.remote.run_partial_update"),
        ):
            mock_finish.sync_detailed.return_value = _response(200, parsed=MagicMock())
            self.backend.update_run(
                run_id, status="FAILED", run_notes="Execution failed: boom"
            )

        body = mock_finish.sync_detailed.call_args.kwargs["body"]
        self.assertEqual(body.status.value, "FAILED")
        self.assertIn("Execution failed: boom", body.note)
        self.assertIn("1 background audit write(s) failed", body.note)
        # Reported once, in the note: the tracker's flush that follows passes.
        self.backend.flush()

    def test_a_cancelled_run_is_still_recorded_as_cancelled(self):
        with patch("hackagent.storage.remote.run_finish_create") as mock_finish:
            mock_finish.sync_detailed.return_value = _response(200, parsed=MagicMock())
            self.backend.update_run(uuid4(), status="CANCELLED")

        body = mock_finish.sync_detailed.call_args.kwargs["body"]
        self.assertEqual(body.status.value, "CANCELLED")
        self.assertIn("background audit write(s) failed", body.note)

    def test_a_run_with_lost_writes_still_cannot_end_completed(self):
        with patch("hackagent.storage.remote.run_finish_create") as mock_finish:
            with self.assertRaisesRegex(RuntimeError, "background audit write"):
                self.backend.update_run(uuid4(), status="COMPLETED")
        mock_finish.sync_detailed.assert_not_called()


if __name__ == "__main__":
    unittest.main()
