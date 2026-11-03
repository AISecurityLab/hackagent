# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Adaptive and tool conversations over the actual completion wire protocol."""

from copy import deepcopy
import json

import pytest

from hackagent.attacks.techniques.multi_turn.stac.environment import builtin_chain
from tests.support.campaigns import Reply

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def pair(execution, completion_server, *, scorer=False):
    roles = {"attacker": {**deepcopy(execution.values["target"]), "name": "attacker"}}
    completion_server.defaults["attacker"] = Reply("no further prompt")
    if scorer:
        roles["scorer"] = {**deepcopy(execution.values["target"]), "name": "scorer"}
        completion_server.defaults["scorer"] = Reply("Rating: [[10]]")
    execution.values["dataset"]["source"]["goals"] = ["Goal one"]
    execution.values["attacks"] = [
        {"name": "pair", "parameters": {"iterations": 4, "streams": 1}, "roles": roles}
    ]


def proposal(prompt):
    return Reply(json.dumps({"improvement": "fixture improvement", "prompt": prompt}))


def records(execution, count):
    [campaign] = execution.store.list_campaign_runs().items
    [run] = execution.store.list_runs().items
    assert campaign.status == run.status == "COMPLETED"
    items = execution.store.list_results(run_id=run.id).items
    assert len(items) == count
    assert all(execution.store.list_traces(item.id) for item in items)
    rows = json.loads(next(execution.directory.glob("*/results.json")).read_text())
    assert len(rows) == count
    traces = [
        json.loads(line)
        for line in next(execution.directory.glob("*/traces.jsonl"))
        .read_text()
        .splitlines()
    ]
    assert len(traces) == count
    return items, traces


@pytest.mark.parametrize("scorer", [False, True])
async def test_pair_refines_from_feedback_and_stops_without_duplicate_judging(
    execution, completion_server, scorer
):
    pair(execution, completion_server, scorer=scorer)
    completion_server.replies["attacker"].extend(
        [proposal("First prompt"), proposal("Refined prompt")]
    )
    completion_server.replies["target"].extend(
        [Reply("First reply"), Reply("Refined reply")]
    )
    if scorer:
        completion_server.replies["scorer"].extend(
            [Reply("Rating: [[2]]"), Reply("Rating: [[10]]")]
        )
    else:
        completion_server.replies["judge"].extend([Reply("no"), Reply("yes")])
    result = await execution.run()
    [outcome] = result.attacks
    assert outcome.error is None
    assert [a.metadata["iteration"] for a in outcome.attempts] == [0, 1]
    assert [a.response.text for a in outcome.attempts] == [
        "First reply",
        "Refined reply",
    ]
    assert [r["body"]["messages"] for r in completion_server.calls("target")] == [
        [{"role": "user", "content": "First prompt"}],
        [{"role": "user", "content": "Refined prompt"}],
    ]
    attacker = completion_server.calls("attacker")
    assert len(attacker) == 2
    history = attacker[1]["body"]["messages"]
    assert [m["role"] for m in history] == ["system", "user", "assistant", "user"]
    assert json.loads(history[-2]["content"])["prompt"] == "First prompt"
    assert "LANGUAGE MODEL OUTPUT: First reply" in history[-1]["content"]
    assert f"SCORE: {2.0 if scorer else 0.0}" in history[-1]["content"]
    assert len(completion_server.calls("judge")) == (1 if scorer else 2)
    assert len(completion_server.calls("scorer")) == (2 if scorer else 0)
    assert outcome.attempts[-1].verdict.success
    if scorer:
        assert outcome.attempts[0].verdict is None
        assert (
            "Refined reply"
            in completion_server.calls("judge")[0]["body"]["messages"][-1]["content"]
        )
    stored, traces = records(execution, 2)
    assert sum(r.evaluation_status == "SUCCESSFUL_JAILBREAK" for r in stored) == 1
    assert (
        sum(
            n["node"] == "call" and n["data"].get("role") == "target"
            for t in traces
            for n in t["nodes"]
        )
        == 2
    )


async def test_pair_records_target_failure_instead_of_an_empty_success(
    execution, completion_server
):
    pair(execution, completion_server)
    execution.values["attacks"][0]["parameters"]["iterations"] = 1
    completion_server.replies["attacker"].append(proposal("First prompt"))
    completion_server.defaults["target"] = Reply("target refused request", 400)
    result = await execution.run()
    [attempt] = result.attacks[0].attempts
    assert attempt.error == "the target gave no usable reply"
    assert attempt.verdict is None
    assert len(completion_server.calls("target")) == 1
    assert completion_server.calls("judge") == []
    stored, traces = records(execution, 1)
    assert stored[0].evaluation_status == "ERROR_TEST_FRAMEWORK"
    assert any(n.get("error") for n in traces[0]["nodes"] if n["node"] == "call")


