# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""``hackagent web`` answers every conformance case exactly.

The platform API replays the same cases against the same sample; a
difference between the two servers fails one of the two suites.
"""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from hackagent import HackAgent, Settings
from hackagent.interfaces.web import _static, create_app
from hackagent.reporting import conformance
from hackagent.storage.local import LocalBackend

from sample_store import load_sample


class TestConformance(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.root = Path(self._tmp.name)
        bundle = self.root / "static"
        bundle.mkdir()
        (bundle / "index.html").write_text("<html>index</html>")
        self._real_static_dir = _static.static_dir
        _static.static_dir = lambda: bundle
        self.backends: list[LocalBackend] = []

    def tearDown(self) -> None:
        _static.static_dir = self._real_static_dir
        for backend in self.backends:
            backend.close()
        self._tmp.cleanup()

    def serve(self):
        backend = LocalBackend(str(self.root / f"{len(self.backends)}.db"))
        self.backends.append(backend)
        load_sample(backend, conformance.sample())
        session = HackAgent(
            Settings.resolve(
                backend="local", db_path=":memory:", env={}, config_path="/nonexistent"
            ),
            backend=backend,
        )
        return backend, create_app(session).test_client()

    def test_every_case_gets_exactly_its_expected_response(self):
        _, client = self.serve()
        cases = conformance.cases()
        self.assertGreater(len(cases), 50)
        for case in cases:
            with self.subTest(case=case.name):
                if case.mutates:
                    _, server = self.serve()
                else:
                    server = client
                response = server.open(
                    f"/api/proxy{case.path}",
                    method=case.method,
                    query_string=case.query or None,
                    headers=case.headers,
                    json=case.body,
                )
                self.assertEqual(response.status_code, case.status)
                self.assertEqual(response.headers.get("ETag"), case.etag)
                if case.expected is None:
                    self.assertEqual(response.data, b"")
                else:
                    self.assertEqual(response.get_json(), case.expected)

    def test_every_successful_read_is_revalidated(self):
        for case in conformance.cases():
            if case.method == "GET" and case.status == 200:
                with self.subTest(case=case.name):
                    self.assertIsNotNone(case.etag)

    def test_the_write_path_keeps_the_tallies_a_full_recomputation_gives(self):
        backend, _ = self.serve()
        tables = ("goal_outcomes", "goal_usage")

        def snapshot():
            return {
                table: sorted(
                    tuple(row)
                    for row in backend._conn.execute(f"SELECT * FROM {table}")
                )
                for table in tables
            }

        kept = snapshot()
        self.assertTrue(all(kept.values()))
        backend._rebuild_tallies()
        self.assertEqual(snapshot(), kept)

    def test_the_sample_and_cases_ship_as_package_data(self):
        sample = conformance.sample()
        self.assertEqual(
            set(sample),
            {
                "agents",
                "campaigns",
                "attacks",
                "campaign_runs",
                "attack_runs",
                "results",
                "traces",
            },
        )
        buckets = {result["evaluation_status"] for result in sample["results"]}
        self.assertTrue(
            {"SUCCESSFUL_JAILBREAK", "FAILED_JAILBREAK", "NOT_EVALUATED"} <= buckets
        )
        names = [case.name for case in conformance.cases()]
        self.assertEqual(len(names), len(set(names)))
        mutating = [case.mutates for case in conformance.cases()]
        self.assertEqual(mutating, sorted(mutating))


if __name__ == "__main__":
    unittest.main()
