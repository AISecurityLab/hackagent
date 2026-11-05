# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tool selection verdicts, poisoned documents and metrics survive the runner."""

import json

from click.testing import CliRunner

from hackagent.catalog.taxonomy import AttackCategory, AttackTag, get_attack_taxonomy
from hackagent.client import catalog_entries
from hackagent.interfaces.cli.commands.campaign import campaign as campaign_command
from hackagent.interfaces.tui.views.campaign.schema import attack_fields
from hackagent.models import ModelResponse
from hackagent.orchestrator.campaign import run_campaign
from tests.fakes import in_memory_store

from .fakes import FakeBuilder, ScriptedModel, campaign, goals


def test_selection_results_and_traces_are_persisted_per_goal(tmp_path):
    values = campaign(
        attacks=[{"name": "toolhijacker", "parameters": {"max_attempts": 1}}],
        evaluation={"judges": []},
        execution={"output": {"directory": str(tmp_path)}},
    )
    target = ScriptedModel(
        ModelResponse(
            text="",
            tool_calls=[
                {
                    "type": "function",
                    "function": {"name": "task_helper", "arguments": "{}"},
                },
            ],
        )
    )
    store = in_memory_store()
    outcome = run_campaign(
        values,
        build=FakeBuilder({"target": target}),
        load=goals("Find a forecast", "Find a flight"),
        store=store,
    )
    assert outcome.attacks[0].error is None
    assert len(outcome.attacks[0].attempts) == 2
    assert len(target.requests) == 6
    assert all(a.verdict.success for a in outcome.attacks[0].attempts)
    records = store.list_results(page_size=50).items
    assert len(records) == 2
    assert all(record.evaluation_status == "SUCCESSFUL_JAILBREAK" for record in records)
    assert all(
        record.metadata["attack_metadata"]["evaluated_variants"] == 3
        for record in records
    )
    nodes = [trace for record in records for trace in store.list_traces(record.id)]
    artifacts = [t.content for t in nodes if t.content.get("node") == "artifact"]
    assert any(t["label"] == "poisoned_tool_document" for t in artifacts)
    assert any(t["label"] == "selection_metrics" for t in artifacts)
    results = next(path for path in outcome.outputs if path.name == "results.json")
    assert "selection_success_rate" in results.read_text()
    traces = next(path for path in outcome.outputs if path.name == "traces.jsonl")
    assert all(
        json.loads(line)["attack"] == "toolhijacker"
        for line in traces.read_text().splitlines()
    )


def test_cli_catalog_and_tui_expose_toolhijacker():
    taxonomy = get_attack_taxonomy("toolhijacker")
    assert taxonomy.category is AttackCategory.ADAPTIVE
    assert taxonomy.tags == (AttackTag.INDIRECT,)
    entry = next(e for e in catalog_entries() if e["attack_type"] == "toolhijacker")
    assert entry["label"] == "ToolHijacker"
    result = CliRunner().invoke(campaign_command, ["list"])
    assert result.exit_code == 0, result.output
    assert "toolhijacker" in result.output
    fields = attack_fields("toolhijacker")
    assert ("parameters", "top_k") in {f.path for f in fields}
    assert not {"attacker", "embedder"} & {f.path[-1] for f in fields}


def test_one_successful_paraphrase_does_not_mark_the_whole_goal_successful(tmp_path):
    values = campaign(
        attacks=[
            {
                "name": "toolhijacker",
                "parameters": {
                    "max_attempts": 1,
                    "paraphrases": ["Will it rain?"],
                },
            }
        ],
        evaluation={"judges": []},
        execution={"output": {"directory": str(tmp_path)}},
    )
    target = ScriptedModel(
        lambda messages: ModelResponse(
            text="",
            tool_calls=[{"name": "task_helper"}]
            if messages[-1]["content"] == "Weather"
            else [],
        )
    )
    store = in_memory_store()
    outcome = run_campaign(
        values,
        build=FakeBuilder({"target": target}),
        load=goals("Weather"),
        store=store,
    )
    [attempt] = outcome.attacks[0].attempts
    assert not attempt.verdict.success
    assert attempt.verdict.score == 5
    [record] = store.list_results(page_size=50).items
    assert record.evaluation_status == "FAILED_JAILBREAK"
    assert record.metadata["attack_metadata"]["selection_success_rate"] == 0.5
