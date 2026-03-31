# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for RemoteBackend (server/storage/remote.py)."""

import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

from hackagent.server.storage.remote import RemoteBackend
from hackagent.server.storage.base import (
    AgentRecord,
    OrganizationContext,
    PaginatedResult,
    RunRecord,
    ResultRecord,
    TraceRecord,
)


def _uid() -> UUID:
    return uuid4()


def _dt() -> datetime:
    return datetime.now(timezone.utc)


def _mock_client(token: str = "test-api-token") -> MagicMock:
    client = MagicMock()
    client.token = token
    return client


def _mock_response(status_code: int, parsed=None, content: bytes = b"{}") -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.parsed = parsed
    resp.content = content
    return resp


def _mock_agent_model(name="test-agent"):
    """Build a minimal agent model mock matching the Django API shape."""
    m = MagicMock()
    m.id = _uid()
    m.name = name
    m.agent_type = MagicMock()
    m.agent_type.value = "LITELLM"
    m.endpoint = "http://localhost:8000"
    m.metadata = {"model": "gpt-4"}
    m.organization = _uid()
    m.owner = 1
    m.created_at = _dt()
    m.updated_at = _dt()
    return m


class TestRemoteBackendApiKey(unittest.TestCase):
    """Test get_api_key returns the client token."""

    def test_returns_token(self):
        backend = RemoteBackend(_mock_client("secret-key"))
        self.assertEqual(backend.get_api_key(), "secret-key")

    def test_returns_empty_string_token(self):
        backend = RemoteBackend(_mock_client(""))
        self.assertEqual(backend.get_api_key(), "")


class TestRemoteBackendGetContext(unittest.TestCase):
    """Test get_context fetches org from the agent list."""

    def test_context_from_agent_list(self):
        client = _mock_client()
        backend = RemoteBackend(client)

        agent_m = _mock_agent_model()
        parsed = MagicMock()
        parsed.results = [agent_m]
        resp = _mock_response(200, parsed=parsed)

        with patch("hackagent.server.storage.remote.agent_list") as mock_list:
            mock_list.sync_detailed.return_value = resp
            ctx = backend.get_context()

        self.assertIsInstance(ctx, OrganizationContext)
        self.assertEqual(ctx.org_id, agent_m.organization)
        self.assertEqual(ctx.user_id, str(agent_m.owner))

    def test_context_cached_after_first_call(self):
        client = _mock_client()
        backend = RemoteBackend(client)

        agent_m = _mock_agent_model()
        parsed = MagicMock()
        parsed.results = [agent_m]
        resp = _mock_response(200, parsed=parsed)

        with patch("hackagent.server.storage.remote.agent_list") as mock_list:
            mock_list.sync_detailed.return_value = resp
            ctx1 = backend.get_context()
            ctx2 = backend.get_context()
            # Second call should not hit the API again
            mock_list.sync_detailed.assert_called_once()

        self.assertEqual(ctx1.org_id, ctx2.org_id)

    def test_context_from_organization_me_when_no_agents(self):
        client = _mock_client()
        backend = RemoteBackend(client)

        parsed = MagicMock()
        parsed.results = []
        resp = _mock_response(200, parsed=parsed)
        org = MagicMock()
        org.id = _uid()

        with (
            patch("hackagent.server.storage.remote.agent_list") as mock_list,
            patch(
                "hackagent.server.storage.remote.organization_me_retrieve"
            ) as mock_org,
        ):
            mock_list.sync_detailed.return_value = resp
            mock_org.sync_detailed.return_value = _mock_response(200, parsed=org)
            ctx = backend.get_context()

        self.assertEqual(ctx.org_id, org.id)
        self.assertEqual(ctx.user_id, "unknown")

    def test_context_raises_on_http_error(self):
        client = _mock_client()
        backend = RemoteBackend(client)

        resp = _mock_response(401, parsed=None)

        with (
            patch("hackagent.server.storage.remote.agent_list") as mock_list,
            patch(
                "hackagent.server.storage.remote.organization_me_retrieve"
            ) as mock_org,
        ):
            mock_list.sync_detailed.return_value = resp
            mock_org.sync_detailed.return_value = _mock_response(500, parsed=None)
            with self.assertRaises(RuntimeError):
                backend.get_context()


