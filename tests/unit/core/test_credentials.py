"""The public credential contract, including configuration and client boundaries."""

import inspect
import json
from unittest.mock import patch

import pytest

from hackagent.core.contracts import ModelSpec
from hackagent.core.credentials import (
    CredentialError,
    is_gateway_endpoint,
    prepare_credentials,
    resolve_api_key,
)
from hackagent.core.settings import Mode, Settings
from hackagent.models.build import build_embedder, build_model
from hackagent.models.config import ConnectionSpec, ModelConfig
from hackagent.orchestrator.campaign.loader import load_campaign
from hackagent.orchestrator.campaign.spec import StorageSpec


def test_only_one_public_credential_field():
    for cls in (ModelSpec, ConnectionSpec, StorageSpec):
        assert "api_key" in cls.model_fields
        assert "api_key_env" not in cls.model_fields
    assert "api_key_env" not in inspect.signature(Settings.resolve).parameters
    assert "api_key" not in inspect.signature(build_model).parameters
    assert "api_key" not in inspect.signature(build_embedder).parameters


def test_default_is_only_hackagent():
    assert (
        resolve_api_key(
            use_default=True,
            env={"HACKAGENT_API_KEY": "platform", "OPENAI_API_KEY": "other"},
        )
        == "platform"
    )
    assert resolve_api_key(use_default=True, env={"OPENAI_API_KEY": "other"}) is None
    assert resolve_api_key(env={"HACKAGENT_API_KEY": "platform"}) is None


@pytest.mark.parametrize("value", [None, "", " "])
def test_selected_reference_never_falls_back(value):
    env = {"HACKAGENT_API_KEY": "fallback"}
    if value is not None:
        env["CUSTOM_KEY"] = value
    with pytest.raises(CredentialError, match="CUSTOM_KEY"):
        resolve_api_key("${CUSTOM_KEY}", use_default=True, env=env)


def test_plain_strings_are_not_variable_names():
    assert (
        resolve_api_key("HACKAGENT_API_KEY", env={"HACKAGENT_API_KEY": "secret"})
        == "HACKAGENT_API_KEY"
    )


def test_file_literals_are_rejected_without_their_values():
    with pytest.raises(CredentialError) as error:
        prepare_credentials({"connection": {"api_key": "do-not-echo"}}, from_file=True)
    assert "do-not-echo" not in str(error.value)


def test_model_exports_reference_and_never_resolved_value(monkeypatch):
    monkeypatch.setenv("HACKAGENT_API_KEY", "private-value")
    spec = ModelSpec(identifier="model", api_key="${HACKAGENT_API_KEY}")
    assert spec.api_key == "private-value"
    assert spec.model_dump()["api_key"] == "${HACKAGENT_API_KEY}"
    assert "private-value" not in repr(spec)
    assert "private-value" not in spec.model_dump_json()
    direct = ModelSpec(identifier="model", api_key="private-value")
    assert "private-value" not in direct.model_dump_json()


def test_reference_is_resolved_once_at_loading_boundary(monkeypatch):
    monkeypatch.setenv("HACKAGENT_API_KEY", "first")
    loaded = prepare_credentials({"api_key": "${HACKAGENT_API_KEY}"}, from_file=True)
    monkeypatch.setenv("HACKAGENT_API_KEY", "second")
    spec = ModelSpec(identifier="model", **loaded)
    assert spec.api_key == "first"
    assert spec.model_dump()["api_key"] == "${HACKAGENT_API_KEY}"


@pytest.mark.parametrize(
    "endpoint,expected",
    [
        ("https://api.hackagent.dev/v1", True),
        ("https://api.hackagent.dev:443/v1/", True),
        ("https://api.hackagent.dev.example.test/v1", False),
        ("https://api.hackagent.dev:444/v1", False),
        ("http://api.hackagent.dev/v1", False),
        ("https://api.hackagent.dev/other/v1", False),
        ("https://api.hackagent.dev/v10", False),
        ("https://api.hackagent.dev/v1?redirect=other", False),
    ],
)
def test_gateway_identity_checks_origin_and_exact_path(endpoint, expected):
    assert is_gateway_endpoint(endpoint, "https://api.hackagent.dev") is expected


