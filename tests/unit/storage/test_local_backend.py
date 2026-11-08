# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for LocalBackend (server/storage/local.py)."""

import os
import sqlite3
import tempfile
import threading
import unittest
from datetime import datetime
from uuid import UUID, uuid4

from hackagent.reporting import AttackRun, campaign_run_costs
from hackagent.storage.local import LocalBackend, _row_to_outcome, _row_to_usage
from hackagent.storage.records import (
    AgentRecord,
    AttackRecord,
    CampaignRunRecord,
    OrganizationContext,
    PaginatedResult,
    RunRecord,
    ResultRecord,
    TraceRecord,
)


def _make_backend(tmp_dir: str) -> LocalBackend:
    return LocalBackend(db_path=os.path.join(tmp_dir, "test.db"))


def _tallies(backend: LocalBackend, run_id) -> tuple[list, list]:
    conn = backend._conn
    outcomes = conn.execute(
        "SELECT * FROM goal_outcomes WHERE run_id=? ORDER BY goal_index",
        (str(run_id),),
    ).fetchall()
    usage = conn.execute(
        "SELECT * FROM goal_usage WHERE run_id=? ORDER BY goal_index, label",
        (str(run_id),),
    ).fetchall()
    return [_row_to_outcome(row) for row in outcomes], [
        _row_to_usage(row) for row in usage
    ]


def _run_costs(backend: LocalBackend, run_id) -> dict:
    """A run's costs from its stored tallies, which must equal the tallies a
    full recomputation gives: the write path keeps them incrementally."""
    kept = _tallies(backend, run_id)
    backend._rebuild_tallies()
    assert _tallies(backend, run_id) == kept
    run = AttackRun(
        id=str(run_id),
        campaign_run="",
        status="COMPLETED",
        created_at=datetime(2026, 1, 1),
    )
    [cost] = campaign_run_costs([run], *kept, backend.report_latencies([str(run_id)]))[
        "runs"
    ]
    return cost


class TestLocalBackendInit(unittest.TestCase):
    """Test LocalBackend initialisation."""

    def test_creates_db_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            backend = _make_backend(tmp)
            try:
                self.assertTrue(os.path.exists(os.path.join(tmp, "test.db")))
            finally:
                backend.close()

    def test_get_api_key_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            backend = _make_backend(tmp)
            try:
                self.assertIsNone(backend.get_api_key())
            finally:
                backend.close()

    def test_existing_database_gains_campaign_run_relationship(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "test.db")
            connection = sqlite3.connect(path)
            connection.execute(
                """CREATE TABLE runs (
                    id TEXT PRIMARY KEY,
                    attack_id TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    config_json TEXT NOT NULL DEFAULT '{}',
                    status TEXT NOT NULL DEFAULT 'PENDING',
                    run_notes TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )"""
            )
            connection.commit()
            connection.close()

            backend = LocalBackend(db_path=path)
            try:
                columns = {
                    row[1]
                    for row in backend._conn.execute(
                        "PRAGMA table_info(runs)"
                    ).fetchall()
                }
                self.assertIn("campaign_run_id", columns)
            finally:
                backend.close()

    def test_existing_database_records_which_campaign_runs_the_dashboard_launched(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "test.db")
            backend = LocalBackend(db_path=path)
            agent = backend.create_or_update_agent("a", {})
            campaign = backend.create_campaign("c", "", agent.id, {})
            launched = backend.start_campaign(agent.id, {})
            backend.link_campaign_run(launched.id, campaign.id)
            cli = backend.start_campaign(agent.id, {})
            # A database from before the column: only a launch set campaign_id.
            backend._conn.execute("ALTER TABLE campaign_runs DROP COLUMN launched")
            backend._conn.commit()
            backend.close()

            backend = LocalBackend(db_path=path)
            try:
                self.assertTrue(backend.get_campaign_run(launched.id).launched)
                self.assertFalse(backend.get_campaign_run(cli.id).launched)
            finally:
                backend.close()

    def test_a_launch_stays_recorded_when_its_campaign_is_deleted(self):
        with tempfile.TemporaryDirectory() as tmp:
            backend = _make_backend(tmp)
            try:
                agent = backend.create_or_update_agent("a", {})
                campaign = backend.create_campaign("c", "", agent.id, {})
                record = backend.start_campaign(agent.id, {})
                backend.link_campaign_run(record.id, campaign.id)
                backend.delete_campaign(campaign.id)
                kept = backend.get_campaign_run(record.id)
                self.assertEqual((kept.campaign_id, kept.launched), (None, True))
            finally:
                backend.close()

    def test_multiple_instances_same_db(self):
        """Two instances pointing at the same path share data."""
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "shared.db")
            b1 = LocalBackend(db_path=path)
            b2 = LocalBackend(db_path=path)
            try:
                # Both see the same context UUID
                ctx1 = b1.get_context()
                ctx2 = b2.get_context()
                self.assertEqual(ctx1.org_id, ctx2.org_id)
            finally:
                b1.close()
                b2.close()