class TestRemoteBackendListAgents(unittest.TestCase):
    """Test list_agents delegates to agent_list API."""

    def _setup_backend_with_context(self):
        client = _mock_client()
        backend = RemoteBackend(client)
        # Pre-populate context to avoid agent_list being called twice
        backend._context = OrganizationContext(org_id=_uid(), user_id="1")
        return backend

    def test_list_agents_returns_paginated(self):
        backend = self._setup_backend_with_context()

        agent_m = _mock_agent_model("alpha")
        parsed = MagicMock()
        parsed.results = [agent_m]
        parsed.count = 1
        resp = _mock_response(200, parsed=parsed)

        with patch("hackagent.server.storage.remote.agent_list") as mock_list:
            mock_list.sync_detailed.return_value = resp
            result = backend.list_agents()

        self.assertIsInstance(result, PaginatedResult)
        self.assertEqual(result.total, 1)
        self.assertEqual(len(result.items), 1)
        self.assertEqual(result.items[0].name, "alpha")

    def test_list_agents_empty_on_http_error(self):
        backend = self._setup_backend_with_context()
        resp = _mock_response(500, parsed=None)

        with patch("hackagent.server.storage.remote.agent_list") as mock_list:
            mock_list.sync_detailed.return_value = resp
            result = backend.list_agents()

        self.assertEqual(result.total, 0)
        self.assertEqual(result.items, [])


class TestRemoteBackendCreateOrUpdateAgent(unittest.TestCase):
    """Test create_or_update_agent."""

    def setUp(self):
        self.client = _mock_client()
        self.backend = RemoteBackend(self.client)
        self.backend._context = OrganizationContext(org_id=_uid(), user_id="1")

    def _no_existing_agent_resp(self):
        parsed = MagicMock()
        parsed.results = []
        parsed.next = None
        parsed.next_ = None
        return _mock_response(200, parsed=parsed)

    def test_creates_new_agent_when_not_exists(self):
        agent_m = _mock_agent_model("new-agent")
        create_resp = _mock_response(201, parsed=agent_m)

        with (
            patch("hackagent.server.storage.remote.agent_list") as mock_list,
            patch("hackagent.server.storage.remote.agent_create") as mock_create,
        ):
            mock_list.sync_detailed.return_value = self._no_existing_agent_resp()
            mock_create.sync_detailed.return_value = create_resp

            rec = self.backend.create_or_update_agent(
                name="new-agent",
                agent_type="LITELLM",
                endpoint="http://localhost",
                metadata={"model": "gpt-4"},
            )

        self.assertIsInstance(rec, AgentRecord)
        mock_create.sync_detailed.assert_called_once()

    def test_raises_on_create_failure(self):
        err_resp = _mock_response(400)

        with (
            patch("hackagent.server.storage.remote.agent_list") as mock_list,
            patch("hackagent.server.storage.remote.agent_create") as mock_create,
        ):
            mock_list.sync_detailed.return_value = self._no_existing_agent_resp()
            mock_create.sync_detailed.return_value = err_resp

            with self.assertRaises(RuntimeError):
                self.backend.create_or_update_agent(
                    "agent", "LITELLM", "http://localhost", {}
                )

    def test_updates_existing_agent(self):
        agent_m = _mock_agent_model("existing")
        list_resp = MagicMock()
        list_resp.status_code = 200
        list_resp.parsed = MagicMock()
        list_resp.parsed.results = [agent_m]
        list_resp.parsed.next_ = None

        updated_m = _mock_agent_model("existing")
        patch_resp = _mock_response(200, parsed=updated_m)

        with (
            patch("hackagent.server.storage.remote.agent_list") as mock_list,
            patch("hackagent.server.storage.remote.agent_partial_update") as mock_patch,
        ):
            mock_list.sync_detailed.return_value = list_resp
            mock_patch.sync_detailed.return_value = patch_resp

            rec = self.backend.create_or_update_agent(
                "existing", "LITELLM", "http://localhost", {"new_key": "val"}
            )

        self.assertIsInstance(rec, AgentRecord)
        mock_patch.sync_detailed.assert_called_once()


