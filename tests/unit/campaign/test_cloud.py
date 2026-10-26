# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""What a campaign may contain to run on HackAgent cloud."""

from __future__ import annotations

import pytest

from hackagent.orchestrator.campaign import CampaignSpec
from hackagent.orchestrator.campaign.cloud import (
    HOSTED_PROVIDERS,
    UNKNOWN_PROVIDER_REASON,
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
        m("gpt-4o", "LITELLM"),
        *(m(f"{provider}/some-model", "LITELLM") for provider in HOSTED_PROVIDERS),
        m("gpt-4o", "LITELLM", "https://llm.example/v1"),
        m("hosted_vllm/org/model", "LITELLM", "https://llm.example/v1"),
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


# --- d. the provider each model resolves to, without an endpoint ----------------


def test_an_ollama_model_needs_an_endpoint():
    assert issues_for(m("llama3", "OLLAMA")) == [
        CloudIssue(
            "target",
            "set an endpoint; ollama_chat models can't run in the cloud without one",
        )
    ]


def test_an_empty_endpoint_counts_as_none():
    assert paths(issues_for(m("llama3", "OLLAMA", ""))) == ["target"]


@pytest.mark.parametrize(
    ("type_", "name", "provider"),
    [
        ("OPENAI", "ollama/llama3", "ollama"),
        ("OPENAI", "ollama_chat/llama3", "ollama_chat"),
        ("LITELLM", "ollama/m", "ollama"),
        ("LITELLM", "lm_studio/m", "lm_studio"),
        ("LITELLM", "hosted_vllm/m", "hosted_vllm"),
        ("LITELLM", "vllm/m", "vllm"),
    ],
)
def test_a_local_runtime_needs_an_endpoint(type_, name, provider):
    assert issues_for(m(name, type_)) == [
        CloudIssue(
            "target",
            f"set an endpoint; {provider} models can't run in the cloud without one",
        )
    ]


@pytest.mark.parametrize(
    "provider",
    [
        "docker_model_runner",
        "lemonade",
        "langgraph",
        "bedrock",
        "vertex_ai",
        "sagemaker",
        "azure",
    ],
)
def test_other_providers_are_refused_without_endpoint(provider):
    assert issues_for(m(f"{provider}/model", "LITELLM")) == [
        CloudIssue("target", f"{provider} models can't run in the cloud")
    ]


@pytest.mark.parametrize(
    ("type_", "name"),
    [
        ("OPENAI", "gpt-4o"),
        ("LITELLM", "openai/gpt-4o"),
        ("LITELLM", "anthropic/claude-x"),
    ],
)
def test_hosted_apis_need_no_endpoint(type_, name):
    assert issues_for(m(name, type_)) == []


# --- d. the provider each model resolves to, at an endpoint --------------------

ENDPOINT = "https://llm.example/v1"


@pytest.mark.parametrize(
    ("name", "provider"),
    [
        ("anthropic.claude-v2", "bedrock"),
        ("amazon.titan-text-express-v1", "bedrock"),
        ("bedrock/model", "bedrock"),
        ("vertex_ai/model", "vertex_ai"),
        ("sagemaker/model", "sagemaker"),
        ("azure/model", "azure"),
        ("langgraph/model", "langgraph"),
    ],
)
def test_a_litellm_model_at_an_endpoint_is_refused_by_its_provider(name, provider):
    assert issues_for(m(name, "LITELLM", ENDPOINT)) == [
        CloudIssue("target", f"{provider} models can't run in the cloud")
    ]


@pytest.mark.parametrize("model_type", ["OPENAI", "OLLAMA"])
@pytest.mark.parametrize("provider", ["bedrock", "vertex_ai", "azure", "replicate"])
def test_a_model_at_an_endpoint_names_no_passthrough_provider(model_type, provider):
    assert issues_for(m(f"{provider}/model", model_type, ENDPOINT)) == [
        CloudIssue("target", f"{provider} models can't run in the cloud")
    ]


@pytest.mark.parametrize(
    "name",
    [
        "openai/gpt-4o",
        "meta-llama/Llama-3.1-8B",
        "ollama/llama3",
        # Not a provider an OPENAI model passes through: sent as openai/sagemaker/x.
        "sagemaker/model",
    ],
)
def test_an_openai_model_at_an_endpoint_may_name_a_repository(name):
    assert issues_for(m(name, "OPENAI", ENDPOINT)) == []


@pytest.mark.parametrize(
    "name",
    ["openai/gpt-4o", "anthropic/claude", "llamafile/m", "hosted_vllm/meta-llama/x"],
)
def test_a_litellm_model_at_an_endpoint_with_an_allowed_provider(name):
    assert issues_for(m(name, "LITELLM", ENDPOINT)) == []


@pytest.mark.parametrize("endpoint", [None, ENDPOINT])
@pytest.mark.parametrize("name", ["llama3", "Hosted_VLLM/m", "claude-3-5-sonnet"])
def test_a_model_whose_provider_litellm_cannot_tell_is_refused(name, endpoint):
    assert issues_for(m(name, "LITELLM", endpoint)) == [
        CloudIssue("target", UNKNOWN_PROVIDER_REASON)
    ]


def test_a_gateway_marker_names_no_passthrough_provider():
    assert issues_for({**GW, "name": "bedrock/model"}) == [
        CloudIssue("target", "bedrock models can't run in the cloud")
    ]
    assert issues_for({**GW, "name": "Qwen/Qwen3-8B"}) == []


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
