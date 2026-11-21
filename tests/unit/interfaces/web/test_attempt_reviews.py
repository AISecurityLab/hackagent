# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Human reviews of attempts under ``/api/proxy/result/{id}/reviews``.

The conformance cases pin the responses that need no write; these cover
recording reviews, what they change in the reports, and existing databases.
"""

import sqlite3
from uuid import uuid4

from test_run_reports import _CampaignRunCase


class _ReviewCase(_CampaignRunCase):
    def review(self, outcome, expected=None, result=None, explanation=""):
        return self.client.post(
            f"/api/proxy/result/{result or self.first.id}/reviews",
            json={
                "outcome": outcome,
                "explanation": explanation,
                "expected_review_id": expected,
            },
        )

    def attempt(self):
        [attempt] = self.get(self.base + "/attempts?goal_index=0")["results"]
        return attempt


class TestRecording(_ReviewCase):
    def test_a_review_overrides_the_automated_outcome_everywhere(self):
        response = self.review("jailbreak", explanation=" Gives the steps. ")
        self.assertEqual(response.status_code, 201)
        body = response.get_json()
        self.assertEqual(
            (body["outcome"], body["explanation"], body["reviewer"]),
            ("jailbreak", "Gives the steps.", "local"),
        )
        self.assertEqual(
            body["attempt"],
            {
                "id": str(self.first.id),
                "run_id": str(self.child.id),
                "goal_index": 0,
                "bucket": "jailbreak",
                "automated_bucket": "mitigated",
            },
        )
        attempt = self.attempt()
        self.assertEqual(
            (attempt["bucket"], attempt["automated_bucket"]),
            ("jailbreak", "mitigated"),
        )
        self.assertEqual(attempt["human_review"]["id"], body["id"])
        summary = self.get(self.base + "/summary")
        self.assertEqual((summary["jailbroken"], summary["mitigated"]), (1, 0))
        [goal] = self.get(self.base + "/goals")["results"]
        self.assertEqual(
            (goal["verdict"], goal["reviewed_attempts"], goal["overridden_attempts"]),
            ("jailbroken", 1, 1),
        )
        report = self.get(self.base + "/report")
        self.assertEqual(
            report["reviews"],
            {
                "reviewed_attempts": 1,
                "inconclusive_attempts": 0,
                "overridden_attempts": 1,
            },
        )
        structure = self.get(
            self.base + f"/structure?goal_index=0&run_id={self.child.id}"
        )
        self.assertEqual(structure["attempts"][0]["bucket"], "jailbreak")
        attempts = self.get(self.base + "/attempts?goal_index=0")
        self.assertEqual(attempts["first_success"]["id"], str(self.first.id))

    def test_withdrawing_restores_the_automated_outcome(self):
        first = self.review("jailbreak").get_json()
        withdrawn = self.review(None, expected=first["id"])
        self.assertEqual(withdrawn.status_code, 201)
        self.assertEqual(withdrawn.get_json()["supersedes_review_id"], first["id"])
        attempt = self.attempt()
        self.assertEqual(attempt["bucket"], "mitigated")
        self.assertIsNone(attempt["human_review"]["outcome"])
        [goal] = self.get(self.base + "/goals")["results"]
        self.assertEqual((goal["verdict"], goal["reviewed_attempts"]), ("mitigated", 0))
        history = self.get(f"/api/proxy/result/{self.first.id}/reviews")
        self.assertEqual(
            [item["outcome"] for item in history["results"]], [None, "jailbreak"]
        )

    def test_an_inconclusive_review_leaves_the_goal_unresolved(self):
        self.review("inconclusive")
        self.assertEqual(self.attempt()["bucket"], "pending")
        [goal] = self.get(self.base + "/goals")["results"]
        self.assertEqual(
            (goal["verdict"], goal["pending"], goal["inconclusive_attempts"]),
            ("unresolved", 1, 1),
        )

    def test_a_stale_review_is_refused_and_changes_nothing(self):
        first = self.review("jailbreak").get_json()
        stale = self.review("mitigated")
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(self.attempt()["human_review"]["id"], first["id"])
        count = self.backend._conn.execute(
            "SELECT COUNT(*) FROM attempt_reviews"
        ).fetchone()[0]
        self.assertEqual(count, 1)

    def test_a_later_evaluation_keeps_the_review(self):
        self.review("mitigated")
        self.backend.update_result(
            self.first.id, evaluation_status="SUCCESSFUL_JAILBREAK"
        )
        attempt = self.attempt()
        self.assertEqual(
            (attempt["bucket"], attempt["automated_bucket"]),
            ("mitigated", "jailbreak"),
        )

    def test_an_unknown_result_is_not_found(self):
        self.assertEqual(self.review("jailbreak", result=uuid4()).status_code, 404)
        self.assertEqual(
            self.client.get(f"/api/proxy/result/{uuid4()}/reviews").status_code, 404
        )


class TestRevalidation(_ReviewCase):
    def test_a_review_changes_the_campaign_runs_etags(self):
        paths = [
            self.base + path
            for path in (
                "/summary",
                "/report",
                "/goals",
                "/matrix",
                "/attempts?goal_index=0",
            )
        ]
        tags = {path: self.client.get(path).headers["ETag"] for path in paths}
        before = self.get(self.base + "/summary")["revision"]
        self.review("jailbreak")
        for path in paths:
            with self.subTest(path=path):
                response = self.client.get(path, headers={"If-None-Match": tags[path]})
                self.assertEqual(response.status_code, 200)
        self.assertEqual(self.get(self.base + "/summary")["revision"], before + 1)

    def test_the_history_revalidates(self):
        path = f"/api/proxy/result/{self.first.id}/reviews"
        tag = self.client.get(path).headers["ETag"]
        self.assertEqual(
            self.client.get(path, headers={"If-None-Match": tag}).status_code, 304
        )
        self.review("jailbreak")
        self.assertEqual(
            self.client.get(path, headers={"If-None-Match": tag}).status_code, 200
        )


class TestTallies(_ReviewCase):
    def test_the_write_path_keeps_what_a_full_recomputation_gives(self):
        self.backend.update_result(
            self.first.id, evaluation_metrics={"eval_a": 0, "eval_b": 1}
        )
        first = self.review("jailbreak").get_json()
        self.review("inconclusive", expected=first["id"])

        def snapshot():
            return {
                table: sorted(
                    (
                        tuple(row)
                        for row in self.backend._conn.execute(f"SELECT * FROM {table}")
                    ),
                    key=repr,
                )
                for table in ("goal_outcomes", "goal_judge_votes")
            }

        kept = snapshot()
        self.backend._rebuild_tallies()
        self.assertEqual(snapshot(), kept)

    def test_the_report_measures_the_judges_not_the_reviewer(self):
        self.backend.update_result(
            self.first.id, evaluation_metrics={"eval_a": 0, "eval_b": 0}
        )
        self.review("jailbreak")
        agreement = self.get(self.base + "/report")["judge_agreement"]
        self.assertEqual(
            agreement["outcome_patterns"],
            [{"outcome": "mitigated", "pattern": "00", "attempts": 1}],
        )

    def test_deleting_a_campaign_run_deletes_its_reviews(self):
        self.review("jailbreak")
        response = self.client.post(
            "/api/proxy/run/delete", json={"ids": [str(self.campaign.id)]}
        )
        self.assertEqual(response.status_code, 204)
        conn = self.backend._conn
        self.assertEqual(
            conn.execute("SELECT COUNT(*) FROM attempt_reviews").fetchone()[0], 0
        )
        self.assertEqual(
            conn.execute(
                "SELECT COUNT(*) FROM goal_judge_votes WHERE campaign_run_id=?",
                (str(self.campaign.id),),
            ).fetchone()[0],
            0,
        )


class TestExistingDatabases(_ReviewCase):
    def test_reviews_recorded_before_the_tallies_counted_them_are_counted(self):
        from hackagent.storage.local import LocalBackend

        path = self.backend._db_path
        self.backend.update_result(self.first.id, evaluation_metrics={"eval_a": 1})
        self.backend.close()
        # A database written by an earlier dashboard: reviews, but tallies
        # without review counts or judge votes.
        conn = sqlite3.connect(path)
        conn.execute(
            "INSERT INTO attempt_reviews (id, result_id, outcome, explanation, "
            "reviewer, created_at) VALUES (?,?,?,?,?,?)",
            (
                str(uuid4()),
                str(self.first.id),
                "jailbreak",
                "",
                "local",
                "2026-01-01T00:00:00+00:00",
            ),
        )
        conn.execute("DROP TABLE goal_judge_votes")
        conn.execute("DROP TABLE goal_outcomes")
        conn.execute(
            "CREATE TABLE goal_outcomes (campaign_run_id TEXT, run_id TEXT NOT NULL, "
            "goal_index INTEGER NOT NULL, goal TEXT NOT NULL, category TEXT NOT NULL, "
            "subcategory TEXT NOT NULL, attempts INTEGER NOT NULL, "
            "jailbreak INTEGER NOT NULL, mitigated INTEGER NOT NULL, "
            "error INTEGER NOT NULL, pending INTEGER NOT NULL, "
            "first_jailbreak_attempt INTEGER, min_jailbreak_elapsed_s REAL, "
            "timed_jailbreaks INTEGER NOT NULL, first_created_at TEXT NOT NULL, "
            "last_updated_at TEXT NOT NULL, labelled_call_attempts INTEGER NOT NULL, "
            "target_call_attempts INTEGER NOT NULL, "
            "interaction_attempts INTEGER NOT NULL, PRIMARY KEY (run_id, goal_index))"
        )
        conn.execute("PRAGMA user_version = 1")
        conn.commit()
        conn.close()

        self.backend = LocalBackend(str(path))
        [outcome] = self.backend.report_goal_outcomes(str(self.campaign.id))
        self.assertEqual(
            (outcome.jailbreak, outcome.reviewed_attempts, outcome.overridden_attempts),
            (1, 1, 1),
        )
        [votes] = self.backend.report_judge_votes(str(self.campaign.id))
        self.assertEqual((votes.outcome, votes.votes), ("mitigated", '{"eval_a":1}'))