class TestRemoteBackendRun(unittest.TestCase):
    """Test run_*  methods via mocked HTTP."""

    def setUp(self):
        self.client = _mock_client()
        self.backend = RemoteBackend(self.client)
        self.backend._context = OrganizationContext(org_id=_uid(), user_id="1")

    def test_create_run_success(self):
        run_id = str(_uid())
        resp = _mock_response(201, content=f'{{"id": "{run_id}"}}'.encode())

        with patch("hackagent.server.storage.remote.run_run_tests_create") as mock_run:
            mock_run.sync_detailed.return_value = resp
            rec = self.backend.create_run(
                attack_id=_uid(),
                agent_id=_uid(),
                run_config={"batch_size": 4},
            )

        self.assertIsInstance(rec, RunRecord)
        self.assertEqual(str(rec.id), run_id)
        self.assertEqual(rec.status, "PENDING")

    def test_create_run_raises_on_error(self):
        resp = _mock_response(500, content=b"{}")

        with patch("hackagent.server.storage.remote.run_run_tests_create") as mock_run:
            mock_run.sync_detailed.return_value = resp
            with self.assertRaises(RuntimeError):
                self.backend.create_run(_uid(), _uid(), {})

    def test_update_run(self):
        run_id = _uid()
        resp = _mock_response(200)

        with patch("hackagent.server.storage.remote.run_partial_update") as mock_patch:
            mock_patch.sync_detailed.return_value = resp
            rec = self.backend.update_run(run_id, status="RUNNING")

        self.assertEqual(rec.id, run_id)
        self.assertEqual(rec.status, "RUNNING")
        mock_patch.sync_detailed.assert_called_once()

    def test_list_runs_success(self):
        run_m = MagicMock()
        run_m.id = _uid()
        run_m.attack = _uid()
        run_m.agent = _uid()
        run_m.run_config = {}
        run_m.status = MagicMock()
        run_m.status.value = "COMPLETED"
        run_m.run_notes = None
        run_m.created_at = _dt()
        run_m.updated_at = _dt()

        parsed = MagicMock()
        parsed.results = [run_m]
        parsed.count = 1
        resp = _mock_response(200, parsed=parsed)

        with patch("hackagent.server.storage.remote.run_list") as mock_list:
            mock_list.sync_detailed.return_value = resp
            result = self.backend.list_runs()

        self.assertEqual(result.total, 1)
        self.assertIsInstance(result.items[0], RunRecord)

    def test_list_runs_uses_run_timestamp_for_created_at(self):
        run_m = MagicMock()
        run_m.id = _uid()
        run_m.attack = _uid()
        run_m.agent = _uid()
        run_m.run_config = {}
        run_m.status = MagicMock()
        run_m.status.value = "COMPLETED"
        run_m.run_notes = None
        run_m.timestamp = _dt()
        run_m.updated_at = None

        parsed = MagicMock()
        parsed.results = [run_m]
        parsed.count = 1
        parsed.next = None

        with patch("hackagent.server.storage.remote.run_list") as mock_list:
            mock_list.sync_detailed.return_value = _mock_response(200, parsed=parsed)
            result = self.backend.list_runs()

        self.assertEqual(result.items[0].created_at, run_m.timestamp)

    def test_list_runs_paginates_when_next_present(self):
        run_1 = MagicMock()
        run_1.id = _uid()
        run_1.attack = _uid()
        run_1.agent = _uid()
        run_1.run_config = {}
        run_1.status = MagicMock()
        run_1.status.value = "COMPLETED"
        run_1.run_notes = None
        run_1.created_at = _dt()
        run_1.updated_at = _dt()

        run_2 = MagicMock()
        run_2.id = _uid()
        run_2.attack = _uid()
        run_2.agent = _uid()
        run_2.run_config = {}
        run_2.status = MagicMock()
        run_2.status.value = "FAILED"
        run_2.run_notes = None
        run_2.created_at = _dt()
        run_2.updated_at = _dt()

        parsed_1 = MagicMock()
        parsed_1.results = [run_1]
        parsed_1.count = 2
        parsed_1.next = "https://api.hackagent.dev/run?page=2"

        parsed_2 = MagicMock()
        parsed_2.results = [run_2]
        parsed_2.count = 2
        parsed_2.next = None

        with patch("hackagent.server.storage.remote.run_list") as mock_list:
            mock_list.sync_detailed.side_effect = [
                _mock_response(200, parsed=parsed_1),
                _mock_response(200, parsed=parsed_2),
            ]
            result = self.backend.list_runs(page=1, page_size=2)

        self.assertEqual(result.total, 2)
        self.assertEqual(len(result.items), 2)
        self.assertEqual(mock_list.sync_detailed.call_count, 2)

    def test_get_run_success(self):
        run_id = _uid()
        run_m = MagicMock()
        run_m.id = run_id
        run_m.attack = _uid()
        run_m.agent = _uid()
        run_m.run_config = {}
        run_m.status = MagicMock()
        run_m.status.value = "PENDING"
        run_m.run_notes = None
        run_m.created_at = _dt()
        run_m.updated_at = _dt()

        resp = _mock_response(200, parsed=run_m)

        with patch("hackagent.server.storage.remote.run_retrieve") as mock_retrieve:
            mock_retrieve.sync_detailed.return_value = resp
            rec = self.backend.get_run(run_id)

        self.assertEqual(rec.id, run_id)


