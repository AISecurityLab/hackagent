# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Standalone app hosting :class:`AttacksTab`, for snapshot testing.

``pytest-textual-snapshot`` runs this module as a script and snapshots the
module-level ``app``, so it must be importable without any network access or
API credentials.
"""

from unittest.mock import MagicMock

from textual.app import App, ComposeResult

from hackagent.cli.config import CLIConfig
from hackagent.cli.tui.views.attacks import AttacksTab


def _stub_config() -> CLIConfig:
    config = MagicMock(spec=CLIConfig)
    config.api_key = "test-api-key-12345"
    config.base_url = "https://api.test.hackagent.dev"
    return config


class AttacksTabApp(App):
    """Minimal host app rendering only the Attacks tab."""

    def compose(self) -> ComposeResult:
        yield AttacksTab(_stub_config())


app = AttacksTabApp()

if __name__ == "__main__":
    app.run()
