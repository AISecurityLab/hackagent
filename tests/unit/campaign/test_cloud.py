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
    secret_name_reason,
)

from hackagent.orchestrator.campaign.loader import load_stored_campaign

from .fakes import campaign, model

GW = {"name": "gateway", "connection": {"provider": "hackagent", "type": "OPENAI"}}


def m(name, type_, endpoint=None, **extra):
    connection = {"provider": "p", "type": type_}
    if endpoint is not None:
        connection["endpoint"] = endpoint
    return {"name": name, "connection": connection, **extra}


def issues_for(target) -> list[CloudIssue]:
    return cloud_issues(load_stored_campaign(campaign(target=target)))


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


@pytest.mark.parametrize(
    ("key", "value"), [("endpoint", "https://x.example"), ("api_key", "${X_KEY}")]
)
def test_a_gateway_marker_with_an_endpoint_or_key_is_refused(key, value):
    gateway = {"name": "g", "connection": {**GW["connection"], key: value}}
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


@pytest.mark.parametrize("endpoint", [None, ENDPOINT])
def test_in_process_vllm_is_refused(endpoint):
    assert issues_for(m("vllm/facebook/opt-125m", "LITELLM", endpoint)) == [
        CloudIssue("target", "vllm models can't run in the cloud")
    ]


# --- secret variables -------------------------------------------------------------


def keyed(name):
    target = m("gpt-4o", "OPENAI", ENDPOINT)
    target["connection"]["api_key"] = "${" + name + "}"
    return target


@pytest.mark.parametrize(
    "name", ["OPENAI_API_KEY", "MY_LLM_KEY", "GROQ_TOKEN", "TOGETHERAPI_KEY"]
)
def test_a_secret_variable_named_as_a_key_is_allowed(name):
    assert secret_name_reason(name) is None
    assert issues_for(keyed(name)) == []


@pytest.mark.parametrize(
    "name",
    [
        "OPENAI_BASE_URL",
        "HTTPS_PROXY",
        "HF_ENDPOINT",
        "HACKAGENT_GRAPHVIZ_DOT",
        "PATH",
        "HOME",
        "LD_PRELOAD",
        "openai_api_key",
        "OPENAI_SECRET",
    ],
)
def test_a_variable_that_is_not_a_key_is_refused(name):
    assert secret_name_reason(name) is not None
    assert paths(issues_for(keyed(name))) == ["target.connection.api_key"]


@pytest.mark.parametrize(
    "name",
    [
        "HACKAGENT_API_KEY",
        "HF_TOKEN",
        "LITELLM_MASTER_KEY",
        "SSL_KEY",
        "REQUESTS_CA_KEY",
        "CURL_TOKEN",
        "PYTHONSTARTUP_KEY",
        "XDG_KEY",
        "HTTPS_PROXY_TOKEN",
        "OPENAI_API_BASE_KEY",
        "MODEL_URL_TOKEN",
        "AZURE_ENDPOINT_KEY",
        "OLLAMA_HOST_KEY",
    ],
)
def test_a_key_named_variable_a_library_reads_settings_from_is_refused(name):
    assert secret_name_reason(name) == f"{name} can't hold a secret in the cloud"
    assert issues_for(keyed(name)) == [
        CloudIssue(
            "target.connection.api_key", f"{name} can't hold a secret in the cloud"
        )
    ]


def test_a_key_given_as_a_value_is_refused():
    target = m("gpt-4o", "OPENAI", ENDPOINT)
    target["connection"]["api_key"] = "sk-literal"
    spec = CampaignSpec.model_validate(campaign(target=target))
    assert cloud_issues(spec) == [
        CloudIssue(
            "target.connection.api_key", "the API key must be a ${VARIABLE} reference"
        )
    ]


# --- gateway marker headers and generation ------------------------------------------


def test_a_gateway_marker_with_headers_is_refused():
    gateway = {**GW, "connection": {**GW["connection"], "headers": {"Host": "x"}}}
    assert issues_for(gateway) == [
        CloudIssue(
            "target.connection.headers", "the HackAgent gateway takes no headers"
        )
    ]


@pytest.mark.parametrize(
    "generation",
    [
        {"extra_body": {"api_base": "http://127.0.0.1"}},
        {"response_format": {"type": "json_object"}},
        {"seed": 1},
        {"stop": "x"},
        {"thinking": True},
    ],
)
def test_a_gateway_marker_takes_only_plain_sampling(generation):
    (key,) = generation
    assert issues_for({**GW, "generation": generation}) == [
        CloudIssue(
            f"target.generation.{key}",
            "the HackAgent gateway takes only temperature, top_p and max_tokens",
        )
    ]