class TestRemoteBackendResult(unittest.TestCase):
    """Test result_* methods via mocked HTTP."""

    def setUp(self):
        self.client = _mock_client()
        self.backend = RemoteBackend(self.client)
        self.backend._context = OrganizationContext(org_id=_uid(), user_id="1")

    def test_create_result_success(self):
        result_id = _uid()
        run_id = _uid()
        parsed_m = MagicMock()
        parsed_m.id = result_id
        resp = _mock_response(201, parsed=parsed_m)

        with patch("hackagent.server.storage.remote.result_create") as mock_create:
            mock_create.sync_detailed.return_value = resp
            rec = self.backend.create_result(
                run_id=run_id,
                goal="Test jailbreak",
                goal_index=0,
                request_payload={"prompt": "ignore"},
                agent_specific_data={},
            )

        self.assertIsInstance(rec, ResultRecord)
        self.assertEqual(rec.evaluation_status, "NOT_EVALUATED")

    def test_update_result_success(self):
        result_id = _uid()
        resp = _mock_response(200, content=b"{}")

        with patch(
            "hackagent.server.storage.remote.result_partial_update"
        ) as mock_patch:
            mock_patch.sync_detailed.return_value = resp
            rec = self.backend.update_result(
                result_id,
                evaluation_status="SUCCESSFUL_JAILBREAK",
                evaluation_notes="Passed",
            )

        self.assertIsInstance(rec, ResultRecord)
        mock_patch.sync_detailed.assert_called_once()

    def test_create_trace_success(self):
        result_id = _uid()
        trace_id = _uid()
        parsed_m = MagicMock()
        parsed_m.id = trace_id
        resp = _mock_response(201, parsed=parsed_m)

        with patch(
            "hackagent.server.storage.remote.result_trace_create"
        ) as mock_create:
            mock_create.sync_detailed.return_value = resp
            rec = self.backend.create_trace(
                result_id=result_id,
                sequence=1,
                step_type="OTHER",
                content={"msg": "hello"},
            )

        self.assertIsInstance(rec, TraceRecord)
        self.assertEqual(rec.result_id, result_id)
        self.assertEqual(rec.sequence, 1)

    def test_create_trace_success_with_integer_id(self):
        result_id = _uid()
        parsed_m = MagicMock()
        parsed_m.id = 44390
        resp = _mock_response(201, parsed=parsed_m)

        with patch(
            "hackagent.server.storage.remote.result_trace_create"
        ) as mock_create:
            mock_create.sync_detailed.return_value = resp
            rec = self.backend.create_trace(
                result_id=result_id,
                sequence=2,
                step_type="OTHER",
                content={"msg": "hello"},
            )

        self.assertIsInstance(rec, TraceRecord)
        self.assertIsInstance(rec.id, UUID)
        self.assertEqual(rec.result_id, result_id)
        self.assertEqual(rec.sequence, 2)

    def test_list_results_empty_on_error(self):
        resp = _mock_response(500, parsed=None)

        with patch("hackagent.server.storage.remote.result_list") as mock_list:
            mock_list.sync_detailed.return_value = resp
            result = self.backend.list_results()

        self.assertEqual(result.total, 0)
        self.assertEqual(result.items, [])

    def test_list_results_filters_by_run_id(self):
        run_id = _uid()
        result_m = MagicMock()
        result_m.id = _uid()
        result_m.run = run_id
        result_m.agent_specific_data = {"goal": "g1", "goal_index": 0}
        result_m.evaluation_status = MagicMock()
        result_m.evaluation_status.value = "SUCCESSFUL_JAILBREAK"
        result_m.evaluation_notes = None
        result_m.evaluation_metrics = {}
        result_m.created_at = _dt()
        result_m.updated_at = _dt()

        parsed = MagicMock()
        parsed.results = [result_m]
        parsed.count = 1
        parsed.next = None

        with patch("hackagent.server.storage.remote.result_list") as mock_list:
            mock_list.sync_detailed.return_value = _mock_response(200, parsed=parsed)
            result = self.backend.list_results(run_id=run_id, page=1, page_size=50)

        self.assertEqual(result.total, 1)
        self.assertEqual(len(result.items), 1)
        self.assertEqual(result.items[0].run_id, run_id)
        _, kwargs = mock_list.sync_detailed.call_args
        self.assertEqual(kwargs.get("run"), run_id)

    def test_list_traces_from_result_retrieve(self):
        result_id = _uid()

        trace_1 = MagicMock()
        trace_1.id = 101
        trace_1.sequence = 2
        trace_1.step_type = MagicMock()
        trace_1.step_type.value = "TOOL_RESPONSE"
        trace_1.content = {"tool": "web", "status": "ok"}
        trace_1.timestamp = _dt()

        trace_2 = MagicMock()
        trace_2.id = 100
        trace_2.sequence = 1
        trace_2.step_type = MagicMock()
        trace_2.step_type.value = "TOOL_CALL"
        trace_2.content = {"tool": "web", "args": {"q": "x"}}
        trace_2.timestamp = _dt()

        parsed_result = MagicMock()
        parsed_result.traces = [trace_1, trace_2]

        with patch("hackagent.server.storage.remote.result_retrieve") as mock_retrieve:
            mock_retrieve.sync_detailed.return_value = _mock_response(
                200, parsed=parsed_result
            )
            traces = self.backend.list_traces(result_id)

        self.assertEqual(len(traces), 2)
        self.assertIsInstance(traces[0], TraceRecord)
        self.assertEqual(traces[0].sequence, 1)
        self.assertEqual(traces[1].sequence, 2)
        self.assertEqual(traces[0].step_type, "TOOL_CALL")
        self.assertEqual(traces[1].step_type, "TOOL_RESPONSE")

    def test_list_traces_empty_on_error(self):
        result_id = _uid()

        with patch("hackagent.server.storage.remote.result_retrieve") as mock_retrieve:
            mock_retrieve.sync_detailed.return_value = _mock_response(500, parsed=None)
            traces = self.backend.list_traces(result_id)

        self.assertEqual(traces, [])


if __name__ == "__main__":
    unittest.main()