@pytest.mark.parametrize("backend", ["remote", Mode.REMOTE])
def test_backend_accepts_enum_and_string(tmp_path, backend):
    settings = Settings.resolve(
        backend=backend,
        env={"HACKAGENT_API_KEY": "secret"},
        config_path=tmp_path / "absent",
    )
    assert settings.mode is Mode.REMOTE


def test_chat_and_embeddings_receive_same_runtime_key():
    config = ModelConfig(
        name="custom-model",
        connection=ConnectionSpec(
            provider="custom",
            type="OPENAI",
            endpoint="https://custom.example/v1",
            api_key="runtime-key",
        ),
    )
    with patch("hackagent.models.build.LiteLLMModel") as chat:
        build_model(config)
    assert (
        chat.call_args.kwargs["connection"].api_key.get_secret_value() == "runtime-key"
    )
    with patch(
        "litellm.embedding", return_value={"data": [{"embedding": [1.0, 2.0]}]}
    ) as embedding:
        import asyncio

        asyncio.run(build_embedder(config)(["hello"]))
    assert embedding.call_args.kwargs["api_key"] == "runtime-key"


def test_saved_settings_reference_overrides_default_and_remains_safe(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"api_key": "${CUSTOM_KEY}"}))
    settings = Settings.resolve(
        config_path=path, env={"CUSTOM_KEY": "custom", "HACKAGENT_API_KEY": "default"}
    )
    assert settings.api_key == "custom"
    assert settings.mode is Mode.LOCAL
    assert "custom" not in repr(settings)


def test_campaign_file_rejects_literal_before_validation_can_echo_it(tmp_path):
    path = tmp_path / "campaign.yaml"
    path.write_text('target:\n  connection:\n    api_key: "never-in-errors"\n')
    with pytest.raises(CredentialError) as error:
        load_campaign(path)
    assert "never-in-errors" not in str(error.value)


def test_explicit_runtime_value_overrides_an_unused_file_reference(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"api_key": "${NOT_SELECTED}"}))
    settings = Settings.resolve(api_key="injected", config_path=path, env={})
    assert settings.api_key == "injected"


def test_transport_does_not_fall_back_to_provider_environment(monkeypatch):
    from hackagent.models.config import ModelConnection

    monkeypatch.setenv("OPENAI_API_KEY", "must-not-use")
    assert ModelConnection().to_litellm()["api_key"] == "not-needed"


@pytest.mark.parametrize(
    "endpoint", ["https://api.hackagent.dev/v1", "https://other.example/v1"]
)
def test_builders_never_reselect_an_ambient_gateway(endpoint, monkeypatch):
    from hackagent.models.factory import ModelFactory
    from hackagent.models.embeddings import embedding_request_kwargs

    monkeypatch.setenv("HACKAGENT_API_KEY", "must-not-leak")
    monkeypatch.setenv("HACKAGENT_BASE_URL", endpoint.removesuffix("/v1"))
    settings = Settings.resolve(
        api_key="selected-private-key",
        base_url="https://private.example",
        config_path="/nonexistent",
        env={},
    )
    model = ModelFactory(settings).for_role(
        ModelSpec(identifier="model", endpoint=endpoint)
    )
    kwargs = model._litellm_kwargs([], {})
    assert kwargs["api_key"] == "not-needed"
    embedded = embedding_request_kwargs({"identifier": "model", "endpoint": endpoint})
    assert embedded["api_key"] == "not-needed"


