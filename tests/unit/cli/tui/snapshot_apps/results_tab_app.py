# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Standalone app hosting :class:`ResultsTab`, for snapshot testing.

``ResultsTab`` deliberately does not fetch on mount (``BaseTab.on_show`` does
the lazy first refresh), so rendering it in isolation is network-free.
"""

from unittest.mock import MagicMock

from textual.app import App, ComposeResult

from hackagent.cli.config import CLIConfig
from hackagent.cli.tui.theme import css_variables
from hackagent.cli.tui.views.results import ResultsTab


def _stub_config() -> CLIConfig:
    config = MagicMock(spec=CLIConfig)
    config.api_key = "test-api-key-12345"
    config.base_url = "https://api.test.hackagent.dev"
    return config


class ResultsTabApp(App):
    """Minimal host app rendering only the Results tab."""

    def get_css_variables(self) -> dict[str, str]:
        """Mirror ``HackAgentTUI``'s brand palette so ``$brand-*`` resolve."""
        return {**super().get_css_variables(), **css_variables()}

    def compose(self) -> ComposeResult:
        yield ResultsTab(_stub_config())


app = ResultsTabApp()

if __name__ == "__main__":
    app.run()
