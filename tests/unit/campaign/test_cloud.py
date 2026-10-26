# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""What a campaign may contain to run on HackAgent cloud."""

from __future__ import annotations

import pytest

from hackagent.orchestrator.campaign import CampaignSpec
from hackagent.orchestrator.campaign.cloud import (
    HOSTED_LITELLM_PREFIXES,
    CloudIssue,
    cloud_issues,
)

from .fakes import campaign, model

GW = {"name": "gateway", "connection": {"provider": "hackagent", "type": "OPENAI"}}


def m(name, type_, endpoint=None, **extra):
    connection = {"provider": "p", "type": type_}
    if endpoint is not None:
        connection["endpoint"] = endpoint
    return {"name": name, "connection": connection, **extra}


def issues_for(target) -> list[CloudIssue]:
    return cloud_issues(CampaignSpec.model_validate(campaign(target=target)))


def paths(issues) -> list[str]:
    return [issue.path for issue in issues]


# --- allowed ----------------------------------------------------------------


def test_api_models_with_an_endpoint_and_the_gateway_are_allowed():
    spec = campaign(
        target=m("llama3", "OLLAMA", "https://ollama.example", options={"num_ctx": 8}),
        attacks=[{"name": "pair", "roles": {"attacker": GW}}],
        evaluation={"judges": [{**GW, "scoring": {"type": "harmbench"}}]},
    )
    assert cloud_issues(CampaignSpec.model_validate(spec)) == []


@pytest.mark.parametrize(
    "target",
    [
        m("gpt-4o-mini", "OPENAI"),
        *(m(f"{prefix}some-model", "LITELLM") for prefix in HOSTED_LITELLM_PREFIXES),
        m("org/model", "LITELLM", "https://llm.example/v1"),
        m("org/model", "OPENAI", "https://llm.example/v1"),
        m("llama3", "OLLAMA", "https://ollama.example", options={"top_k": 5}),
    ],
)
def test_hosted_apis_and_endpoints_are_allowed(target):
    assert issues_for(target) == []


# --- a. the gateway marker ----------------------------------------------------


@pytest.mark.parametrize(
    "agent_type", ["CLAUDE_CODE", "CODEX", "HERMES", "WEB", "GOOGLE_ADK", "LITELLM"]
)
def test_a_gateway_marker_of_another_type_is_refused(agent_type):
    gateway = {
        "name": "gateway",
        "connection": {"provider": "hackagent", "type": agent_type},
    }
    assert issues_for(gateway) == [
        CloudIssue("target", "the HackAgent gateway must have type OPENAI")
    ]


def test_a_gateway_marker_with_options_is_refused():
    gateway = {**GW, "options": {"extra_args": ["--yolo"]}}
    assert issues_for(gateway) == [
        CloudIssue("target", "the HackAgent gateway takes no options")
    ]


@pytest.mark.parametrize("key", ["endpoint", "api_key_env"])
def test_a_gateway_marker_with_an_endpoint_or_key_is_refused(key):
    gateway = {"name": "g", "connection": {**GW["connection"], key: "X"}}
    assert paths(issues_for(gateway)) == ["target"]


# --- b. model types -----------------------------------------------------------


@pytest.mark.parametrize(
    "agent_type", ["CLAUDE_CODE", "CODEX", "HERMES", "WEB", "GOOGLE_ADK", "LANGCHAIN"]
)
def test_other_model_types_are_refused(agent_type):
    assert issues_for(m("agent", agent_type, "https://x.example")) == [
        CloudIssue("target", f"model type {agent_type} can't run in the cloud")
    ]


# --- c. options -----------------------------------------------------------------


@pytest.mark.parametrize(
    "target",
    [
        m("gpt-4o", "OPENAI", options={"extra_args": ["--x"]}),
        m("openai/gpt-4o", "LITELLM", options={"binary": "/bin/sh"}),
        m("llama3", "OLLAMA", "https://o.example", options={"cwd": "/"}),
    ],
)
def test_options_outside_the_types_allowlist_are_refused(target):
    key = next(iter(target["options"]))
    assert issues_for(target) == [
        CloudIssue(
            f"target.options.{key}", f"option {key!r} can't be used in the cloud"
        )
    ]


# --- d. models without an endpoint ----------------------------------------------


def test_an_ollama_model_needs_an_endpoint():
    assert paths(issues_for(m("llama3", "OLLAMA"))) == ["target"]


@pytest.mark.parametrize("name", ["ollama/llama3", "ollama_chat/llama3", "org/model"])
def test_an_openai_model_without_endpoint_needs_a_bare_name(name):
    prefix = name.split("/")[0]
    assert issues_for(m(name, "OPENAI")) == [
        CloudIssue(
            "target",
            f"set an endpoint; {prefix}/ models can't run in the cloud without one",
        )
    ]


@pytest.mark.parametrize(
    "prefix",
    [
        "ollama/",
        "ollama_chat/",
        "docker_model_runner/",
        "lemonade/",
        "langgraph/",
        "langflow/",
        "lm_studio/",
        "hosted_vllm/",
        "bedrock/",
        "vertex_ai/",
        "sagemaker/",
        "azure/",
    ],
)
def test_a_litellm_model_without_endpoint_needs_a_hosted_prefix(prefix):
    assert issues_for(m(f"{prefix}model", "LITELLM")) == [
        CloudIssue(
            "target",
            f"set an endpoint; {prefix} models can't run in the cloud without one",
        )
    ]


def test_a_litellm_model_without_endpoint_or_prefix_is_refused():
    [issue] = issues_for(m("gpt-4o", "LITELLM"))
    assert issue.path == "target"
    assert issue.reason.startswith("set an endpoint, or start the model name with")


def test_an_empty_endpoint_counts_as_none():
    assert paths(issues_for(m("llama3", "OLLAMA", ""))) == ["target"]


# --- every model of the spec ----------------------------------------------------


def test_every_model_of_the_spec_is_checked():
    bad = m("agent", "CLAUDE_CODE")
    spec = campaign(
        target=bad,
        attacks=[
            {"name": "rag", "roles": {"attacker": bad, "embedder": bad}},
            {"name": "pair", "roles": {"attacker": GW}},
        ],
        evaluation={
            "judges": [
                {**model("judge"), "scoring": {"type": "harmbench"}},
                {**bad, "scoring": {"type": "harmbench"}},
            ]
        },
        guardrails={"before": bad, "after": bad},
        dataset={"preset": "harmbench", "classifier": bad},
    )
    assert paths(cloud_issues(CampaignSpec.model_validate(spec))) == [
        "target",
        "attacks.0.roles.attacker",
        "attacks.0.roles.embedder",
        "evaluation.judges.1",
        "guardrails.before",
        "guardrails.after",
        "dataset.classifier",
    ]
