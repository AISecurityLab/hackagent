# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for Client and AuthenticatedClient classes."""

import unittest

import httpx

from hackagent.client import Client, AuthenticatedClient


class TestClientInitialization(unittest.TestCase):
    """Test Client initialization."""

    def test_client_initialization_minimal(self):
        """Test Client with minimal parameters."""
        client = Client(base_url="https://api.example.com")

        self.assertEqual(client._base_url, "https://api.example.com")
        self.assertEqual(client._cookies, {})
        self.assertEqual(client._headers, {})
        self.assertFalse(client.raise_on_unexpected_status)

    def test_client_initialization_with_options(self):
        """Test Client with all options."""
        timeout = httpx.Timeout(30.0)
        client = Client(
            base_url="https://api.example.com",
            cookies={"session": "abc123"},
            headers={"X-Custom": "value"},
            timeout=timeout,
            verify_ssl=False,
            follow_redirects=True,
            raise_on_unexpected_status=True,
        )

        self.assertEqual(client._base_url, "https://api.example.com")
        self.assertEqual(client._cookies, {"session": "abc123"})
        self.assertEqual(client._headers, {"X-Custom": "value"})
        self.assertEqual(client._timeout, timeout)
        self.assertFalse(client._verify_ssl)
        self.assertTrue(client._follow_redirects)
        self.assertTrue(client.raise_on_unexpected_status)


class TestClientWithMethods(unittest.TestCase):
    """Test Client with_* methods."""

    def test_with_headers(self):
        """Test with_headers returns new client with merged headers."""
        client = Client(
            base_url="https://api.example.com",
            headers={"X-Original": "original"},
        )

        new_client = client.with_headers({"X-New": "new"})

        self.assertEqual(new_client._headers["X-Original"], "original")
        self.assertEqual(new_client._headers["X-New"], "new")

    def test_with_cookies(self):
        """Test with_cookies returns new client with merged cookies."""
        client = Client(
            base_url="https://api.example.com",
            cookies={"original": "value1"},
        )

        new_client = client.with_cookies({"new": "value2"})

        self.assertEqual(new_client._cookies["original"], "value1")
        self.assertEqual(new_client._cookies["new"], "value2")

    def test_with_timeout(self):
        """Test with_timeout returns new client with new timeout."""
        client = Client(base_url="https://api.example.com")
        timeout = httpx.Timeout(60.0)

        new_client = client.with_timeout(timeout)

        self.assertEqual(new_client._timeout, timeout)


class TestClientHttpxClient(unittest.TestCase):
    """Test Client httpx client management."""

    def test_get_httpx_client_creates_client(self):
        """Test get_httpx_client creates a new client if none exists."""
        client = Client(base_url="https://api.example.com")

        httpx_client = client.get_httpx_client()

        self.assertIsNotNone(httpx_client)
        self.assertIsInstance(httpx_client, httpx.Client)

    def test_get_httpx_client_returns_same_instance(self):
        """Test get_httpx_client returns the same instance on subsequent calls."""
        client = Client(base_url="https://api.example.com")

        httpx_client1 = client.get_httpx_client()
        httpx_client2 = client.get_httpx_client()

        self.assertIs(httpx_client1, httpx_client2)

    def test_set_httpx_client(self):
        """Test set_httpx_client sets custom client."""
        client = Client(base_url="https://api.example.com")
        custom_httpx = httpx.Client(base_url="https://custom.example.com")

        result = client.set_httpx_client(custom_httpx)

        self.assertIs(result, client)
        self.assertIs(client.get_httpx_client(), custom_httpx)

        custom_httpx.close()


class TestClientContextManager(unittest.TestCase):
    """Test Client context manager."""

    def test_context_manager(self):
        """Test Client as context manager."""
        with Client(base_url="https://api.example.com") as client:
            self.assertIsNotNone(client.get_httpx_client())


class TestAuthenticatedClientInitialization(unittest.TestCase):
    """Test AuthenticatedClient initialization."""

    def test_authenticated_client_initialization(self):
        """Test AuthenticatedClient with token."""
        client = AuthenticatedClient(
            base_url="https://api.example.com",
            token="my-secret-token",
        )

        self.assertEqual(client._base_url, "https://api.example.com")
        self.assertEqual(client.token, "my-secret-token")
        self.assertEqual(client.prefix, "Bearer")
        self.assertEqual(client.auth_header_name, "Authorization")

    def test_authenticated_client_custom_prefix(self):
        """Test AuthenticatedClient with custom prefix."""
        client = AuthenticatedClient(
            base_url="https://api.example.com",
            token="my-token",
            prefix="Token",
        )

        self.assertEqual(client.prefix, "Token")

    def test_authenticated_client_custom_auth_header(self):
        """Test AuthenticatedClient with custom auth header name."""
        client = AuthenticatedClient(
            base_url="https://api.example.com",
            token="my-token",
            auth_header_name="X-API-Key",
        )

        self.assertEqual(client.auth_header_name, "X-API-Key")


class TestAuthenticatedClientWithMethods(unittest.TestCase):
    """Test AuthenticatedClient with_* methods."""

    def test_with_headers(self):
        """Test with_headers returns new client with merged headers."""
        client = AuthenticatedClient(
            base_url="https://api.example.com",
            token="my-token",
            headers={"X-Original": "original"},
        )

        new_client = client.with_headers({"X-New": "new"})

        self.assertIsInstance(new_client, AuthenticatedClient)
        self.assertEqual(new_client._headers["X-Original"], "original")
        self.assertEqual(new_client._headers["X-New"], "new")

    def test_with_cookies(self):
        """Test with_cookies returns new client with merged cookies."""
        client = AuthenticatedClient(
            base_url="https://api.example.com",
            token="my-token",
            cookies={"original": "value1"},
        )

        new_client = client.with_cookies({"new": "value2"})

        self.assertIsInstance(new_client, AuthenticatedClient)
        self.assertEqual(new_client._cookies["original"], "value1")
        self.assertEqual(new_client._cookies["new"], "value2")

    def test_with_timeout(self):
        """Test with_timeout returns new client with new timeout."""
        client = AuthenticatedClient(
            base_url="https://api.example.com",
            token="my-token",
        )
        timeout = httpx.Timeout(60.0)

        new_client = client.with_timeout(timeout)

        self.assertIsInstance(new_client, AuthenticatedClient)
        self.assertEqual(new_client._timeout, timeout)


