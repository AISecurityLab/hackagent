# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Standalone app hosting :class:`ResultsTab`, for snapshot testing.

``ResultsTab`` deliberately does not fetch on mount (``BaseTab.on_show`` does
the lazy first refresh), so rendering it in isolation is network-free. Its
``create_backend()`` is overridden below to point at a throwaway temp-dir
database instead of ``LocalBackend()``'s default
``~/.local/share/hackagent/hackagent.db`` — without this, the snapshot
reflects whatever real attack-run history happens to exist on the machine
running the test, rather than the deterministic empty state.
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from textual.app import App, ComposeResult

from hackagent.cli.config import CLIConfig
from hackagent.cli.tui.theme import css_variables
from hackagent.cli.tui.views.results import ResultsTab
from hackagent.server.storage.local import LocalBackend


def _stub_config() -> CLIConfig:
    config = MagicMock(spec=CLIConfig)
    config.api_key = "test-api-key-12345"
    config.base_url = "https://api.test.hackagent.dev"
    return config


def _isolated_results_tab() -> ResultsTab:
    tab = ResultsTab(_stub_config())
    db_path = Path(tempfile.mkdtemp(prefix="hackagent-snapshot-")) / "results.db"
    tab.create_backend = lambda: LocalBackend(db_path=str(db_path))
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
