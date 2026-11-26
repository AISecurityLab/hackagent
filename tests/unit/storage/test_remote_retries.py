# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""RemoteBackend over a connection the server may drop: its client sends
safe requests again, results carry a client-chosen id so their creation is
safe too once the server honours it, and a lost write does not keep a failed
run from being recorded as FAILED."""

import asyncio
import json
import os
import unittest
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import httpx

from hackagent.orchestrator.execution.adopted import AdoptedRunStore
from hackagent.storage._http.api.result import result_create, result_trace_create
from hackagent.storage._http.retry import RetryingTransport, RetryPolicy
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


def _create(store):
    return store.create_result(
        run_id=uuid4(),
        goal="g",
        goal_index=0,
        request_payload={},
        agent_specific_data={},
    )


def _echoing(mock_create, status=201):
    """A server that keeps the client's id."""
    mock_create.sync_detailed.side_effect = lambda **kw: _response(
        status, parsed=_created(_sent_id(mock_create))
    )


def _post_result():
    return httpx.Request("POST", BASE + "/result", content=b"{}")


def _adopted(client):
    return AdoptedRunStore.for_run(
        client,
        {"id": str(uuid4()), "agent": str(uuid4()), "organization": str(uuid4())},
    )


class TestConnect(unittest.TestCase):
    def setUp(self):
        self.backend = RemoteBackend.connect(BASE, "key", verify=False)

    def tearDown(self):
        self.backend.close(close_client=True)

    def test_the_sync_client_sends_dropped_requests_again(self):
        policy = self.backend.client.retry
        self.assertIsInstance(policy, RetryPolicy)
        # The retry sits under httpx: it applies to every call the generated
        # endpoints make through this client.
        transport = self.backend.client.get_httpx_client()._transport
        self.assertIsInstance(transport, RetryingTransport)
        self.assertIs(transport.policy, policy)

    def test_the_async_client_keeps_its_own_transport(self):
        async_client = self.backend.client.get_async_httpx_client()
        self.assertNotIsInstance(async_client._transport, RetryingTransport)
        self.assertTrue(hasattr(async_client._transport, "handle_async_request"))
        asyncio.run(async_client.aclose())

    def test_a_dropped_read_is_sent_again(self):
        calls = []

        def server(request):
            calls.append(request)
            if len(calls) == 1:
                raise httpx.RemoteProtocolError("Server disconnected")
            return httpx.Response(200, json={"count": 0, "results": []})

        transport = self.backend.client.get_httpx_client()._transport
        transport._inner = httpx.MockTransport(server)
        self.backend.client.retry.sleep = lambda s: None

        self.assertEqual(self.backend.check_connection(), 200)
        self.assertEqual(len(calls), 2)


class TestProxiesFromTheEnvironment(unittest.TestCase):
    """HTTPS_PROXY and NO_PROXY reach the API client as httpx reads them, and
    the retry wraps the proxy too."""

    def _connect(self, **environment):
        with patch.dict(os.environ, environment, clear=False):
            # Only the variables this test sets: urllib prefers a lowercase
            # one, and an empty one cancels its uppercase twin.
            for name in ("HTTP_PROXY", "ALL_PROXY", "NO_PROXY"):
                if name not in environment:
                    os.environ.pop(name, None)
                os.environ.pop(name.lower(), None)
            os.environ.pop("https_proxy", None)
            backend = RemoteBackend.connect(BASE, "key")
            self.addCleanup(backend.close, close_client=True)
            return backend.client.get_httpx_client()

    def test_the_proxy_is_used_and_retried(self):
        client = self._connect(HTTPS_PROXY="http://proxy.example:3128")
        proxied = [t for t in client._mounts.values() if t is not None]

        self.assertEqual(len(proxied), 1)
        self.assertIsInstance(proxied[0], RetryingTransport)
        self.assertIsInstance(
            client._transport_for_url(httpx.URL(BASE)), RetryingTransport
        )
        self.assertIsNot(client._transport_for_url(httpx.URL(BASE)), client._transport)

    def test_hosts_without_the_proxy_stay_direct(self):
        client = self._connect(
            HTTPS_PROXY="http://proxy.example:3128",
            NO_PROXY="api.example.com",
        )

        self.assertIs(client._transport_for_url(httpx.URL(BASE)), client._transport)