class TestLocalBackendContext(unittest.TestCase):
    """Test get_context behaviour."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.backend = _make_backend(self.tmp)

    def test_returns_organization_context(self):
        ctx = self.backend.get_context()
        self.assertIsInstance(ctx, OrganizationContext)
        self.assertIsInstance(ctx.org_id, UUID)
        self.assertEqual(ctx.user_id, "local")

    def test_idempotent_on_repeated_calls(self):
        ctx1 = self.backend.get_context()
        ctx2 = self.backend.get_context()
        self.assertEqual(ctx1.org_id, ctx2.org_id)

    def test_context_persisted_across_instances(self):
        path = os.path.join(self.tmp, "ctx.db")
        b1 = LocalBackend(db_path=path)
        org_id = b1.get_context().org_id
        b2 = LocalBackend(db_path=path)
        self.assertEqual(b2.get_context().org_id, org_id)


class TestLocalBackendAgent(unittest.TestCase):
    """Test agent CRUD operations."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.backend = _make_backend(self.tmp)

    def _create_agent(self, name="my-agent") -> AgentRecord:
        return self.backend.create_or_update_agent(
            name,
            {
                "connection": {"type": "LITELLM", "endpoint": "http://localhost:8000"},
                "generation": {"model": "gpt-4o-mini"},
            },
        )

    def test_create_agent_returns_record(self):
        rec = self._create_agent()
        self.assertIsInstance(rec, AgentRecord)
        self.assertEqual(rec.name, "my-agent")
        self.assertEqual(rec.agent_type, "LITELLM")
        self.assertEqual(rec.endpoint, "http://localhost:8000")
        self.assertEqual(rec.metadata["generation"], {"model": "gpt-4o-mini"})
        self.assertEqual(rec.owner, "local")
        self.assertIsInstance(rec.id, UUID)
        self.assertIsInstance(rec.created_at, datetime)

    def test_create_agent_assigned_to_org(self):
        ctx = self.backend.get_context()
        rec = self._create_agent()
        self.assertEqual(rec.organization, ctx.org_id)

    def test_same_name_returns_same_id(self):
        rec1 = self._create_agent("duplicate")
        rec2 = self._create_agent("duplicate")
        self.assertEqual(rec1.id, rec2.id)

    def test_update_agent_replaces_the_config(self):
        self._create_agent()
        rec2 = self.backend.create_or_update_agent(
            "my-agent",
            {
                "connection": {"type": "OLLAMA", "endpoint": "http://localhost:11434"},
                "generation": {"temperature": 0.5},
            },
        )
        self.assertEqual(rec2.agent_type, "OLLAMA")
        self.assertEqual(rec2.endpoint, "http://localhost:11434")
        self.assertEqual(rec2.metadata["generation"], {"temperature": 0.5})
        self.assertEqual(self.backend.get_agent(rec2.id), rec2)

    def test_agent_without_endpoint(self):
        rec = self.backend.create_or_update_agent(
            "hosted", {"connection": {"type": "OPENAI"}}
        )
        self.assertEqual(rec.endpoint, "")

    def test_list_agents_empty(self):
        result = self.backend.list_agents()
        self.assertIsInstance(result, PaginatedResult)
        self.assertEqual(result.total, 0)
        self.assertEqual(result.items, [])

    def test_list_agents_after_create(self):
        self._create_agent("agent-a")
        self._create_agent("agent-b")
        result = self.backend.list_agents()
        self.assertEqual(result.total, 2)
        self.assertEqual(len(result.items), 2)
        names = {a.name for a in result.items}
        self.assertEqual(names, {"agent-a", "agent-b"})

    def test_get_agent_by_id(self):
        created = self._create_agent()
        fetched = self.backend.get_agent(created.id)
        self.assertEqual(fetched.id, created.id)
        self.assertEqual(fetched.name, created.name)

    def test_get_agent_not_found_raises(self):
        with self.assertRaises(RuntimeError):
            self.backend.get_agent(uuid4())

    def test_delete_agent(self):
        rec = self._create_agent()
        self.backend.delete_agent(rec.id)
        result = self.backend.list_agents()
        self.assertEqual(result.total, 0)

    def test_delete_nonexistent_agent_no_error(self):
        # Should not raise — graceful no-op
        self.backend.delete_agent(uuid4())

    def test_list_agents_pagination(self):
        for i in range(5):
            self._create_agent(f"agent-{i}")
        page1 = self.backend.list_agents(page=1, page_size=3)
        page2 = self.backend.list_agents(page=2, page_size=3)
        self.assertEqual(page1.total, 5)
        self.assertEqual(len(page1.items), 3)
        self.assertEqual(len(page2.items), 2)


