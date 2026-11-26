# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The results wording and a mounted ResultsTab preserve untrusted text."""

from types import SimpleNamespace

import pytest
from rich.text import Text
from textual.app import App, ComposeResult
from textual.widgets import Tree

from hackagent.interfaces.cli.config import CLIConfig
from hackagent.interfaces.results import campaign_line, goal_line, reply_lines
from hackagent.interfaces.tui.views.results import ResultsTab
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


def _result(content):
    return SimpleNamespace(
        goal=content,
        metadata={"response": content},
        evaluation_status="SUCCESSFUL_JAILBREAK",
        evaluation_notes=None,
    )


@pytest.mark.parametrize("content", STRINGS)
@pytest.mark.parametrize(
    "words",
    [
        lambda content: goal_line(_result(content)),
        lambda content: " ".join(reply_lines(_result(content), width=200)),
        lambda content: campaign_line(
            SimpleNamespace(id="c", name=content, agent_id="a", created_at=None),
            [],
            {},
            {"a": content},
        ),
    ],
)
def test_the_results_wording_keeps_user_text_literal(content, words):
    assert content in Text.from_markup(words(content)).plain


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
        # Read on a thread of its own; the goals are listed when opened.
        await app.workers.wait_for_complete()
        await pilot.pause()
        tree = tab.query_one(Tree)
        assert len(tree.root.children) == 1, str(tab.said)
        [campaign_node] = tree.root.children
        [attack_node] = campaign_node.children
        campaign_node.expand()
        attack_node.expand()
        await pilot.pause()
        [goal_node] = attack_node.children
        goal_node.expand()
        await pilot.pause()
        assert name in campaign_node.label.plain
        assert goal in goal_node.label.plain
        assert reply in " ".join(child.label.plain for child in goal_node.children)
