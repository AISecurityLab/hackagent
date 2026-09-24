# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The web UI reads through the facade. ``delete_run`` is the local write."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from hackagent import HackAgent, Settings
from hackagent.interfaces.web import _static, create_app
from tests.fakes import RecordingStore


def _settings():
    return Settings.resolve(
        api_key="",
        db_path=":memory:",
        env={},
        config_path="/nonexistent/hackagent/config.json",
    )


class TestWebReadsThroughFacade(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        bundle = Path(self._tmp.name) / "static"
        bundle.mkdir()
        (bundle / "index.html").write_text("<html>index</html>")
        self._real_static_dir = _static.static_dir
        _static.static_dir = lambda: bundle

        self.store = RecordingStore()
        self.agent = self.store.create_or_update_agent(
            "demo-agent", "OPENAI_SDK", "http://localhost:1234", {"description": "d"}
        )
        attack = self.store.create_attack(
            "pair", self.agent.id, self.store.context.org_id, {"goals": ["g"]}
        )
        self.run = self.store.create_run(attack.id, self.agent.id, {"n": 1})
        self.result = self.store.create_result(
            self.run.id, "goal one", 0, {"prompt": "p"}, {}
        )
        self.store.create_trace(self.result.id, 0, "prompt", {"text": "hi"})
        self.store.calls.clear()

        session = HackAgent(_settings(), backend=self.store)
        self.client = create_app(session).test_client()

    def tearDown(self):
        _static.static_dir = self._real_static_dir
        self._tmp.cleanup()

    def test_agent_and_run_lists_read_through_the_facade(self):
        agents = self.client.get("/api/proxy/agent")
        runs = self.client.get("/api/proxy/run")
        detail = self.client.get(f"/api/proxy/result/{self.result.id}")

        self.assertEqual(agents.status_code, 200)
        self.assertEqual(agents.get_json()["results"][0]["name"], "demo-agent")
        self.assertEqual(runs.status_code, 200)
        self.assertEqual(runs.get_json()["count"], 1)
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(len(detail.get_json()["traces"]), 1)
        names = self.store.call_names()
        self.assertIn("list_agents", names)
        self.assertIn("list_runs", names)
        self.assertIn("list_results", names)
        self.assertIn("list_traces", names)
        self.assertNotIn("delete_run", names)

    def test_delete_run_is_the_only_local_write(self):
        refused = self.client.post("/api/proxy/run/run_tests", json={})
        self.assertEqual(refused.status_code, 501)
        self.assertNotIn("delete_run", self.store.call_names())

        deleted = self.client.delete(f"/api/proxy/run/{self.run.id}")
        self.assertEqual(deleted.status_code, 204)
        self.assertIn("delete_run", self.store.call_names())
        self.assertNotIn(self.run.id, self.store.runs)

        listing = self.client.get("/api/proxy/run")
        self.assertEqual(listing.get_json()["count"], 0)

    def test_unknown_run_delete_does_not_invent_a_second_write(self):
        missing = self.client.delete(f"/api/proxy/run/{self.agent.id}")
        self.assertEqual(missing.status_code, 404)
        self.assertIn("delete_run", self.store.call_names())
        self.assertIn(self.run.id, self.store.runs)
