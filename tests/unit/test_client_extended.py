# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Extended tests for Client and AuthenticatedClient — covering async and edge cases."""

import asyncio
import unittest

import httpx

from hackagent.client import AuthenticatedClient, Client


class TestClientSSLAndRedirects(unittest.TestCase):
    """Test Client SSL and redirect settings."""

    def test_verify_ssl_default_true(self):
        """Test verify_ssl defaults to True."""
        client = Client(base_url="https://api.example.com")
        self.assertTrue(client._verify_ssl)

    def test_verify_ssl_false(self):
        """Test verify_ssl can be set to False."""
        client = Client(base_url="https://api.example.com", verify_ssl=False)
        self.assertFalse(client._verify_ssl)

    def test_follow_redirects_default_false(self):
        """Test follow_redirects defaults to False."""
        client = Client(base_url="https://api.example.com")
        self.assertFalse(client._follow_redirects)

    def test_follow_redirects_true(self):
        """Test follow_redirects can be set to True."""
        client = Client(base_url="https://api.example.com", follow_redirects=True)
        self.assertTrue(client._follow_redirects)


class TestClientHttpxArgs(unittest.TestCase):
    """Test Client with custom httpx_args."""

    def test_httpx_args_passed_to_client(self):
        """Test custom httpx_args are passed to underlying client."""
        client = Client(
            base_url="https://api.example.com",
            httpx_args={"http2": False},
        )
        httpx_client = client.get_httpx_client()
        self.assertIsNotNone(httpx_client)


class TestClientAsyncContextManager(unittest.TestCase):
    """Test Client async context manager."""

    def test_async_context_manager(self):
        """Test Client as async context manager."""

        async def _test():
            async with Client(base_url="https://api.example.com") as client:
                self.assertIsNotNone(client.get_async_httpx_client())

        asyncio.run(_test())


class TestAuthenticatedClientAsyncContextManager(unittest.TestCase):
    """Test AuthenticatedClient async context manager."""

    def test_async_context_manager(self):
        """Test AuthenticatedClient as async context manager."""

        async def _test():
            async with AuthenticatedClient(
                base_url="https://api.example.com",
                token="test-token",
            ) as client:
                self.assertIsNotNone(client.get_async_httpx_client())

        asyncio.run(_test())

    def test_async_client_adds_auth_header(self):
        """Test get_async_httpx_client adds auth header."""
        client = AuthenticatedClient(
            base_url="https://api.example.com",
            token="my-secret",
        )
        client.get_async_httpx_client()
        self.assertIn("Authorization", client._headers)
        self.assertEqual(client._headers["Authorization"], "Bearer my-secret")

    def test_async_client_no_prefix(self):
        """Test get_async_httpx_client with empty prefix."""
        client = AuthenticatedClient(
            base_url="https://api.example.com",
            token="raw-token",
            prefix="",
        )
        client.get_async_httpx_client()
        self.assertEqual(client._headers["Authorization"], "raw-token")


class TestClientWithMethodsUpdateAsyncClients(unittest.TestCase):
    """Test that with_* methods also update async clients."""

    def test_with_headers_updates_async_client(self):
        """Test with_headers updates existing async client headers."""
        client = Client(base_url="https://api.example.com")
        async_client = client.get_async_httpx_client()

        client.with_headers({"X-Custom": "value"})
        self.assertIn("x-custom", async_client.headers)

    def test_with_cookies_updates_async_client(self):
        """Test with_cookies updates existing async client cookies."""
        client = Client(base_url="https://api.example.com")
        async_client = client.get_async_httpx_client()

        client.with_cookies({"session": "abc"})
        self.assertIn("session", async_client.cookies)

    def test_with_timeout_updates_async_client(self):
        """Test with_timeout updates existing async client timeout."""
        client = Client(base_url="https://api.example.com")
        async_client = client.get_async_httpx_client()

        timeout = httpx.Timeout(60.0)
        client.with_timeout(timeout)
        self.assertEqual(async_client.timeout, timeout)


class TestAuthenticatedClientWithMethodsUpdateAsyncClients(unittest.TestCase):
    """Test AuthenticatedClient with_* methods update async clients."""

    def test_with_headers_updates_async_client(self):
        """Test with_headers updates existing async client."""
        client = AuthenticatedClient(
            base_url="https://api.example.com",
            token="token",
        )
        async_client = client.get_async_httpx_client()

        client.with_headers({"X-Custom": "value"})
        self.assertIn("x-custom", async_client.headers)

    def test_with_cookies_updates_async_client(self):
        """Test with_cookies updates existing async client."""
        client = AuthenticatedClient(
            base_url="https://api.example.com",
            token="token",
        )
        async_client = client.get_async_httpx_client()

        client.with_cookies({"session": "abc"})
        self.assertIn("session", async_client.cookies)

    def test_with_timeout_updates_async_client(self):
        """Test with_timeout updates existing async client."""
        client = AuthenticatedClient(
            base_url="https://api.example.com",
            token="token",
        )
        async_client = client.get_async_httpx_client()

        timeout = httpx.Timeout(120.0)
        client.with_timeout(timeout)
        self.assertEqual(async_client.timeout, timeout)


class TestClientExitCleanup(unittest.TestCase):
    """Test that context manager __exit__ properly closes."""

    def test_sync_exit(self):
        """Test sync context manager exit."""
        with Client(base_url="https://api.example.com") as client:
            httpx_client = client.get_httpx_client()
            self.assertIsNotNone(httpx_client)
        # After exiting, client should be closed (no assertion needed if no error)

    def test_auth_sync_exit(self):
        """Test authenticated sync context manager exit."""
        with AuthenticatedClient(
            base_url="https://api.example.com", token="test"
        ) as client:
            httpx_client = client.get_httpx_client()
            self.assertIsNotNone(httpx_client)


if __name__ == "__main__":
    unittest.main()
