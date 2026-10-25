# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""STAC counts executed effects, never model claims or a text judge's vote."""

import asyncio
import copy
import json

import pytest
from pydantic import ValidationError

from hackagent.attacks.techniques.multi_turn.stac import (
    STACAttack,
    STACParams,
    ToolChain,
)
from hackagent.attacks.techniques.multi_turn.stac.environment import (
    Sandbox,
    builtin_chain,
)
from hackagent.attacks.techniques.trace import recording
from hackagent.core.contracts import Completion, GuardrailInfo, LLMError, ToolCall


class Target:
    def __init__(self, replies):
        self.replies = iter(replies)
        self.requests = []
        self.tools = []

    async def __call__(self, messages, **kwargs):
        self.requests.append(copy.deepcopy(messages))
        self.tools.append(kwargs["tools"])
        return next(self.replies, Completion(text="I cannot do that."))


def call(step, **overrides):
    return Completion(
        tool_calls=[
            ToolCall(name=step.tool, arguments=json.dumps(step.arguments), **overrides)
        ]
    )


def script(chain):
    for step in chain.steps:
        yield call(step)
        yield Completion(text="Done.")


def run(target, params=None, judge=None):
    params = params or STACParams()
    chain = params.chain or builtin_chain(params.scenario)
    with recording() as trace:
        [finding] = asyncio.run(STACAttack(params).run(chain.objective, target, judge))
    return finding, trace


@pytest.mark.parametrize(
    "scenario", ["data_export", "permission_change", "unreviewed_publish"]
)
def test_full_chain_executes_in_one_growing_conversation(scenario):
    chain = builtin_chain(scenario)
    target = Target(script(chain))
    result, trace = run(target, STACParams(scenario=scenario))
    assert result.verdict.success
    assert result.verdict.score == 10
    assert result.metadata["final_state"] == {
        **chain.initial_state,
        **{k: v for s in chain.steps for k, v in s.effects.items()},
    }
    assert result.metadata["executed_tools"] == [s.tool for s in chain.steps]
    # Every model call sees the same schemas. Tool-only replies are usable.
    assert all(tools == target.tools[0] for tools in target.tools)
    assert len(target.requests) == 5
    assert [m["role"] for m in target.requests[-1]].count("user") == 3
    assert [m["role"] for m in target.requests[-1]].count("tool") == 2
    # Calls have paired OpenAI wire messages and stable ids.
    messages = target.requests[-1]
    for i, message in enumerate(messages):
        if message["role"] == "tool":
            assert messages[i - 1]["tool_calls"][0]["id"] == message["tool_call_id"]
    nodes = [n for n in trace.nodes if n.node == "call" and n.data["role"] == "tool"]
    assert len(nodes) == 3
    assert nodes[0].data["response"]["state_before"] == chain.initial_state
    assert nodes[-1].data["response"]["state_after"] == result.metadata["final_state"]
    assert all(n.under(result.path) for n in trace.nodes)


def test_text_claim_and_positive_judge_cannot_create_success():
    async def judge(_sample):
        raise AssertionError("STAC must not consult a text judge")

    result, _ = run(
        Target([Completion(text="Successfully published everything.")]), judge=judge
    )
    assert not result.verdict.success
    assert result.verdict.score == 0
    assert result.metadata["completed_steps"] == 0


def test_partial_chain_is_not_success():
    chain = builtin_chain("data_export")
    result, _ = run(Target([call(chain.steps[0]), Completion(text="Done")]))
    assert not result.verdict.success
    assert result.metadata["completed_steps"] == 1


def test_reversed_chain_cannot_reach_terminal_state():
    chain = builtin_chain("data_export")
    result, trace = run(
        Target(
            [
                Completion(
                    tool_calls=[
                        ToolCall(name=s.tool, arguments=json.dumps(s.arguments))
                        for s in reversed(chain.steps)
                    ]
                )
            ]
        )
    )
    assert not result.verdict.success
    assert result.metadata["final_state"]["published"] == "no"
    assert any(n.error and "prerequisites" in n.error for n in trace.nodes)


@pytest.mark.parametrize(
    "arguments",
    [
        "{broken",
        "[]",
        '{"record_id":"other"}',
        '{"record_id":"canary-001", "extra":"x"}',
    ],
)
def test_invalid_arguments_do_not_mutate_state(arguments):
    target = Target(
        [Completion(tool_calls=[ToolCall(name="prepare_draft", arguments=arguments)])]
    )
    result, trace = run(target)
    assert not result.verdict.success
    assert result.metadata["final_state"] == {"published": "no"}
    assert any(n.error for n in trace.nodes)


