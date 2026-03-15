# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for storage/base.py – record models and protocol."""

import unittest
from datetime import datetime, timezone
from uuid import UUID, uuid4

from pydantic import ValidationError

from hackagent.server.storage.base import (
    AgentRecord,
    AttackRecord,
    OrganizationContext,
    PaginatedResult,
    ResultRecord,
    RunRecord,
    TraceRecord,
)


def _dt() -> datetime:
    return datetime.now(timezone.utc)


def _uid() -> UUID:
    return uuid4()


class TestOrganizationContext(unittest.TestCase):
    """OrganizationContext dataclass."""

    def test_fields(self):
        org_id = _uid()
        ctx = OrganizationContext(org_id=org_id, user_id="42")
        self.assertEqual(ctx.org_id, org_id)
        self.assertEqual(ctx.user_id, "42")

    def test_is_frozen(self):
        ctx = OrganizationContext(org_id=_uid(), user_id="local")
        with self.assertRaises(ValidationError):
            ctx.user_id = "other"  # type: ignore[misc]

    def test_local_user_id(self):
        ctx = OrganizationContext(org_id=_uid(), user_id="local")
        self.assertEqual(ctx.user_id, "local")


class TestAgentRecord(unittest.TestCase):
    """AgentRecord dataclass."""

    def _make(self, **kw) -> AgentRecord:
        defaults = dict(
            id=_uid(),
            name="test-agent",
            agent_type="LITELLM",
            endpoint="http://localhost:8000",
            metadata={"key": "val"},
            organization=_uid(),
            owner="local",
            created_at=_dt(),
            updated_at=_dt(),
        )
        defaults.update(kw)
        return AgentRecord(**defaults)

    def test_fields(self):
        uid = _uid()
        org = _uid()
        now = _dt()
        rec = self._make(id=uid, name="my-agent", organization=org, created_at=now)
        self.assertEqual(rec.id, uid)
        self.assertEqual(rec.name, "my-agent")
        self.assertEqual(rec.organization, org)
        self.assertEqual(rec.created_at, now)

    def test_is_frozen(self):
        rec = self._make()
        with self.assertRaises(ValidationError):
            rec.name = "other"  # type: ignore[misc]

    def test_metadata_preserved(self):
        meta = {"model": "gpt-4", "temperature": 0.7}
        rec = self._make(metadata=meta)
        self.assertEqual(rec.metadata, meta)


class TestAttackRecord(unittest.TestCase):
    """AttackRecord dataclass."""

    def test_fields(self):
        aid = _uid()
        agent = _uid()
        org = _uid()
        now = _dt()
        rec = AttackRecord(
            id=aid,
            type="flipattack",
            agent_id=agent,
            organization=org,
            configuration={"n_attempts": 5},
            created_at=now,
        )
        self.assertEqual(rec.id, aid)
        self.assertEqual(rec.type, "flipattack")
        self.assertEqual(rec.agent_id, agent)
        self.assertEqual(rec.configuration["n_attempts"], 5)

    def test_is_frozen(self):
        rec = AttackRecord(
            id=_uid(),
            type="x",
            agent_id=_uid(),
            organization=_uid(),
            configuration={},
            created_at=_dt(),
        )
        with self.assertRaises(ValidationError):
            rec.type = "y"  # type: ignore[misc]


class TestRunRecord(unittest.TestCase):
    """RunRecord dataclass."""

    def test_fields_and_defaults(self):
        run_id = _uid()
        now = _dt()
        rec = RunRecord(
            id=run_id,
            attack_id=_uid(),
            agent_id=_uid(),
            run_config={"goals": ["test goal"]},
            status="PENDING",
            run_notes=None,
            created_at=now,
            updated_at=now,
        )
        self.assertEqual(rec.id, run_id)
        self.assertEqual(rec.status, "PENDING")
        self.assertIsNone(rec.run_notes)

    def test_is_frozen(self):
        rec = RunRecord(
            id=_uid(),
            attack_id=_uid(),
            agent_id=_uid(),
            run_config={},
            status="PENDING",
            run_notes=None,
            created_at=_dt(),
            updated_at=_dt(),
        )
        with self.assertRaises(ValidationError):
            rec.status = "RUNNING"  # type: ignore[misc]