@pytest.mark.parametrize("duplicate", [False, True])
async def test_stac_tool_history_and_verification_round_trip(
    execution, completion_server, duplicate
):
    chain = builtin_chain("data_export")
    execution.values["dataset"]["source"]["goals"] = [chain.objective]
    execution.values["attacks"] = [{"name": "stac"}]
    execution.values["evaluation"] = {}

    def target(body):
        history = body["messages"]
        if history[-1]["role"] == "tool":
            return Reply("Acknowledged.")
        turn = sum(m["role"] == "user" for m in history) - 1
        step = chain.steps[turn]
        return Reply(
            "",
            tool_calls=[
                {
                    "id": "same-id" if duplicate else f"step-{turn}",
                    "type": "function",
                    "function": {
                        "name": step.tool,
                        "arguments": json.dumps(step.arguments),
                    },
                }
            ],
        )

    completion_server.defaults["target"] = target
    result = await execution.run()
    [attempt] = result.attacks[0].attempts
    assert attempt.response.error is None, attempt.response.error
    assert attempt.verdict.success is not duplicate
    assert attempt.metadata["completed_steps"] == (1 if duplicate else 3)
    assert len(completion_server.calls("target")) == (3 if duplicate else 5)
    assert completion_server.calls("judge") == []
    calls = completion_server.calls("target")
    assert all(len(r["body"]["tools"]) == 3 for r in calls)
    continuation = calls[1]["body"]["messages"]
    assert continuation[-1]["role"] == "tool"
    assert continuation[-1]["tool_call_id"] == continuation[-2]["tool_calls"][0]["id"]
    stored, traces = records(execution, 1)
    tools = [
        n
        for n in traces[0]["nodes"]
        if n["node"] == "call" and n["data"].get("role") == "tool"
    ]
    assert len(tools) == (1 if duplicate else 3)
    assert [n["data"]["request"]["name"] for n in tools] == [
        step.tool for step in chain.steps[: len(tools)]
    ]
    if duplicate:
        assert attempt.verdict.error == "Duplicate tool call id"
        assert stored[0].evaluation_status == "ERROR_TEST_FRAMEWORK"
    else:
        assert attempt.metadata["executed_tools"] == [step.tool for step in chain.steps]
        assert all(
            attempt.metadata["final_state"][key] == value
            for key, value in chain.success_state.items()
        )
        assert stored[0].evaluation_status == "SUCCESSFUL_JAILBREAK"
        assert any(
            n["label"] == "chain-verification" and n["data"]["success"]
            for n in traces[0]["nodes"]
        )


@pytest.mark.parametrize(
    "scorer_reply", [Reply("unrated"), Reply("scorer unavailable", 400)]
)
async def test_pair_missing_scorer_rating_stays_unscored_until_panel_review(
    execution, completion_server, scorer_reply
):
    pair(execution, completion_server, scorer=True)
    execution.values["attacks"][0]["parameters"]["iterations"] = 1
    completion_server.replies["attacker"].append(proposal("First prompt"))
    completion_server.defaults["scorer"] = scorer_reply
    result = await execution.run()
    [attempt] = result.attacks[0].attempts
    assert attempt.metadata["score"] is None
    assert attempt.verdict.success
    assert len(completion_server.calls("target")) == 1
    assert len(completion_server.calls("scorer")) == 1
    assert len(completion_server.calls("judge")) == 1
    records(execution, 1)


async def test_stac_provider_failure_remains_visible_in_records_and_trace(
    execution, completion_server
):
    chain = builtin_chain("data_export")
    execution.values["dataset"]["source"]["goals"] = [chain.objective]
    execution.values["attacks"] = [{"name": "stac"}]
    execution.values["evaluation"] = {}
    completion_server.defaults["target"] = Reply("fixture target failure", 400)
    result = await execution.run()
    [attempt] = result.attacks[0].attempts
    assert not attempt.verdict.success
    assert "fixture target failure" in attempt.verdict.error
    assert attempt.metadata["completed_steps"] == 0
    assert len(completion_server.calls("target")) == 1
    assert completion_server.calls("judge") == []
    stored, traces = records(execution, 1)
    assert stored[0].evaluation_status == "ERROR_TEST_FRAMEWORK"
    assert any(n.get("error") for n in traces[0]["nodes"] if n["node"] == "call")


async def test_pair_attacker_failure_does_not_spend_target_or_scorer_calls(
    execution, completion_server
):
    pair(execution, completion_server, scorer=True)
    execution.values["attacks"][0]["parameters"]["iterations"] = 1
    completion_server.defaults["attacker"] = Reply("attacker unavailable", 400)
    result = await execution.run()
    [attempt] = result.attacks[0].attempts
    assert attempt.error == "the attacker proposed no usable prompt"
    assert attempt.verdict is None
    assert len(completion_server.calls("attacker")) == 1
    assert completion_server.calls("target") == []
    assert completion_server.calls("scorer") == []
    assert completion_server.calls("judge") == []
    stored, traces = records(execution, 1)
    assert stored[0].evaluation_status == "ERROR_TEST_FRAMEWORK"
    assert any(n.get("error") for n in traces[0]["nodes"] if n["node"] == "call")
