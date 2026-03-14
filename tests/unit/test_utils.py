# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for hackagent/utils.py — resolve_agent_type, resolve_api_token, display."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from hackagent.router.types import AgentTypeEnum
from hackagent.utils import (
    _load_api_key_from_config,
    display_hackagent_splash,
    resolve_agent_type,
    resolve_api_token,
)


class TestResolveAgentType(unittest.TestCase):
    """Test resolve_agent_type function."""

    def test_enum_input_passthrough(self):
        """Test that enum input is returned as-is."""
        self.assertEqual(
            resolve_agent_type(AgentTypeEnum.LITELLM), AgentTypeEnum.LITELLM
        )

    def test_string_uppercase(self):
        """Test uppercase string input."""
        self.assertEqual(resolve_agent_type("LITELLM"), AgentTypeEnum.LITELLM)

    def test_string_lowercase(self):
        """Test lowercase string input."""
        self.assertEqual(resolve_agent_type("litellm"), AgentTypeEnum.LITELLM)

    def test_string_with_hyphens(self):
        """Test string with hyphens (e.g., google-adk)."""
        self.assertEqual(resolve_agent_type("google-adk"), AgentTypeEnum.GOOGLE_ADK)

    def test_unknown_string_fallback(self):
        """Test unknown string falls back to UNKNOWN."""
        self.assertEqual(resolve_agent_type("nonexistent_type"), AgentTypeEnum.UNKNOWN)

    def test_invalid_type_fallback(self):
        """Test non-string/non-enum type falls back to UNKNOWN."""
        self.assertEqual(resolve_agent_type(42), AgentTypeEnum.UNKNOWN)
        self.assertEqual(resolve_agent_type(None), AgentTypeEnum.UNKNOWN)
        self.assertEqual(resolve_agent_type([]), AgentTypeEnum.UNKNOWN)

    def test_unknown_enum(self):
        """Test UNKNOWN enum passthrough."""
        self.assertEqual(
            resolve_agent_type(AgentTypeEnum.UNKNOWN), AgentTypeEnum.UNKNOWN
        )


class TestResolveApiToken(unittest.TestCase):
    """Test resolve_api_token function."""

    def test_direct_parameter_wins(self):
        """Test direct parameter takes highest priority."""
        result = resolve_api_token(direct_api_key_param="direct-key")
        self.assertEqual(result, "direct-key")

    @patch.dict(os.environ, {"HACKAGENT_API_KEY": ""})
    def test_config_file_fallback(self):
        """Test config file is used when no direct parameter."""
        config = {"api_key": "config-key"}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config, f)
            path = f.name
        try:
            result = resolve_api_token(direct_api_key_param=None, config_file_path=path)
            self.assertEqual(result, "config-key")
        finally:
            Path(path).unlink()

    @patch.dict(os.environ, {"HACKAGENT_API_KEY": ""})
    def test_no_sources_raises_value_error(self):
        """Test ValueError when no token source available."""
        with self.assertRaises(ValueError) as ctx:
            resolve_api_token(
                direct_api_key_param=None,
                config_file_path="/nonexistent/config.json",
            )
        self.assertIn("API token not found", str(ctx.exception))

    def test_direct_parameter_over_config(self):
        """Test direct parameter wins over config file."""
        config = {"api_key": "config-key"}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config, f)
            path = f.name
        try:
            result = resolve_api_token(
                direct_api_key_param="direct-key", config_file_path=path
            )
            self.assertEqual(result, "direct-key")
        finally:
            Path(path).unlink()


class TestLoadApiKeyFromConfig(unittest.TestCase):
    """Test _load_api_key_from_config function."""

    def test_valid_json_config(self):
        """Test loading from valid JSON config."""
        config = {"api_key": "json-key"}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config, f)
            path = f.name
        try:
            result = _load_api_key_from_config(path)
            self.assertEqual(result, "json-key")
        finally:
            Path(path).unlink()

    def test_missing_file_returns_none(self):
        """Test non-existent file returns None."""
        result = _load_api_key_from_config("/nonexistent/file.json")
        self.assertIsNone(result)

    def test_config_without_api_key_returns_none(self):
        """Test config file without api_key returns None."""
        config = {"other": "value"}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config, f)
            path = f.name
        try:
            result = _load_api_key_from_config(path)
            self.assertIsNone(result)
        finally:
            Path(path).unlink()

    def test_invalid_json_returns_none(self):
        """Test invalid JSON returns None."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("not valid json!")
            path = f.name
        try:
            result = _load_api_key_from_config(path)
            self.assertIsNone(result)
        finally:
            Path(path).unlink()

    def test_default_config_path(self):
        """Test default config path is used when none specified."""
        config = {"api_key": "home-key"}
        with tempfile.TemporaryDirectory() as tmp:
            with patch("pathlib.Path.home", return_value=Path(tmp)):
                config_dir = Path(tmp) / ".config" / "hackagent"
                config_dir.mkdir(parents=True)
                config_file = config_dir / "config.json"
                with open(config_file, "w") as f:
                    json.dump(config, f)

                result = _load_api_key_from_config()
                self.assertEqual(result, "home-key")


class TestDisplayHackagentSplash(unittest.TestCase):
    """Test display_hackagent_splash function."""

    def test_splash_does_not_raise(self):
        """Test that splash display does not raise exceptions."""
        # Capture console output
        from io import StringIO
        from rich.console import Console

        buffer = StringIO()
        console = Console(file=buffer, width=120)
        with patch("hackagent.utils.Console", return_value=console):
            display_hackagent_splash()
        # Just ensure it ran without error


if __name__ == "__main__":
    unittest.main()
