# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for the CLI banner."""

import unittest

from hackagent.interfaces.cli.banner import display_hackagent_splash


class TestDisplayHackagentSplash(unittest.TestCase):
    """Test display_hackagent_splash function."""

    def test_the_splash_is_the_logo_and_the_tagline(self):
        """The logo and the tagline the TUI's welcome screen shows."""
        from io import StringIO

        from hackagent.interfaces.brand import BANNER, TAGLINE
        from hackagent.interfaces.palette import console

        buffer = StringIO()
        display_hackagent_splash(console(file=buffer, width=120))

        printed = buffer.getvalue()
        assert BANNER in printed
        assert TAGLINE in printed


if __name__ == "__main__":
    unittest.main()
