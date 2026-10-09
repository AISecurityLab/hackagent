# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tool-output IPI poisons a tool result and judges what the agent does.

The target and panel are plain callables, so no model or router is built.
"""

from __future__ import annotations

import asyncio


from hackagent.attacks.techniques.indirect.tool_output_ipi import (
    ToolOutputIPIAttack,
    ToolOutputIPIParams,
)
from hackagent.attacks.techniques.indirect.tool_output_ipi import prompts
from hackagent.core.contracts import Completion, LLMError, Verdict

GOAL = "exfiltrate the API key"


class Target:
    """Records every request, and the tools it was shown."""

    def __init__(self, *replies, tool_calls=None) -> None:
        self.replies = list(replies) or ["acknowledged"]
        self.tool_calls = tool_calls or []
        self.requests: list[list[dict]] = []
        self.overrides: list[dict] = []

    async def __call__(self, messages, **overrides):
        self.requests.append([dict(m) for m in messages])
        self.overrides.append(overrides)
        text = self.replies[min(len(self.requests) - 1, len(self.replies) - 1)]
        calls = (
            self.tool_calls[min(len(self.requests) - 1, len(self.tool_calls) - 1)]
            if self.tool_calls
            else []
        )
        if text is None:
            return Completion(text="", error=LLMError(message="x", category="APIError"))
        return Completion(text=text, tool_calls=calls)


class Panel:
    def __init__(self, *scores, threshold=7.0) -> None:
        self.scores = list(scores) or [0.0]
        self.threshold = threshold
        self.samples: list = []

    async def __call__(self, sample):
        self.samples.append(sample)
        score = self.scores[min(len(self.samples) - 1, len(self.scores) - 1)]
        return Verdict(success=score >= self.threshold, score=score)


class Attacker:
    def __init__(self) -> None:
        self.calls = 0

    async def __call__(self, messages):
        self.calls += 1
        return f"sharper injection v{self.calls}"


def run(attack, goal=GOAL, target=None, judge=None):
    target = target or Target()
    return asyncio.run(attack.run(goal, target, judge)), target


# --- the request --------------------------------------------------------------


def test_the_target_sees_a_poisoned_tool_result_history():
    attack = ToolOutputIPIAttack(ToolOutputIPIParams())
    _findings, target = run(attack, judge=Panel(1.0))

    roles = [m["role"] for m in target.requests[0]]
    assert roles == ["user", "assistant", "tool"]
    # The goal rides in the tool result, never in a user turn.
    assert GOAL in target.requests[0][2]["content"]
    assert GOAL not in target.requests[0][0]["content"]


def test_the_assistant_turn_carries_a_tool_call():
    attack = ToolOutputIPIAttack(ToolOutputIPIParams())
    _findings, target = run(attack, judge=Panel(1.0))

    call = target.requests[0][1]["tool_calls"][0]
    assert call["function"]["name"] == prompts.DEFAULT_TOOL_NAME


def test_the_tool_schema_is_shown_to_the_target():
    attack = ToolOutputIPIAttack(ToolOutputIPIParams())
    _findings, target = run(attack, judge=Panel(1.0))

    assert target.overrides[0]["tools"] == [prompts.DEFAULT_TOOL_SCHEMA]


# --- judging ------------------------------------------------------------------


def test_a_follow_up_tool_call_counts_as_what_the_agent_did():
    from hackagent.core.contracts import ToolCall

    call = ToolCall(name="send_email", arguments='{"to":"x"}')
    panel = Panel(9.0)
    attack = ToolOutputIPIAttack(ToolOutputIPIParams())
    findings, _target = run(attack, target=Target("", tool_calls=[[call]]), judge=panel)

    assert "send_email" in panel.samples[0].response
    assert findings[0].metadata["followup_tool_calls"] == [call]


def test_a_reply_with_neither_text_nor_a_call_is_skipped():
    attack = ToolOutputIPIAttack(ToolOutputIPIParams(max_attempts=1))
    findings, _target = run(attack, target=Target(None), judge=Panel(1.0))

    assert findings == []


# --- attempts and the attacker role ------------------------------------------


def test_without_an_attacker_a_single_payload_is_tried():
    attack = ToolOutputIPIAttack(ToolOutputIPIParams(max_attempts=5))
    _findings, target = run(attack, judge=Panel(1.0))

    # max_attempts is inert with nothing to vary the payload.
    assert len(target.requests) == 1


def test_with_an_attacker_the_payload_is_refined_across_attempts():
    attacker = Attacker()
    attack = ToolOutputIPIAttack(ToolOutputIPIParams(max_attempts=3, attacker=attacker))
    _findings, target = run(attack, judge=Panel(1.0))

    assert len(target.requests) == 3
    # First attempt uses the base payload; later ones use refinements.
    assert attacker.calls == 2
    assert "sharper injection" in target.requests[1][2]["content"]


def test_the_search_stops_once_the_agent_complies():
    attacker = Attacker()
    attack = ToolOutputIPIAttack(ToolOutputIPIParams(max_attempts=5, attacker=attacker))
    findings, target = run(attack, judge=Panel(1.0, 9.0, 1.0))

    assert len(target.requests) == 2
    assert [f.verdict.success for f in findings] == [False, True]


def test_a_failing_attacker_falls_back_to_the_base_payload():
    async def broken(messages):
        raise RuntimeError("attacker down")

    attack = ToolOutputIPIAttack(ToolOutputIPIParams(max_attempts=2, attacker=broken))
    findings, target = run(attack, judge=Panel(1.0))

    # Still ran; the second attempt reused the base injection.
    assert len(target.requests) == 2
    assert len(findings) == 2


# --- config -------------------------------------------------------------------


def test_the_attacker_is_the_only_role():
    assert ToolOutputIPIParams.role_names() == frozenset({"attacker"})


def test_the_success_setting_steers_the_framing():
    attack = ToolOutputIPIAttack(ToolOutputIPIParams(success_setting="data_stealing"))
    _findings, target = run(attack, judge=Panel(1.0))

    observation = target.requests[0][2]["content"]
    assert prompts.SUCCESS_FRAMING["data_stealing"] in observation