class TestResultRecord(unittest.TestCase):
    """ResultRecord dataclass."""

    def test_fields(self):
        rid = _uid()
        run_id = _uid()
        rec = ResultRecord(
            id=rid,
            run_id=run_id,
            goal="Ignore previous instructions",
            goal_index=0,
            evaluation_status="NOT_EVALUATED",
            evaluation_notes=None,
            evaluation_metrics={},
            metadata={"prompt": "test"},
            created_at=_dt(),
            updated_at=_dt(),
        )
        self.assertEqual(rec.id, rid)
        self.assertEqual(rec.goal, "Ignore previous instructions")
        self.assertEqual(rec.evaluation_status, "NOT_EVALUATED")

    def test_evaluation_status_values(self):
        """Check that the status field accepts the known enum-string values."""
        for status in (
            "NOT_EVALUATED",
            "SUCCESSFUL_JAILBREAK",
            "FAILED_JAILBREAK",
            "ERROR_TEST_FRAMEWORK",
        ):
            rec = ResultRecord(
                id=_uid(),
                run_id=_uid(),
                goal="g",
                goal_index=0,
                evaluation_status=status,
                evaluation_notes=None,
                evaluation_metrics={},
                metadata={},
                created_at=_dt(),
                updated_at=_dt(),
            )
            self.assertEqual(rec.evaluation_status, status)


class TestTraceRecord(unittest.TestCase):
    """TraceRecord dataclass."""

    def test_fields(self):
        tid = _uid()
        rid = _uid()
        content = {"role": "user", "content": "hello"}
        rec = TraceRecord(
            id=tid,
            result_id=rid,
            sequence=1,
            step_type="OTHER",
            content=content,
            created_at=_dt(),
        )
        self.assertEqual(rec.id, tid)
        self.assertEqual(rec.sequence, 1)
        self.assertEqual(rec.content, content)

    def test_is_frozen(self):
        rec = TraceRecord(
            id=_uid(),
            result_id=_uid(),
            sequence=0,
            step_type="OTHER",
            content={},
            created_at=_dt(),
        )
        with self.assertRaises(ValidationError):
            rec.sequence = 99  # type: ignore[misc]


class TestPaginatedResult(unittest.TestCase):
    """PaginatedResult generic dataclass."""

    def test_empty(self):
        result: PaginatedResult[AgentRecord] = PaginatedResult(items=[], total=0)
        self.assertEqual(result.items, [])
        self.assertEqual(result.total, 0)

    def test_with_items(self):
        items = [1, 2, 3]
        result: PaginatedResult[int] = PaginatedResult(items=items, total=100)
        self.assertEqual(result.items, [1, 2, 3])
        self.assertEqual(result.total, 100)

    def test_total_can_exceed_items_len(self):
        """total reflects server count, not just the page size."""
        result: PaginatedResult[str] = PaginatedResult(items=["a", "b"], total=500)
        self.assertEqual(len(result.items), 2)
        self.assertEqual(result.total, 500)


class TestStorageBackendProtocol(unittest.TestCase):
    """Structural tests — ensure LocalBackend satisfies the protocol at runtime."""

    def test_local_backend_is_runtime_checkable(self):
        """LocalBackend should pass isinstance check against StorageBackend."""
        import tempfile
        import os
        from hackagent.server.storage.local import LocalBackend

        with tempfile.TemporaryDirectory() as tmp:
            backend = LocalBackend(db_path=os.path.join(tmp, "test.db"))
            try:
                # Python Protocols are not always runtime-checkable by default,
                # but we can verify the duck-type by checking required methods exist.
                required_methods = [
                    "get_context",
                    "get_api_key",
                    "create_or_update_agent",
                    "list_agents",
                    "get_agent",
                    "delete_agent",
                    "create_attack",
                    "list_attacks",
                    "create_run",
                    "update_run",
                    "list_runs",
                    "get_run",
                    "create_result",
                    "update_result",
                    "list_results",
                    "get_result",
                    "create_trace",
                    "list_traces",
                ]
                for method in required_methods:
                    self.assertTrue(
                        hasattr(backend, method),
                        f"LocalBackend missing method: {method}",
                    )
            finally:
                backend.close()


if __name__ == "__main__":
    unittest.main()
