# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Offline campaign run reports under ``/api/proxy/run``.

The exact responses are pinned by the conformance cases
(``tests/unit/reporting``); these cover what a fixed sample cannot: what is
read to answer, revalidation across writes, and deletion.
"""

import sqlite3
from unittest.mock import patch
from uuid import uuid4

from test_local_api import _WebUITestCase


class _CampaignRunCase(_WebUITestCase):
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
        self.base = f"/api/proxy/run/{self.campaign.id}"


class TestReads(_CampaignRunCase):
    READS = ("/summary", "/report", "/goals", "/matrix", "/costs")

    def test_summaries_reports_and_costs_read_no_result_or_trace(self):
        self.backend.create_trace(self.first.id, 1, "interaction", {"response": {}})
        refuse = AssertionError("raw rows read")
        with (
            patch.object(self.backend, "_row_to_result", side_effect=refuse),
            patch.object(self.backend, "list_results", side_effect=refuse),
            patch.object(self.backend, "list_runs", side_effect=refuse),
            patch.object(self.backend, "list_traces", side_effect=refuse),
        ):
            self.get("/api/proxy/run/summary")
            for path in self.READS:
                self.get(self.base + path)
            self.get(self.base + f"/compare?baseline={self.other_run().id}")

    def other_run(self):
        other = self.backend.start_campaign(self.agent.id, {"campaign": {"name": "x"}})
        self.backend.update_campaign_run(other.id, status="COMPLETED")
        return other

    def test_attempts_page_without_materializing_results(self):
        with patch.object(
            self.backend, "_row_to_result", side_effect=AssertionError("decoded")
        ):
            payload = self.get(self.base + "/attempts?goal_index=0&page_size=1")
        self.assertEqual(payload["results"][0]["id"], str(self.first.id))

    def test_structure_reads_only_the_selected_goal(self):
        unrelated = self.backend.create_result(self.child.id, "Other goal", 1, {}, {})
        payload = self.get(
            self.base + f"/structure?goal_index=0&run_id={self.child.id}"
        )
        ids = [item["id"] for item in payload["results"]]
        self.assertEqual(ids, [str(self.first.id)])
        self.assertNotIn(str(unrelated.id), ids)

    def test_summary_and_delete_are_not_campaign_run_ids(self):
        self.assertEqual(self.get("/api/proxy/run/summary")["count"], 1)
        response = self.client.post("/api/proxy/run/delete", json={"ids": []})
        self.assertEqual(response.status_code, 400)

    def test_an_attack_run_id_is_not_a_campaign_run(self):
        for path in (*self.READS, "/attempts?goal_index=0", "/compare"):
            with self.subTest(path=path):
                response = self.client.get(f"/api/proxy/run/{self.child.id}{path}")
                self.assertEqual(response.status_code, 404)
                self.assertEqual(
                    response.get_json(), {"detail": "Campaign run not found."}
                )

    def test_evaluations_that_land_later_change_the_verdicts(self):
        self.backend.update_campaign_run(self.campaign.id, status="RUNNING")
        self.backend.update_run(self.child.id, status="RUNNING")
        pending = self.backend.create_result(self.child.id, "Pending goal", 1, {}, {})
        goals = self.get(self.base + "/goals")["results"]
        self.assertEqual(goals[1]["attack_outcomes"][0]["verdict"], "unresolved")
        self.backend.update_result(pending.id, evaluation_status="SUCCESSFUL_JAILBREAK")
        goals = self.get(self.base + "/goals")["results"]
        self.assertEqual(goals[1]["verdict"], "jailbroken")
        self.assertEqual(self.get(self.base + "/summary")["jailbroken"], 1)

    def test_list_filters_by_campaign_agent_and_status(self):
        self.other_run()
        self.assertEqual(self.get("/api/proxy/run/summary")["count"], 2)
        self.assertEqual(
            self.get(f"/api/proxy/run/summary?agent={self.agent.id}")["count"], 2
        )
        self.assertEqual(
            self.get(f"/api/proxy/run/summary?agent={uuid4()}")["count"], 0
        )
        self.assertEqual(
            self.get("/api/proxy/run/summary?campaign=not-a-uuid")["count"], 0
        )
        self.assertEqual(self.get("/api/proxy/run/summary?status=RUNNING")["count"], 0)


class TestRevalidation(_CampaignRunCase):
    def etag(self, path):
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Cache-Control"], "private, no-cache")
        return response.headers["ETag"]

    def revalidate(self, path, tag):
        return self.client.get(path, headers={"If-None-Match": tag})

    def test_an_unchanged_response_is_not_sent_again(self):
        for path in (
            "/api/proxy/run/summary",
            self.base + "/summary",
            self.base + "/report",
            self.base + "/goals",
            self.base + "/matrix",
            self.base + "/costs",
            self.base + "/attempts?goal_index=0",
            self.base + f"/structure?goal_index=0&run_id={self.child.id}",
        ):
            with self.subTest(path=path):
                tag = self.etag(path)
                response = self.revalidate(path, tag)
                self.assertEqual(response.status_code, 304)
                self.assertEqual(response.data, b"")
                self.assertEqual(response.headers["ETag"], tag)

    def test_a_not_modified_answer_builds_nothing(self):
        tag = self.etag(self.base + "/report")
        refuse = AssertionError("built")
        with (
            patch.object(self.backend, "report_goal_outcomes", side_effect=refuse),
            patch.object(self.backend, "report_attack_runs", side_effect=refuse),
        ):
            self.assertEqual(
                self.revalidate(self.base + "/report", tag).status_code, 304
            )

    def test_every_write_to_the_campaign_run_changes_its_etag(self):
        path = self.base + "/report"
        writes = (
            lambda: self.backend.create_result(self.child.id, "Second", 1, {}, {}),
            lambda: self.backend.update_result(
                self.first.id, evaluation_status="SUCCESSFUL_JAILBREAK"
            ),
            lambda: self.backend.create_trace(self.first.id, 1, "interaction", {}),
            lambda: self.backend.update_run(self.child.id, run_notes="note"),
            lambda: self.backend.create_run(
                self.attack.id, self.agent.id, {}, campaign_run_id=self.campaign.id
            ),
            lambda: self.backend.update_campaign_run(self.campaign.id, run_notes="n"),
        )
        for write in writes:
            tag = self.etag(path)
            before = self.get(self.base + "/summary")["revision"]
            write()
            response = self.revalidate(path, tag)
            self.assertEqual(response.status_code, 200)
            self.assertNotEqual(response.headers["ETag"], tag)
            self.assertEqual(self.get(self.base + "/summary")["revision"], before + 1)

    def test_another_campaign_runs_writes_leave_this_etag_alone(self):
        tag = self.etag(self.base + "/report")
        other = self.backend.start_campaign(self.agent.id, {"campaign": {"name": "x"}})
        run = self.backend.create_run(
            self.attack.id, self.agent.id, {}, campaign_run_id=other.id
        )
        self.backend.create_result(run.id, "g", 0, {}, {})
        self.assertEqual(self.revalidate(self.base + "/report", tag).status_code, 304)

    def test_a_new_previous_run_changes_the_report_etag(self):
        later = self.backend.start_campaign(
            self.agent.id, {"version": 1, "campaign": {"name": "Campaign demo"}}
        )
        path = f"/api/proxy/run/{later.id}/report"
        tag = self.etag(path)
        self.assertIsNotNone(self.get(path)["previous"])
        self.backend.update_result(
            self.first.id, evaluation_status="SUCCESSFUL_JAILBREAK"
        )
        response = self.revalidate(path, tag)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["previous"]["jailbroken"], 1)

    def test_a_new_campaign_run_changes_the_list_etag(self):
        tag = self.etag("/api/proxy/run/summary")
        self.backend.start_campaign(self.agent.id, {"campaign": {"name": "x"}})
        self.assertEqual(
            self.revalidate("/api/proxy/run/summary", tag).status_code, 200
        )


class TestDeletion(_CampaignRunCase):
    def test_bulk_delete_removes_selected_runs_and_their_tallies(self):
        other = self.backend.start_campaign(self.agent.id, {"campaign": {"name": "O"}})
        self.backend.update_campaign_run(other.id, status="FAILED")
        response = self.client.post(
            "/api/proxy/run/delete",
            json={"ids": [str(self.campaign.id), str(other.id)]},
        )
        self.assertEqual(response.status_code, 204)
        self.assertEqual(self.backend.list_campaign_runs().total, 0)
        self.assertEqual(self.backend.get_run(self.run.id).id, self.run.id)
        for table in ("goal_outcomes", "goal_usage"):
            self.assertEqual(
                self.backend._conn.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE campaign_run_id=?",
                    (str(self.campaign.id),),
                ).fetchone()[0],
                0,
            )

    def test_bulk_delete_of_an_active_run_deletes_nothing(self):
        active = self.backend.start_campaign(self.agent.id, {"campaign": {"name": "A"}})
        response = self.client.post(
            "/api/proxy/run/delete",
            json={"ids": [str(self.campaign.id), str(active.id)]},
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.get_json(), {"detail": "An active campaign run cannot be deleted."}
        )
        self.assertEqual(self.backend.list_campaign_runs().total, 2)

    def test_bulk_delete_of_a_missing_run_deletes_nothing(self):
        response = self.client.post(
            "/api/proxy/run/delete",
            json={"ids": [str(self.campaign.id), str(uuid4())]},
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.backend.get_result(self.first.id).id, self.first.id)

    def test_bulk_delete_refuses_malformed_bodies(self):
        for body in ({}, {"ids": []}, {"ids": ["invalid"]}, {"ids": [4]}):
            with self.subTest(body=body):
                response = self.client.post("/api/proxy/run/delete", json=body)
                self.assertEqual(response.status_code, 400)

    def test_a_failed_delete_rolls_back(self):
        self.backend._conn.execute(
            "CREATE TEMP TRIGGER refuse BEFORE DELETE ON campaign_runs "
            "BEGIN SELECT RAISE(ABORT, 'test failure'); END"
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.backend.delete_campaign_run(self.campaign.id)
        self.assertEqual(self.backend.get_result(self.first.id).id, self.first.id)
        self.assertEqual(self.get(self.base + "/summary")["attempts"], 1)

    def test_deleting_an_attack_run_drops_it_from_the_report(self):
        second = self.backend.create_run(
            self.attack.id, self.agent.id, {}, campaign_run_id=self.campaign.id
        )
        self.backend.create_result(second.id, "First goal", 0, {}, {})
        self.assertEqual(self.get(self.base + "/summary")["attempts"], 2)
        self.backend.delete_run(second.id)
        summary = self.get(self.base + "/summary")
        self.assertEqual((summary["attack_runs"], summary["attempts"]), (1, 1))


class TestExistingDatabases(_CampaignRunCase):
    def test_a_database_written_before_the_tallies_gets_them_when_opened(self):
        from hackagent.storage.local import LocalBackend

        path = self.backend._db_path
        self.backend._conn.execute("DELETE FROM goal_outcomes")
        self.backend._conn.execute("PRAGMA user_version = 0")
        self.backend._conn.commit()
        reopened = LocalBackend(str(path))
        try:
            [outcome] = reopened.report_goal_outcomes(str(self.campaign.id))
            self.assertEqual((outcome.attempts, outcome.mitigated), (1, 1))
        finally:
            reopened.close()