class TestLocalBackendAttack(unittest.TestCase):
    """Test attack CRUD."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.backend = _make_backend(self.tmp)
        self.agent = self.backend.create_or_update_agent(
            "test-agent",
            {"connection": {"type": "LITELLM", "endpoint": "http://localhost:8000"}},
        )

    def test_create_attack(self):
        org = self.backend.get_context().org_id
        rec = self.backend.create_attack(
            attack_type="flipattack",
            agent_id=self.agent.id,
            organization=org,
            configuration={"goals": ["test"]},
        )
        self.assertIsInstance(rec, AttackRecord)
        self.assertEqual(rec.type, "flipattack")
        self.assertEqual(rec.agent_id, self.agent.id)
        self.assertEqual(rec.configuration["goals"], ["test"])

    def test_list_attacks_empty(self):
        result = self.backend.list_attacks()
        self.assertEqual(result.total, 0)

    def test_list_attacks_after_create(self):
        org = self.backend.get_context().org_id
        self.backend.create_attack("tap", self.agent.id, org, {})
        self.backend.create_attack("bon", self.agent.id, org, {})
        result = self.backend.list_attacks()
        self.assertEqual(result.total, 2)
        types = {a.type for a in result.items}
        self.assertEqual(types, {"tap", "bon"})


class TestLocalBackendCampaignRun(unittest.TestCase):
    """Campaign runs own the spec and audit; attack runs link to them."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.backend = _make_backend(self.tmp)
        self.agent = self.backend.create_or_update_agent(
            "campaign-target",
            {
                "connection": {
                    "type": "OPENAI_SDK",
                    "endpoint": "http://localhost:8000/v1",
                }
            },
        )

    def test_campaign_run_round_trip(self):
        record = self.backend.start_campaign(
            self.agent.id,
            {"version": 1, "campaign": {"name": "safety campaign"}},
        )
        self.assertIsInstance(record, CampaignRunRecord)
        self.assertEqual(record.name, "safety campaign")
        self.assertEqual(record.status, "RUNNING")

        audit = {"samples": 2, "passed": True, "judges": []}
        updated = self.backend.update_campaign_run(
            record.id, status="COMPLETED", audit=audit
        )
        fetched = self.backend.get_campaign_run(record.id)

        self.assertEqual(updated.audit, audit)
        self.assertEqual(fetched, updated)
        self.assertEqual(self.backend.list_campaign_runs().items, [updated])

    def test_attack_run_has_a_real_campaign_foreign_key(self):
        campaign_run = self.backend.start_campaign(
            self.agent.id, {"version": 1, "campaign": {"name": "campaign"}}
        )
        attack = self.backend.create_attack(
            "baseline", self.agent.id, self.backend.get_context().org_id, {}
        )
        attack_run = self.backend.create_run(
            attack.id,
            self.agent.id,
            {},
            campaign_run_id=campaign_run.id,
        )

        self.assertEqual(attack_run.campaign_run_id, campaign_run.id)
        self.assertEqual(
            self.backend.get_run(attack_run.id).campaign_run_id, campaign_run.id
        )


