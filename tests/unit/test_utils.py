# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for hackagent/utils.py — resolve_agent_type, resolve_api_token, display."""

import unittest
from unittest.mock import patch

from hackagent.router.types import AgentTypeEnum
from hackagent.utils import (
    display_hackagent_splash,
    resolve_agent_type,
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