class TestClientChosenResultIds(unittest.TestCase):
    def setUp(self):
        self.backend = RemoteBackend.connect(BASE, "key")
        self.transport = self.backend.client.retry

    def tearDown(self):
        self.backend.close(close_client=True)

    def test_a_result_is_created_with_an_id_of_the_clients(self):
        with patch("hackagent.storage.remote.result_create") as mock_create:
            _echoing(mock_create)
            record = _create(self.backend)

        self.assertEqual(record.id, _sent_id(mock_create))

    def test_creation_is_repeatable_once_the_server_keeps_the_id(self):
        self.assertFalse(self.transport.repeatable(_post_result()))

        with patch("hackagent.storage.remote.result_create") as mock_create:
            _echoing(mock_create)
            _create(self.backend)

        self.assertTrue(self.transport.repeatable(_post_result()))

    def test_a_server_that_picks_its_own_id_keeps_creation_unrepeatable(self):
        server_id = uuid4()
        with patch("hackagent.storage.remote.result_create") as mock_create:
            mock_create.sync_detailed.return_value = _response(
                201, parsed=_created(server_id)
            )
            record = _create(self.backend)

        self.assertEqual(record.id, server_id)
        self.assertFalse(self.transport.repeatable(_post_result()))

    def test_a_store_sharing_the_client_teaches_it_too(self):
        # The cloud executor creates results through an AdoptedRunStore built
        # on the claiming backend's client: what it learns must reach the
        # policy that client sends through.
        adopted = _adopted(self.backend.client)
        try:
            with patch("hackagent.storage.remote.result_create") as mock_create:
                _echoing(mock_create)
                _create(adopted)
        finally:
            adopted.close()

        self.assertTrue(self.transport.repeatable(_post_result()))

    def test_a_result_stored_by_an_earlier_try_is_accepted(self):
        with patch("hackagent.storage.remote.result_create") as mock_create:
            _echoing(mock_create, status=200)
            record = _create(self.backend)

        self.assertEqual(record.id, _sent_id(mock_create))

    def test_other_calls_keep_the_default_policy(self):
        self.assertTrue(
            self.transport.repeatable(httpx.Request("GET", BASE + "/run/r1"))
        )
        self.assertFalse(
            self.transport.repeatable(httpx.Request("POST", BASE + "/run/r1/finish"))
        )

    def test_a_backend_without_the_retry_transport_still_creates_results(self):
        backend = RemoteBackend(MagicMock())
        try:
            with patch("hackagent.storage.remote.result_create") as mock_create:
                _echoing(mock_create)
                self.assertEqual(_create(backend).id, _sent_id(mock_create))
        finally:
            backend.close()


class TestGeneratedParsers(unittest.TestCase):
    """A repeat answered 200 parses, even with strict status handling."""

    STRICT = MagicMock(raise_on_unexpected_status=True)

    def test_a_result_answered_200(self):
        result_id = uuid4()
        body = {"id": str(result_id), "run": str(uuid4()), "run_id": str(uuid4())}
        body.update(timestamp="2026-11-26T14:27:00Z", traces=[])
        parsed = result_create._parse_response(
            client=self.STRICT,
            response=httpx.Response(200, content=json.dumps(body).encode()),
        )
        self.assertEqual(parsed.id, result_id)

    def test_a_trace_step_answered_200(self):
        body = {
            "id": 7,
            "result": str(uuid4()),
            "sequence": 0,
            "step_type": "OTHER",
            "timestamp": "2026-11-26T14:27:00Z",
            "content": {},
        }
        parsed = result_trace_create._parse_response(
            client=self.STRICT,
            response=httpx.Response(200, content=json.dumps(body).encode()),
        )
        self.assertEqual(parsed.sequence, 0)


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


def _finish_body(mock_finish):
    return mock_finish.sync_detailed.call_args.kwargs["body"]