class TestLocalBackendRun(unittest.TestCase):
    """Test run CRUD."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.backend = _make_backend(self.tmp)
        self.agent = self.backend.create_or_update_agent(
            "test-agent",
            {"connection": {"type": "LITELLM", "endpoint": "http://localhost:8000"}},
        )
        org = self.backend.get_context().org_id
        self.attack = self.backend.create_attack("flipattack", self.agent.id, org, {})

    def test_create_run(self):
        rec = self.backend.create_run(
            attack_id=self.attack.id,
            agent_id=self.agent.id,
            run_config={"batch_size": 4},
        )
        self.assertIsInstance(rec, RunRecord)
        self.assertEqual(rec.status, "PENDING")
        self.assertIsNone(rec.run_notes)
        self.assertEqual(rec.run_config["batch_size"], 4)

    def test_create_run_generates_unique_ids(self):
        r1 = self.backend.create_run(self.attack.id, self.agent.id, {})
        r2 = self.backend.create_run(self.attack.id, self.agent.id, {})
        self.assertNotEqual(r1.id, r2.id)

    def test_update_run_status(self):
        rec = self.backend.create_run(self.attack.id, self.agent.id, {})
        updated = self.backend.update_run(rec.id, status="RUNNING")
        self.assertEqual(updated.status, "RUNNING")

    def test_update_run_notes(self):
        rec = self.backend.create_run(self.attack.id, self.agent.id, {})
        updated = self.backend.update_run(rec.id, run_notes="Test notes")
        self.assertEqual(updated.run_notes, "Test notes")

    def test_update_run_status_and_notes(self):
        rec = self.backend.create_run(self.attack.id, self.agent.id, {})
        updated = self.backend.update_run(rec.id, status="COMPLETED", run_notes="done")
        self.assertEqual(updated.status, "COMPLETED")
        self.assertEqual(updated.run_notes, "done")

    def test_get_run(self):
        rec = self.backend.create_run(self.attack.id, self.agent.id, {})
        fetched = self.backend.get_run(rec.id)
        self.assertEqual(fetched.id, rec.id)
        self.assertEqual(fetched.status, "PENDING")

    def test_get_run_not_found_raises(self):
        with self.assertRaises(RuntimeError):
            self.backend.get_run(uuid4())

    def test_list_runs_all(self):
        self.backend.create_run(self.attack.id, self.agent.id, {})
        self.backend.create_run(self.attack.id, self.agent.id, {})
        result = self.backend.list_runs()
        self.assertEqual(result.total, 2)

    def test_list_runs_by_attack(self):
        r1 = self.backend.create_run(self.attack.id, self.agent.id, {})
        org = self.backend.get_context().org_id
        atk2 = self.backend.create_attack("bon", self.agent.id, org, {})
        self.backend.create_run(atk2.id, self.agent.id, {})

        # Filter by attack 1
        result = self.backend.list_runs(attack_id=self.attack.id)
        self.assertEqual(result.total, 1)
        self.assertEqual(result.items[0].id, r1.id)

    def test_list_runs_pagination(self):
        for _ in range(5):
            self.backend.create_run(self.attack.id, self.agent.id, {})
        page1 = self.backend.list_runs(page=1, page_size=3)
        page2 = self.backend.list_runs(page=2, page_size=3)
        self.assertEqual(page1.total, 5)
        self.assertEqual(len(page1.items), 3)
        self.assertEqual(len(page2.items), 2)


class TestLocalBackendResult(unittest.TestCase):
    """Test result CRUD."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.backend = _make_backend(self.tmp)
        agent = self.backend.create_or_update_agent(
            "agent", {"connection": {"type": "LITELLM", "endpoint": "http://localhost"}}
        )
        org = self.backend.get_context().org_id
        attack = self.backend.create_attack("tap", agent.id, org, {})
        self.run = self.backend.create_run(attack.id, agent.id, {})

    def test_create_result(self):
        rec = self.backend.create_result(
            run_id=self.run.id,
            goal="Test jailbreak goal",
            goal_index=0,
            request_payload={"prompt": "ignore instructions"},
            agent_specific_data={"model": "gpt-4"},
        )
        self.assertIsInstance(rec, ResultRecord)
        self.assertEqual(rec.run_id, self.run.id)
        self.assertEqual(rec.goal, "Test jailbreak goal")
        self.assertEqual(rec.goal_index, 0)
        self.assertEqual(rec.evaluation_status, "NOT_EVALUATED")
        self.assertIsNone(rec.evaluation_notes)

    def test_cost_samples_aggregate_real_goals_without_double_counting_traces(self):
        first = self.backend.create_result(self.run.id, "goal", 0, {}, {})
        second = self.backend.create_result(self.run.id, "goal", 0, {}, {})
        untraced = self.backend.create_result(self.run.id, "other", 1, {}, {})
        for result in (first, second):
            self.backend.create_trace(
                result.id,
                0,
                "interaction",
                {"response": {"usage": {"prompt_tokens": 10, "completion_tokens": 2}}},
            )
            self.backend.create_trace(
                result.id,
                1,
                "OTHER",
                {
                    "node": "call",
                    "label": "target",
                    "data": {"usage": {"prompt_tokens": 10, "completion_tokens": 2}},
                },
            )
            self.backend.create_trace(
                result.id, 2, "OTHER", {"node": "call", "label": "attacker"}
            )
            self.backend.create_trace(
                result.id, 3, "OTHER", {"node": "call", "label": "panel"}
            )
        self.backend.create_trace(untraced.id, 0, "interaction", {})
        self.backend._conn.execute(
            "UPDATE results SET created_at = ?, updated_at = ? WHERE id IN (?, ?)",
            (
                "2026-01-01T00:00:00+00:00",
                "2026-01-01T00:00:10+00:00",
                str(first.id),
                str(second.id),
            ),
        )
        self.backend._conn.commit()
        self.backend._rebuild_tallies()
        cost = _run_costs(self.backend, self.run.id)
        samples = {sample["goal_index"]: sample for sample in cost["goal_samples"]}
        self.assertEqual(
            samples[0],
            {
                "goal_index": 0,
                "attempts": 2,
                "calls": 6,
                "target_tokens": 24,
                "elapsed_s": 10.0,
                "first_jailbreak_attempt": None,
                "first_jailbreak_elapsed_s": None,
            },
        )
        self.assertEqual(samples[1]["attempts"], 1)
        self.assertIsNone(samples[1]["calls"])
        self.assertIsNone(samples[1]["target_tokens"])
        # Goal 1 recorded only an interaction: its target call counts, and its
        # attacker and judge calls, so the run's, are unknown.
        self.assertEqual(cost["calls"], {"target": 3, "attacker": None, "judge": None})
        self.assertFalse(cost["calls_traced"])

    def test_first_success_uses_conversation_order_and_earliest_response_clock(self):
        results = [
            self.backend.create_result(self.run.id, "goal", 0, {}, {}) for _ in range(4)
        ]
        results.sort(key=lambda result: str(result.id))
        for index, result in enumerate(results):
            self.backend.update_result(
                result.id,
                evaluation_status="SUCCESSFUL_JAILBREAK"
                if index in (1, 2)
                else "FAILED_JAILBREAK",
                agent_specific_data={
                    "attack_metadata": {
                        "goal_active_target_elapsed_s": [0, 9, 3, 20][index]
                    }
                },
            )
            self.backend._conn.execute(
                "UPDATE results SET created_at = ?, updated_at = ? WHERE id = ?",
                (
                    "2026-01-01T00:00:00+00:00",
                    "2026-01-01T00:00:30+00:00",
                    str(result.id),
                ),
            )
        self.backend._conn.commit()
        self.backend._rebuild_tallies()
        sample = _run_costs(self.backend, self.run.id)["goal_samples"][0]
        self.assertEqual(sample["attempts"], 4)
        self.assertEqual(sample["first_jailbreak_attempt"], 2)
        self.assertEqual(sample["first_jailbreak_elapsed_s"], 3)

    def test_tokens_are_unknown_when_one_call_has_no_usage(self):
        for index, usage in enumerate(
            ({"prompt_tokens": 10, "completion_tokens": 2}, {})
        ):
            result = self.backend.create_result(self.run.id, "goal", 0, {}, {})
            self.backend.create_trace(
                result.id,
                0,
                "OTHER",
                {"node": "call", "label": "target", "data": {"usage": usage}},
            )
        cost = _run_costs(self.backend, self.run.id)
        self.assertIsNone(cost["target_tokens"])
        self.assertIsNone(cost["goal_samples"][0]["target_tokens"])

    def test_tokens_require_target_coverage_for_every_attempt(self):
        first = self.backend.create_result(self.run.id, "goal", 0, {}, {})
        second = self.backend.create_result(self.run.id, "goal", 0, {}, {})
        self.backend.create_trace(
            first.id,
            0,
            "OTHER",
            {
                "node": "call",
                "label": "target",
                "data": {"usage": {"prompt_tokens": 10, "completion_tokens": 2}},
            },
        )
        self.backend.create_trace(
            second.id, 0, "OTHER", {"node": "call", "label": "panel"}
        )
        cost = _run_costs(self.backend, self.run.id)
        self.assertIsNone(cost["target_tokens"])
        self.assertIsNone(cost["goal_samples"][0]["target_tokens"])

    def test_legacy_and_shared_batch_usage_remain_measurable(self):
        for shared in (False, True):
            with self.subTest(shared=shared):
                goal_index = int(shared)
                first = self.backend.create_result(
                    self.run.id, "goal", goal_index, {}, {}
                )
                second = self.backend.create_result(
                    self.run.id, "goal", goal_index, {}, {}
                )
                for index, result in enumerate((first, second)):
                    usage = {"prompt_tokens": 0, "completion_tokens": 0}
                    content = (
                        {
                            "node": "call",
                            "label": "target",
                            "scope": "goal",
                            "data": {"usage": usage},
                        }
                        if shared
                        else {"response": {"usage": usage}}
                    )
                    self.backend.create_trace(
                        first.id if shared else result.id,
                        index,
                        "OTHER" if shared else "interaction",
                        content,
                    )
                cost = _run_costs(self.backend, self.run.id)
                sample = next(
                    s for s in cost["goal_samples"] if s["goal_index"] == goal_index
                )
                self.assertEqual(sample["target_tokens"], 0)
                self.assertEqual(cost["target_tokens"], {"prompt": 0, "completion": 0})

    def test_run_tokens_are_unknown_when_another_goal_is_untraced(self):
        first = self.backend.create_result(self.run.id, "goal", 0, {}, {})
        self.backend.create_result(self.run.id, "other goal", 1, {}, {})
        self.backend.create_trace(
            first.id,
            0,
            "interaction",
            {"response": {"usage": {"prompt_tokens": 10, "completion_tokens": 2}}},
        )
        cost = _run_costs(self.backend, self.run.id)
        self.assertIsNone(cost["target_tokens"])

    def test_run_tokens_sum_legacy_and_current_goals_without_double_counting(self):
        for index in (0, 1):
            result = self.backend.create_result(self.run.id, "goal", index, {}, {})
            usage = {"prompt_tokens": 10, "completion_tokens": 2}
            self.backend.create_trace(
                result.id, 0, "interaction", {"response": {"usage": usage}}
            )
            if index:
                self.backend.create_trace(
                    result.id,
                    1,
                    "OTHER",
                    {"node": "call", "label": "target", "data": {"usage": usage}},
                )
        cost = _run_costs(self.backend, self.run.id)
        self.assertEqual(cost["target_tokens"], {"prompt": 20, "completion": 4})
        self.assertEqual([s["target_tokens"] for s in cost["goal_samples"]], [12, 12])

    def test_missing_completion_usage_is_not_assumed_to_be_zero(self):
        result = self.backend.create_result(self.run.id, "goal", 0, {}, {})
        self.backend.create_trace(
            result.id,
            0,
            "interaction",
            {"response": {"usage": {"prompt_tokens": 10}}},
        )
        cost = _run_costs(self.backend, self.run.id)
        self.assertIsNone(cost["target_tokens"])
        self.assertIsNone(cost["goal_samples"][0]["target_tokens"])

    def test_first_success_keeps_missing_timing_null_and_zero_measurable(self):
        for index, status, timing in (
            (0, "SUCCESSFUL_JAILBREAK", None),
            (1, "SUCCESSFUL_JAILBREAK", 0),
            (2, "FAILED_JAILBREAK", 5),
            (3, "ERROR_AGENT_RESPONSE", 5),
            (4, "NOT_EVALUATED", 5),
        ):
            result = self.backend.create_result(self.run.id, "goal", index, {}, {})
            self.backend.update_result(
                result.id,
                evaluation_status=status,
                agent_specific_data={
                    "attack_metadata": {"goal_active_target_elapsed_s": timing}
                },
            )
        samples = {
            sample["goal_index"]: sample
            for sample in _run_costs(self.backend, self.run.id)["goal_samples"]
        }
        self.assertEqual(samples[0]["first_jailbreak_attempt"], 1)
        self.assertIsNone(samples[0]["first_jailbreak_elapsed_s"])
        self.assertEqual(samples[1]["first_jailbreak_elapsed_s"], 0)
        for index in (2, 3, 4):
            self.assertIsNone(samples[index]["first_jailbreak_attempt"])
            self.assertIsNone(samples[index]["first_jailbreak_elapsed_s"])
        later = self.backend.create_result(self.run.id, "goal", 0, {}, {})
        self.backend.update_result(
            later.id,
            evaluation_status="SUCCESSFUL_JAILBREAK",
            agent_specific_data={
                "attack_metadata": {"goal_active_target_elapsed_s": 10}
            },
        )
        sample = _run_costs(self.backend, self.run.id)["goal_samples"][0]
        self.assertIsNone(sample["first_jailbreak_elapsed_s"])

    def test_first_success_does_not_substitute_legacy_queue_inclusive_clock(self):
        result = self.backend.create_result(self.run.id, "goal", 0, {}, {})
        self.backend.update_result(
            result.id,
            evaluation_status="SUCCESSFUL_JAILBREAK",
            agent_specific_data={"attack_metadata": {"goal_target_elapsed_s": 1063}},
        )
        sample = _run_costs(self.backend, self.run.id)["goal_samples"][0]
        self.assertEqual(sample["first_jailbreak_attempt"], 1)
        self.assertIsNone(sample["first_jailbreak_elapsed_s"])

    def test_cost_samples_accept_shared_goal_scoped_batch_traces(self):
        first = self.backend.create_result(self.run.id, "goal", 0, {}, {})
        self.backend.create_result(self.run.id, "goal", 0, {}, {})
        for sequence, label in enumerate(
            ("attacker", "target", "panel", "target", "panel")
        ):
            self.backend.create_trace(
                first.id,
                sequence,
                "OTHER",
                {"node": "call", "scope": "goal", "label": label},
            )
        cost = _run_costs(self.backend, self.run.id)
        self.assertEqual(cost["goal_samples"][0]["calls"], 5)
        self.assertEqual(cost["goal_samples"][0]["attempts"], 2)

    def test_cost_samples_reject_incomplete_goal_scoped_batch_traces(self):
        first = self.backend.create_result(self.run.id, "goal", 0, {}, {})
        self.backend.create_result(self.run.id, "goal", 0, {}, {})
        for sequence, label in enumerate(("attacker", "target", "panel")):
            self.backend.create_trace(
                first.id,
                sequence,
                "OTHER",
                {"node": "call", "scope": "goal", "label": label},
            )
        cost = _run_costs(self.backend, self.run.id)
        self.assertIsNone(cost["goal_samples"][0]["calls"])

    def test_cost_samples_do_not_infer_coverage_from_unscoped_calls(self):
        first = self.backend.create_result(self.run.id, "goal", 0, {}, {})
        self.backend.create_result(self.run.id, "goal", 0, {}, {})
        for sequence in range(2):
            self.backend.create_trace(
                first.id, sequence, "OTHER", {"node": "call", "label": "target"}
            )
        cost = _run_costs(self.backend, self.run.id)
        self.assertIsNone(cost["goal_samples"][0]["calls"])

    def test_create_result_unique_ids(self):
        r1 = self.backend.create_result(self.run.id, "g1", 0, {}, {})
        r2 = self.backend.create_result(self.run.id, "g2", 1, {}, {})
        self.assertNotEqual(r1.id, r2.id)

    def test_request_payload_survives_evaluation_metadata_updates(self):
        payload = {"messages": [{"role": "user", "content": "Recorded prompt"}]}
        result = self.backend.create_result(self.run.id, "goal", 0, payload, {})
        self.assertEqual(result.metadata["request_payload"], payload)
        updated = self.backend.update_result(
            result.id, agent_specific_data={"response": "Recorded reply"}
        )
        self.assertEqual(updated.metadata["request_payload"], payload)
        fetched = self.backend.get_result(result.id)
        self.assertEqual(fetched.metadata["request_payload"], payload)
        self.assertEqual(fetched.metadata["response"], "Recorded reply")

    def test_update_result_evaluation_status(self):
        rec = self.backend.create_result(self.run.id, "goal", 0, {}, {})
        updated = self.backend.update_result(
            rec.id,
            evaluation_status="SUCCESSFUL_JAILBREAK",
            evaluation_notes="Model complied",
        )
        self.assertEqual(updated.evaluation_status, "SUCCESSFUL_JAILBREAK")
        self.assertEqual(updated.evaluation_notes, "Model complied")

    def test_update_result_metrics(self):
        rec = self.backend.create_result(self.run.id, "goal", 0, {}, {})
        updated = self.backend.update_result(
            rec.id,
            evaluation_metrics={"score": 0.9, "latency": 1.2},
        )
        self.assertEqual(updated.evaluation_metrics["score"], 0.9)

    def test_update_result_keeps_the_target_latency_in_the_metadata(self):
        # There are no columns for these; the web layer reads them from the
        # metadata, as it does the other response fields.
        rec = self.backend.create_result(self.run.id, "goal", 0, {}, {})
        updated = self.backend.update_result(
            rec.id,
            agent_specific_data={"request_index": 0},
            latency_ms=1250,
            response_status_code=429,
        )
        self.assertEqual(
            updated.metadata,
            {"request_index": 0, "latency_ms": 1250, "response_status_code": 429},
        )

    def test_update_result_adds_the_latency_to_the_stored_metadata(self):
        rec = self.backend.create_result(
            self.run.id, "goal", 0, {}, {"request_index": 0}
        )
        updated = self.backend.update_result(rec.id, latency_ms=80)
        self.assertEqual(updated.metadata, {"request_index": 0, "latency_ms": 80})

    def test_get_result(self):
        rec = self.backend.create_result(self.run.id, "goal", 0, {}, {})
        fetched = self.backend.get_result(rec.id)
        self.assertEqual(fetched.id, rec.id)
        self.assertEqual(fetched.goal, "goal")

    def test_get_result_not_found_raises(self):
        with self.assertRaises(RuntimeError):
            self.backend.get_result(uuid4())

    def test_list_results_by_run(self):
        self.backend.create_result(self.run.id, "g1", 0, {}, {})
        self.backend.create_result(self.run.id, "g2", 1, {}, {})
        result = self.backend.list_results(run_id=self.run.id)
        self.assertEqual(result.total, 2)
        goals = {r.goal for r in result.items}
        self.assertEqual(goals, {"g1", "g2"})

    def test_list_results_all(self):
        self.backend.create_result(self.run.id, "g1", 0, {}, {})
        self.backend.create_result(self.run.id, "g2", 1, {}, {})
        result = self.backend.list_results()
        self.assertEqual(result.total, 2)