class TestAuthenticatedClientHttpxClient(unittest.TestCase):
    """Test AuthenticatedClient httpx client management."""

    def test_get_httpx_client_adds_auth_header(self):
        """Test get_httpx_client adds Authorization header."""
        client = AuthenticatedClient(
            base_url="https://api.example.com",
            token="my-secret-token",
        )

        client.get_httpx_client()

        # The headers should include the Authorization header
        self.assertIn("Authorization", client._headers)
        self.assertEqual(client._headers["Authorization"], "Bearer my-secret-token")

    def test_get_httpx_client_no_prefix(self):
        """Test get_httpx_client with empty prefix."""
        client = AuthenticatedClient(
            base_url="https://api.example.com",
            token="my-token",
            prefix="",
        )

        client.get_httpx_client()

        # The token should be used without prefix
        self.assertEqual(client._headers["Authorization"], "my-token")

    def test_set_httpx_client(self):
        """Test set_httpx_client sets custom client."""
        client = AuthenticatedClient(
            base_url="https://api.example.com",
            token="my-token",
        )
        custom_httpx = httpx.Client(base_url="https://custom.example.com")

        result = client.set_httpx_client(custom_httpx)

        self.assertIs(result, client)
        self.assertIs(client.get_httpx_client(), custom_httpx)

        custom_httpx.close()


class TestAuthenticatedClientContextManager(unittest.TestCase):
    """Test AuthenticatedClient context manager."""

    def test_context_manager(self):
        """Test AuthenticatedClient as context manager."""
        with AuthenticatedClient(
            base_url="https://api.example.com",
            token="my-token",
        ) as client:
            self.assertIsNotNone(client.get_httpx_client())


class TestClientAsyncClient(unittest.TestCase):
    """Test Client async client management."""

    def test_get_async_httpx_client_creates_client(self):
        """Test get_async_httpx_client creates a new async client if none exists."""
        client = Client(base_url="https://api.example.com")

        async_client = client.get_async_httpx_client()

        self.assertIsNotNone(async_client)
        self.assertIsInstance(async_client, httpx.AsyncClient)

    def test_get_async_httpx_client_returns_same_instance(self):
        """Test get_async_httpx_client returns the same instance on subsequent calls."""
        client = Client(base_url="https://api.example.com")

        async_client1 = client.get_async_httpx_client()
        async_client2 = client.get_async_httpx_client()

        self.assertIs(async_client1, async_client2)

    def test_set_async_httpx_client(self):
        """Test set_async_httpx_client sets custom async client."""
        client = Client(base_url="https://api.example.com")
        custom_async = httpx.AsyncClient(base_url="https://custom.example.com")

        result = client.set_async_httpx_client(custom_async)

        self.assertIs(result, client)
        self.assertIs(client.get_async_httpx_client(), custom_async)


class TestAuthenticatedClientAsyncClient(unittest.TestCase):
    """Test AuthenticatedClient async client management."""

    def test_get_async_httpx_client_adds_auth_header(self):
        """Test get_async_httpx_client adds Authorization header."""
        client = AuthenticatedClient(
            base_url="https://api.example.com",
            token="my-secret-token",
        )

        client.get_async_httpx_client()

        # The headers should include the Authorization header
        self.assertIn("Authorization", client._headers)
        self.assertEqual(client._headers["Authorization"], "Bearer my-secret-token")

    def test_set_async_httpx_client(self):
        """Test set_async_httpx_client sets custom async client."""
        client = AuthenticatedClient(
            base_url="https://api.example.com",
            token="my-token",
        )
        custom_async = httpx.AsyncClient(base_url="https://custom.example.com")

        result = client.set_async_httpx_client(custom_async)

        self.assertIsInstance(result, AuthenticatedClient)
        self.assertIs(client.get_async_httpx_client(), custom_async)


class TestClientWithMethodsUpdatesExistingClients(unittest.TestCase):
    """Test that with_* methods update existing httpx clients."""

    def test_with_headers_updates_existing_client(self):
        """Test with_headers updates existing httpx client headers."""
        client = Client(base_url="https://api.example.com")
        # Create the httpx client first
        httpx_client = client.get_httpx_client()

        client.with_headers({"X-New": "new"})

        # The original httpx client should have been updated
        self.assertIn("X-New", httpx_client.headers)

    def test_with_cookies_updates_existing_client(self):
        """Test with_cookies updates existing httpx client cookies."""
        client = Client(base_url="https://api.example.com")
        # Create the httpx client first
        httpx_client = client.get_httpx_client()

        client.with_cookies({"new_cookie": "value"})

        # The original httpx client should have been updated
        self.assertIn("new_cookie", httpx_client.cookies)

    def test_with_timeout_updates_existing_client(self):
        """Test with_timeout updates existing httpx client timeout."""
        client = Client(base_url="https://api.example.com")
        # Create the httpx client first
        httpx_client = client.get_httpx_client()
        timeout = httpx.Timeout(120.0)

        client.with_timeout(timeout)

        # The original httpx client should have been updated
        self.assertEqual(httpx_client.timeout, timeout)


if __name__ == "__main__":
    unittest.main()
