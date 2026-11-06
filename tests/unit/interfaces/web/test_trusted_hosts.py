# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""The dashboard answers only requests addressed to this machine, and takes
browser writes only from its own origin: a page that rebinds its name to
127.0.0.1, or posts to it, gets nothing."""

from hackagent.interfaces.web import create_app

from tests.unit.interfaces.web.test_local_api import _WebUITestCase

LOCAL = "127.0.0.1:7860"


class TestTrustedHosts(_WebUITestCase):
    def status(self, host: str, client=None) -> int:
        return (
            (client or self.client).get("/healthz", headers={"Host": host}).status_code
        )

    def test_loopback_names_are_served(self):
        for host in (LOCAL, "localhost:7860", "LOCALHOST", "[::1]:7860"):
            self.assertEqual(self.status(host), 200, host)

    def test_other_names_are_refused(self):
        for host in ("attacker.example:7860", "127.0.0.1.attacker.example", ""):
            self.assertEqual(self.status(host), 400, host)

    def test_api_routes_are_refused_for_other_names(self):
        response = self.client.get(
            "/api/proxy/agent", headers={"Host": "attacker.example:7860"}
        )
        self.assertEqual(response.status_code, 400)

    def test_the_host_it_listens_on_is_served(self):
        client = create_app(self.session, hosts=["devbox.lan"]).test_client()
        self.assertEqual(self.status("devbox.lan:7860", client), 200)
        self.assertEqual(self.status("attacker.example", client), 400)

    def test_listening_on_every_address_trusts_no_extra_name(self):
        client = create_app(self.session, hosts=["0.0.0.0"]).test_client()
        self.assertEqual(self.status("0.0.0.0:7860", client), 400)
        self.assertEqual(self.status(LOCAL, client), 200)


class TestSameOriginWrites(_WebUITestCase):
    def delete_run(self, **headers):
        return self.client.delete(
            f"/api/proxy/run/{self.run.id}", headers={"Host": LOCAL, **headers}
        )

    def test_a_write_from_another_origin_is_refused(self):
        response = self.delete_run(Origin="http://attacker.example")
        self.assertEqual(response.status_code, 403)
        self.assertIsNotNone(self.backend.get_run(self.run.id))

    def test_a_write_from_the_dashboard_is_served(self):
        self.assertEqual(self.delete_run(Origin=f"http://{LOCAL}").status_code, 204)

    def test_a_write_without_origin_is_served(self):
        self.assertEqual(self.delete_run().status_code, 204)

    def test_reads_from_another_origin_are_served(self):
        response = self.client.get(
            "/healthz", headers={"Host": LOCAL, "Origin": "http://attacker.example"}
        )
        self.assertEqual(response.status_code, 200)
