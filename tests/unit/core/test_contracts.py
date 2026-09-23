# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for ``hackagent.core.contracts``."""

import pytest
from pydantic import ValidationError

from hackagent.core.contracts import (
    LLM,
    AgentType,
    Completion,
    EvalStatus,
    Goal,
    GuardrailInfo,
    JudgeSpec,
    LLMError,
    Message,
    ModelSpec,
    RunStatus,
    StepKind,
    Verdict,
)


@pytest.mark.parametrize(
    "value,expected",
    [
        (AgentType.GOOGLE_ADK, AgentType.GOOGLE_ADK),
        ("LITELLM", AgentType.LITELLM),
        ("litellm", AgentType.LITELLM),
        ("google-adk", AgentType.GOOGLE_ADK),
        ("GOOGLE_ADK", AgentType.GOOGLE_ADK),
        ("google adk", AgentType.GOOGLE_ADK),
        ("adk", AgentType.GOOGLE_ADK),
        ("openai", AgentType.OPENAI_SDK),
        ("openai-sdk", AgentType.OPENAI_SDK),
        ("claude", AgentType.CLAUDE_CODE),
        ("claude-code", AgentType.CLAUDE_CODE),
        ("hermes-agent", AgentType.HERMES),
        ("web-chatbot", AgentType.WEB),
        ("browser", AgentType.WEB),
        ("lang_chain", AgentType.LANGCHAIN),
        ("lite-llm", AgentType.LITELLM),
        ("other", AgentType.UNKNOWN),
        ("unknown", AgentType.UNKNOWN),
    ],
)
def test_agent_type_parse_accepts_names_and_aliases(value, expected):
    assert AgentType.parse(value) is expected


@pytest.mark.parametrize("value", ["invalid-type", 123, None, []])
def test_agent_type_parse_falls_back_to_unknown(value):
    assert AgentType.parse(value) is AgentType.UNKNOWN


def test_agent_type_strict_constructor_still_rejects_unknown_strings():
    assert AgentType("openai") is AgentType.OPENAI_SDK
    with pytest.raises(ValueError):
        AgentType("not-a-type")


def test_enum_wire_values_are_unchanged():
    assert [m.value for m in RunStatus] == [
        "PENDING",
        "RUNNING",
        "COMPLETED",
        "FAILED",
        "CANCELLED",
    ]
    assert StepKind.A2_A_COMM.value == "A2A_COMM"
    assert EvalStatus.SUCCESSFUL_JAILBREAK.value == "SUCCESSFUL_JAILBREAK"
    assert str(AgentType.OLLAMA) == "OLLAMA"


def test_completion_ok_requires_no_error_and_no_guardrail():
    assert Completion(text="hi").ok
    assert not Completion(error=LLMError(message="boom", status_code=500)).ok
    assert not Completion(guardrail=GuardrailInfo(side="before")).ok


def test_message_accepts_content_parts():
    message = Message(
        role="user",
        content=[
            {"type": "text", "text": "describe"},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,"}},
        ],
    )
    assert message.content[1]["type"] == "image_url"


def test_model_spec_parses_agent_type_and_forbids_unknown_fields():
    spec = ModelSpec(identifier="llama3", agent_type="ollama")
    assert spec.agent_type is AgentType.OLLAMA

    with pytest.raises(ValidationError):
        ModelSpec(identifier="llama3", not_a_field=True)


def test_judge_spec_extends_model_spec():
    judge = JudgeSpec(identifier="judge-model", type="jailbreakbench", range="binary")
    assert isinstance(judge, ModelSpec)
    with pytest.raises(ValidationError):
        JudgeSpec(identifier="judge-model", range="percent")


def test_verdict_score_is_bounded_to_normalised_scale():
    assert Verdict(success=True, score=10.0).score == 10.0
    with pytest.raises(ValidationError):
        Verdict(success=True, score=10.5)


def test_goal_index_is_non_negative():
    assert Goal(text="g", index=0).labels == {}
    with pytest.raises(ValidationError):
        Goal(text="g", index=-1)


def test_llm_protocol_is_structural():
    class Echo:
        def complete(self, messages, **params):
            return Completion(text=str(messages))

        async def acomplete(self, messages, **params):
            return self.complete(messages)

        def with_params(self, **params):
            return self

        def describe(self):
            return ModelSpec(identifier="echo")

    assert isinstance(Echo(), LLM)
    assert not isinstance(object(), LLM)
