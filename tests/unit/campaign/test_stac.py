# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The STAC path from campaign resolution through persisted trace and verdict."""

import json

import pytest
from pathlib import Path

from hackagent.attacks.techniques.multi_turn.stac.environment import builtin_chain
from hackagent.client import catalog_entries
from hackagent.interfaces.tui.views.results.formatters.traces import _format_trace_block
from hackagent.models import ModelResponse
from hackagent.orchestrator.campaign import load_campaign, run_campaign
from hackagent.orchestrator.campaign.results import trace_payload
from hackagent.orchestrator.campaign.spec import OutputSpec
from tests.fakes import RecordingStore

from .fakes import FakeBuilder, ScriptedModel, campaign, goals


def test_stac_campaign_persists_execution_verdict_and_tool_timeline(tmp_path):
    chain = builtin_chain("data_export")

    def reply(messages):
        if messages[-1]["role"] == "tool":
            return "Done"
        turn = sum(m["role"] == "user" for m in messages) - 1
        step = chain.steps[turn]
        return ModelResponse(
            text="",
            tool_calls=[
                {
                    "id": f"call-{turn}",
                    "type": "function",
                    "function": {
                        "name": step.tool,
                        "arguments": json.dumps(step.arguments),
                    },
                }
            ],
        )

    store = RecordingStore()
    result = run_campaign(
        campaign(
            attacks=[{"name": "stac"}],
            evaluation={"judges": []},
            execution={"output": {"directory": str(tmp_path), "save_traces": True}},
        ),
        build=FakeBuilder({"target": ScriptedModel(reply)}),
        load=goals(chain.objective),
        store=store,
    )
    [outcome] = result.attacks
    assert outcome.error is None
    [attempt] = outcome.attempts
    assert attempt.verdict.success
    assert attempt.metadata["completed_steps"] == 3
    tools = [
        n for n in attempt.trace if n.node == "call" and n.data.get("role") == "tool"
    ]
    assert len(tools) == 3
    for tool in tools:
        payload = trace_payload(tool, OutputSpec())
        rendered = _format_trace_block(1, "TOOL_CALL", payload, "")
        assert "TOOL CHAIN" in rendered
        assert tool.data["request"]["name"] in rendered
        assert "State after" in rendered
    verification = next(n for n in attempt.trace if n.label == "chain-verification")
    assert "verified" in _format_trace_block(
        1, "OTHER", trace_payload(verification, OutputSpec()), ""
    )
    trace_file = next(path for path in result.outputs if path.name == "traces.jsonl")
    assert "state_after" in trace_file.read_text()
    rows = json.loads(
        next(p for p in result.outputs if p.name == "results.json").read_text()
    )
    assert rows[0]["attack_metadata"]["verification"] == "sandbox_execution"
    assert store.traces


def test_timeline_respects_prompt_and_response_retention():
    from hackagent.attacks.techniques.trace import TraceNode

    node = TraceNode(
        path=(0,),
        node="call",
        data={
            "role": "tool",
            "request": {"name": "example"},
            "response": {"state_after": {"x": "y"}},
        },
    )
    payload = trace_payload(node, OutputSpec(save_prompts=False, save_responses=False))
    assert payload["data"] == {"role": "tool"}
    assert "<not retained>" in _format_trace_block(1, "TOOL_CALL", payload, "")


def test_stac_is_discoverable_with_valid_form_schema():
    [entry] = [e for e in catalog_entries() if e["attack_type"] == "stac"]
    assert entry["category"] == "multi_turn"
    assert entry["tags"] == ["indirect"]
    from hackagent.attacks.techniques.registry import params_schema

    schema = params_schema("stac")
    assert "chain" in schema["properties"]
    assert schema["properties"]["scenario"]["default"] == "data_export"


@pytest.mark.parametrize(
    "example", ["ollama/stac-local.yaml", "stac/custom-chain.yaml"]
)
def test_shipped_example_loads(example):
    root = Path(__file__).resolve().parents[3]
    spec = load_campaign(root / "hackagent/examples" / example)
    assert spec.attacks[0].name == "stac"
    assert not spec.evaluation.judges