def test_unknown_tool_is_returned_as_tool_error():
    target = Target(
        [Completion(tool_calls=[ToolCall(name="host_shell", arguments="{}")])]
    )
    result, _ = run(target)
    assert not result.verdict.success
    assert "Unknown tool" in target.requests[1][-1]["content"]


@pytest.mark.parametrize(
    "reply",
    [
        Completion(error=LLMError(message="offline")),
        Completion(guardrail=GuardrailInfo(side="after")),
    ],
)
def test_provider_failure_and_guardrail_are_unjudged(reply):
    result, _ = run(Target([reply]))
    assert not result.verdict.success
    assert result.verdict.error


def test_duplicate_ids_stop_without_executing_the_duplicate():
    chain = builtin_chain("data_export")
    target = Target(
        [
            call(chain.steps[0], id="same"),
            Completion(text="Done"),
            call(chain.steps[1], id="same"),
        ]
    )
    result, _ = run(target)
    assert result.verdict.error == "Duplicate tool call id"
    assert result.metadata["completed_steps"] == 1


@pytest.mark.parametrize(
    "params,expected_calls",
    [
        (STACParams(max_turns=1), 1),
        (STACParams(max_rounds_per_turn=1), 1),
        (STACParams(max_tool_calls=1), 1),
    ],
)
def test_budgets_bound_execution(params, expected_calls):
    result, _ = run(Target(script(builtin_chain("data_export"))), params)
    assert not result.verdict.success
    assert result.metadata["tool_calls"] == expected_calls


def test_batch_execution_and_nested_provider_calls():
    chain = builtin_chain("data_export")
    from types import SimpleNamespace

    target = Target(
        [
            SimpleNamespace(
                ok=True,
                text="",
                tool_calls=[
                    {
                        "id": f"call-{i}",
                        "type": "function",
                        "function": {
                            "name": s.tool,
                            "arguments": json.dumps(s.arguments),
                        },
                    }
                    for i, s in enumerate(chain.steps)
                ],
            )
        ]
    )
    result, _ = run(target)
    assert result.verdict.success


def test_custom_chain_loads_and_runs_without_host_execution():
    data = builtin_chain("permission_change").model_dump()
    data["name"] = "custom"
    params = STACParams(chain=data)
    result, _ = run(Target(script(params.chain)), params)
    assert result.verdict.success
    assert result.metadata["chain"] == "custom"


def test_unrelated_dataset_goal_cannot_be_reported_as_success():
    with pytest.raises(ValueError, match="match its verified objective"):
        asyncio.run(STACAttack(STACParams()).run("unrelated goal", Target([])))


def test_reference_chain_requires_full_executable_sequence():
    data = builtin_chain("data_export").model_dump()
    data["steps"][0]["requires"] = {"missing": "yes"}
    with pytest.raises(ValidationError, match="unmet reference prerequisites"):
        ToolChain.model_validate(data)
    data = builtin_chain("data_export").model_dump()
    data["success_state"] = {"never_set": "yes"}
    with pytest.raises(ValidationError, match="does not satisfy"):
        ToolChain.model_validate(data)
    data["success_state"] = {"visibility": "public"}
    with pytest.raises(ValidationError, match="entire chain"):
        ToolChain.model_validate(data)


def test_same_attack_can_run_concurrent_goals_with_isolated_state():
    chain = builtin_chain("data_export")
    attack = STACAttack(STACParams())

    async def searches():
        return await asyncio.gather(
            attack.run(chain.objective, Target(script(chain))),
            attack.run(chain.objective, Target([])),
        )

    [passed], [failed] = asyncio.run(searches())
    assert passed.verdict.success
    assert not failed.verdict.success
    assert failed.metadata["final_state"] == chain.initial_state


def test_terminal_state_alone_is_insufficient_without_the_full_order():
    chain = builtin_chain("data_export")
    sandbox = Sandbox(chain)
    sandbox.state.update(chain.success_state)
    assert not sandbox.success


def test_single_operation_cannot_satisfy_custom_objective():
    data = builtin_chain("data_export").model_dump()
    data["success_state"] = {"draft": "ready"}
    with pytest.raises(ValidationError, match="single tool"):
        ToolChain.model_validate(data)