class TestLostWritesAndTheRunsEnd(unittest.TestCase):
    def setUp(self):
        self.backend = RemoteBackend(MagicMock())
        self.backend._count_failure()

    def tearDown(self):
        self.backend.close()

    def _finishing(self):
        mock = patch("hackagent.storage.remote.run_finish_create").start()
        self.addCleanup(patch.stopall)
        mock.sync_detailed.return_value = _response(200, parsed=MagicMock())
        return mock

    def test_a_failed_run_is_still_recorded_as_failed(self):
        mock_finish = self._finishing()
        with patch("hackagent.storage.remote.run_partial_update"):
            self.backend.update_run(
                uuid4(), status="FAILED", run_notes="Execution failed: boom"
            )

        body = _finish_body(mock_finish)
        self.assertEqual(body.status.value, "FAILED")
        self.assertIn("Execution failed: boom", body.note)
        self.assertIn("1 background audit write(s) failed", body.note)
        # Reported once, in the note: the tracker's flush that follows passes.
        self.backend.flush()

    def test_a_cancelled_run_is_still_recorded_as_cancelled(self):
        mock_finish = self._finishing()
        self.backend.update_run(uuid4(), status="CANCELLED")

        body = _finish_body(mock_finish)
        self.assertEqual(body.status.value, "CANCELLED")
        self.assertIn("background audit write(s) failed", body.note)

    def test_a_run_with_lost_writes_still_cannot_end_completed(self):
        mock_finish = self._finishing()
        with self.assertRaisesRegex(RuntimeError, "background audit write"):
            self.backend.update_run(uuid4(), status="COMPLETED")
        mock_finish.sync_detailed.assert_not_called()

    def test_a_direct_finish_records_the_loss(self):
        # The executor ends a cloud run with finish_run itself.
        mock_finish = self._finishing()
        self.backend.finish_run(uuid4(), "FAILED", "Attack runs failed: crescendo")

        body = _finish_body(mock_finish)
        self.assertEqual(body.status.value, "FAILED")
        self.assertIn("Attack runs failed: crescendo", body.note)
        self.assertIn("1 background audit write(s) failed", body.note)

    def test_a_direct_finish_never_claims_completed_over_lost_writes(self):
        mock_finish = self._finishing()
        self.backend.finish_run(uuid4(), "COMPLETED")

        body = _finish_body(mock_finish)
        self.assertEqual(body.status.value, "FAILED")
        self.assertIn("1 background audit write(s) failed", body.note)

    def test_a_run_ended_through_update_run_leaves_later_losses_alone(self):
        # Parallel attacks share the store: a write of another attack lost
        # while this one finishes is not this run's, and must not turn it FAILED.
        self.backend._take_failures()
        mock_finish = self._finishing()
        drains = []
        drain = self.backend._drain

        def draining():
            drains.append(1)
            drain()
            if len(drains) == 2:  # after this run's settlement, before its finish
                self.backend._count_failure()

        with patch.object(self.backend, "_drain", draining):
            self.backend.update_run(uuid4(), status="COMPLETED")

        body = _finish_body(mock_finish)
        self.assertEqual((body.status.value, body.note), ("COMPLETED", ""))
        self.assertEqual(self.backend._take_failures(), 1)

    def test_a_direct_finish_without_losses_is_unchanged(self):
        self.backend._take_failures()
        mock_finish = self._finishing()
        self.backend.finish_run(uuid4(), "COMPLETED", "done")

        body = _finish_body(mock_finish)
        self.assertEqual((body.status.value, body.note), ("COMPLETED", "done"))


class TestAdoptedCampaignRunEnd(unittest.TestCase):
    """The cloud executor's store keeps the campaign run's final status for
    the executor; a lost write must not keep a FAILED or CANCELLED one back."""

    def setUp(self):
        self.store = _adopted(MagicMock())
        self.store._count_failure()

    def tearDown(self):
        self.store.close()

    def test_a_failed_campaign_keeps_its_status_and_the_loss(self):
        self.store.update_campaign_run(
            self.store.run_id, status="FAILED", run_notes="Attack runs failed"
        )

        status, note = self.store.final_status
        self.assertEqual(status, "FAILED")
        self.assertIn("Attack runs failed", note)
        self.assertIn("1 background audit write(s) failed", note)

    def test_a_failed_campaign_with_an_audit_keeps_its_status(self):
        with patch("hackagent.storage.remote.run_partial_update") as mock_patch:
            mock_patch.sync_detailed.return_value = _response(200, parsed=MagicMock())
            with patch("hackagent.storage.remote._campaign_record"):
                self.store.update_campaign_run(
                    self.store.run_id, status="CANCELLED", audit={"passed": False}
                )

        status, note = self.store.final_status
        self.assertEqual(status, "CANCELLED")
        self.assertIn("background audit write(s) failed", note)

    def test_a_campaign_with_lost_writes_still_cannot_end_completed(self):
        with self.assertRaisesRegex(RuntimeError, "background audit write"):
            self.store.update_campaign_run(self.store.run_id, status="COMPLETED")
        self.assertIsNone(self.store.final_status)


if __name__ == "__main__":
    unittest.main()
