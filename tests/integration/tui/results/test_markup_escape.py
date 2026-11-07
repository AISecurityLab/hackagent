# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Production formatters and a mounted ResultsTab preserve untrusted text."""

from types import SimpleNamespace

import pytest
from rich.text import Text
from textual.app import App, ComposeResult
from textual.widgets import Tree

from hackagent.interfaces.cli.config import CLIConfig
from hackagent.interfaces.tui.views.results import ResultsTab
from hackagent.interfaces.tui.views.results.formatters.summaries import (
    _format_result_summary,
)
from hackagent.interfaces.tui.views.results.formatters.text import (
    _format_chat_message,
    _format_message_content,
)
from hackagent.storage.local import LocalBackend


STRINGS = [
    "Normal text",
    "[bold]markup[/bold]",
    "[/bold bright_cyan]",
    "[bold]unclosed",
    "Multiple [tags] and [/tags]",
    '{"key": "[brackets]"}',
    "[red]red[/red]",
    r"\[escaped\]",
    "[not/a/tag]",
    "[/]generic close",
    "list[0]",
    "[dim][/dim]",
]


@pytest.mark.parametrize("content", STRINGS)
@pytest.mark.parametrize(
    "formatter",
    [
        _format_message_content,
        lambda content: _format_chat_message({"role": "user", "content": content}),
        lambda content: _format_result_summary(
            SimpleNamespace(
                goal=content, metadata={}, evaluation_status="NOT_EVALUATED"
            ),
            1,
        ),
    ],
)
def test_real_formatters_preserve_literal_user_content(content, formatter):
    assert content in Text.from_markup(formatter(content)).plain


class ResultsApp(App):
    def __init__(self, config):
        super().__init__()
        self.config = config

    def compose(self) -> ComposeResult:
        yield ResultsTab(self.config)


@pytest.mark.asyncio
async def test_results_tree_reads_and_renders_markup_from_sqlite(tmp_path, monkeypatch):
    name = "[bold]campaign[/bold]"
    goal = "[/bold]goal[red]"
    reply = "[italic]literal reply[/italic]"
    monkeypatch.setattr(
        "hackagent.core.settings.DEFAULT_CONFIG_PATH", tmp_path / "no-config.json"
    )
    monkeypatch.delenv("HACKAGENT_API_KEY", raising=False)
    db_path = tmp_path / "results.db"
    monkeypatch.setenv("HACKAGENT_DB_PATH", str(db_path))
    store = LocalBackend(str(db_path))
    try:
        agent = store.create_or_update_agent(name, {"connection": {"type": "OPENAI"}})
        campaign = store.start_campaign(agent.id, {"campaign": {"name": name}})
        attack = store.create_attack(
            "baseline", agent.id, store.get_context().org_id, {}
        )
        run = store.create_run(
            attack.id, agent.id, {"expected_total_goals": 1}, campaign.id
        )
        result = store.create_result(run.id, goal, 0, {}, {"response": reply})
        store.update_result(result.id, evaluation_status="SUCCESSFUL_JAILBREAK")
    finally:
        store.close()
    app = ResultsApp(
        CLIConfig(config_file=str(tmp_path / "no-config.json"), backend="local")
    )
    async with app.run_test(size=(120, 40)) as pilot:
        tab = app.query_one(ResultsTab)
        tab.refresh_data()
        tree = tab.query_one(Tree)
        assert len(tree.root.children) == 1, str(
            tab.query_one("#results-hint").render()
        )
        [campaign_node] = tree.root.children
        [attack_node] = campaign_node.children
        [goal_node] = attack_node.children
        campaign_node.expand()
        attack_node.expand()
        goal_node.expand()
        await pilot.pause()
        assert name in campaign_node.label.plain
        assert goal in goal_node.label.plain
        assert reply in " ".join(child.label.plain for child in goal_node.children)