def test_a_gateway_marker_may_set_temperature_top_p_and_max_tokens():
    generation = {"temperature": 0.2, "top_p": 0.9, "max_tokens": 64}
    assert issues_for({**GW, "generation": generation}) == []


# --- technique parameters -----------------------------------------------------------

PROGRAM = (
    'TransformFxDecorator(transform_fx="import os\\ndef transform(prompt, '
    "assistant, random_state):\\n    return os.popen('id').read()\")"
)


def attack_issues(attack) -> list[CloudIssue]:
    spec = campaign(target=m("gpt-4o", "OPENAI"), attacks=[attack])
    return cloud_issues(CampaignSpec.model_validate(spec))


@pytest.mark.parametrize(
    "program",
    [
        PROGRAM,
        f"IdentityDecorator().then({PROGRAM})",
        # v1: one constructor per statement.
        f"IdentityDecorator()\n{PROGRAM}",
        # Not a program the compiler builds, refused by the name it contains.
        "TransformFxDecorator(",
    ],
)
def test_an_h4rm3l_program_that_runs_code_is_refused(program):
    syntax_version = 1 if "\n" in program else 2
    attack = {
        "name": "h4rm3l",
        "parameters": {"program": program, "syntax_version": syntax_version},
        "roles": {"decorator": GW},
    }
    assert attack_issues(attack) == [
        CloudIssue(
            "attacks.0.parameters.program",
            "TransformFxDecorator can't run in the cloud",
        )
    ]


@pytest.mark.parametrize(
    "program",
    [
        "refusal_suppression",
        "translate_zulu",
        "Base64Decorator().then(RoleplayingDecorator(prefix='TransformFxDecorator'))",
    ],
)
def test_an_h4rm3l_program_of_plain_decorators_is_allowed(program):
    attack = {
        "name": "h4rm3l",
        "parameters": {"program": program},
        "roles": {"decorator": GW},
    }
    assert attack_issues(attack) == []


# --- goals, paths and repository code ------------------------------------------------


@pytest.mark.parametrize(
    "dataset",
    [
        {"source": {"type": "provider", "provider": "file", "path": "/etc/passwd"}},
        {"source": {"type": "provider", "provider": "huggingface", "path": "x/y"}},
    ],
)
def test_goals_come_from_a_preset_or_the_campaign(dataset):
    spec = campaign(target=m("gpt-4o", "OPENAI"), dataset=dataset)
    assert cloud_issues(CampaignSpec.model_validate(spec)) == [
        CloudIssue(
            "dataset.source",
            "dataset source 'provider' can't be used in the cloud; use a preset or "
            "inline goals",
        )
    ]


def test_inline_goals_are_allowed():
    spec = campaign(
        target=m("gpt-4o", "OPENAI"),
        dataset={"source": {"type": "inline", "goals": ["a goal"]}},
    )
    assert cloud_issues(CampaignSpec.model_validate(spec)) == []


def test_trust_remote_code_is_refused_wherever_it_is():
    spec = campaign(
        target=m("gpt-4o", "OPENAI"),
        dataset={
            "source": {
                "type": "provider",
                "provider": "huggingface",
                "path": "x/y",
                "options": {"trust_remote_code": True},
            }
        },
    )
    issues = cloud_issues(CampaignSpec.model_validate(spec))
    assert (
        CloudIssue(
            "dataset.source.options.trust_remote_code",
            "trust_remote_code can't be used in the cloud",
        )
        in issues
    )


@pytest.mark.parametrize(
    ("key", "value"), [("cache_dir", "/tmp/anywhere"), ("revision", "attacker/main")]
)
def test_audit_dataset_paths_are_refused(key, value):
    spec = campaign(
        target=m("gpt-4o", "OPENAI"),
        evaluation={"audit": {"enabled": True, "dataset": {key: value}}},
    )
    assert cloud_issues(CampaignSpec.model_validate(spec)) == [
        CloudIssue(
            f"evaluation.audit.dataset.{key}", f"{key} can't be set in the cloud"
        )
    ]


def test_a_fixed_run_id_is_refused():
    spec = campaign(
        target=m("gpt-4o", "OPENAI"), execution={"output": {"run_id": "../../x"}}
    )
    assert cloud_issues(CampaignSpec.model_validate(spec)) == [
        CloudIssue("execution.output.run_id", "run_id can't be set in the cloud")
    ]
