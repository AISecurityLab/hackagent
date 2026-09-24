# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Remote mode: forwarding the SPA's API calls to the hosted API.

The point of keeping a proxy hop at all is that the API key lives in this
process and not in the browser, so the tests that matter here are the ones
about which headers cross which boundary.
"""

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import httpx

from hackagent import HackAgent, Settings
from hackagent.interfaces.web import _static, create_app


def _session(api_key: str = "", base_url: str = "https://api.example.test"):
    return HackAgent(
        Settings.resolve(
            api_key=api_key,
            base_url=base_url,
            db_path=":memory:",
            env={},
            config_path="/nonexistent",
        )
    )


class _StubResponse:
    def __init__(self, status_code=200, content=b"{}", headers=None):
        self.status_code = status_code
        self.content = content
        self.headers = headers or {"Content-Type": "application/json"}


class TestRemoteProxy(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        bundle = Path(self._tmp.name) / "static"
        bundle.mkdir()
        (bundle / "index.html").write_text("<html>index</html>")
        self._real_static_dir = _static.static_dir
        _static.static_dir = lambda: bundle

        self.app = create_app(_session("secret-key", "https://api.example.test"))
        self.client = self.app.test_client()

    def tearDown(self) -> None:
        _static.static_dir = self._real_static_dir
        self._tmp.cleanup()

    def _capture(self, response=None):
        """Patch the proxy's HTTP client and return the recorded call kwargs."""
        recorded = {}

        # Patched onto the class, so the bound instance arrives as `self`.
        def _request(_self, method, url, **kwargs):
            recorded["method"] = method
            recorded["url"] = url
            recorded.update(kwargs)
            return response or _StubResponse()

        return recorded, patch.object(httpx.Client, "request", _request)

    def test_request_is_forwarded_to_the_configured_base_url(self):
        recorded, patched = self._capture()
        with patched:
            self.client.get("/api/proxy/run?page=2")
        self.assertEqual(recorded["url"], "https://api.example.test/run")
        self.assertEqual(recorded["method"], "GET")
        self.assertEqual(recorded["params"]["page"], "2")

    def test_api_key_is_attached_server_side(self):
        recorded, patched = self._capture()
        with patched:
            self.client.get("/api/proxy/user/me")
        self.assertEqual(recorded["headers"]["Authorization"], "Bearer secret-key")

    def test_browser_supplied_authorization_is_replaced_not_forwarded(self):
        # The SPA runs with auth disabled and sends a placeholder token; it must
        # never be able to influence what this process authenticates as.
        recorded, patched = self._capture()
        with patched:
            self.client.get(
                "/api/proxy/user/me",
                headers={"Authorization": "Bearer mock-dev-token"},
            )
        self.assertEqual(recorded["headers"]["Authorization"], "Bearer secret-key")

    def test_hop_by_hop_headers_are_stripped(self):
        recorded, patched = self._capture()
        with patched:
            self.client.get("/api/proxy/run")
        lowered = {k.lower() for k in recorded["headers"]}
        self.assertNotIn("host", lowered)
        self.assertNotIn("content-length", lowered)

    def test_request_body_is_forwarded_for_writes(self):
        recorded, patched = self._capture()
        with patched:
            self.client.post("/api/proxy/attack", json={"type": "tap"})
        self.assertIn(b"tap", recorded["content"])

    def test_upstream_status_and_body_are_passed_through(self):
        recorded, patched = self._capture(
            _StubResponse(status_code=403, content=b'{"detail":"nope"}')
        )
        with patched:
            response = self.client.get("/api/proxy/run")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["detail"], "nope")

    def test_no_content_response_has_no_body(self):
        recorded, patched = self._capture(_StubResponse(status_code=204, content=b""))
        with patched:
            response = self.client.delete("/api/proxy/run/abc")
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.data, b"")

    def test_upstream_failure_becomes_502_rather_than_a_traceback(self):
        def _boom(_self, method, url, **kwargs):
            raise httpx.ConnectError("connection refused")

        with patch.object(httpx.Client, "request", _boom):
            response = self.client.get("/api/proxy/run")
        self.assertEqual(response.status_code, 502)
        self.assertIn("Proxy error", response.get_json()["detail"])

    def test_remote_mode_still_serves_the_spa(self):
        self.assertIn(b"index", self.client.get("/").data)

    def test_healthz_reports_remote_mode_and_target(self):
        payload = self.client.get("/healthz").get_json()
        self.assertEqual(payload["mode"], "remote")
        self.assertEqual(
            self.app.config["HACKAGENT_TARGET"], "https://api.example.test"
        )

    def test_config_json_never_contains_the_api_key(self):
        body = self.client.get("/config.json").data
        self.assertNotIn(b"secret-key", body)


class TestCreateAppValidation(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self._real_static_dir = _static.static_dir
        # "No bundle" now means neither the package tree nor an installed
        # hackagent-webui has one. A None entry makes the import fail, which
        # matters because the real distribution may be installed here.
        self._saved_module = sys.modules.get("hackagent_webui")
        sys.modules["hackagent_webui"] = None

    def tearDown(self) -> None:
        _static.static_dir = self._real_static_dir
        if self._saved_module is not None:
            sys.modules["hackagent_webui"] = self._saved_module
        else:
            sys.modules.pop("hackagent_webui", None)
        self._tmp.cleanup()

    def test_missing_bundle_raises_with_install_instructions(self):
        from hackagent.interfaces.web import MissingBundleError

        _static.static_dir = lambda: Path(self._tmp.name) / "absent"
        with self.assertRaises(MissingBundleError) as ctx:
            create_app(_session("k"))
        message = str(ctx.exception)
        self.assertIn("hackagent[web]", message)
        self.assertIn("build_webui", message)

    def test_offline_mode_requires_a_backend(self):
        bundle = Path(self._tmp.name) / "static"
        bundle.mkdir()
        (bundle / "index.html").write_text("x")
        _static.static_dir = lambda: bundle
        with self.assertRaises(ValueError):
            create_app(None)


if __name__ == "__main__":
    unittest.main()
