# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for the CLI banner."""

import unittest
from unittest.mock import patch

from hackagent.cli.banner import display_hackagent_splash


class TestDisplayHackagentSplash(unittest.TestCase):
    """Test display_hackagent_splash function."""

    def test_splash_does_not_raise(self):
        """Test that splash display does not raise exceptions."""
        # Capture console output
        from io import StringIO
        from rich.console import Console

        buffer = StringIO()
        console = Console(file=buffer, width=120)
        with patch("hackagent.cli.banner.Console", return_value=console):
            display_hackagent_splash()
        # Just ensure it ran without error


if __name__ == "__main__":
    unittest.main()
