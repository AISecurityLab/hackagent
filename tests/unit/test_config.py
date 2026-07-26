# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for ``hackagent/config.py`` Ollama endpoint resolution."""

import os
import unittest
from unittest.mock import patch

from hackagent.config import resolve_ollama_base_url


class TestResolveOllamaBaseUrl(unittest.TestCase):
    def _resolve(self, env):
        with patch.dict(os.environ, env, clear=True):
            return resolve_ollama_base_url()

    def test_defaults_to_localhost_11434(self):
        self.assertEqual(self._resolve({}), "http://localhost:11434")

    def test_ollama_base_url_wins(self):
        self.assertEqual(
            self._resolve({"OLLAMA_BASE_URL": "http://ollama:11435"}),
            "http://ollama:11435",
        )

    def test_ollama_api_base_is_used(self):
        self.assertEqual(
            self._resolve({"OLLAMA_API_BASE": "http://localhost:11500"}),
            "http://localhost:11500",
        )

    def test_ollama_host_without_scheme(self):
        self.assertEqual(
            self._resolve({"OLLAMA_HOST": "127.0.0.1:11435"}),
            "http://127.0.0.1:11435",
        )

    def test_ollama_host_port_only(self):
        self.assertEqual(
            self._resolve({"OLLAMA_HOST": ":11435"}), "http://localhost:11435"
        )

    def test_ollama_host_without_port_gets_default_port(self):
        self.assertEqual(
            self._resolve({"OLLAMA_HOST": "my-ollama"}), "http://my-ollama:11434"
        )

    def test_trailing_slash_is_stripped(self):
        self.assertEqual(
            self._resolve({"OLLAMA_BASE_URL": "http://localhost:11435/"}),
            "http://localhost:11435",
        )

    def test_blank_env_var_falls_through(self):
        self.assertEqual(
            self._resolve({"OLLAMA_BASE_URL": "  ", "OLLAMA_HOST": "host:11499"}),
            "http://host:11499",
        )

    def test_https_scheme_keeps_implicit_port(self):
        self.assertEqual(
            self._resolve({"OLLAMA_HOST": "https://remote.example.com"}),
            "https://remote.example.com",
        )


if __name__ == "__main__":
    unittest.main()
