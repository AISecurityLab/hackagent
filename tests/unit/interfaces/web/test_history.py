# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import sqlite3
from unittest.mock import patch

from hackagent.interfaces.web._history import _goals, _read_all
from hackagent.storage.records import PaginatedResult

from test_local_api import _WebUITestCase


class TestCampaignHistory(_WebUITestCase):
    def test_category_summaries_preserve_distinct_ordering_contracts(self):
        self.backend.update_result(
            self.first.id,
            agent_specific_data={"category": "Safety", "subcategory": "Zulu"},
        )
        self.backend.create_result(
            self.child.id, "Second", 1, {}, {"category": "Privacy"}
        )
        self.backend.create_result(
            self.child.id,
            "Third",
            2,
            {},
            {"category": "Safety", "subcategory": "Alpha"},
        )
        payload = self.get(self.base)
        categories = payload["category_outcomes"]
        self.assertEqual(
            [item["category"] for item in categories], ["Privacy", "Safety"]
        )
        self.assertEqual(
            [item["name"] for item in categories[1]["subcategories"]], ["Zulu", "Alpha"]
        )
        self.assertEqual(categories[0]["subcategories"][0]["name"], "Unspecified")
        self.assertEqual(categories[1]["recorded_goals"], 2)
        safety = next(
            item
            for item in payload["attack_category_outcomes"]
            if item["category"] == "Safety"
        )
        self.assertEqual(
            [item["name"] for item in safety["subcategories"]], ["Alpha", "Zulu"]
        )

    def test_summary_views_do_not_decode_payloads(self):
        self.backend.update_result(
            self.first.id,
            agent_specific_data={
                "category": "E. Cybersecurity Threats",
                "subcategory": "E2. Exploit Development",
                "response": "large response not needed in a summary",
            },
        )
        original = self.backend._row_to_result

        def lightweight(row):
            self.assertEqual(row["request_payload_json"], "{}")
            self.assertEqual(row["metrics_json"], "{}")
            result = original(row)
            self.assertEqual(set(result.metadata), {"category", "subcategory"})
            return result

        with patch.object(self.backend, "_row_to_result", side_effect=lightweight):
            self.get(self.base)
            goals = self.get(self.base + "/goals")["results"]
        self.assertEqual(goals[0]["subcategory"], "E2. Exploit Development")

    def test_attempt_pagination_does_not_materialize_result_records(self):
        with patch.object(
            self.backend, "_row_to_result", side_effect=AssertionError("Decoded result")
        ):
            payload = self.get(self.base + "/attempts?goal_index=0&page_size=1")
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["results"][0]["id"], str(self.first.id))

    def test_structure_reads_full_results_only_for_the_selected_goal(self):
        unrelated = self.backend.create_result(self.child.id, "Other goal", 1, {}, {})
        original = self.backend._row_to_result

        def selected_only(row):
            self.assertNotEqual(row["id"], str(unrelated.id))
            return original(row)

        with patch.object(self.backend, "_row_to_result", side_effect=selected_only):
            payload = self.get(
                self.base + f"/structure?goal_index=0&run_id={self.child.id}"
            )
        self.assertEqual([r["id"] for r in payload["results"]], [str(self.first.id)])

    def test_history_summaries_do_not_load_result_payloads(self):
        with (
            patch.object(
                self.backend,
                "list_results",
                side_effect=AssertionError("Payloads loaded"),
            ),
            patch.object(
                self.backend, "list_runs", side_effect=AssertionError("Runs loaded")
            ),
        ):
            row = self.get("/api/proxy/local/history")["results"][0]
        self.assertEqual(row["attack_runs"], 1)
        self.assertEqual(row["recorded_goals"], 1)
        self.assertEqual(row["mitigated"], 1)
        self.assertEqual(row["attempts"], 1)

    def test_database_summaries_match_goal_verdicts(self):
        second = self.backend.create_run(
            self.attack.id, self.agent.id, {}, campaign_run_id=self.campaign.id
        )
        self.backend.update_run(second.id, status="COMPLETED")
        outcomes = [
            ("SUCCESSFUL_JAILBREAK", None),
            ("FAILED_JAILBREAK", None),
            ("PASSED_CRITERIA", None),
            ("FAILED_CRITERIA", None),
            ("ERROR", None),
            ("NOT_EVALUATED", None),
            ("SUCCESSFUL_JAILBREAK", "Failed with exception: timeout"),
            ("custom_SUCCESSFUL_JAILBREAK", None),
        ]
        for index, (status, notes) in enumerate(outcomes, 1):
            for run in (self.child, second):
                result = self.backend.create_result(
                    run.id, f"Goal {index}", index, {}, {}
                )
                self.backend.update_result(
                    result.id, evaluation_status=status, evaluation_notes=notes
                )
        for campaign_status, child_status in (
            ("COMPLETED", "COMPLETED"),
            ("FAILED", "COMPLETED"),
            ("COMPLETED", "RUNNING"),
        ):
            self.backend.update_campaign_run(self.campaign.id, status=campaign_status)
            self.backend.update_run(second.id, status=child_status)
            results = [
                *self.backend.list_results(run_id=self.child.id).items,
                *self.backend.list_results(run_id=second.id).items,
            ]
            expected = _goals(results, campaign_status == child_status == "COMPLETED")
            row = self.get("/api/proxy/local/history")["results"][0]
            self.assertEqual(row["attempts"], len(results))
            self.assertEqual(row["recorded_goals"], len(expected))
            for verdict in ("jailbroken", "mitigated", "unresolved"):
                self.assertEqual(
                    row[verdict], sum(g["verdict"] == verdict for g in expected)
                )

    def test_bulk_delete_removes_selected_executions(self):
        other = self.backend.start_campaign(
            self.agent.id, {"campaign": {"name": "Other"}}
        )
        self.backend.update_campaign_run(other.id, status="FAILED")
        response = self.client.delete(
            "/api/proxy/local/history",
            json={"ids": [str(self.campaign.id), str(other.id)]},
        )
        self.assertEqual(response.status_code, 204)
        self.assertEqual(self.backend.list_campaign_runs().total, 0)
        self.assertEqual(self.backend.get_run(self.run.id).id, self.run.id)

    def test_bulk_delete_active_execution_preserves_entire_selection(self):
        other = self.backend.start_campaign(
            self.agent.id, {"campaign": {"name": "Active"}}
        )
        response = self.client.delete(
            "/api/proxy/local/history",
            json={"ids": [str(self.campaign.id), str(other.id)]},
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.backend.get_result(self.first.id).id, self.first.id)
        self.assertEqual(self.backend.list_campaign_runs().total, 2)

    def test_bulk_delete_missing_execution_preserves_entire_selection(self):
        from uuid import uuid4

        response = self.client.delete(
            "/api/proxy/local/history",
            json={"ids": [str(self.campaign.id), str(uuid4())]},
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.backend.get_result(self.first.id).id, self.first.id)

    def test_bulk_delete_rejects_invalid_input(self):
        for body in ({}, {"ids": []}, {"ids": ["invalid"]}, {"ids": [4]}):
            self.assertEqual(
                self.client.delete("/api/proxy/local/history", json=body).status_code,
                400,
            )

    def test_failed_delete_rolls_back_child_data(self):
        trace = self.backend.create_trace(self.first.id, 1, "test", {})
        self.backend._conn.execute(
            "CREATE TEMP TRIGGER reject_campaign_delete BEFORE DELETE ON campaign_runs "
            "BEGIN SELECT RAISE(ABORT, 'test failure'); END"
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.backend.delete_campaign_run(self.campaign.id)
        self.assertEqual(self.backend.get_result(self.first.id).id, self.first.id)
        self.assertEqual(self.backend.list_traces(self.first.id)[0].id, trace.id)
        self.assertEqual(self.backend.get_run(self.child.id).id, self.child.id)

    def test_delete_execution_removes_children_but_preserves_other_data(self):
        trace = self.backend.create_trace(self.first.id, 1, "test", {})
        other = self.backend.start_campaign(
            self.agent.id, {"campaign": {"name": "Keep"}}
        )
        response = self.client.delete(self.base)
        self.assertEqual(response.status_code, 204)
        for table, ident in (
            ("campaign_runs", self.campaign.id),
            ("runs", self.child.id),
            ("results", self.first.id),
            ("traces", trace.id),
        ):
            self.assertIsNone(
                self.backend._conn.execute(
                    f"SELECT id FROM {table} WHERE id=?", (str(ident),)
                ).fetchone()
            )
        self.assertEqual(self.backend.get_campaign_run(other.id).name, "Keep")
        self.assertEqual(self.backend.get_run(self.run.id).id, self.run.id)
        self.assertEqual(self.client.delete(self.base).status_code, 404)

    def test_delete_active_execution_or_child_returns_conflict(self):
        self.backend.update_campaign_run(self.campaign.id, status="RUNNING")
        self.assertEqual(self.client.delete(self.base).status_code, 409)
        self.backend.update_campaign_run(self.campaign.id, status="COMPLETED")
        self.backend.update_run(self.child.id, status="RUNNING")
        self.assertEqual(self.client.delete(self.base).status_code, 409)
        self.assertEqual(self.backend.get_result(self.first.id).id, self.first.id)

    def test_delete_invalid_execution_id_returns_not_found(self):
        self.assertEqual(
            self.client.delete("/api/proxy/local/history/not-a-uuid").status_code, 404
        )

    def setUp(self):
        super().setUp()
        self.campaign = self.backend.start_campaign(
            self.agent.id, {"version": 1, "campaign": {"name": "Campaign demo"}}
        )
        self.child = self.backend.create_run(
            self.attack.id, self.agent.id, {}, campaign_run_id=self.campaign.id
        )
        self.first = self.backend.create_result(self.child.id, "First goal", 0, {}, {})
        self.backend.update_result(self.first.id, evaluation_status="FAILED_JAILBREAK")
        self.backend.update_run(self.child.id, status="COMPLETED")
        self.backend.update_campaign_run(
            self.campaign.id, status="COMPLETED", audit={"samples": 5, "judges": []}
        )
        self.base = f"/api/proxy/local/history/{self.campaign.id}"

    def test_one_history_row_per_execution_not_attack_run(self):
        second = self.backend.create_run(
            self.attack.id, self.agent.id, {}, campaign_run_id=self.campaign.id
        )
        result = self.backend.create_result(second.id, "First goal", 0, {}, {})
        self.backend.update_result(result.id, evaluation_status="SUCCESSFUL_JAILBREAK")
        self.backend.update_run(second.id, status="COMPLETED")
        page = self.get("/api/proxy/local/history")
        self.assertEqual(page["count"], 1)
        row = page["results"][0]
        self.assertEqual(row["attack_runs"], 2)
        self.assertEqual(row["recorded_goals"], 1)
        self.assertEqual(row["jailbroken"], 1)
        self.assertEqual(row["attempts"], 2)

    def test_detail_exposes_stored_audit_configuration_and_children(self):
        payload = self.get(self.base)
        self.assertEqual(payload["configuration"], self.campaign.campaign_config)
        self.assertEqual(payload["audit"], {"samples": 5, "judges": []})
        self.assertEqual(payload["runs"][0]["id"], str(self.child.id))
        self.assertEqual(payload["runs"][0]["technique"], "tap")
        self.assertEqual(payload["runs"][0]["family"], "adaptive")
        self.assertEqual(payload["runs"][0]["configuration"], {})
        self.assertEqual(payload["runs"][0]["outcomes"]["mitigated"], 1)

    def test_detail_exposes_each_runs_recorded_attack_block_without_credentials(self):
        attack = self.backend.create_attack(
            "advprefix",
            self.agent.id,
            self.attack.organization,
            {
                "parameters": {"samples_per_candidate": 4, "api_key": "sk-secret"},
                "roles": {
                    "attacker": {
                        "name": "writer",
                        "endpoint": "http://user:pass@127.0.0.1:8001/v1",
                    }
                },
            },
        )
        run = self.backend.create_run(
            attack.id, self.agent.id, {}, campaign_run_id=self.campaign.id
        )
        payload = self.get(self.base)
        block = next(r for r in payload["runs"] if r["id"] == str(run.id))[
            "attack_configuration"
        ]
        self.assertEqual(block["parameters"]["samples_per_candidate"], 4)
        self.assertNotIn("api_key", block["parameters"])
        self.assertEqual(
            block["roles"]["attacker"]["endpoint"],
            "http://[REDACTED]@127.0.0.1:8001/v1",
        )

    def test_structure_combines_whole_goal_and_preserves_lineage(self):
        self.backend.update_result(
            self.first.id,
            agent_specific_data={
                "attack_metadata": {"candidate_path": [0, 0], "parent_path": []}
            },
        )
        self.backend.create_trace(
            self.first.id,
            1,
            "phase",
            {
                "v": 1,
                "node": "phase",
                "path": [0, 0],
                "label": "candidate",
                "data": {"parent_path": []},
            },
        )
        second = self.backend.create_result(self.child.id, "First goal", 0, {}, {})
        self.backend.create_trace(
            second.id,
            1,
            "decision",
            {"v": 1, "node": "decision", "path": [1], "label": "pruned"},
        )
        self.backend.create_result(self.child.id, "Other goal", 1, {}, {})
        payload = self.get(
            self.base + f"/structure?run_id={self.child.id}&goal_index=0"
        )
        self.assertEqual(len(payload["attempts"]), 2)
        self.assertEqual([a["ordinal"] for a in payload["attempts"]], [1, 2])
        self.assertEqual(len(payload["traces"]), 2)
        self.assertEqual(len(payload["results"]), 2)
        self.assertEqual(payload["results"][0]["id"], str(self.first.id))
        self.assertEqual(payload["attempts"][0]["metadata"]["candidate_path"], [0, 0])
        self.assertEqual(
            self.client.get(self.base + "/structure?goal_index=0").status_code, 404
        )
        self.assertEqual(
            self.client.get(
                self.base + f"/structure?run_id={self.child.id}&goal_index=-1"
            ).status_code,
            400,
        )

    def test_goal_matrix_preserves_campaign_scope_and_individual_attack_outcomes(self):
        second = self.backend.create_run(
            self.attack.id, self.agent.id, {}, campaign_run_id=self.campaign.id
        )
        result = self.backend.create_result(second.id, "First goal", 0, {}, {})
        self.backend.update_result(result.id, evaluation_status="SUCCESSFUL_JAILBREAK")
        self.backend.update_run(second.id, status="COMPLETED")
        self.backend.create_result(self.child.id, "Other goal", 27, {}, {})
        goal = self.get(self.base + "/goals?goal_index=0")["results"][0]
        self.assertEqual(goal["verdict"], "jailbroken")
        self.assertEqual(
            {item["run_id"]: item["verdict"] for item in goal["attack_outcomes"]},
            {str(self.child.id): "mitigated", str(second.id): "jailbroken"},
        )
        other = self.get(self.base + "/goals?goal_index=27")["results"][0]
        self.assertEqual(len(other["attack_outcomes"]), 1)
        self.assertEqual(other["run_ids"], [str(self.child.id)])
        self.assertEqual(
            self.client.get(self.base + "/goals?goal_index=bad").status_code, 400
        )
        self.assertEqual(
            self.client.get(self.base + "/goals?goal_index=-1").status_code, 400
        )
        self.assertEqual(self.get(self.base + "/goals?goal_index=99")["results"], [])

    def test_structure_returns_conversation_without_extra_result_requests(self):
        result = self.backend.create_result(
            self.child.id,
            "First goal",
            0,
            {"messages": [{"role": "user", "content": "Fixture prompt"}]},
            {"response": "Fixture response"},
        )
        payload = self.get(
            self.base + f"/structure?run_id={self.child.id}&goal_index=0"
        )
        evidence = next(
            item for item in payload["results"] if item["id"] == str(result.id)
        )
        self.assertEqual(
            evidence["request_payload"]["messages"][0]["content"], "Fixture prompt"
        )
        self.assertEqual(
            evidence["agent_specific_data"]["response"], "Fixture response"
        )

    def test_attack_category_counts_include_unresolved_and_explicit_untested(self):
        self.backend.update_result(
            self.first.id, agent_specific_data={"category": "Privacy"}
        )
        second = self.backend.create_run(
            self.attack.id, self.agent.id, {}, campaign_run_id=self.campaign.id
        )
        result = self.backend.create_result(
            second.id, "First goal", 0, {}, {"category": "Privacy"}
        )
        self.backend.update_result(result.id, evaluation_status="SUCCESSFUL_JAILBREAK")
        # A second successful attempt must not double-count the goal.
        duplicate = self.backend.create_result(second.id, "First goal", 0, {}, {})
        self.backend.update_result(
            duplicate.id, evaluation_status="SUCCESSFUL_JAILBREAK"
        )
        error = self.backend.create_result(
            second.id, "Second goal", 1, {}, {"category": "Privacy"}
        )
        self.backend.update_result(error.id, evaluation_status="ERROR_AGENT_RESPONSE")
        self.backend.create_result(
            self.child.id, "Other category", 2, {}, {"category": "Tools"}
        )
        self.backend.update_run(second.id, status="COMPLETED")
        cells = {
            (item["run_id"], item["category"]): item
            for item in self.get(self.base)["attack_category_outcomes"]
        }
        privacy = cells[(str(second.id), "Privacy")]
        self.assertEqual(privacy["recorded_goals"], 2)
        self.assertEqual(privacy["jailbroken"], 1)
        self.assertEqual(privacy["unresolved"], 1)
        self.assertEqual(cells[(str(self.child.id), "Privacy")]["mitigated"], 1)
        tools = cells[(str(second.id), "Tools")]
        self.assertEqual(tools["recorded_goals"], 0)
        self.assertEqual(tools["jailbroken"], 0)

    def test_attack_category_counts_respect_execution_scope(self):
        other = self.backend.create_run(
            self.attack.id, self.agent.id, {}, campaign_run_id=self.campaign.id
        )
        result = self.backend.create_result(other.id, "Other goal", 1, {}, {})
        self.backend.update_result(result.id, evaluation_status="SUCCESSFUL_JAILBREAK")
        payload = self.get(self.base + f"?run_id={self.child.id}")
        self.assertEqual(len(payload["attack_category_outcomes"]), 1)
        self.assertEqual(
            payload["attack_category_outcomes"][0]["run_id"], str(self.child.id)
        )
        self.assertEqual(payload["attack_category_outcomes"][0]["jailbroken"], 0)

    def test_subcategory_drilldown_preserves_goal_denominators_and_missing_coverage(
        self,
    ):
        labels = {"category": "Privacy", "subcategory": "Personal data"}
        self.backend.update_result(self.first.id, agent_specific_data=labels)
        repeat = self.backend.create_result(self.child.id, "First goal", 0, {}, labels)
        self.backend.update_result(repeat.id, evaluation_status="SUCCESSFUL_JAILBREAK")
        other = self.backend.create_result(
            self.child.id,
            "Second goal",
            1,
            {},
            {"category": "Privacy", "subcategory": "Credentials"},
        )
        self.backend.update_result(other.id, evaluation_status="FAILED_JAILBREAK")
        second_run = self.backend.create_run(
            self.attack.id, self.agent.id, {}, campaign_run_id=self.campaign.id
        )
        self.backend.create_result(second_run.id, "First goal", 0, {}, labels)
        cells = self.get(self.base)["attack_category_outcomes"]
        first = next(item for item in cells if item["run_id"] == str(self.child.id))
        subs = {item["name"]: item for item in first["subcategories"]}
        self.assertEqual(subs["Personal data"]["recorded_goals"], 1)
        self.assertEqual(subs["Personal data"]["jailbroken"], 1)
        second = next(item for item in cells if item["run_id"] == str(second_run.id))
        untested = next(
            item for item in second["subcategories"] if item["name"] == "Credentials"
        )
        self.assertEqual(untested["recorded_goals"], 0)
        goals = self.get(self.base + "/goals?category=Privacy&subcategory=Credentials")
        self.assertEqual(goals["count"], 1)
        self.assertEqual(goals["results"][0]["index"], 1)
        self.assertEqual(self.get(self.base + "/goals?subcategory=Missing")["count"], 0)

    def test_detail_orders_repeated_attack_executions_chronologically(self):
        second = self.backend.create_run(
            self.attack.id, self.agent.id, {}, campaign_run_id=self.campaign.id
        )
        runs = self.get(self.base)["runs"]
        self.assertEqual(
            [run["id"] for run in runs], [str(self.child.id), str(second.id)]
        )
        self.assertEqual([run["technique"] for run in runs], ["tap", "tap"])

    def test_structure_does_not_truncate_conversation_to_a_page(self):
        for index in range(25):
            self.backend.create_result(
                self.child.id,
                "First goal",
                0,
                {"messages": [{"role": "user", "content": f"Prompt {index}"}]},
                {},
            )
        payload = self.get(
            self.base + f"/structure?run_id={self.child.id}&goal_index=0"
        )
        self.assertEqual(len(payload["attempts"]), 26)
        self.assertEqual(len(payload["results"]), 26)
        self.assertEqual(payload["attempts"][-1]["ordinal"], 26)

    def test_technique_graphs_deduplicate_goals_across_runs(self):
        second = self.backend.create_run(
            self.attack.id, self.agent.id, {}, campaign_run_id=self.campaign.id
        )
        result = self.backend.create_result(second.id, "First goal", 0, {}, {})
        self.backend.update_result(result.id, evaluation_status="SUCCESSFUL_JAILBREAK")
        self.backend.update_run(second.id, status="COMPLETED")
        other_attack = self.backend.create_attack(
            "pair", self.agent.id, self.org_id, {}
        )
        other_run = self.backend.create_run(
            other_attack.id, self.agent.id, {}, campaign_run_id=self.campaign.id
        )
        other_result = self.backend.create_result(other_run.id, "First goal", 0, {}, {})
        self.backend.update_result(
            other_result.id, evaluation_status="ERROR_AGENT_RESPONSE"
        )
        self.backend.update_run(other_run.id, status="COMPLETED")
        payload = self.get(self.base)
        self.assertEqual(payload["recorded_goals"], 1)
        self.assertEqual(
            payload["technique_outcomes"],
            [
                {
                    "technique": "pair",
                    "recorded_goals": 1,
                    "jailbroken": 0,
                    "mitigated": 0,
                    "unresolved": 1,
                    "attempts": 1,
                },
                {
                    "technique": "tap",
                    "recorded_goals": 1,
                    "jailbroken": 1,
                    "mitigated": 0,
                    "unresolved": 0,
                    "attempts": 2,
                },
            ],
        )

    def test_running_attack_reports_evaluated_goal_without_waiting_for_other_goals(
        self,
    ):
        self.backend.update_campaign_run(self.campaign.id, status="RUNNING")
        self.backend.update_run(self.child.id, status="RUNNING")
        pending = self.backend.create_result(self.child.id, "Pending goal", 1, {}, {})
        failed = self.backend.create_result(self.child.id, "Errored goal", 2, {}, {})
        self.backend.update_result(failed.id, evaluation_status="ERROR_AGENT_RESPONSE")
        payload = self.get(self.base)
        technique = payload["technique_outcomes"][0]
        self.assertEqual(technique["mitigated"], 1)
        self.assertEqual(technique["unresolved"], 2)
        self.assertEqual(payload["runs"][0]["outcomes"]["mitigated"], 1)
        goals = self.get(self.base + "/goals")["results"]
        self.assertEqual(goals[0]["verdict"], "unresolved")
        self.assertEqual(goals[0]["attack_outcomes"][0]["verdict"], "mitigated")
        self.assertEqual(goals[1]["attack_outcomes"][0]["verdict"], "unresolved")
        self.assertEqual(goals[2]["attack_outcomes"][0]["verdict"], "error")
        scoped = self.get(self.base + f"?run_id={self.child.id}")
        self.assertEqual(scoped["mitigated"], 1)
        self.assertEqual(scoped["unresolved"], 2)
        scoped_goals = self.get(
            self.base + f"/goals?run_id={self.child.id}&verdict=mitigated"
        )
        self.assertEqual(scoped_goals["count"], 1)
        self.assertEqual(scoped_goals["results"][0]["index"], 0)
        self.backend.update_result(pending.id, evaluation_status="SUCCESSFUL_JAILBREAK")
        updated = self.get(self.base + "/goals")["results"][1]
        self.assertEqual(updated["attack_outcomes"][0]["verdict"], "jailbroken")

    def test_scoped_detail_and_categories_use_only_selected_execution(self):
        self.backend.update_result(
            self.first.id,
            agent_specific_data={"category": "Safety", "subcategory": "Privacy"},
        )
        second = self.backend.create_run(
            self.attack.id, self.agent.id, {}, campaign_run_id=self.campaign.id
        )
        result = self.backend.create_result(
            second.id,
            "First goal",
            0,
            {},
            {"category": "Safety", "subcategory": "Privacy"},
        )
        self.backend.update_result(result.id, evaluation_status="SUCCESSFUL_JAILBREAK")
        self.backend.update_run(second.id, status="COMPLETED")
        whole = self.get(self.base)
        scoped = self.get(self.base + f"?run_id={self.child.id}")
        self.assertEqual(whole["jailbroken"], 1)
        self.assertEqual(scoped["jailbroken"], 0)
        self.assertEqual(scoped["mitigated"], 1)
        self.assertEqual(scoped["scope_run_id"], str(self.child.id))
        self.assertEqual(len(scoped["runs"]), 2)
        category = scoped["category_outcomes"][0]
        self.assertEqual(category["category"], "Safety")
        self.assertEqual(category["mitigated"], 1)
        self.assertEqual(category["subcategories"][0]["name"], "Privacy")
        goals = self.get(self.base + f"/goals?run_id={self.child.id}&category=Safety")
        self.assertEqual(goals["count"], 1)
        self.assertEqual(goals["results"][0]["category_source"], "recorded")
        self.assertEqual(self.get(self.base + "/goals?category=Missing")["count"], 0)
        for endpoint in ("", "/goals", "/attempts?goal_index=0"):
            separator = "&" if "?" in endpoint else "?"
            response = self.client.get(
                self.base + endpoint + separator + f"run_id={self.run.id}"
            )
            self.assertEqual(response.status_code, 404)

    def test_missing_categories_are_unknown_and_jump_has_stable_page(self):
        goal = self.get(self.base + "/goals")["results"][0]
        self.assertEqual(goal["category"], "Unknown")
        success = self.backend.create_result(self.child.id, "First goal", 0, {}, {})
        self.backend.update_result(success.id, evaluation_status="SUCCESSFUL_JAILBREAK")
        page = self.get(self.base + "/attempts?goal_index=0&page_size=1")
        self.assertEqual(page["results"][0]["ordinal"], 1)
        self.assertEqual(page["first_success"], {"id": str(success.id), "page": 2})

    def test_offline_profile_does_not_prompt_for_unsaveable_analytics_consent(self):
        self.assertEqual(
            self.get("/api/proxy/user/me")["analytics_consent"], "declined"
        )

    def test_evidence_keeps_the_original_request_and_recorded_reply(self):
        payload = {"messages": [{"role": "user", "content": "Recorded prompt"}]}
        result = self.backend.create_result(self.child.id, "First goal", 0, payload, {})
        self.backend.update_result(
            result.id, agent_specific_data={"response": "Recorded reply"}
        )
        evidence = self.get(f"/api/proxy/result/{result.id}")
        self.assertEqual(evidence["request_payload"], payload)
        self.assertEqual(evidence["agent_specific_data"]["response"], "Recorded reply")

    def test_goal_filters_apply_before_pagination(self):
        result = self.backend.create_result(self.child.id, "Second goal", 1, {}, {})
        self.backend.update_result(result.id, evaluation_status="SUCCESSFUL_JAILBREAK")
        page = self.get(self.base + "/goals?verdict=jailbroken&page_size=1")
        self.assertEqual(page["count"], 1)
        self.assertEqual(page["results"][0]["index"], 1)
        self.assertEqual(self.get(self.base + "/goals?search=FIRST")["count"], 1)

    def test_errors_and_incomplete_executions_are_not_mitigated(self):
        self.backend.update_result(
            self.first.id,
            evaluation_status="FAILED_JAILBREAK",
            evaluation_notes="Attack failed with exception: timeout",
        )
        goal = self.get(self.base + "/goals")["results"][0]
        self.assertEqual(goal["verdict"], "unresolved")
        self.assertEqual(goal["errors"], 1)
        self.backend.update_result(
            self.first.id, evaluation_status="FAILED_JAILBREAK", evaluation_notes=""
        )
        self.backend.update_campaign_run(self.campaign.id, status="RUNNING")
        self.assertEqual(
            self.get(self.base + "/goals")["results"][0]["verdict"], "unresolved"
        )

    def test_attempts_are_scoped_ordered_and_paginated(self):
        second = self.backend.create_result(self.child.id, "First goal", 0, {}, {})
        self.backend.create_result(self.child.id, "Second goal", 1, {}, {})
        page = self.get(self.base + "/attempts?goal_index=0&page_size=1")
        self.assertEqual(page["count"], 2)
        self.assertEqual(page["results"][0]["id"], str(self.first.id))
        page2 = self.get(self.base + "/attempts?goal_index=0&page_size=1&page=2")
        self.assertEqual(page2["results"][0]["id"], str(second.id))
        self.assertEqual(
            self.client.get(
                self.base + f"/attempts?goal_index=0&run_id={self.run.id}"
            ).status_code,
            404,
        )

    def test_invalid_inputs_and_unknown_campaigns(self):
        for query in ("", "?goal_index=-1", "?goal_index=abc"):
            self.assertEqual(
                self.client.get(self.base + "/attempts" + query).status_code, 400
            )
        self.assertEqual(
            self.client.get(self.base + "/goals?verdict=invalid").status_code, 400
        )
        self.assertEqual(
            self.client.get("/api/proxy/local/history/nope").status_code, 404
        )

    def test_reads_continue_past_a_storage_page(self):
        pages = []

        def listing(*, page, page_size):
            pages.append(page)
            return PaginatedResult(items=[page], total=3)

        self.assertEqual(_read_all(listing), [1, 2, 3])
        self.assertEqual(pages, [1, 2, 3])

    def test_costs_first_success_matches_structure_order_and_reported_asr(self):
        repeat = self.backend.create_result(self.child.id, "First goal", 0, {}, {})
        self.backend.update_result(
            repeat.id,
            evaluation_status="SUCCESSFUL_JAILBREAK",
            agent_specific_data={
                "attack_metadata": {"goal_active_target_elapsed_s": 12.5}
            },
        )
        payload = self.get(self.base + "/costs")
        sample = next(
            run for run in payload["runs"] if run["run_id"] == str(self.child.id)
        )["goal_samples"][0]
        structure = self.get(
            self.base + f"/structure?goal_index=0&run_id={self.child.id}"
        )
        self.assertEqual(
            sample["first_jailbreak_attempt"],
            next(
                index
                for index, attempt in enumerate(structure["attempts"], 1)
                if attempt["bucket"] == "jailbreak"
            ),
        )
        self.assertEqual(sample["first_jailbreak_elapsed_s"], 12.5)
        child = next(
            run
            for run in self.get(self.base)["runs"]
            if run["id"] == str(self.child.id)
        )
        self.assertEqual(child["outcomes"]["jailbroken"], 1)

    def test_costs_split_traced_calls_by_role_and_mark_untraced_as_unknown(self):
        self.backend.update_result(self.first.id, latency_ms=1000)
        call = {
            "node": "call",
            "data": {"usage": {"prompt_tokens": 10, "completion_tokens": 5}},
        }
        self.backend.create_trace(
            self.first.id, 0, "TOOL_CALL", {**call, "label": "target"}
        )
        self.backend.create_trace(
            self.first.id, 1, "TOOL_CALL", {**call, "label": "target"}
        )
        self.backend.create_trace(
            self.first.id, 2, "TOOL_CALL", {"node": "call", "label": "attacker"}
        )
        self.backend.create_trace(
            self.first.id, 3, "TOOL_CALL", {"node": "call", "label": "on_topic"}
        )
        self.backend.create_trace(
            self.first.id, 4, "TOOL_CALL", {"node": "call", "label": "panel"}
        )
        self.backend.create_trace(
            self.first.id, 5, "OTHER", {"node": "phase", "label": "branch"}
        )
        self.backend.create_trace(
            self.first.id,
            6,
            "interaction",
            {"response": {"usage": {"prompt_tokens": 99, "completion_tokens": 99}}},
        )
        static = self.backend.create_run(
            self.attack.id, self.agent.id, {}, campaign_run_id=self.campaign.id
        )
        for index, ms in enumerate((100, 300, 200)):
            result = self.backend.create_result(
                static.id, f"Goal {index}", index, {}, {}
            )
            self.backend.update_result(result.id, latency_ms=ms)
            self.backend.create_trace(
                result.id,
                0,
                "interaction",
                {"response": {"usage": {"prompt_tokens": 3, "completion_tokens": 7}}},
            )

        payload = self.get(self.base + "/costs")

        self.assertTrue(payload["available"])
        runs = {run["run_id"]: run for run in payload["runs"]}
        traced = runs[str(self.child.id)]
        self.assertTrue(traced["calls_traced"])
        self.assertEqual(traced["calls"], {"target": 2, "attacker": 2, "judge": 1})
        self.assertEqual(traced["target_tokens"], {"prompt": 20, "completion": 10})
        self.assertEqual(traced["goals"], 1)
        untraced = runs[str(static.id)]
        self.assertFalse(untraced["calls_traced"])
        self.assertEqual(
            untraced["calls"], {"target": 3, "attacker": None, "judge": None}
        )
        self.assertEqual(untraced["target_tokens"], {"prompt": 9, "completion": 21})
        self.assertEqual(untraced["target_latency_ms"]["median"], 200)
        self.assertEqual(untraced["target_latency_ms"]["samples"], 3)
        self.assertEqual((untraced["goals"], untraced["attempts"]), (3, 3))
        self.assertGreaterEqual(untraced["elapsed_s"], 0)

    def test_costs_of_a_traced_static_run_count_each_call_once(self):
        static = self.backend.create_run(
            self.attack.id, self.agent.id, {}, campaign_run_id=self.campaign.id
        )
        usage = {"prompt_tokens": 4, "completion_tokens": 6}
        for index in range(2):
            result = self.backend.create_result(
                static.id, f"Goal {index}", index, {}, {}
            )
            self.backend.create_trace(
                result.id,
                0,
                "TOOL_CALL",
                {"node": "call", "label": "target", "data": {"usage": usage}},
            )
            self.backend.create_trace(
                result.id, 1, "TOOL_CALL", {"node": "call", "label": "panel"}
            )
            self.backend.create_trace(
                result.id, 2, "interaction", {"response": {"usage": usage}}
            )

        runs = {run["run_id"]: run for run in self.get(self.base + "/costs")["runs"]}
        traced = runs[str(static.id)]

        self.assertTrue(traced["calls_traced"])
        self.assertEqual(traced["calls"], {"target": 2, "attacker": 0, "judge": 2})
        self.assertEqual(traced["target_tokens"], {"prompt": 8, "completion": 12})

    def test_costs_unknown_campaign_is_not_found(self):
        response = self.client.get(
            "/api/proxy/local/history/00000000-0000-0000-0000-000000000000/costs"
        )
        self.assertEqual(response.status_code, 404)