@pytest.mark.parametrize("explicit_key", [None, "own-model-key"])
def test_campaign_binds_selected_gateway_to_chat_and_embedding(
    explicit_key, monkeypatch
):
    from hackagent.models.factory import ModelFactory
    from hackagent.orchestrator.campaign import CampaignSpec, resolve_campaign
    from tests.unit.campaign.fakes import campaign, ScriptedModel

    monkeypatch.setenv("HACKAGENT_API_KEY", "wrong-ambient-key")
    settings = Settings.resolve(
        api_key="selected-key",
        base_url="https://private.example/prefix",
        env={},
        config_path="/nonexistent",
    )
    config = ModelConfig(
        name="model",
        connection=ConnectionSpec(
            provider="gateway",
            type="OPENAI",
            endpoint="https://private.example/prefix/v1",
            api_key=explicit_key,
        ),
    )
    expected = explicit_key or "selected-key"
    bound = ModelFactory(settings).with_model_credentials(config)
    assert bound.connection.api_key == expected
    assert config.connection.api_key == explicit_key
    assert "selected-key" not in bound.model_dump_json()
    with patch("hackagent.models.build.LiteLLMModel") as chat:
        build_model(bound)
    assert chat.call_args.kwargs["connection"].api_key.get_secret_value() == expected
    import asyncio

    with patch(
        "litellm.embedding", return_value={"data": [{"embedding": [1.0]}]}
    ) as embedding:
        asyncio.run(build_embedder(bound)(["hello"]))
    assert embedding.call_args.kwargs["api_key"] == expected

    spec = CampaignSpec.model_validate(campaign())
    spec = spec.model_copy(update={"target": config})
    seen = []

    def build(config, **kwargs):
        seen.append(config)
        return ScriptedModel()

    resolve_campaign(spec, settings=settings, build=build, load=lambda _: [])
    assert seen[0].connection.api_key == expected
    assert spec.target.connection.api_key == explicit_key


@pytest.mark.parametrize(
    "name", ["ollama_chat/llama3", "bedrock/anthropic.claude", "vertex_ai/gemini-pro"]
)
def test_alternative_auth_chat_does_not_require_or_inject_an_api_key(name, monkeypatch):
    monkeypatch.setenv("HACKAGENT_API_KEY", "not-for-provider")
    monkeypatch.setenv("OPENAI_API_KEY", "not-for-provider")
    config = ModelConfig(
        name=name, connection=ConnectionSpec(provider="provider", type="LITELLM")
    )
    kwargs = build_model(config)._litellm_kwargs([], {})
    assert kwargs["model"] == name
    assert "api_key" not in kwargs


@pytest.mark.parametrize(
    "name", ["bedrock/amazon.titan-embed-text-v1", "vertex_ai/text-embedding-004"]
)
def test_cloud_identity_embeddings_do_not_require_an_api_key(name):
    import asyncio

    config = ModelConfig(
        name=name, connection=ConnectionSpec(provider="cloud", type="LITELLM")
    )
    with patch(
        "litellm.embedding", return_value={"data": [{"embedding": [1.0]}]}
    ) as embedding:
        asyncio.run(build_embedder(config)(["hello"]))
    assert embedding.call_args.kwargs["model"] == name
    assert "api_key" not in embedding.call_args.kwargs


@pytest.mark.parametrize(
    "name", ["openai/gpt-4o-mini", "anthropic/claude", "groq/llama"]
)
def test_api_key_providers_still_require_an_explicit_key(name, monkeypatch):
    monkeypatch.setenv("HACKAGENT_API_KEY", "not-for-provider")
    monkeypatch.setenv("OPENAI_API_KEY", "not-for-provider")
    config = ModelConfig(
        name=name, connection=ConnectionSpec(provider="external", type="LITELLM")
    )
    with pytest.raises(CredentialError):
        build_model(config)


def test_embedding_timeout_reaches_both_request_paths():
    import asyncio
    from hackagent.models.embeddings import request_embedding

    config = ModelConfig(
        name="embed",
        connection=ConnectionSpec(
            provider="local",
            type="OPENAI",
            endpoint="http://localhost:8000/v1",
            timeout=7.5,
        ),
    )
    with patch(
        "litellm.embedding", return_value={"data": [{"embedding": [1.0]}]}
    ) as embedding:
        asyncio.run(build_embedder(config)(["hello"]))
        assert embedding.call_args.kwargs["timeout"] == 7.5
        request_embedding(
            {
                "identifier": "embed",
                "endpoint": "http://localhost:8000/v1",
                "request_timeout": 3.5,
            },
            "hello",
        )
        assert embedding.call_args.kwargs["timeout"] == 3.5
