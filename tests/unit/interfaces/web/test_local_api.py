# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Offline mode: the REST contract served from the local SQLite store.

These assert the *wire* shape rather than the Python objects, because the
consumer is a generated TypeScript client that dereferences snake_case keys
unconditionally — a missing key is a runtime crash in the browser, not a
type error here.
"""

import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from hackagent import HackAgent, Settings
from hackagent.storage.local import LocalBackend
from hackagent.interfaces.web import _static, create_app


class _WebUITestCase(unittest.TestCase):
    """Seeds a local database and a placeholder bundle, then serves both."""

    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        root = Path(self._tmp.name)

        bundle = root / "static"
        bundle.mkdir()
        (bundle / "index.html").write_text("<html>index</html>")
        (bundle / "agents.html").write_text("<html>agents</html>")
        (bundle / "404.html").write_text("<html>missing</html>")
        (bundle / "VERSION").write_text("9.9.9\n")
        self._real_static_dir = _static.static_dir
        _static.static_dir = lambda: bundle

        self.backend = LocalBackend(str(root / "hackagent.db"))
        self.org_id = self.backend.get_context().org_id
        self.agent = self.backend.create_or_update_agent(
            "demo-agent",
            {
                "connection": {
                    "type": "OPENAI_SDK",
                    "endpoint": "http://localhost:1234",
                },
                "generation": {"description": "d"},
            },
        )
        self.attack = self.backend.create_attack(
            "tap", self.agent.id, self.org_id, {"goals": ["g"]}
        )
        self.run = self.backend.create_run(self.attack.id, self.agent.id, {"n": 1})

        self.jailbreak = self.backend.create_result(
            self.run.id, "goal one", 0, {"prompt": "p"}, {"extra": 1}
        )
        self.backend.update_result(
            self.jailbreak.id, evaluation_status="SUCCESSFUL_JAILBREAK"
        )
        self.mitigated = self.backend.create_result(
            self.run.id, "goal two", 1, {"prompt": "q"}, {}
        )
        self.backend.update_result(
            self.mitigated.id, evaluation_status="FAILED_JAILBREAK"
        )
        self.backend.create_trace(self.jailbreak.id, 0, "prompt", {"text": "hi"})

        session = HackAgent(
            Settings.resolve(
                backend="local",
                db_path=":memory:",
                env={},
                config_path="/nonexistent",
            ),
            backend=self.backend,
        )
        self.client = create_app(session).test_client()

    def tearDown(self) -> None:
        _static.static_dir = self._real_static_dir
        self.backend.close()
        self._tmp.cleanup()

    def get(self, path: str):
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200, path)
        return response.get_json()


class TestIdentityEndpoints(_WebUITestCase):
    def test_user_me_reports_the_local_identity(self):
        payload = self.get("/api/proxy/user/me")
        self.assertEqual(payload["username"], "local")
        self.assertEqual(payload["organization"], str(self.org_id))
        # The client reads these unconditionally; they must exist, even as null.
        for key in ("email", "first_name", "last_name", "auth0_user_id"):
            self.assertIn(key, payload)

    def test_organization_me_reports_zero_credits(self):
        payload = self.get("/api/proxy/organization/me")
        self.assertEqual(payload["id"], str(self.org_id))
        self.assertEqual(payload["credits"], "0.00")

    def test_api_keys_and_logs_are_empty_offline(self):
        for path in ("/api/proxy/key", "/api/proxy/apilogs"):
            payload = self.get(path)
            self.assertEqual(payload["count"], 0)
            self.assertEqual(payload["results"], [])


class TestAgentAndAttackEndpoints(_WebUITestCase):
    def test_agent_list_carries_nested_detail_objects(self):
        payload = self.get("/api/proxy/agent")
        self.assertEqual(payload["count"], 1)
        agent = payload["results"][0]
        self.assertEqual(agent["name"], "demo-agent")
        self.assertEqual(agent["organization_detail"]["id"], str(self.org_id))
        self.assertEqual(agent["owner_detail"]["username"], "local")

    def test_agent_detail_round_trips(self):
        payload = self.get(f"/api/proxy/agent/{self.agent.id}")
        self.assertEqual(payload["id"], str(self.agent.id))

    def test_unknown_agent_is_404_not_500(self):
        response = self.client.get(f"/api/proxy/agent/{self.run.id}")
        self.assertEqual(response.status_code, 404)

    def test_malformed_uuid_is_404_not_500(self):
        response = self.client.get("/api/proxy/agent/not-a-uuid")
        self.assertEqual(response.status_code, 404)

    def test_attack_list_resolves_the_agent_name(self):
        attack = self.get("/api/proxy/attack")["results"][0]
        self.assertEqual(attack["type"], "tap")
        self.assertEqual(attack["agent_name"], "demo-agent")
        # The generated client reads 'configuration', not '_configuration'.
        self.assertEqual(attack["configuration"], {"goals": ["g"]})


class TestRunEndpoints(_WebUITestCase):
    def test_run_list_aggregates_outcome_counts(self):
        summary = self.get("/api/proxy/run")["results"][0]
        self.assertEqual(summary["total_results"], 2)
        self.assertEqual(summary["successful_jailbreaks"], 1)
        self.assertEqual(summary["failed_jailbreaks"], 1)
        self.assertEqual(summary["errors"], 0)
        self.assertEqual(summary["not_evaluated"], 0)
        self.assertEqual(summary["attack_type"], "tap")
        self.assertEqual(summary["organization"], str(self.org_id))
        self.assertEqual(summary["executor"], "cli")

    def test_operational_failures_count_as_errors_not_mitigated(self):
        failed = self.backend.create_result(self.run.id, "g", 2, {}, {})
        self.backend.update_result(
            failed.id,
            evaluation_status="FAILED_JAILBREAK",
            evaluation_notes="Attack failed with exception: boom",
        )
        summary = self.get("/api/proxy/run")["results"][0]
        self.assertEqual(summary["errors"], 1)
        self.assertEqual(summary["failed_jailbreaks"], 1)

    def test_run_list_filters_by_agent_and_status(self):
        self.assertEqual(self.get(f"/api/proxy/run?agent={self.agent.id}")["count"], 1)
        self.assertEqual(self.get(f"/api/proxy/run?agent={self.run.id}")["count"], 0)
        self.assertEqual(self.get("/api/proxy/run?status=NOPE")["count"], 0)

    def test_run_detail_embeds_results_and_their_traces(self):
        payload = self.get(f"/api/proxy/run/{self.run.id}")
        self.assertEqual(len(payload["results"]), 2)
        traced = [r for r in payload["results"] if r["id"] == str(self.jailbreak.id)][0]
        self.assertEqual(len(traced["traces"]), 1)
        self.assertEqual(traced["traces"][0]["content"], {"text": "hi"})

    def test_run_delete_removes_the_run(self):
        response = self.client.delete(f"/api/proxy/run/{self.run.id}")
        self.assertEqual(response.status_code, 204)
        self.assertEqual(self.get("/api/proxy/run")["count"], 0)


class TestResultEndpoints(_WebUITestCase):
    def test_result_list_always_carries_a_traces_array(self):
        for result in self.get("/api/proxy/result")["results"]:
            self.assertIsInstance(result["traces"], list)

    def test_result_list_filters_by_run_and_status(self):
        self.assertEqual(self.get(f"/api/proxy/result?run={self.run.id}")["count"], 2)
        filtered = self.get("/api/proxy/result?evaluation_status=SUCCESSFUL_JAILBREAK")
        self.assertEqual(filtered["count"], 1)
        self.assertEqual(filtered["results"][0]["id"], str(self.jailbreak.id))

    def test_result_detail_includes_traces(self):
        payload = self.get(f"/api/proxy/result/{self.jailbreak.id}")
        self.assertEqual(len(payload["traces"]), 1)

    def test_pagination_envelope_advertises_further_pages(self):
        page = self.get("/api/proxy/result?page_size=1")
        self.assertEqual(page["count"], 2)
        self.assertEqual(len(page["results"]), 1)
        self.assertIsNotNone(page["next"])
        self.assertIsNone(page["previous"])

        second = self.get("/api/proxy/result?page_size=1&page=2")
        self.assertIsNone(second["next"])
        self.assertIsNotNone(second["previous"])


class TestWriteRoutesAreRejected(_WebUITestCase):
    def test_creating_a_run_offline_is_refused_with_guidance(self):
        response = self.client.post("/api/proxy/run", json={})
        self.assertEqual(response.status_code, 501)
        self.assertIn("hosted service", response.get_json()["detail"])

    def test_creating_an_agent_offline_is_refused(self):
        self.assertEqual(self.client.post("/api/proxy/agent", json={}).status_code, 501)


class TestCampaignBuilderOffline(_WebUITestCase):
    def test_techniques_are_served(self):
        payload = self.get("/api/proxy/campaign/techniques")
        self.assertIsInstance(payload, list)
        self.assertTrue(payload)

    def test_schema_carries_sorted_dataset_presets(self):
        payload = self.get("/api/proxy/campaign/schema")
        self.assertIn("schema", payload)
        names = [p["name"] for p in payload["dataset_presets"]]
        self.assertTrue(names)
        self.assertEqual(names, sorted(names))


_TARGET = {
    "name": "aurora",
    "connection": {
        "provider": "local",
        "type": "OPENAI",
        "endpoint": "http://127.0.0.1:8010/v1",
    },
}

_SPEC = {
    "version": 1,
    "dataset": {"source": {"type": "inline", "goals": ["wire 9800 EUR"]}},
    "attacks": [{"name": "baseline"}],
    "evaluation": {
        "judges": [
            {
                "name": "judge",
                "connection": {
                    "provider": "local",
                    "type": "OPENAI",
                    "endpoint": "http://127.0.0.1:8001/v1",
                },
                "scoring": {"type": "harmbench"},
            }
        ]
    },
}


class _CampaignTestCase(_WebUITestCase):
    def setUp(self) -> None:
        super().setUp()
        self.target = self.backend.create_or_update_agent("aurora", _TARGET)

    def save(self, **overrides):
        body = {"name": "Aurora L6", "agent": str(self.target.id), "spec": _SPEC}
        return self.client.post("/api/proxy/campaign", json={**body, **overrides})

    def saved(self):
        response = self.save()
        self.assertEqual(response.status_code, 201)
        return response.get_json()


class TestSavedCampaigns(_CampaignTestCase):
    def test_a_saved_campaign_is_listed_and_read_back(self):
        saved = self.saved()
        self.assertEqual(saved["agent"], str(self.target.id))
        self.assertEqual(saved["spec"], _SPEC)

        listing = self.get("/api/proxy/campaign")
        self.assertEqual([c["id"] for c in listing["results"]], [saved["id"]])
        self.assertEqual(
            self.get(f"/api/proxy/campaign/{saved['id']}")["name"], "Aurora L6"
        )

    def test_put_replaces_and_patch_merges(self):
        saved = self.saved()
        path = f"/api/proxy/campaign/{saved['id']}"
        body = {"name": "Renamed", "agent": str(self.target.id), "spec": _SPEC}
        self.assertEqual(self.client.put(path, json=body).get_json()["name"], "Renamed")
        patched = self.client.patch(path, json={"description": "statement"}).get_json()
        self.assertEqual(
            (patched["name"], patched["description"]), ("Renamed", "statement")
        )

    def test_delete_removes_it(self):
        saved = self.saved()
        path = f"/api/proxy/campaign/{saved['id']}"
        self.assertEqual(self.client.delete(path).status_code, 204)
        self.assertEqual(self.client.get(path).status_code, 404)

    def test_target_and_execution_are_left_to_the_launch(self):
        response = self.save(spec={**_SPEC, "target": _TARGET})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["spec"], {"target": "set by the server"})

    def test_an_unknown_agent_or_missing_name_is_refused(self):
        response = self.save(agent="00000000-0000-0000-0000-000000000000", name="")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(set(response.get_json()), {"agent", "name"})

    def test_an_invalid_spec_is_refused(self):
        response = self.save(spec={**_SPEC, "attacks": "baseline"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("spec", response.get_json())

    def test_agents_carry_their_model_config(self):
        agent = self.get(f"/api/proxy/agent/{self.target.id}")
        self.assertEqual(agent["config"]["connection"]["type"], "OPENAI")


def _fake_run(spec, *, store, on_event, **_kwargs):
    """Record a campaign run with one attack run and one result, then finish."""
    agent = store.create_or_update_agent(spec.target.name, spec.target.model_dump())
    record = store.start_campaign(agent.id, spec.recorded())
    attack = store.create_attack("baseline", agent.id, store.get_context().org_id, {})
    run = store.create_run(attack.id, agent.id, {}, campaign_run_id=record.id)
    store.create_result(run.id, "wire 9800 EUR", 0, {}, {})
    store.update_campaign_run(record.id, status="COMPLETED")


def _slow_run(spec, *, store, on_event, **_kwargs):
    """Record a campaign run, then report progress until cancelled."""
    agent = store.create_or_update_agent(spec.target.name, spec.target.model_dump())
    record = store.start_campaign(agent.id, spec.recorded())
    try:
        for _ in range(500):
            on_event("attempt_finished")
            time.sleep(0.01)
    except Exception:
        store.update_campaign_run(record.id, status="CANCELLED")
        raise


class TestLaunchingOnThisMachine(_CampaignTestCase):
    def launch(self, campaign_id, executor="local"):
        body = {} if executor is None else {"executor": executor}
        return self.client.post(f"/api/proxy/campaign/{campaign_id}/launch", json=body)

    def wait_until_final(self, run_id):
        for _ in range(200):
            run = self.get(f"/api/proxy/run/{run_id}")
            if run["status"] in ("COMPLETED", "FAILED", "CANCELLED"):
                return run
            time.sleep(0.02)
        self.fail(f"run {run_id} did not finish")

    @mock.patch("hackagent.interfaces.web._launcher.resolve_campaign")
    @mock.patch(
        "hackagent.interfaces.web._launcher.run_campaign", side_effect=_fake_run
    )
    def test_launch_runs_here_and_serves_the_parent_run(self, run, _resolve):
        saved = self.saved()
        # The dashboard leaves where to the deployment: offline, this machine.
        response = self.launch(saved["id"], executor=None)
        self.assertEqual(response.status_code, 201)
        parent = response.get_json()
        self.assertEqual(parent["executor"], "local")
        self.assertEqual(parent["campaign"], saved["id"])
        self.assertEqual(parent["claimed_by"], "hackagent web")
        self.assertIsNotNone(parent["claimed_at"])

        launched = run.call_args.args[0]
        self.assertEqual(
            launched.target.connection.endpoint, _TARGET["connection"]["endpoint"]
        )
        self.assertEqual(launched.campaign.name, "Aurora L6")

        finished = self.wait_until_final(parent["id"])
        self.assertEqual(finished["status"], "COMPLETED")
        self.assertIsNotNone(finished["finished_at"])
        children = self.get(f"/api/proxy/run?parent={parent['id']}")["results"]
        self.assertEqual(len(children), 1)
        self.assertEqual(children[0]["parent"], parent["id"])
        self.assertEqual(children[0]["executor"], "local")
        self.assertEqual(children[0]["total_results"], 1)

        last = self.get(
            f"/api/proxy/run?campaign={saved['id']}&parent__isnull=true&page_size=1"
        )["results"]
        self.assertEqual([r["id"] for r in last], [parent["id"]])
        self.assertEqual(last[0]["total_results"], 1)

        # The Runs page opens a parent by id: its results are its attack runs'.
        self.assertEqual(finished["total_results"], 1)
        self.assertEqual(self.get(f"/api/proxy/result?run={parent['id']}")["count"], 1)
        self.assertEqual(self.get(f"/api/proxy/run/{parent['id']}/result")["count"], 1)

    @mock.patch("hackagent.interfaces.web._launcher.resolve_campaign")
    @mock.patch(
        "hackagent.interfaces.web._launcher.run_campaign", side_effect=_slow_run
    )
    def test_cancel_stops_the_run(self, _run, _resolve):
        parent = self.launch(self.saved()["id"]).get_json()
        response = self.client.post(f"/api/proxy/run/{parent['id']}/cancel")
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.get_json()["cancel_requested_at"])
        self.assertEqual(self.wait_until_final(parent["id"])["status"], "CANCELLED")

    def test_cancelling_a_run_not_running_here_is_refused(self):
        record = self.backend.start_campaign(
            self.target.id, {"campaign": {"name": "cli"}}
        )
        response = self.client.post(f"/api/proxy/run/{record.id}/cancel")
        self.assertEqual(response.status_code, 400)

    def test_a_cli_campaign_run_is_served_as_a_cli_parent(self):
        record = self.backend.start_campaign(
            self.target.id, {"campaign": {"name": "cli"}}
        )
        parent = self.get(f"/api/proxy/run/{record.id}")
        self.assertEqual((parent["executor"], parent["campaign"]), ("cli", None))

    def test_cloud_is_unavailable_offline(self):
        saved = self.saved()
        preflight = self.get(
            f"/api/proxy/campaign/{saved['id']}/preflight?executor=cloud"
        )
        self.assertFalse(preflight["ok"])
        self.assertEqual(preflight["problems"][0]["code"], "CLOUD_UNAVAILABLE")
        response = self.launch(saved["id"], executor="cloud")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.get_json()["problems"][0]["code"], "CLOUD_UNAVAILABLE"
        )

    def test_local_preflight_passes_for_a_valid_campaign(self):
        saved = self.saved()
        for query in ("?executor=local", ""):
            preflight = self.get(f"/api/proxy/campaign/{saved['id']}/preflight{query}")
            self.assertEqual(
                preflight, {"executor": "local", "ok": True, "problems": []}
            )

    @mock.patch(
        "hackagent.interfaces.web._launcher.resolve_campaign",
        side_effect=ValueError("judge unreachable"),
    )
    def test_a_campaign_that_cannot_resolve_is_refused(self, _resolve):
        response = self.launch(self.saved()["id"])
        self.assertEqual(response.status_code, 400)
        problem = response.get_json()["problems"][0]
        self.assertEqual(
            (problem["code"], problem["message"]),
            ("LAUNCH_REFUSED", "judge unreachable"),
        )


class TestStaticServing(_WebUITestCase):
    def test_root_serves_the_index(self):
        self.assertIn(b"index", self.client.get("/").data)

    def test_clean_route_resolves_to_its_exported_html(self):
        # `next build --output export` writes /agents as agents.html.
        self.assertIn(b"agents", self.client.get("/agents").data)

    def test_unknown_route_serves_the_404_page(self):
        response = self.client.get("/does-not-exist")
        self.assertEqual(response.status_code, 404)
        self.assertIn(b"missing", response.data)

    def test_serves_through_a_symlinked_bundle_path(self):
        """A symlink anywhere above the bundle must not break serving.

        macOS resolves temporary and per-user directories under /private, and
        virtualenvs are often installed beneath a symlinked prefix, so comparing
        a resolved candidate against an unresolved base would 404 everything.
        """
        real = Path(self._tmp.name) / "real-bundle"
        real.mkdir()
        (real / "index.html").write_text("<html>via symlink</html>")
        link = Path(self._tmp.name) / "linked-bundle"
        link.symlink_to(real, target_is_directory=True)

        _static.static_dir = lambda: link
        session = HackAgent(
            Settings.resolve(
                backend="local",
                db_path=":memory:",
                env={},
                config_path="/nonexistent",
            ),
            backend=self.backend,
        )
        client = create_app(session).test_client()
        response = client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"via symlink", response.data)

    def test_traversal_outside_the_bundle_is_refused(self):
        response = self.client.get("/../../etc/passwd")
        self.assertNotIn(b"root:", response.data)

    def test_config_json_disables_auth_and_points_at_the_local_proxy(self):
        payload = self.get("/config.json")
        self.assertTrue(payload["disableAuth"])
        self.assertEqual(payload["authProvider"], "disabled")
        self.assertEqual(payload["apiUrl"], "/api/proxy")

    def test_healthz_reports_mode_version_and_bundle_source(self):
        payload = self.get("/healthz")
        self.assertEqual(payload["mode"], "local")
        self.assertEqual(payload["webapp_version"], "9.9.9")
        self.assertEqual(payload["webapp_source"], "package")


if __name__ == "__main__":
    unittest.main()
