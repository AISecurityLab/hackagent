# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for dashboard API route registration and handlers."""

import asyncio
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from hackagent.server.dashboard._api import register_api
from hackagent.server.storage.base import PaginatedResult, ResultRecord, RunRecord


class _FakeBackend:
    def __init__(self, runs, results_by_run, api_key=None):
        self._runs = runs
        self._results_by_run = results_by_run
        self._api_key = api_key
        self._db_path = "/tmp/hackagent-test.db"
        self._ctx = SimpleNamespace(org_id=uuid4(), user_id="local")

    def get_context(self):
        return self._ctx

    def get_api_key(self):
        return self._api_key

    def list_agents(self, page=1, page_size=100):
        return PaginatedResult(
            items=[SimpleNamespace(model_dump=lambda mode="json": {})], total=1
        )

    def list_attacks(self, page=1, page_size=100):
        return PaginatedResult(
            items=[SimpleNamespace(model_dump=lambda mode="json": {})], total=1
        )

    def list_runs(self, page=1, page_size=100):
        start = (page - 1) * page_size
        end = start + page_size
        return PaginatedResult(items=self._runs[start:end], total=len(self._runs))

    def list_results(self, run_id=None, page=1, page_size=100):
        items = list(self._results_by_run.get(run_id, []))
        start = (page - 1) * page_size
        end = start + page_size
        return PaginatedResult(items=items[start:end], total=len(items))


class TestDashboardApiRoutes(unittest.TestCase):
    """Test selected dashboard API handler behavior after registration."""

    def _register(self, backend):
        routes = {}

        def _fake_get(path):
            def _decorator(func):
                routes[path] = func
                return func

            return _decorator

        from unittest.mock import patch

        with patch(
            "hackagent.server.dashboard._api._fastapi_app.get", side_effect=_fake_get
        ):
            register_api(backend)

        return routes

    def test_status_route_reports_local_mode(self):
        run = RunRecord(
            id=uuid4(),
            attack_id=uuid4(),
            agent_id=uuid4(),
            run_config={},
            status="PENDING",
            run_notes=None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        backend = _FakeBackend(runs=[run], results_by_run={}, api_key=None)
        routes = self._register(backend)

        payload = asyncio.run(routes["/api/status"]())

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["mode"], "local")
        self.assertEqual(payload["db_path"], "/tmp/hackagent-test.db")

    def test_stats_and_runs_routes_use_bucket_classification(self):
        run = RunRecord(
            id=uuid4(),
            attack_id=uuid4(),
            agent_id=uuid4(),
            run_config={},
            status="PENDING",
            run_notes=None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        results = [
            ResultRecord(
                id=uuid4(),
                run_id=run.id,
                goal="g1",
                goal_index=0,
                evaluation_status="SUCCESSFUL_JAILBREAK",
                evaluation_notes=None,
                evaluation_metrics={},
                metadata={},
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            ),
            ResultRecord(
                id=uuid4(),
                run_id=run.id,
                goal="g2",
                goal_index=1,
                evaluation_status="FAILED_JAILBREAK",
                evaluation_notes="agent failed with exception: timeout",
                evaluation_metrics={},
                metadata={},
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            ),
        ]

        backend = _FakeBackend(
            runs=[run], results_by_run={run.id: results}, api_key="k"
        )
        routes = self._register(backend)

        stats_payload = asyncio.run(routes["/api/stats"]())
        runs_payload = asyncio.run(routes["/api/runs"]())

        self.assertEqual(stats_payload["total_runs"], 1)
        self.assertEqual(stats_payload["total_results"], 2)
        self.assertEqual(stats_payload["successful_jailbreaks"], 1)
        self.assertEqual(stats_payload["errors"], 1)

        self.assertEqual(runs_payload["total"], 1)
        self.assertEqual(runs_payload["items"][0]["total_results"], 2)
        self.assertEqual(runs_payload["items"][0]["successful_jailbreaks"], 1)
        self.assertEqual(runs_payload["items"][0]["status"], "FAILED")


if __name__ == "__main__":
    unittest.main()