class TestLocalBackendTrace(unittest.TestCase):
    """Test trace creation and listing."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.backend = _make_backend(self.tmp)
        agent = self.backend.create_or_update_agent(
            "agent", {"connection": {"type": "LITELLM", "endpoint": "http://localhost"}}
        )
        org = self.backend.get_context().org_id
        attack = self.backend.create_attack("bon", agent.id, org, {})
        run = self.backend.create_run(attack.id, agent.id, {})
        self.result = self.backend.create_result(run.id, "goal", 0, {}, {})

    def test_create_trace(self):
        rec = self.backend.create_trace(
            result_id=self.result.id,
            sequence=1,
            step_type="OTHER",
            content={"role": "user", "content": "test message"},
        )
        self.assertIsInstance(rec, TraceRecord)
        self.assertEqual(rec.result_id, self.result.id)
        self.assertEqual(rec.sequence, 1)
        self.assertEqual(rec.step_type, "OTHER")
        self.assertEqual(rec.content["role"], "user")

    def test_list_traces_ordered_by_sequence(self):
        self.backend.create_trace(self.result.id, 3, "OTHER", {"seq": 3})
        self.backend.create_trace(self.result.id, 1, "OTHER", {"seq": 1})
        self.backend.create_trace(self.result.id, 2, "OTHER", {"seq": 2})

        traces = self.backend.list_traces(self.result.id)
        self.assertEqual(len(traces), 3)
        self.assertEqual(traces[0].sequence, 1)
        self.assertEqual(traces[1].sequence, 2)
        self.assertEqual(traces[2].sequence, 3)

    def test_list_traces_empty(self):
        traces = self.backend.list_traces(self.result.id)
        self.assertEqual(traces, [])

    def test_list_traces_isolated_by_result(self):
        """Traces from different results don't bleed into each other."""
        # Create a second result
        agent = self.backend.create_or_update_agent(
            "agent2",
            {"connection": {"type": "LITELLM", "endpoint": "http://localhost"}},
        )
        org = self.backend.get_context().org_id
        atk = self.backend.create_attack("x", agent.id, org, {})
        run = self.backend.create_run(atk.id, agent.id, {})
        other_result = self.backend.create_result(run.id, "goal2", 0, {}, {})

        self.backend.create_trace(self.result.id, 1, "OTHER", {"msg": "mine"})
        self.backend.create_trace(other_result.id, 1, "OTHER", {"msg": "theirs"})

        mine = self.backend.list_traces(self.result.id)
        theirs = self.backend.list_traces(other_result.id)
        self.assertEqual(len(mine), 1)
        self.assertEqual(len(theirs), 1)
        self.assertEqual(mine[0].content["msg"], "mine")
        self.assertEqual(theirs[0].content["msg"], "theirs")


