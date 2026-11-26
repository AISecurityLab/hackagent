# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for RetryingTransport and RetryPolicy: requests the server dropped
are sent again, but only those that are safe to send twice, and only while
the time budget lasts."""

import socket
import ssl
import unittest

import httpx

from hackagent.storage._http.retry import (
    RetryingTransport,
    RetryPolicy,
    repeatable_api_call,
)

BASE = "https://api.example.com/api"


class _Server:
    """A mock transport that fails the first ``failures`` requests, raising
    ``error`` (an exception or a factory) or answering ``status``."""

    def __init__(self, failures, error=None, status=None, clock=None, takes_s=0.0):
        self.failures = failures
        self.error = error
        self.status = status
        self.requests = []
        self.clock = clock
        self.takes_s = takes_s

    def __call__(self, request):
        self.requests.append(request)
        if self.clock is not None:
            self.clock.now += self.takes_s
        if len(self.requests) <= self.failures:
            if self.error is not None:
                raise self.error()
            return httpx.Response(self.status)
        return httpx.Response(200, json={"ok": True})


class _Clock:
    """Time that only moves when the transport sleeps, or a try takes long."""

    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


def _dropped():
    return httpx.RemoteProtocolError("Server disconnected without sending a response.")


def _client(server, *, repeatable=repeatable_api_call, budget_s=60.0, clock=None):
    clock = clock or _Clock()
    if isinstance(server, _Server) and server.clock is None:
        server.clock = clock
    transport = RetryingTransport(
        httpx.MockTransport(server),
        repeatable=repeatable,
        budget_s=budget_s,
        sleep=clock.sleep,
        clock=clock,
    )
    return httpx.Client(base_url=BASE, transport=transport), clock.sleeps


class TestRetry(unittest.TestCase):
    def test_a_dropped_repeatable_request_is_sent_again(self):
        server = _Server(1, error=_dropped)
        client, sleeps = _client(server)

        response = client.post("/result/r1/trace", json={"sequence": 0})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(server.requests), 2)
        self.assertEqual(server.requests[1].content, server.requests[0].content)
        self.assertEqual(len(sleeps), 1)

    def test_a_reset_connection_is_retried(self):
        server = _Server(2, error=lambda: httpx.ReadError("Connection reset by peer"))
        client, _ = _client(server)

        self.assertEqual(client.patch("/result/r1", json={}).status_code, 200)
        self.assertEqual(len(server.requests), 3)

    def test_a_request_that_is_not_safe_to_repeat_is_sent_once(self):
        server = _Server(1, error=_dropped)
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
        server = _Server(1, error=lambda: httpx.ReadTimeout("timed out"))
        client, _ = _client(server)

        with self.assertRaises(httpx.ReadTimeout):
            client.get("/run/r1")
        self.assertEqual(len(server.requests), 1)

    def test_a_full_pool_is_not_waited_for_again(self):
        server = _Server(1, error=lambda: httpx.PoolTimeout("pool full"))
        client, _ = _client(server)

        with self.assertRaises(httpx.PoolTimeout):
            client.get("/run/r1")
        self.assertEqual(len(server.requests), 1)

    def test_it_gives_up_once_the_time_budget_is_spent(self):
        server = _Server(1000, error=_dropped)
        client, sleeps = _client(server, budget_s=30.0)

        with self.assertRaises(httpx.RemoteProtocolError):
            client.get("/run/r1")

        self.assertLessEqual(sum(sleeps), 30.0)
        self.assertEqual(len(server.requests), len(sleeps) + 1)
        self.assertGreater(len(sleeps), 3)

    def test_the_budget_counts_the_tries_too(self):
        # A try that hangs until the client's timeout uses up the budget: the
        # request is not sent again for another full timeout.
        clock = _Clock()
        server = _Server(1000, error=_dropped, clock=clock, takes_s=120.0)
        client, sleeps = _client(server, clock=clock, budget_s=90.0)

        with self.assertRaises(httpx.RemoteProtocolError):
            client.get("/run/r1")

        self.assertEqual(len(server.requests), 1)
        self.assertEqual(sleeps, [])

    def test_the_delays_grow(self):
        server = _Server(4, error=_dropped)
        client, sleeps = _client(server)

        client.get("/run/r1")

        self.assertEqual(sleeps, sorted(sleeps))
        self.assertLess(sleeps[0], sleeps[-1])

    def test_the_predicate_decides(self):
        server = _Server(1, error=_dropped)
        client, _ = _client(server, repeatable=lambda request: True)

        self.assertEqual(client.post("/result", json={}).status_code, 200)


class TestUnreachableServer(unittest.TestCase):
    """A server that refuses the connection may be restarting: a short retry.
    A certificate or a host name that fails never gets better: none."""

    def _connect_error(self, cause):
        def raise_it():
            try:
                raise cause
            except type(cause) as exc:
                raise httpx.ConnectError(str(exc)) from exc

        return raise_it

    def test_a_refused_connection_is_retried_briefly(self):
        server = _Server(1000, error=lambda: httpx.ConnectError("Connection refused"))
        client, sleeps = _client(server, budget_s=90.0)

        with self.assertRaises(httpx.ConnectError):
            client.get("/run/r1")

        self.assertGreater(len(sleeps), 1)
        self.assertLessEqual(sum(sleeps), 10.0)

    def test_a_refused_connection_that_comes_back_succeeds(self):
        server = _Server(2, error=lambda: httpx.ConnectError("Connection refused"))
        client, _ = _client(server)

        self.assertEqual(client.get("/run/r1").status_code, 200)

    def test_an_untrusted_certificate_is_not_retried(self):
        cause = ssl.SSLCertVerificationError("certificate verify failed")
        server = _Server(1000, error=self._connect_error(cause))
        client, sleeps = _client(server)

        with self.assertRaises(httpx.ConnectError):
            client.get("/run/r1")
        self.assertEqual((len(server.requests), sleeps), (1, []))

    def test_a_host_name_that_does_not_resolve_is_not_retried(self):
        cause = socket.gaierror(8, "nodename nor servname provided, or not known")
        server = _Server(1000, error=self._connect_error(cause))
        client, sleeps = _client(server)

        with self.assertRaises(httpx.ConnectError):
            client.get("/run/r1")
        self.assertEqual((len(server.requests), sleeps), (1, []))


class TestRepeatableApiCall(unittest.TestCase):
    def _call(self, method, path, **kwargs):
        return repeatable_api_call(httpx.Request(method, BASE + path), **kwargs)

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

    def test_creating_a_result_once_the_server_keeps_its_id(self):
        self.assertFalse(self._call("POST", "/result"))
        self.assertTrue(self._call("POST", "/result", result_ids_kept=True))
        self.assertTrue(self._call("POST", "/result/", result_ids_kept=True))
        # The SDK sends no client id through the run's own result route.
        self.assertFalse(self._call("POST", "/run/r1/result", result_ids_kept=True))

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
                self.assertFalse(self._call(method, path, result_ids_kept=False))


class TestPolicyInstall(unittest.TestCase):
    def test_every_transport_of_a_client_is_wrapped_with_one_policy(self):
        policy = RetryPolicy()
        proxy = httpx.HTTPTransport(proxy="http://proxy.example:3128")
        client = httpx.Client(mounts={"https://": proxy, "https://local.test": None})

        policy.install(client)

        self.assertIsInstance(client._transport, RetryingTransport)
        self.assertIs(client._transport.policy, policy)
        mounted = list(client._mounts.values())
        self.assertIn(None, mounted)
        wrapped = [t for t in mounted if t is not None]
        self.assertEqual(len(wrapped), 1)
        self.assertIs(wrapped[0].policy, policy)
        self.assertIs(wrapped[0]._inner, proxy)
        client.close()


if __name__ == "__main__":
    unittest.main()
