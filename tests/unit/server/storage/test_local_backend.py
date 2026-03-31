# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for LocalBackend (server/storage/local.py)."""

import os
import tempfile
import threading
import unittest
from datetime import datetime
from uuid import UUID, uuid4

from hackagent.server.storage.local import LocalBackend
from hackagent.server.storage.base import (
    AgentRecord,
    AttackRecord,
    OrganizationContext,
    PaginatedResult,
    RunRecord,
    ResultRecord,
    TraceRecord,
)


def _make_backend(tmp_dir: str) -> LocalBackend:
    return LocalBackend(db_path=os.path.join(tmp_dir, "test.db"))


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
            name=name,
            agent_type="LITELLM",
            endpoint="http://localhost:8000",
            metadata={"model": "gpt-4o-mini"},
        )

    def test_create_agent_returns_record(self):
        rec = self._create_agent()
        self.assertIsInstance(rec, AgentRecord)
        self.assertEqual(rec.name, "my-agent")
        self.assertEqual(rec.agent_type, "LITELLM")
        self.assertEqual(rec.endpoint, "http://localhost:8000")
        self.assertEqual(rec.metadata["model"], "gpt-4o-mini")
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

    def test_update_agent_merges_metadata(self):
        self._create_agent()
        rec2 = self.backend.create_or_update_agent(
            name="my-agent",
            agent_type="LITELLM",
            endpoint="http://localhost:8000",
            metadata={"temperature": 0.5},
        )
        # merged: original model + new temperature
        self.assertIn("model", rec2.metadata)
        self.assertIn("temperature", rec2.metadata)

    def test_update_agent_no_overwrite(self):
        self._create_agent()
        rec2 = self.backend.create_or_update_agent(
            name="my-agent",
            agent_type="LITELLM",
            endpoint="http://localhost:8000",
            metadata={"new_key": "new_val"},
            overwrite_metadata=False,
        )
        self.assertNotIn("new_key", rec2.metadata)

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
            name="test-agent",
            agent_type="LITELLM",
            endpoint="http://localhost:8000",
            metadata={},
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


class TestLocalBackendRun(unittest.TestCase):
    """Test run CRUD."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.backend = _make_backend(self.tmp)
        self.agent = self.backend.create_or_update_agent(
            name="test-agent",
            agent_type="LITELLM",
            endpoint="http://localhost:8000",
            metadata={},
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
            "agent", "LITELLM", "http://localhost", {}
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

    def test_create_result_unique_ids(self):
        r1 = self.backend.create_result(self.run.id, "g1", 0, {}, {})
        r2 = self.backend.create_result(self.run.id, "g2", 1, {}, {})
        self.assertNotEqual(r1.id, r2.id)

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
            "agent", "LITELLM", "http://localhost", {}
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
            "agent2", "LITELLM", "http://localhost", {}
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
            "agent", "LITELLM", "http://localhost", {}
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
                "failed": 2,
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
        other_attack = self.backend.create_attack("baseline", self.agent.id, org, {})

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
                            name=f"agent-{i}",
                            agent_type="LITELLM",
                            endpoint="http://localhost",
                            metadata={},
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
                    "agent", "LITELLM", "http://localhost", {}
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


if __name__ == "__main__":
    unittest.main()