class TestLocalBackendDeleteAndBuckets(unittest.TestCase):
    """Test deletion cascades and dashboard bucket counters."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.backend = _make_backend(self.tmp)
        self.agent = self.backend.create_or_update_agent(
            "agent", {"connection": {"type": "LITELLM", "endpoint": "http://localhost"}}
        )
        org = self.backend.get_context().org_id
        self.attack = self.backend.create_attack("pair", self.agent.id, org, {})

    def _create_result_with_status(
        self,
        run_id: UUID,
        goal: str,
        goal_index: int,
        status: str,
        notes: str | None = None,
    ) -> ResultRecord:
        result = self.backend.create_result(run_id, goal, goal_index, {}, {})
        return self.backend.update_result(
            result.id,
            evaluation_status=status,
            evaluation_notes=notes,
        )

    def test_count_result_buckets(self):
        run = self.backend.create_run(self.attack.id, self.agent.id, {})

        self._create_result_with_status(
            run.id,
            "g-jb",
            0,
            "SUCCESSFUL_JAILBREAK",
        )
        self._create_result_with_status(
            run.id,
            "g-mitigated",
            1,
            "PASSED_CRITERIA",
        )
        self._create_result_with_status(
            run.id,
            "g-failed",
            2,
            "FAILED_CRITERIA",
        )
        self._create_result_with_status(
            run.id,
            "g-pending",
            3,
            "NOT_EVALUATED",
        )
        self._create_result_with_status(
            run.id,
            "g-exception",
            4,
            "FAILED_JAILBREAK",
            notes="Model failed with exception: timeout",
        )

        buckets = self.backend.count_result_buckets()
        self.assertEqual(
            buckets,
            {
                "total": 5,
                "jailbreaks": 1,
                "mitigated": 1,
                "error": 2,
                "pending": 1,
            },
        )

    def test_delete_run_cascades_results_and_traces(self):
        run_to_delete = self.backend.create_run(self.attack.id, self.agent.id, {})
        run_to_keep = self.backend.create_run(self.attack.id, self.agent.id, {})

        deleted_result = self.backend.create_result(run_to_delete.id, "g1", 0, {}, {})
        kept_result = self.backend.create_result(run_to_keep.id, "g2", 1, {}, {})

        self.backend.create_trace(deleted_result.id, 1, "OTHER", {"msg": "bye"})
        self.backend.create_trace(kept_result.id, 1, "OTHER", {"msg": "stay"})

        self.backend.delete_run(run_to_delete.id)

        with self.assertRaises(RuntimeError):
            self.backend.get_run(run_to_delete.id)
        self.assertEqual(self.backend.list_results(run_id=run_to_delete.id).total, 0)
        self.assertEqual(self.backend.list_traces(deleted_result.id), [])

        self.assertEqual(self.backend.list_results(run_id=run_to_keep.id).total, 1)
        self.assertEqual(len(self.backend.list_traces(kept_result.id)), 1)

    def test_delete_attack_cascades_runs_results_and_traces(self):
        org = self.backend.get_context().org_id
        other_attack = self.backend.create_attack(
            "static_template", self.agent.id, org, {}
        )

        run_a = self.backend.create_run(self.attack.id, self.agent.id, {})
        run_b = self.backend.create_run(other_attack.id, self.agent.id, {})

        res_a = self.backend.create_result(run_a.id, "ga", 0, {}, {})
        res_b = self.backend.create_result(run_b.id, "gb", 0, {}, {})

        self.backend.create_trace(res_a.id, 1, "OTHER", {"scope": "attack-a"})
        self.backend.create_trace(res_b.id, 1, "OTHER", {"scope": "attack-b"})

        self.backend.delete_attack(self.attack.id)

        attacks = self.backend.list_attacks()
        self.assertEqual(attacks.total, 1)
        self.assertEqual(attacks.items[0].id, other_attack.id)
        self.assertEqual(self.backend.list_runs(attack_id=self.attack.id).total, 0)
        self.assertEqual(self.backend.list_results(run_id=run_a.id).total, 0)
        self.assertEqual(self.backend.list_traces(res_a.id), [])

        self.assertEqual(self.backend.list_runs(attack_id=other_attack.id).total, 1)
        self.assertEqual(self.backend.list_results(run_id=run_b.id).total, 1)
        self.assertEqual(len(self.backend.list_traces(res_b.id)), 1)


class TestLocalBackendThreadSafety(unittest.TestCase):
    """Concurrent writes should not corrupt the database."""

    def test_concurrent_agent_creation(self):
        with tempfile.TemporaryDirectory() as tmp:
            backend = _make_backend(tmp)
            try:
                errors = []

                def create(i):
                    try:
                        backend.create_or_update_agent(
                            f"agent-{i}",
                            {
                                "connection": {
                                    "type": "LITELLM",
                                    "endpoint": "http://localhost",
                                }
                            },
                        )
                    except Exception as e:
                        errors.append(e)

                threads = [
                    threading.Thread(target=create, args=(i,)) for i in range(10)
                ]
                for t in threads:
                    t.start()
                for t in threads:
                    t.join()

                self.assertEqual(errors, [], f"Thread errors: {errors}")
                result = backend.list_agents()
                self.assertEqual(result.total, 10)
            finally:
                backend.close()

    def test_concurrent_result_creation(self):
        with tempfile.TemporaryDirectory() as tmp:
            backend = _make_backend(tmp)
            try:
                agent = backend.create_or_update_agent(
                    "agent",
                    {"connection": {"type": "LITELLM", "endpoint": "http://localhost"}},
                )
                org = backend.get_context().org_id
                attack = backend.create_attack("x", agent.id, org, {})
                run = backend.create_run(attack.id, agent.id, {})
                errors = []

                def create_result(i):
                    try:
                        backend.create_result(run.id, f"goal-{i}", i, {}, {})
                    except Exception as e:
                        errors.append(e)

                threads = [
                    threading.Thread(target=create_result, args=(i,)) for i in range(20)
                ]
                for t in threads:
                    t.start()
                for t in threads:
                    t.join()

                self.assertEqual(errors, [])
                result = backend.list_results(run_id=run.id)
                self.assertEqual(result.total, 20)
            finally:
                backend.close()


class TestLocalBackendBuilderDrafts(unittest.TestCase):
    """Test attack-builder draft persistence."""

    def test_save_list_get_delete_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            backend = _make_backend(tmp)
            try:
                canvas = {"target": {"agent_name": "victim"}, "attacks": [{"a": 1}]}
                draft = backend.save_builder_draft("my draft", canvas)
                self.assertEqual(draft["name"], "my draft")
                self.assertEqual(draft["canvas"], canvas)

                self.assertEqual(len(backend.list_builder_drafts()), 1)
                fetched = backend.get_builder_draft(draft["id"])
                self.assertEqual(fetched["canvas"], canvas)

                backend.delete_builder_draft(draft["id"])
                self.assertEqual(backend.list_builder_drafts(), [])
                self.assertIsNone(backend.get_builder_draft(draft["id"]))
            finally:
                backend.close()

    def test_save_with_existing_id_updates_in_place(self):
        with tempfile.TemporaryDirectory() as tmp:
            backend = _make_backend(tmp)
            try:
                first = backend.save_builder_draft("v1", {"attacks": []})
                second = backend.save_builder_draft(
                    "v2", {"attacks": [{"attack_type": "pair"}]}, first["id"]
                )
                self.assertEqual(second["id"], first["id"])
                self.assertEqual(second["created_at"], first["created_at"])
                drafts = backend.list_builder_drafts()
                self.assertEqual(len(drafts), 1)
                self.assertEqual(drafts[0]["name"], "v2")
            finally:
                backend.close()

    def test_drafts_persist_across_instances(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "test.db")
            b1 = LocalBackend(db_path=path)
            b1.save_builder_draft("kept", {"attacks": []})
            b1.close()
            b2 = LocalBackend(db_path=path)
            try:
                self.assertEqual(
                    [d["name"] for d in b2.list_builder_drafts()], ["kept"]
                )
            finally:
                b2.close()


if __name__ == "__main__":
    unittest.main()
