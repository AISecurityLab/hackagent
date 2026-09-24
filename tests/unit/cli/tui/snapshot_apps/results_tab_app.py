# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Standalone app hosting :class:`ResultsTab`, for snapshot testing.

``ResultsTab`` deliberately does not fetch on mount (``BaseTab.on_show`` does
the lazy first refresh), so rendering it in isolation is network-free. Its
``client()`` is overridden below to a throwaway local database. The stub
config carries an API key, and without the override a refresh would open
the remote API.
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from textual.app import App, ComposeResult

from hackagent import HackAgent, Settings
from hackagent.interfaces.cli.config import CLIConfig
from hackagent.interfaces.tui.theme import css_variables
from hackagent.interfaces.tui.views.results import ResultsTab
from hackagent.storage.local import LocalBackend


def _stub_config() -> CLIConfig:
    config = MagicMock(spec=CLIConfig)
    config.api_key = "test-api-key-12345"
    config.base_url = "https://api.test.hackagent.dev"
    return config


def _isolated_results_tab() -> ResultsTab:
    tab = ResultsTab(_stub_config())
    db_path = str(Path(tempfile.mkdtemp(prefix="hackagent-snapshot-")) / "results.db")
    store = LocalBackend(db_path=db_path)
    session = HackAgent(
        Settings.resolve(api_key="", db_path=db_path, env={}, config_path="/nonexistent"),
        backend=store,
    )
    tab.client = lambda: session
    return tab


class ResultsTabApp(App):
    """Minimal host app rendering only the Results tab."""

    def get_css_variables(self) -> dict[str, str]:
        """Mirror ``HackAgentTUI``'s brand palette so ``$brand-*`` resolve."""
        return {**super().get_css_variables(), **css_variables()}

    def compose(self) -> ComposeResult:
        yield _isolated_results_tab()


app = ResultsTabApp()

if __name__ == "__main__":
    app.run()
