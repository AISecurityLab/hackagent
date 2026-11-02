# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for RemoteBackend (server/storage/remote.py)."""

import threading
import time
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

from hackagent.storage import remote
from hackagent.storage._http.api.models import PaginatedAgentList
from hackagent.storage._http.api.agent import agent_create, agent_partial_update
from hackagent.storage._http.api.campaign import campaign_start_create
from hackagent.storage._http.api.result import result_create, result_partial_update
from hackagent.storage._http.api.run import (
    run_children_create,
    run_claim_create,
    run_claim_next_create,
    run_finish_create,
    run_partial_update,
)
from hackagent.storage import (
    ClaimFailed,
    ClaimResult,
    ExecutorRejected,
    RunNotClaimable,
)
from hackagent.storage.remote import RemoteBackend
from hackagent.storage.records import (
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


def _sent_json(endpoint, mock_endpoint) -> dict:
    """The JSON body ``endpoint`` would send for the call made to its mock."""
    kwargs = dict(mock_endpoint.sync_detailed.call_args.kwargs)
    kwargs.pop("client")
    return endpoint._get_kwargs(**kwargs)["json"]


def _agent_config(name="test-agent") -> dict:
    """A target's model config, as register_target sends it."""
    return {
        "name": name,
        "connection": {
            "type": "LITELLM",
            "endpoint": "http://localhost:8000",
            "api_key": "${TARGET_KEY}",
        },
        "generation": {"temperature": 0.2},
    }


def _mock_agent_model(name="test-agent"):
    """Build a minimal agent model mock matching the Django API shape."""
    m = MagicMock()
    m.id = _uid()
    m.name = name
    m.agent_type = "LITELLM"
    m.endpoint = "http://localhost:8000"
    m.config = _agent_config(name)
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

        with patch("hackagent.storage.remote.agent_list") as mock_list:
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

        with patch("hackagent.storage.remote.agent_list") as mock_list:
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
            patch("hackagent.storage.remote.agent_list") as mock_list,
            patch("hackagent.storage.remote.organization_me_retrieve") as mock_org,
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
            patch("hackagent.storage.remote.agent_list") as mock_list,
            patch("hackagent.storage.remote.organization_me_retrieve") as mock_org,
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

        with patch("hackagent.storage.remote.agent_list") as mock_list:
            mock_list.sync_detailed.return_value = resp
            result = backend.list_agents()

        self.assertIsInstance(result, PaginatedResult)
        self.assertEqual(result.total, 1)
        self.assertEqual(len(result.items), 1)
        self.assertEqual(result.items[0].name, "alpha")

    def test_list_agents_parses_an_agent_without_an_endpoint(self):
        backend = self._setup_backend_with_context()
        org = str(_uid())
        agent = {
            "id": str(_uid()),
            "name": "no-endpoint",
            "endpoint": "",
            "agent_type": "LITELLM",
            "config": {},
            "organization": org,
            "organization_detail": {"id": org, "name": "org"},
            "owner": None,
            "owner_detail": None,
            "created_at": "2026-10-25T10:00:00Z",
            "updated_at": "2026-10-25T10:00:00Z",
        }
        parsed = PaginatedAgentList.model_validate(
            {"count": 1, "next": None, "previous": None, "results": [agent]}
        )
        resp = _mock_response(200, parsed=parsed)

        with patch("hackagent.storage.remote.agent_list") as mock_list:
            mock_list.sync_detailed.return_value = resp
            result = backend.list_agents()

        self.assertEqual(result.items[0].name, "no-endpoint")

    def test_list_agents_empty_on_http_error(self):
        backend = self._setup_backend_with_context()
        resp = _mock_response(500, parsed=None)

        with patch("hackagent.storage.remote.agent_list") as mock_list:
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
        config = _agent_config("new-agent")

        with (
            patch("hackagent.storage.remote.agent_list") as mock_list,
            patch("hackagent.storage.remote.agent_create") as mock_create,
        ):
            mock_list.sync_detailed.return_value = self._no_existing_agent_resp()
            mock_create.sync_detailed.return_value = create_resp

            rec = self.backend.create_or_update_agent("new-agent", config)

        self.assertIsInstance(rec, AgentRecord)
        self.assertEqual(rec.agent_type, "LITELLM")
        self.assertEqual(rec.endpoint, "http://localhost:8000")
        self.assertEqual(rec.metadata, config)
        body = _sent_json(agent_create, mock_create)
        # Type and endpoint are read-only copies the server derives from it.
        self.assertEqual(set(body), {"name", "description", "config"})
        self.assertEqual(body["config"], config)

    def test_raises_on_create_failure(self):
        err_resp = _mock_response(400)

        with (
            patch("hackagent.storage.remote.agent_list") as mock_list,
            patch("hackagent.storage.remote.agent_create") as mock_create,
        ):
            mock_list.sync_detailed.return_value = self._no_existing_agent_resp()
            mock_create.sync_detailed.return_value = err_resp

            with self.assertRaises(RuntimeError):
                self.backend.create_or_update_agent("agent", _agent_config("agent"))

    def test_updates_existing_agent_with_the_whole_config(self):
        agent_m = _mock_agent_model("existing")
        list_resp = MagicMock()
        list_resp.status_code = 200
        list_resp.parsed = MagicMock()
        list_resp.parsed.results = [agent_m]
        list_resp.parsed.next_ = None

        updated_m = _mock_agent_model("existing")
        patch_resp = _mock_response(200, parsed=updated_m)
        config = {**_agent_config("existing"), "generation": {"max_tokens": 64}}

        with (
            patch("hackagent.storage.remote.agent_list") as mock_list,
            patch("hackagent.storage.remote.agent_partial_update") as mock_patch,
        ):
            mock_list.sync_detailed.return_value = list_resp
            mock_patch.sync_detailed.return_value = patch_resp

            rec = self.backend.create_or_update_agent("existing", config)

        self.assertIsInstance(rec, AgentRecord)
        self.assertEqual(
            _sent_json(agent_partial_update, mock_patch), {"config": config}
        )


class TestRemoteBackendRun(unittest.TestCase):
    """Test run_*  methods via mocked HTTP."""

    def setUp(self):
        self.client = _mock_client()
        self.backend = RemoteBackend(self.client)
        self.backend._context = OrganizationContext(org_id=_uid(), user_id="1")

    def _mock_run_model(self, idx: int) -> MagicMock:
        run_m = MagicMock()
        run_m.id = _uid()
        run_m.attack = _uid()
        run_m.agent = _uid()
        run_m.run_config = {"idx": idx}
        run_m.status = MagicMock()
        run_m.status.value = "COMPLETED"
        run_m.run_notes = None
        run_m.created_at = _dt()
        run_m.updated_at = _dt()
        return run_m

    def test_create_run_uses_children_endpoint(self):
        run_id = str(_uid())
        campaign_run_id, attack_id, agent_id = _uid(), _uid(), _uid()
        resp = _mock_response(201, content=f'{{"id": "{run_id}"}}'.encode())

        with patch("hackagent.storage.remote.run_children_create") as mock_children:
            mock_children.sync_detailed.return_value = resp
            rec = self.backend.create_run(
                attack_id=attack_id,
                agent_id=agent_id,
                run_config={"batch_size": 4},
                campaign_run_id=campaign_run_id,
            )

        self.assertEqual(
            mock_children.sync_detailed.call_args.kwargs["id"], campaign_run_id
        )
        self.assertEqual(
            _sent_json(run_children_create, mock_children),
            {
                "attack": str(attack_id),
                "agent": str(agent_id),
                "run_config": {"batch_size": 4},
            },
        )
        self.assertIsInstance(rec, RunRecord)
        self.assertEqual(str(rec.id), run_id)
        self.assertEqual(rec.campaign_run_id, campaign_run_id)
        # Child runs are created already running.
        self.assertEqual(rec.status, "RUNNING")

    def test_create_run_needs_its_campaign_run(self):
        with patch("hackagent.storage.remote.run_children_create") as mock_children:
            with self.assertRaises(ValueError):
                self.backend.create_run(_uid(), _uid(), {})
        mock_children.sync_detailed.assert_not_called()

    def test_create_run_raises_on_error(self):
        resp = _mock_response(409, content=b"{}")

        with patch("hackagent.storage.remote.run_children_create") as mock_children:
            mock_children.sync_detailed.return_value = resp
            with self.assertRaises(RuntimeError):
                self.backend.create_run(_uid(), _uid(), {}, campaign_run_id=_uid())

    def test_running_status_is_noop(self):
        run_id = _uid()

        with (
            patch("hackagent.storage.remote.run_partial_update") as mock_patch,
            patch("hackagent.storage.remote.run_finish_create") as mock_finish,
        ):
            rec = self.backend.update_run(run_id, status="RUNNING")

        self.assertEqual(rec.id, run_id)
        self.assertEqual(rec.status, "RUNNING")
        mock_patch.sync_detailed.assert_not_called()
        mock_finish.sync_detailed.assert_not_called()

    def test_final_status_calls_finish(self):
        run_id = _uid()

        with (
            patch("hackagent.storage.remote.run_partial_update") as mock_patch,
            patch("hackagent.storage.remote.run_finish_create") as mock_finish,
        ):
            mock_finish.sync_detailed.return_value = _mock_response(
                200, parsed=MagicMock()
            )
            rec = self.backend.update_run(
                run_id, status="FAILED", run_notes="Execution failed: boom"
            )

        self.assertEqual(mock_finish.sync_detailed.call_args.kwargs["id"], run_id)
        self.assertEqual(
            _sent_json(run_finish_create, mock_finish),
            {"status": "FAILED", "note": "Execution failed: boom"},
        )
        mock_patch.sync_detailed.assert_not_called()
        self.assertEqual(rec.status, "FAILED")

    def test_update_run_patches_the_run_config(self):
        run_id = _uid()

        with (
            patch("hackagent.storage.remote.run_partial_update") as mock_patch,
            patch("hackagent.storage.remote.run_finish_create") as mock_finish,
        ):
            mock_patch.sync_detailed.return_value = _mock_response(200)
            self.backend.update_run(run_id, run_config={"done_goals": 3})

        self.assertEqual(
            _sent_json(run_partial_update, mock_patch),
            {"run_config": {"done_goals": 3}},
        )
        mock_finish.sync_detailed.assert_not_called()

    def test_update_run_raises_when_the_patch_fails(self):
        with (
            patch("hackagent.storage.remote.run_partial_update") as mock_patch,
            patch("hackagent.storage.remote.run_finish_create") as mock_finish,
        ):
            mock_patch.sync_detailed.return_value = _mock_response(500)
            with self.assertRaisesRegex(RuntimeError, "update_run"):
                self.backend.update_run(
                    _uid(), status="COMPLETED", run_config={"done_goals": 3}
                )

        # A run whose config could not be written is not finished either.
        mock_finish.sync_detailed.assert_not_called()

    def test_update_run_never_finishes_over_lost_writes(self):
        """An attack run whose results did not all reach the server is not
        COMPLETED: the failure surfaces first, and the tracker records it."""
        self.backend._count_failure()

        with patch("hackagent.storage.remote.run_finish_create") as mock_finish:
            with self.assertRaisesRegex(RuntimeError, "background audit write"):
                self.backend.update_run(_uid(), status="COMPLETED")

        mock_finish.sync_detailed.assert_not_called()

    def test_update_run_refuses_a_status_the_executor_cannot_set(self):
        with self.assertRaises(ValueError):
            self.backend.update_run(_uid(), status="PENDING")

    def test_update_run_raises_on_error(self):
        run_id = _uid()

        with patch("hackagent.storage.remote.run_finish_create") as mock_finish:
            mock_finish.sync_detailed.return_value = _mock_response(500)
            with self.assertRaisesRegex(RuntimeError, "finish"):
                self.backend.update_run(run_id, status="FAILED")

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

        with patch("hackagent.storage.remote.run_list") as mock_list:
            mock_list.sync_detailed.return_value = resp
            result = self.backend.list_runs()

        self.assertEqual(result.total, 1)
        self.assertIsInstance(result.items[0], RunRecord)

    def test_list_runs_injects_agent_name_into_run_config(self):
        run_m = MagicMock()
        run_m.id = _uid()
        run_m.attack = _uid()
        run_m.agent = _uid()
        run_m.run_config = {"mode": "fast"}
        run_m.agent_name = "assistant-a"
        run_m.status = MagicMock()
        run_m.status.value = "COMPLETED"
        run_m.run_notes = None
        run_m.created_at = _dt()
        run_m.updated_at = _dt()

        parsed = MagicMock()
        parsed.results = [run_m]
        parsed.count = 1
        parsed.next = None

        with patch("hackagent.storage.remote.run_list") as mock_list:
            mock_list.sync_detailed.return_value = _mock_response(200, parsed=parsed)
            result = self.backend.list_runs()

        self.assertEqual(result.total, 1)
        self.assertEqual(result.items[0].run_config.get("mode"), "fast")
        self.assertEqual(result.items[0].run_config.get("_agent_name"), "assistant-a")

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

        with patch("hackagent.storage.remote.run_list") as mock_list:
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

        with patch("hackagent.storage.remote.run_list") as mock_list:
            mock_list.sync_detailed.side_effect = [
                _mock_response(200, parsed=parsed_1),
                _mock_response(200, parsed=parsed_2),
            ]
            result = self.backend.list_runs(page=1, page_size=2)

        self.assertEqual(result.total, 2)
        self.assertEqual(len(result.items), 2)
        self.assertEqual(mock_list.sync_detailed.call_count, 2)

    def test_list_runs_logical_page_has_no_overlap(self):
        runs = [self._mock_run_model(i) for i in range(5)]

        parsed_1 = MagicMock()
        parsed_1.results = runs[0:2]
        parsed_1.count = 5
        parsed_1.next = "https://api.hackagent.dev/run?page=2"

        parsed_2 = MagicMock()
        parsed_2.results = runs[2:4]
        parsed_2.count = 5
        parsed_2.next = "https://api.hackagent.dev/run?page=3"

        parsed_3 = MagicMock()
        parsed_3.results = runs[4:5]
        parsed_3.count = 5
        parsed_3.next = None

        with patch("hackagent.storage.remote.run_list") as mock_list:
            mock_list.sync_detailed.side_effect = [
                _mock_response(200, parsed=parsed_1),
                _mock_response(200, parsed=parsed_2),
                _mock_response(200, parsed=parsed_1),
                _mock_response(200, parsed=parsed_2),
                _mock_response(200, parsed=parsed_3),
            ]

            page_1 = self.backend.list_runs(page=1, page_size=3)
            page_2 = self.backend.list_runs(page=2, page_size=3)

        ids_1 = {r.id for r in page_1.items}
        ids_2 = {r.id for r in page_2.items}

        self.assertEqual(page_1.total, 5)
        self.assertEqual(page_2.total, 5)
        self.assertEqual(len(page_1.items), 3)
        self.assertEqual(len(page_2.items), 2)
        self.assertTrue(ids_1.isdisjoint(ids_2))

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

        with patch("hackagent.storage.remote.run_retrieve") as mock_retrieve:
            mock_retrieve.sync_detailed.return_value = resp
            rec = self.backend.get_run(run_id)

        self.assertEqual(rec.id, run_id)


class TestRemoteBackendResult(unittest.TestCase):
    """Test result_* methods via mocked HTTP."""

    def setUp(self):
        self.client = _mock_client()
        self.backend = RemoteBackend(self.client)
        self.backend._context = OrganizationContext(org_id=_uid(), user_id="1")

    def _mock_result_model(self, run_id: UUID, goal_index: int) -> MagicMock:
        result_m = MagicMock()
        result_m.id = _uid()
        result_m.run = run_id
        result_m.agent_specific_data = {
            "goal": f"g{goal_index + 1}",
            "goal_index": goal_index,
        }
        result_m.evaluation_status = MagicMock()
        result_m.evaluation_status.value = "NOT_EVALUATED"
        result_m.evaluation_notes = None
        result_m.evaluation_metrics = {}
        result_m.created_at = _dt()
        result_m.updated_at = _dt()
        return result_m

    def test_create_result_success(self):
        result_id = _uid()
        run_id = _uid()
        parsed_m = MagicMock()
        parsed_m.id = result_id
        resp = _mock_response(201, parsed=parsed_m)

        with patch("hackagent.storage.remote.result_create") as mock_create:
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

    def test_create_result_sends_the_goal(self):
        run_id = _uid()
        parsed_m = MagicMock()
        parsed_m.id = _uid()

        with patch("hackagent.storage.remote.result_create") as mock_create:
            mock_create.sync_detailed.return_value = _mock_response(201, parsed_m)
            self.backend.create_result(
                run_id=run_id,
                goal="Test jailbreak",
                goal_index=3,
                request_payload={"prompt": "ignore"},
                agent_specific_data={"request_index": 1},
            )

        body = _sent_json(result_create, mock_create)
        self.assertEqual(body["run"], str(run_id))
        self.assertEqual(body["goal"], "Test jailbreak")
        self.assertEqual(body["goal_index"], 3)
        self.assertEqual(body["agent_specific_data"], {"request_index": 1})

    def test_update_result_sends_the_evaluation_metrics(self):
        with patch("hackagent.storage.remote.result_partial_update") as mock_patch:
            mock_patch.sync_detailed.return_value = _mock_response(200)
            self.backend.update_result(
                _uid(),
                evaluation_status="FAILED_JAILBREAK",
                evaluation_metrics={"eval_hb": 0, "explanation_hb": "refused"},
            )
            self.backend.flush()

        self.assertEqual(
            _sent_json(result_partial_update, mock_patch),
            {
                "evaluation_status": "FAILED_JAILBREAK",
                "evaluation_metrics": {"eval_hb": 0, "explanation_hb": "refused"},
            },
        )

    def test_update_result_sends_the_target_latency_and_status(self):
        with patch("hackagent.storage.remote.result_partial_update") as mock_patch:
            mock_patch.sync_detailed.return_value = _mock_response(200)
            self.backend.update_result(
                _uid(), latency_ms=1250, response_status_code=429
            )
            self.backend.flush()

        self.assertEqual(
            _sent_json(result_partial_update, mock_patch),
            {"latency_ms": 1250, "response_status_code": 429},
        )

    def test_update_result_sends_only_what_was_given(self):
        with patch("hackagent.storage.remote.result_partial_update") as mock_patch:
            mock_patch.sync_detailed.return_value = _mock_response(200)
            self.backend.update_result(_uid(), evaluation_notes="Passed")
            self.backend.flush()

        self.assertEqual(
            _sent_json(result_partial_update, mock_patch),
            {"evaluation_notes": "Passed"},
        )

    def test_get_result_reads_the_goal_field(self):
        result_m = self._mock_result_model(_uid(), goal_index=0)
        result_m.goal = "the stored goal"
        result_m.goal_index = 4

        with patch("hackagent.storage.remote.result_retrieve") as mock_retrieve:
            mock_retrieve.sync_detailed.return_value = _mock_response(200, result_m)
            rec = self.backend.get_result(result_m.id)

        self.assertEqual((rec.goal, rec.goal_index), ("the stored goal", 4))

    def test_get_result_falls_back_to_the_goal_in_agent_data(self):
        # A server without the goal fields: the mock has no real values there.
        result_m = self._mock_result_model(_uid(), goal_index=2)

        with patch("hackagent.storage.remote.result_retrieve") as mock_retrieve:
            mock_retrieve.sync_detailed.return_value = _mock_response(200, result_m)
            rec = self.backend.get_result(result_m.id)

        self.assertEqual((rec.goal, rec.goal_index), ("g3", 2))

    def test_update_result_success(self):
        result_id = _uid()
        resp = _mock_response(200, content=b"{}")

        with patch("hackagent.storage.remote.result_partial_update") as mock_patch:
            mock_patch.sync_detailed.return_value = resp
            rec = self.backend.update_result(
                result_id,
                evaluation_status="SUCCESSFUL_JAILBREAK",
                evaluation_notes="Passed",
            )
            # update_result is now deferred to the background writer; flush so the
            # PATCH runs while the mock is still patched in.
            self.backend.flush()
            mock_patch.sync_detailed.assert_called_once()

        self.assertIsInstance(rec, ResultRecord)

    def test_update_result_failure_surfaces_at_flush(self):
        result_id = _uid()

        with (
            patch("hackagent.storage.remote.result_partial_update") as mock_patch,
            patch("hackagent.storage.remote.logger"),
        ):
            mock_patch.sync_detailed.return_value = _mock_response(500)
            self.backend.update_result(
                result_id,
                evaluation_status="ERROR_TEST_FRAMEWORK",
                evaluation_notes="audit failure",
            )
            with self.assertRaisesRegex(RuntimeError, "audit write"):
                self.backend.flush()
            self.backend.close()

    def test_a_failed_write_is_reported_once(self):
        """Later flushes report later failures, not the same one again."""
        with (
            patch("hackagent.storage.remote.result_partial_update") as mock_patch,
            patch("hackagent.storage.remote.logger"),
        ):
            mock_patch.sync_detailed.return_value = _mock_response(500)
            self.backend.update_result(_uid(), evaluation_status="FAILED_JAILBREAK")
            with self.assertRaisesRegex(RuntimeError, "1 background"):
                self.backend.flush()

            mock_patch.sync_detailed.return_value = _mock_response(200)
            self.backend.update_result(_uid(), evaluation_status="FAILED_JAILBREAK")
            self.backend.flush()
            self.backend.close()

    def test_create_trace_success(self):
        result_id = _uid()
        trace_id = _uid()
        parsed_m = MagicMock()
        parsed_m.id = trace_id
        resp = _mock_response(201, parsed=parsed_m)

        with patch("hackagent.storage.remote.result_trace_create") as mock_create:
            mock_create.sync_detailed.return_value = resp
            rec = self.backend.create_trace(
                result_id=result_id,
                sequence=1,
                step_type="OTHER",
                content={"msg": "hello"},
            )
            # Trace POST is deferred to the background writer; flush so it runs
            # while the mock is still patched in.
            self.backend.flush()
            mock_create.sync_detailed.assert_called_once()

        self.assertIsInstance(rec, TraceRecord)
        self.assertEqual(rec.result_id, result_id)
        self.assertEqual(rec.sequence, 1)

    def test_create_trace_failure_surfaces_at_flush(self):
        result_id = _uid()

        with (
            patch("hackagent.storage.remote.result_trace_create") as mock_create,
            patch("hackagent.storage.remote.logger"),
        ):
            mock_create.sync_detailed.return_value = _mock_response(500)
            self.backend.create_trace(
                result_id=result_id,
                sequence=1,
                step_type="OTHER",
                content={"msg": "lost audit trace"},
            )
            with self.assertRaisesRegex(RuntimeError, "audit write"):
                self.backend.flush()
            self.backend.close()

    def test_create_trace_success_with_integer_id(self):
        result_id = _uid()
        parsed_m = MagicMock()
        parsed_m.id = 44390
        resp = _mock_response(201, parsed=parsed_m)

        with patch("hackagent.storage.remote.result_trace_create") as mock_create:
            mock_create.sync_detailed.return_value = resp
            rec = self.backend.create_trace(
                result_id=result_id,
                sequence=2,
                step_type="OTHER",
                content={"msg": "hello"},
            )
            self.backend.flush()

        self.assertIsInstance(rec, TraceRecord)
        self.assertIsInstance(rec.id, UUID)
        self.assertEqual(rec.result_id, result_id)
        self.assertEqual(rec.sequence, 2)

    def test_list_results_empty_on_error(self):
        resp = _mock_response(500, parsed=None)

        with patch("hackagent.storage.remote.result_list") as mock_list:
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

        with patch("hackagent.storage.remote.result_list") as mock_list:
            mock_list.sync_detailed.return_value = _mock_response(200, parsed=parsed)
            result = self.backend.list_results(run_id=run_id, page=1, page_size=50)

        self.assertEqual(result.total, 1)
        self.assertEqual(len(result.items), 1)
        self.assertEqual(result.items[0].run_id, run_id)
        _, kwargs = mock_list.sync_detailed.call_args
        self.assertEqual(kwargs.get("run"), run_id)

    def test_list_results_falls_back_to_run_retrieve_when_empty(self):
        run_id = _uid()

        empty_page = MagicMock()
        empty_page.results = []
        empty_page.count = 0
        empty_page.next = None

        embedded = MagicMock()
        embedded.id = _uid()
        embedded.run = run_id
        embedded.agent_specific_data = {"goal": "fallback-goal", "goal_index": 7}
        embedded.evaluation_status = MagicMock()
        embedded.evaluation_status.value = "NOT_EVALUATED"
        embedded.evaluation_notes = None
        embedded.evaluation_metrics = {}
        embedded.created_at = _dt()
        embedded.updated_at = _dt()

        run_with_embedded = MagicMock()
        run_with_embedded.results = [embedded]

        with (
            patch("hackagent.storage.remote.result_list") as mock_list,
            patch("hackagent.storage.remote.run_retrieve") as mock_run_retrieve,
        ):
            mock_list.sync_detailed.return_value = _mock_response(
                200, parsed=empty_page
            )
            mock_run_retrieve.sync_detailed.return_value = _mock_response(
                200, parsed=run_with_embedded
            )

            result = self.backend.list_results(run_id=run_id)

        self.assertEqual(result.total, 1)
        self.assertEqual(len(result.items), 1)
        self.assertEqual(result.items[0].run_id, run_id)
        self.assertEqual(result.items[0].goal, "fallback-goal")
        self.assertEqual(result.items[0].goal_index, 7)

    def test_list_results_logical_page_has_no_overlap(self):
        run_id = _uid()
        results = [self._mock_result_model(run_id, i) for i in range(5)]

        parsed_1 = MagicMock()
        parsed_1.results = results[0:2]
        parsed_1.count = 5
        parsed_1.next = "https://api.hackagent.dev/result?page=2"

        parsed_2 = MagicMock()
        parsed_2.results = results[2:4]
        parsed_2.count = 5
        parsed_2.next = "https://api.hackagent.dev/result?page=3"

        parsed_3 = MagicMock()
        parsed_3.results = results[4:5]
        parsed_3.count = 5
        parsed_3.next = None

        with patch("hackagent.storage.remote.result_list") as mock_list:
            mock_list.sync_detailed.side_effect = [
                _mock_response(200, parsed=parsed_1),
                _mock_response(200, parsed=parsed_2),
                _mock_response(200, parsed=parsed_1),
                _mock_response(200, parsed=parsed_2),
                _mock_response(200, parsed=parsed_3),
            ]

            page_1 = self.backend.list_results(run_id=run_id, page=1, page_size=3)
            page_2 = self.backend.list_results(run_id=run_id, page=2, page_size=3)

        ids_1 = {r.id for r in page_1.items}
        ids_2 = {r.id for r in page_2.items}

        self.assertEqual(page_1.total, 5)
        self.assertEqual(page_2.total, 5)
        self.assertEqual(len(page_1.items), 3)
        self.assertEqual(len(page_2.items), 2)
        self.assertTrue(ids_1.isdisjoint(ids_2))

    def test_list_results_does_not_fallback_on_page_gt_1(self):
        run_id = _uid()

        empty_page = MagicMock()
        empty_page.results = []
        empty_page.count = 0
        empty_page.next = None

        with (
            patch("hackagent.storage.remote.result_list") as mock_list,
            patch("hackagent.storage.remote.run_retrieve") as mock_run_retrieve,
        ):
            mock_list.sync_detailed.return_value = _mock_response(
                200, parsed=empty_page
            )
            result = self.backend.list_results(run_id=run_id, page=2, page_size=100)

        self.assertEqual(result.total, 0)
        self.assertEqual(result.items, [])
        mock_run_retrieve.sync_detailed.assert_not_called()

    def test_count_result_buckets_aggregates_filtered_counts(self):
        counts = [12, 4, 2, 1, 3, 2, 1, 5]

        def _resp(count: int):
            parsed = MagicMock()
            parsed.count = count
            return _mock_response(200, parsed=parsed)

        with patch("hackagent.storage.remote.result_list") as mock_result_list:
            mock_result_list.sync_detailed.side_effect = [_resp(c) for c in counts]
            result = self.backend.count_result_buckets()

        self.assertEqual(
            result,
            {
                "total": 12,
                "jailbreaks": 4,
                "mitigated": 3,
                "error": 6,
                "pending": 5,
            },
        )
        self.assertEqual(mock_result_list.sync_detailed.call_count, 8)

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

        with patch("hackagent.storage.remote.result_retrieve") as mock_retrieve:
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

        with patch("hackagent.storage.remote.result_retrieve") as mock_retrieve:
            mock_retrieve.sync_detailed.return_value = _mock_response(500, parsed=None)
            traces = self.backend.list_traces(result_id)

        self.assertEqual(traces, [])


class TestRemoteBackendDelete(unittest.TestCase):
    """Test delete operations delegated to remote API."""

    def setUp(self):
        self.client = _mock_client()
        self.backend = RemoteBackend(self.client)

    def test_delete_run_calls_run_destroy(self):
        run_id = _uid()
        with patch("hackagent.storage.remote.run_destroy") as mock_destroy:
            mock_destroy.sync_detailed.return_value = _mock_response(204, parsed=None)
            self.backend.delete_run(run_id)

        mock_destroy.sync_detailed.assert_called_once_with(
            id=run_id, client=self.client
        )

    def test_delete_attack_deletes_runs_then_attack(self):
        attack_id = _uid()

        run_a = RunRecord(
            id=_uid(),
            attack_id=attack_id,
            agent_id=_uid(),
            run_config={},
            status="COMPLETED",
            run_notes=None,
            created_at=_dt(),
            updated_at=_dt(),
        )
        run_b = RunRecord(
            id=_uid(),
            attack_id=attack_id,
            agent_id=_uid(),
            run_config={},
            status="FAILED",
            run_notes=None,
            created_at=_dt(),
            updated_at=_dt(),
        )

        with (
            patch.object(self.backend, "list_runs") as mock_list_runs,
            patch.object(self.backend, "delete_run") as mock_delete_run,
            patch("hackagent.storage.remote.attack_destroy") as mock_attack_destroy,
        ):
            mock_list_runs.return_value = PaginatedResult(items=[run_a, run_b], total=2)
            mock_attack_destroy.sync_detailed.return_value = _mock_response(
                204, parsed=None
            )

            self.backend.delete_attack(attack_id)

        mock_list_runs.assert_called_once_with(
            attack_id=attack_id, page=1, page_size=100
        )
        self.assertEqual(mock_delete_run.call_count, 2)
        deleted_ids = {call.args[0] for call in mock_delete_run.call_args_list}
        self.assertEqual(deleted_ids, {run_a.id, run_b.id})
        mock_attack_destroy.sync_detailed.assert_called_once_with(
            id=attack_id,
            client=self.client,
        )


def _mock_run_row(run_config, *, status="COMPLETED", parent=None) -> MagicMock:
    """One row as the hosted run endpoint returns it."""
    row = MagicMock()
    row.id = _uid()
    row.attack = _uid()
    row.agent = _uid()
    row.parent = parent
    row.run_config = run_config
    row.status = MagicMock()
    row.status.value = status
    row.run_notes = None
    row.agent_name = None
    row.timestamp = _dt()
    row.updated_at = _dt()
    return row


def _mock_page(rows, count, next_url=None) -> MagicMock:
    parsed = MagicMock()
    parsed.results = rows
    parsed.count = count
    parsed.next = next_url
    return _mock_response(200, parsed=parsed)


def _campaign_marker(name="Nightly", config=None, audit=None) -> dict:
    return {
        "_record_type": "campaign_run",
        "campaign_name": name,
        "campaign_config": config if config is not None else {"version": 1},
        **({"evaluation_audit": audit} if audit is not None else {}),
    }


class TestRemoteBackendCampaignRun(unittest.TestCase):
    """Campaign runs are parent runs whose run_config carries a marker."""

    def setUp(self):
        self.client = _mock_client()
        self.backend = RemoteBackend(self.client)
        self.backend._context = OrganizationContext(org_id=_uid(), user_id="1")

    def test_start_campaign_posts_spec(self):
        agent_id = _uid()
        spec = {"version": 1, "campaign": {"name": "Nightly"}, "attacks": []}
        stored = {"version": 1, "campaign": {"name": "Nightly"}}
        row = _mock_run_row(_campaign_marker(config=stored), status="RUNNING")

        with (
            patch("hackagent.storage.remote.campaign_start_create") as mock_start,
            patch("hackagent.storage.remote.socket.gethostname", return_value="box"),
            patch("hackagent.storage.remote.getpass.getuser", return_value="ana"),
        ):
            mock_start.sync_detailed.return_value = _mock_response(201, parsed=row)
            record = self.backend.start_campaign(agent_id, spec)

        self.assertEqual(
            _sent_json(campaign_start_create, mock_start),
            {"agent": str(agent_id), "spec": spec, "claimed_by": "local:box (ana)"},
        )
        self.assertEqual(record.id, row.id)
        self.assertEqual(record.name, "Nightly")
        self.assertEqual(record.campaign_config, stored)
        self.assertEqual(record.status, "RUNNING")
        self.assertIsNone(record.audit)

    def test_start_campaign_names_the_given_executor(self):
        row = _mock_run_row(_campaign_marker(), status="RUNNING")

        with patch("hackagent.storage.remote.campaign_start_create") as mock_start:
            mock_start.sync_detailed.return_value = _mock_response(201, parsed=row)
            self.backend.start_campaign(
                _uid(), {"campaign": {"name": "Nightly"}}, claimed_by="ci:job-7"
            )

        self.assertEqual(
            _sent_json(campaign_start_create, mock_start)["claimed_by"], "ci:job-7"
        )

    def test_start_campaign_raises_so_a_run_never_starts_unrecorded(self):
        with patch("hackagent.storage.remote.campaign_start_create") as mock_start:
            mock_start.sync_detailed.return_value = _mock_response(400)
            with self.assertRaisesRegex(RuntimeError, "start campaign"):
                self.backend.start_campaign(_uid(), {"campaign": {"name": "x"}})

    def test_get_campaign_run_reads_the_marker_back(self):
        audit = {"passed": True, "precision": 1.0}
        row = _mock_run_row(_campaign_marker(config={"version": 1}, audit=audit))

        with patch("hackagent.storage.remote.run_retrieve") as mock_get:
            mock_get.sync_detailed.return_value = _mock_response(200, parsed=row)
            record = self.backend.get_campaign_run(row.id)

        self.assertEqual(record.name, "Nightly")
        self.assertEqual(record.campaign_config, {"version": 1})
        self.assertEqual(record.audit, audit)

    def test_get_campaign_run_rejects_a_plain_attack_run(self):
        row = _mock_run_row({"batch_size": 4})

        with patch("hackagent.storage.remote.run_retrieve") as mock_get:
            mock_get.sync_detailed.return_value = _mock_response(200, parsed=row)
            with self.assertRaisesRegex(RuntimeError, "not a campaign run"):
                self.backend.get_campaign_run(row.id)

    def test_update_campaign_run_merges_the_audit_then_finishes(self):
        audit = {"passed": False}
        row = _mock_run_row(_campaign_marker(audit=audit), status="FAILED")
        order = []

        def _record(name):
            def call(**_kwargs):
                order.append(name)
                return _mock_response(200, parsed=row)

            return call

        with (
            patch("hackagent.storage.remote.run_retrieve") as mock_get,
            patch("hackagent.storage.remote.run_partial_update") as mock_patch,
            patch("hackagent.storage.remote.run_finish_create") as mock_finish,
        ):
            mock_patch.sync_detailed.side_effect = _record("patch")
            mock_finish.sync_detailed.side_effect = _record("finish")
            record = self.backend.update_campaign_run(
                row.id, status="FAILED", audit=audit, run_notes="Audit failed"
            )

        # The server merges run_config key by key, so only the audit is sent;
        # it is written while the run still accepts its executor's writes.
        self.assertEqual(order, ["patch", "finish"])
        self.assertEqual(
            _sent_json(run_partial_update, mock_patch),
            {"run_config": {"evaluation_audit": audit}},
        )
        self.assertEqual(
            _sent_json(run_finish_create, mock_finish),
            {"status": "FAILED", "note": "Audit failed"},
        )
        # The record comes from the finish response: no read-back.
        mock_get.sync_detailed.assert_not_called()
        self.assertEqual(record.status, "FAILED")
        self.assertEqual(record.audit, audit)

    def test_update_campaign_run_does_not_read_back_after_finish(self):
        """Finishing a campaign run revokes its run token, so a read after
        the finish would be refused; the finished run is in the response."""
        row = _mock_run_row(_campaign_marker(), status="COMPLETED")

        with (
            patch("hackagent.storage.remote.run_retrieve") as mock_get,
            patch("hackagent.storage.remote.run_finish_create") as mock_finish,
        ):
            mock_get.sync_detailed.return_value = _mock_response(401)
            mock_finish.sync_detailed.return_value = _mock_response(200, parsed=row)
            record = self.backend.update_campaign_run(row.id, status="COMPLETED")

        mock_get.sync_detailed.assert_not_called()
        self.assertEqual(record.id, row.id)
        self.assertEqual(record.status, "COMPLETED")

    def test_update_campaign_run_running_is_noop(self):
        row = _mock_run_row(_campaign_marker(), status="RUNNING")

        with (
            patch("hackagent.storage.remote.run_retrieve") as mock_get,
            patch("hackagent.storage.remote.run_partial_update") as mock_patch,
            patch("hackagent.storage.remote.run_finish_create") as mock_finish,
        ):
            mock_get.sync_detailed.return_value = _mock_response(200, parsed=row)
            record = self.backend.update_campaign_run(row.id, status="RUNNING")

        mock_patch.sync_detailed.assert_not_called()
        mock_finish.sync_detailed.assert_not_called()
        self.assertEqual(record.status, "RUNNING")

    def test_update_campaign_run_clears_a_note_with_an_empty_string(self):
        row = _mock_run_row(_campaign_marker())
        row.run_notes = ""

        with patch("hackagent.storage.remote.run_finish_create") as mock_finish:
            mock_finish.sync_detailed.return_value = _mock_response(200, parsed=row)
            record = self.backend.update_campaign_run(
                row.id, status="COMPLETED", run_notes=""
            )

        self.assertEqual(
            _sent_json(run_finish_create, mock_finish),
            {"status": "COMPLETED", "note": ""},
        )
        self.assertEqual(record.run_notes, "")

    def test_update_campaign_run_never_finishes_over_lost_writes(self):
        """A campaign whose results did not all reach the server is not
        COMPLETED: the failure surfaces first, and the caller records it."""
        self.backend._count_failure()

        with patch("hackagent.storage.remote.run_finish_create") as mock_finish:
            with self.assertRaisesRegex(RuntimeError, "background audit write"):
                self.backend.update_campaign_run(_uid(), status="COMPLETED")

        mock_finish.sync_detailed.assert_not_called()

    def test_update_campaign_run_raises_on_error(self):
        with patch("hackagent.storage.remote.run_partial_update") as mock_patch:
            mock_patch.sync_detailed.return_value = _mock_response(500)
            with self.assertRaisesRegex(RuntimeError, "campaign run"):
                self.backend.update_campaign_run(_uid(), audit={"passed": True})

    def test_list_campaign_runs_returns_only_the_markers(self):
        rows = [
            _mock_run_row({"batch_size": 4}),
            _mock_run_row(_campaign_marker(name="Nightly")),
            _mock_run_row(_campaign_marker(name="Weekly")),
        ]

        with patch("hackagent.storage.remote.run_list") as mock_list:
            mock_list.sync_detailed.return_value = _mock_page(rows, count=3)
            result = self.backend.list_campaign_runs()

        self.assertEqual([item.name for item in result.items], ["Nightly", "Weekly"])


class TestRemoteBackendRunCampaignLink(unittest.TestCase):
    """An attack run is a child of its campaign run."""

    def setUp(self):
        self.client = _mock_client()
        self.backend = RemoteBackend(self.client)
        self.backend._context = OrganizationContext(org_id=_uid(), user_id="1")

    def test_get_run_reads_the_campaign_parent_back(self):
        campaign_run_id = _uid()
        row = _mock_run_row({"expected_total_goals": 3}, parent=campaign_run_id)

        with patch("hackagent.storage.remote.run_retrieve") as mock_get:
            mock_get.sync_detailed.return_value = _mock_response(200, parsed=row)
            record = self.backend.get_run(row.id)

        self.assertEqual(record.campaign_run_id, campaign_run_id)

    def test_list_runs_reads_the_campaign_parent(self):
        campaign_run_id = _uid()
        row = _mock_run_row({}, parent=campaign_run_id)

        with patch("hackagent.storage.remote.run_list") as mock_list:
            mock_list.sync_detailed.return_value = _mock_page([row], count=1)
            result = self.backend.list_runs()

        self.assertEqual(result.items[0].campaign_run_id, campaign_run_id)

    def test_list_runs_hides_campaign_markers(self):
        attack_row = _mock_run_row({"batch_size": 4})
        rows = [_mock_run_row(_campaign_marker()), attack_row]

        with patch("hackagent.storage.remote.run_list") as mock_list:
            mock_list.sync_detailed.return_value = _mock_page(rows, count=2)
            result = self.backend.list_runs()

        self.assertEqual([item.id for item in result.items], [attack_row.id])
        self.assertEqual(result.total, 1)

    def test_list_runs_total_counts_only_what_paging_can_reach(self):
        """A marker on an early page must not inflate the total.

        The hosted count includes campaign parents this listing filters out,
        so stopping at the requested page would report runs that no later
        page can produce. Once a marker is seen the scan runs to the end.
        """
        page_one = _mock_page(
            [_mock_run_row(_campaign_marker()), _mock_run_row({"n": 1})],
            count=5,
            next_url="https://api.example.com/run/?page=2",
        )
        page_two = _mock_page(
            [
                _mock_run_row(_campaign_marker()),
                _mock_run_row({"n": 2}),
                _mock_run_row({"n": 3}),
            ],
            count=5,
        )

        with patch("hackagent.storage.remote.run_list") as mock_list:
            mock_list.sync_detailed.side_effect = [page_one, page_two]
            result = self.backend.list_runs(page=1, page_size=1)

        self.assertEqual(len(result.items), 1)
        # Three attack runs, not the hosted count of five.
        self.assertEqual(result.total, 3)

    def test_list_runs_stops_at_the_requested_page_when_nothing_is_filtered(self):
        """Without a marker the hosted count is exact, so one request is enough."""
        page_one = _mock_page(
            [_mock_run_row({"n": 1})],
            count=10,
            next_url="https://api.example.com/run/?page=2",
        )

        with patch("hackagent.storage.remote.run_list") as mock_list:
            mock_list.sync_detailed.side_effect = [page_one]
            result = self.backend.list_runs(page=1, page_size=1)

        self.assertEqual(mock_list.sync_detailed.call_count, 1)
        self.assertEqual(result.total, 10)


class TestRemoteBackendClose(unittest.TestCase):
    """Closing a backend releases what it holds, so many can come and go."""

    def test_close_drops_the_exit_hook(self):
        with patch("hackagent.storage.remote.atexit") as mock_atexit:
            backend = RemoteBackend(_mock_client())
            mock_atexit.register.assert_called_once_with(backend.close)
            backend.close()
            backend.close()
        mock_atexit.unregister.assert_called_once_with(backend.close)

    def test_close_keeps_a_shared_client_open_unless_asked(self):
        client = _mock_client()
        backend = RemoteBackend(client)
        backend.close()
        client.get_httpx_client.return_value.close.assert_not_called()

        backend.close(close_client=True)
        client.get_httpx_client.return_value.close.assert_called_once()


class TestRemoteBackendExecutorProtocol(unittest.TestCase):
    """Claim, heartbeat and finish: the calls an executor makes on a run."""

    def setUp(self):
        self.client = _mock_client()
        self.backend = RemoteBackend(self.client)

    def test_get_run_detail_returns_the_raw_run(self):
        run_id = _uid()
        content = (
            f'{{"id": "{run_id}", "status": "PENDING", "executor": "local", '
            '"claimed_by": "", "run_config": {"campaign_config": {"version": 1}}}'
        ).encode()

        with patch("hackagent.storage.remote.run_retrieve") as mock_get:
            mock_get.sync_detailed.return_value = _mock_response(200, content=content)
            detail = self.backend.get_run_detail(run_id)

        self.assertEqual(detail["status"], "PENDING")
        self.assertEqual(detail["executor"], "local")
        self.assertEqual(detail["claimed_by"], "")
        self.assertEqual(detail["run_config"], {"campaign_config": {"version": 1}})
        # The executor needs the run, not every result it will produce.
        self.assertIs(mock_get.sync_detailed.call_args.kwargs["include_results"], False)

    def test_get_run_detail_raises_when_missing(self):
        with patch("hackagent.storage.remote.run_retrieve") as mock_get:
            mock_get.sync_detailed.return_value = _mock_response(404)
            with self.assertRaisesRegex(RuntimeError, "not found"):
                self.backend.get_run_detail(_uid())

    def test_claim_returns_the_run_with_its_credentials(self):
        run_id = _uid()
        content = (
            f'{{"id": "{run_id}", "status": "RUNNING", "run_token": "tok", '
            '"env": {"OPENAI_KEY": "value"}}'
        ).encode()

        with patch("hackagent.storage.remote.run_claim_create") as mock_claim:
            mock_claim.sync_detailed.return_value = _mock_response(200, content=content)
            claim = self.backend.claim_run(run_id, "cloud-worker:pod-1")

        self.assertEqual(mock_claim.sync_detailed.call_args.kwargs["id"], run_id)
        self.assertEqual(
            _sent_json(run_claim_create, mock_claim),
            {"claimed_by": "cloud-worker:pod-1"},
        )
        self.assertIsInstance(claim, ClaimResult)
        self.assertEqual(claim.run, {"id": str(run_id), "status": "RUNNING"})
        self.assertEqual(claim.run_token, "tok")
        self.assertEqual(claim.env, {"OPENAI_KEY": "value"})

    def test_a_local_claim_has_no_credentials(self):
        content = b'{"id": "x", "status": "RUNNING"}'

        with patch("hackagent.storage.remote.run_claim_create") as mock_claim:
            mock_claim.sync_detailed.return_value = _mock_response(200, content=content)
            claim = self.backend.claim_run(_uid(), "local:host (me)")

        self.assertIsNone(claim.run_token)
        self.assertEqual(claim.env, {})

    def test_claim_409_raises_not_claimable(self):
        content = (
            b'{"detail": "Run is already claimed by local:other.", '
            b'"claimed_by": "local:other", "status": "RUNNING"}'
        )

        with patch("hackagent.storage.remote.run_claim_create") as mock_claim:
            mock_claim.sync_detailed.return_value = _mock_response(409, content=content)
            with self.assertRaises(RunNotClaimable) as caught:
                self.backend.claim_run(_uid(), "local:host (me)")

        self.assertEqual(caught.exception.claimed_by, "local:other")
        self.assertEqual(caught.exception.status, "RUNNING")
        self.assertEqual(
            caught.exception.note, "Run is already claimed by local:other."
        )

    def test_claim_409_of_an_unclaimed_run_names_nobody(self):
        content = (
            b'{"detail": "Run is cancelled and cannot be claimed.", '
            b'"claimed_by": "", "status": "CANCELLED"}'
        )

        with patch("hackagent.storage.remote.run_claim_create") as mock_claim:
            mock_claim.sync_detailed.return_value = _mock_response(409, content=content)
            with self.assertRaises(RunNotClaimable) as caught:
                self.backend.claim_run(_uid(), "local:host (me)")

        self.assertIsNone(caught.exception.claimed_by)
        self.assertEqual(caught.exception.status, "CANCELLED")

    def test_claim_raises_on_other_errors(self):
        with patch("hackagent.storage.remote.run_claim_create") as mock_claim:
            mock_claim.sync_detailed.return_value = _mock_response(403)
            with self.assertRaisesRegex(RuntimeError, "403"):
                self.backend.claim_run(_uid(), "local:host (me)")

    def test_a_refused_claim_carries_its_status_and_reason_only(self):
        content = b'{"detail": "Invalid token.", "echo": "secret-value"}'
        with patch("hackagent.storage.remote.run_claim_next_create") as mock_next:
            mock_next.sync_detailed.return_value = _mock_response(401, content=content)
            with self.assertRaises(ClaimFailed) as caught:
                self.backend.claim_next_run("cloud-worker:pod-1")

        self.assertEqual(caught.exception.status_code, 401)
        self.assertEqual(caught.exception.detail, "Invalid token.")
        self.assertNotIn("secret-value", str(caught.exception))

    def test_claim_next_returns_a_claim(self):
        content = b'{"id": "x", "status": "RUNNING", "run_token": "tok", "env": {}}'

        with patch("hackagent.storage.remote.run_claim_next_create") as mock_next:
            mock_next.sync_detailed.return_value = _mock_response(200, content=content)
            claim = self.backend.claim_next_run("cloud-worker:pod-1")

        self.assertEqual(
            _sent_json(run_claim_next_create, mock_next),
            {"claimed_by": "cloud-worker:pod-1"},
        )
        self.assertEqual(claim.run_token, "tok")

    def test_claim_next_returns_none_when_the_queue_is_empty(self):
        with patch("hackagent.storage.remote.run_claim_next_create") as mock_next:
            mock_next.sync_detailed.return_value = _mock_response(204, content=b"")
            self.assertIsNone(self.backend.claim_next_run("cloud-worker:pod-1"))

    def test_heartbeat_returns_whether_a_cancel_was_requested(self):
        with patch("hackagent.storage.remote.run_heartbeat_create") as mock_hb:
            mock_hb.sync_detailed.return_value = _mock_response(
                200, content=b'{"cancel_requested": true}'
            )
            self.assertTrue(self.backend.heartbeat_run(_uid()))
            mock_hb.sync_detailed.return_value = _mock_response(
                200, content=b'{"cancel_requested": false}'
            )
            self.assertFalse(self.backend.heartbeat_run(_uid()))

    def test_heartbeat_401_raises_executor_rejected(self):
        for status in (401, 403):
            with patch("hackagent.storage.remote.run_heartbeat_create") as mock_hb:
                mock_hb.sync_detailed.return_value = _mock_response(status)
                with self.assertRaises(ExecutorRejected):
                    self.backend.heartbeat_run(_uid())

    def test_heartbeat_raises_on_other_errors(self):
        with patch("hackagent.storage.remote.run_heartbeat_create") as mock_hb:
            mock_hb.sync_detailed.return_value = _mock_response(502)
            with self.assertRaises(RuntimeError) as caught:
                self.backend.heartbeat_run(_uid())
        self.assertNotIsInstance(caught.exception, ExecutorRejected)

    def test_finish_run_sends_status_and_note(self):
        run_id = _uid()

        finished = MagicMock()

        with patch("hackagent.storage.remote.run_finish_create") as mock_finish:
            mock_finish.sync_detailed.return_value = _mock_response(
                200, parsed=finished
            )
            run = self.backend.finish_run(run_id, "CANCELLED", "Campaign cancelled")

        self.assertIs(run, finished)

        self.assertEqual(mock_finish.sync_detailed.call_args.kwargs["id"], run_id)
        self.assertEqual(
            _sent_json(run_finish_create, mock_finish),
            {"status": "CANCELLED", "note": "Campaign cancelled"},
        )

    def test_finish_run_waits_for_queued_writes(self):
        """Finishing a campaign run revokes its run token, so every queued
        result and trace write must reach the server before the finish."""
        started, release = threading.Event(), threading.Event()
        order = []

        def queued_write():
            started.set()
            release.wait(5)
            order.append("write")

        def finish(**_kwargs):
            order.append("finish")
            return _mock_response(200, parsed=MagicMock())

        self.backend._enqueue(queued_write)
        self.assertTrue(started.wait(5))
        with patch("hackagent.storage.remote.run_finish_create") as mock_finish:
            mock_finish.sync_detailed.side_effect = finish
            finisher = threading.Thread(
                target=self.backend.finish_run, args=(_uid(), "COMPLETED")
            )
            finisher.start()
            time.sleep(0.1)  # time for a finish that does not wait to happen
            self.assertEqual(order, [])
            release.set()
            finisher.join(5)

        self.assertEqual(order, ["write", "finish"])

    def test_finish_run_refuses_a_status_that_is_not_final(self):
        with self.assertRaises(ValueError):
            self.backend.finish_run(_uid(), "RUNNING")

    def test_finish_run_403_raises_executor_rejected(self):
        with patch("hackagent.storage.remote.run_finish_create") as mock_finish:
            mock_finish.sync_detailed.return_value = _mock_response(403)
            with self.assertRaises(ExecutorRejected):
                self.backend.finish_run(_uid(), "COMPLETED")

    def test_no_run_tests_calls(self):
        """Runs are created by the campaign start and children endpoints only."""
        import inspect

        self.assertNotIn("run_run_tests", inspect.getsource(remote))


if __name__ == "__main__":
    unittest.main()


def test_check_key_raises_invalid_api_key_on_401():
    from hackagent.storage import InvalidApiKey
    from hackagent.storage._http.api.key import key_context_retrieve

    backend = RemoteBackend(MagicMock())
    with patch.object(
        key_context_retrieve, "sync_detailed", return_value=MagicMock(status_code=401)
    ):
        with unittest.TestCase().assertRaises(InvalidApiKey):
            backend.check_key()
    with patch.object(
        key_context_retrieve, "sync_detailed", return_value=MagicMock(status_code=200)
    ):
        backend.check_key()


def test_list_queued_local_runs_filters_and_orders_newest_first():
    from hackagent.storage._http.api.run import run_list

    def run(day):
        return MagicMock(
            id=_uid(),
            agent_name="a",
            campaign=None,
            timestamp=datetime(2026, 1, day, tzinfo=timezone.utc),
        )

    old, new = run(1), run(2)
    page = MagicMock(status_code=200, parsed=MagicMock(results=[old, new], next=None))
    with patch.object(run_list, "sync_detailed", return_value=page) as listing:
        runs = RemoteBackend(MagicMock()).list_queued_local_runs()
    assert [r["id"] for r in runs] == [str(new.id), str(old.id)]
    kwargs = listing.call_args.kwargs
    assert kwargs["executor"].value == "local"
    assert kwargs["status"].value == "PENDING"
    assert kwargs["parent_isnull"] is True
