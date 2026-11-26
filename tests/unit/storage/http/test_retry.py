# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for RetryingTransport: requests the server dropped are sent again,
but only those that are safe to send twice."""

import unittest

import httpx

from hackagent.storage._http.retry import RetryingTransport, repeatable_api_call

BASE = "https://api.example.com/api"


class _Server:
    """A mock transport that fails the first ``failures`` requests."""

    def __init__(self, failures, error=None, status=None):
        self.failures = failures
        self.error = error
        self.status = status
        self.requests = []

    def __call__(self, request):
        self.requests.append(request)
        if len(self.requests) <= self.failures:
            if self.error is not None:
                raise self.error("Server disconnected without sending a response.")
            return httpx.Response(self.status)
        return httpx.Response(200, json={"ok": True})


def _client(server, *, repeatable=repeatable_api_call, budget_s=60.0):
    sleeps = []
    transport = RetryingTransport(
        httpx.MockTransport(server),
        repeatable=repeatable,
        budget_s=budget_s,
        sleep=sleeps.append,
    )
    return httpx.Client(base_url=BASE, transport=transport), sleeps


class TestRetry(unittest.TestCase):
    def test_a_dropped_repeatable_request_is_sent_again(self):
        server = _Server(1, error=httpx.RemoteProtocolError)
        client, sleeps = _client(server)

        response = client.post("/result/r1/trace", json={"sequence": 0})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(server.requests), 2)
        self.assertEqual(server.requests[1].content, server.requests[0].content)
        self.assertEqual(len(sleeps), 1)

    def test_a_reset_connection_is_retried(self):
        server = _Server(2, error=httpx.ReadError)
        client, _ = _client(server)

        self.assertEqual(client.patch("/result/r1", json={}).status_code, 200)
        self.assertEqual(len(server.requests), 3)

    def test_a_request_that_is_not_safe_to_repeat_is_sent_once(self):
        server = _Server(1, error=httpx.RemoteProtocolError)
        client, sleeps = _client(server)

        with self.assertRaises(httpx.RemoteProtocolError):
            client.post("/run/r1/children", json={})

        self.assertEqual(len(server.requests), 1)
        self.assertEqual(sleeps, [])

    def test_an_unavailable_server_is_asked_again(self):
        server = _Server(2, status=503)
        client, _ = _client(server)

        self.assertEqual(client.get("/run/r1").status_code, 200)
        self.assertEqual(len(server.requests), 3)

    def test_an_unavailable_answer_to_an_unsafe_request_is_returned(self):
        server = _Server(1, status=502)
        client, _ = _client(server)

        self.assertEqual(client.post("/run/r1/finish", json={}).status_code, 502)
        self.assertEqual(len(server.requests), 1)

    def test_a_read_timeout_is_not_retried(self):
        # The server may still be working on it: waiting the full timeout
        # again would only double the wait.
        server = _Server(1, error=httpx.ReadTimeout)
        client, _ = _client(server)

        with self.assertRaises(httpx.ReadTimeout):
            client.get("/run/r1")
        self.assertEqual(len(server.requests), 1)

    def test_it_gives_up_once_the_time_budget_is_spent(self):
        server = _Server(1000, error=httpx.ConnectError)
        client, sleeps = _client(server, budget_s=10.0)

        with self.assertRaises(httpx.ConnectError):
            client.get("/run/r1")

        self.assertLessEqual(sum(sleeps), 10.0)
        self.assertEqual(len(server.requests), len(sleeps) + 1)
        self.assertGreater(len(sleeps), 1)

    def test_the_delays_grow(self):
        server = _Server(4, error=httpx.ConnectError)
        client, sleeps = _client(server)

        client.get("/run/r1")

        self.assertEqual(sleeps, sorted(sleeps))
        self.assertLess(sleeps[0], sleeps[-1])

    def test_the_predicate_decides(self):
        server = _Server(1, error=httpx.RemoteProtocolError)
        client, _ = _client(server, repeatable=lambda request: True)

        self.assertEqual(client.post("/result", json={}).status_code, 200)


class TestRepeatableApiCall(unittest.TestCase):
    def _call(self, method, path):
        return repeatable_api_call(httpx.Request(method, BASE + path))

    def test_reads_and_updates_are_repeatable(self):
        self.assertTrue(self._call("GET", "/run/r1"))
        self.assertTrue(self._call("HEAD", "/run/r1"))
        self.assertTrue(self._call("PATCH", "/result/r1"))
        self.assertTrue(self._call("PATCH", "/run/r1/"))

    def test_writes_the_server_takes_once_are_repeatable(self):
        # Events are kept by seq, trace steps by sequence; a heartbeat only
        # moves a timestamp.
        self.assertTrue(self._call("POST", "/run/r1/events"))
        self.assertTrue(self._call("POST", "/run/r1/heartbeat/"))
        self.assertTrue(self._call("POST", "/result/r1/trace"))

    def test_other_writes_are_not(self):
        for method, path in [
            ("POST", "/result"),
            ("POST", "/run/r1/finish"),
            ("POST", "/run/claim-next"),
            ("POST", "/run/r1/claim"),
            ("POST", "/run/r1/children"),
            ("POST", "/attack"),
            ("PUT", "/result/r1"),
            ("DELETE", "/run/r1"),
        ]:
            with self.subTest(method=method, path=path):
                self.assertFalse(self._call(method, path))


if __name__ == "__main__":
    unittest.main()
