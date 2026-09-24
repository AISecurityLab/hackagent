# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Facade session against a recording store.

Construction takes settings only. ``.target(...).hack()`` and ``.hack_chain()``
deliver ``on_event``. Reads and ``delete_run`` go through the injected store.
"""

import subprocess
import sys
import unittest
from unittest.mock import patch

from hackagent import HackAgent, Settings
from tests.fakes import RecordingStore


def _settings(**kwargs):
    kwargs.setdefault("api_key", "")
    kwargs.setdefault("db_path", ":memory:")
    kwargs.setdefault("env", {})
    kwargs.setdefault("config_path", "/nonexistent/hackagent/config.json")
    return Settings.resolve(**kwargs)


class TestSettingsOnlyConstruction(unittest.TestCase):
    def test_constructor_binds_settings_and_the_injected_store(self):
        store = RecordingStore()
        settings = _settings()
        session = HackAgent(settings, backend=store)
        self.assertIs(session.settings, settings)
        self.assertIs(session.backend, store)
        self.assertEqual(store.call_names(), [])

    def test_endpoint_is_not_a_constructor_argument(self):
        with self.assertRaises(TypeError):
            HackAgent(_settings(), endpoint="http://localhost:8000")

    def test_api_key_opens_the_remote_store(self):
        remote = object()
        with (
            patch(
                "hackagent.storage.remote.RemoteBackend.connect", return_value=remote
            ) as connect,
            patch("hackagent.storage.local.LocalBackend") as local,
        ):
            session = HackAgent(
                _settings(api_key="test-key", base_url="https://api.hackagent.dev")
            )
        connect.assert_called_once()
        self.assertEqual(connect.call_args.args[1], "test-key")
        local.assert_not_called()
        self.assertIs(session.backend, remote)

    def test_empty_key_opens_the_local_store_at_the_configured_path(self):
        with patch("hackagent.storage.local.LocalBackend") as local:
            HackAgent(_settings(api_key="", db_path="/tmp/phase8-facade.db"))
        local.assert_called_once_with(db_path="/tmp/phase8-facade.db")

    def test_close_reaches_the_store(self):
        store = RecordingStore()
        HackAgent(_settings(), backend=store).close()
        self.assertTrue(store.closed)
        self.assertEqual(store.call_names(), ["close"])

    def test_importing_the_package_does_not_pull_textual(self):
        code = "import sys, hackagent; raise SystemExit('textual' in sys.modules)"
        result = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0, result.stderr)


class TestOnEvent(unittest.TestCase):
    def setUp(self):
        self.store = RecordingStore()
        self.session = HackAgent(_settings(), backend=self.store)
        self.target = self.session.target(
            "http://localhost:8000", "openai-sdk", name="bot"
        )

    def test_hack_delivers_events_to_the_callback(self):
        seen = []

        def on_event(event_type, **payload):
            seen.append((event_type, payload))

        def fake_run(_agent, _attack_config, **kwargs):
            kwargs["_tui_event_bus"].emit("goal_finalized", goal="g", success=True)
            return [{"goal": "g"}]

        with patch("hackagent.orchestrator.execution.runner.run", side_effect=fake_run):
            rows = self.target.hack(
                attack_config={"attack_type": "baseline", "goals": ["g"]},
                on_event=on_event,
            )

        self.assertEqual(rows, [{"goal": "g"}])
        self.assertEqual(seen, [("goal_finalized", {"goal": "g", "success": True})])

    def test_hack_chain_forwards_on_event_into_each_step(self):
        seen = []

        def on_event(event_type, **payload):
            seen.append((event_type, payload.get("attack")))

        def fake_run(_agent, attack_config, **kwargs):
            kwargs["_tui_event_bus"].emit(
                "step_started", attack=attack_config["attack_type"]
            )
            return [{"goal": "g", "is_success": False}]

        with patch("hackagent.orchestrator.execution.runner.run", side_effect=fake_run):
            self.target.hack_chain(
                attacks=[{"attack_type": "baseline"}, {"attack_type": "pair"}],
                goals=["g"],
                on_event=on_event,
            )

        self.assertEqual(seen, [("step_started", "baseline"), ("step_started", "pair")])


class TestReadApi(unittest.TestCase):
    def setUp(self):
        self.store = RecordingStore()
        self.session = HackAgent(_settings(), backend=self.store)
        self.agent = self.store.create_or_update_agent(
            "bot", "OPENAI_SDK", "http://localhost:8000", {"description": "d"}
        )
        self.attack = self.store.create_attack(
            "pair", self.agent.id, self.store.context.org_id, {"goals": ["g"]}
        )
        self.run = self.store.create_run(self.attack.id, self.agent.id, {"n": 1})
        self.result = self.store.create_result(
            self.run.id, "goal", 0, {"prompt": "p"}, {}
        )
        self.store.create_trace(self.result.id, 0, "prompt", {"text": "hi"})
        self.store.calls.clear()

    def test_reads_are_forwarded_to_the_store(self):
        self.assertEqual(self.session.agents().items[0].name, "bot")
        self.assertEqual(
            self.session.agent(self.agent.id).endpoint, "http://localhost:8000"
        )
        self.assertEqual(self.session.runs().total, 1)
        self.assertEqual(self.session.run(str(self.run.id)).status, "completed")
        page = self.session.results(run_id=self.run.id)
        self.assertEqual(page.total, 1)
        self.assertEqual(page.items[0].goal, "goal")
        self.assertEqual(self.session.result(self.result.id).id, self.result.id)
        self.assertEqual(self.session.traces(self.result.id)[0].step_type, "prompt")
        self.assertEqual(
            self.store.call_names(),
            [
                "list_agents",
                "get_agent",
                "list_runs",
                "get_run",
                "list_results",
                "get_result",
                "list_traces",
            ],
        )

    def test_delete_run_is_the_write_path(self):
        self.session.delete_run(self.run.id)
        self.assertEqual(self.store.call_names(), ["delete_run"])
        self.assertNotIn(self.run.id, self.store.runs)
        self.assertEqual(self.session.runs().total, 0)

    def test_local_session_check_connection_is_zero(self):
        self.assertEqual(self.session.check_connection(), 0)
        self.assertNotIn("check_connection", self.store.call_names())

    def test_catalog_includes_registry_techniques(self):
        ids = {entry["attack_type"] for entry in self.session.catalog()}
        self.assertIn("crescendo", ids)
        self.assertIn("rag", ids)
