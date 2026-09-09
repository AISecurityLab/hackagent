# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Offline embedding provider and response validation regression tests."""

import json
import logging
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import patch

import httpx
import numpy as np
import pytest

from hackagent.attacks.shared.embedding_utils import (
    embedding_request_kwargs,
    extract_embedding_vector,
    normalize_embedding_endpoint,
    request_embedding,
)


@pytest.mark.parametrize(
    "suffix",
    [
        "",
        "/",
        "/v1",
        "/v1/",
        "/v1/embeddings",
        "/v1/embeddings/",
        "/api/embed",
        "/api/embeddings",
    ],
)
@pytest.mark.parametrize(
    "model",
    [
        "embeddinggemma:300m",
        "ollama/embeddinggemma:300m",
        "ollama_chat/embeddinggemma:300m",
    ],
)
def test_ollama_endpoint_and_prefix_normalization(suffix, model):
    kwargs = embedding_request_kwargs(
        {
            "identifier": model,
            "endpoint": "http://ollama.test/proxy" + suffix,
            "agent_type": "OLLAMA",
        }
    )
    assert kwargs == {
        "model": "embeddinggemma:300m",
        "custom_llm_provider": "openai",
        "encoding_format": "float",
        "api_base": "http://ollama.test/proxy/v1",
        "api_key": "ollama",
    }


@pytest.mark.parametrize(
    ("endpoint", "expected"),
    [
        ("https://example.test", "https://example.test/v1"),
        ("https://example.test/v1/", "https://example.test/v1"),
        ("https://example.test/v1/embeddings/", "https://example.test/v1"),
        ("https://example.test/api/v1/embeddings", "https://example.test/api/v1"),
        ("https://example.test/custom", "https://example.test/custom"),
        ("https://example.test/embeddings", "https://example.test"),
    ],
)
def test_compatible_endpoint_normalization(endpoint, expected):
    assert normalize_embedding_endpoint(endpoint) == expected


@pytest.mark.parametrize(
    ("configured", "expected"),
    [
        ("explicit-key", "explicit-key"),
        ("EMBEDDING_KEY", "environment-key"),
        ("${EMBEDDING_KEY}", "environment-key"),
        (None, "openai-key"),
    ],
)
def test_openai_keys(configured, expected):
    with patch.dict(
        "os.environ",
        {"EMBEDDING_KEY": "environment-key", "OPENAI_API_KEY": "openai-key"},
        clear=True,
    ):
        kwargs = embedding_request_kwargs(
            {
                "identifier": "openai/text-embedding-3-small",
                "agent_type": "OPENAI_SDK",
                "api_key": configured,
            }
        )
    assert kwargs["api_key"] == expected
    assert kwargs["model"] == "text-embedding-3-small"
    assert "api_base" not in kwargs


def test_no_storage_key_fallback_and_unset_env_reference():
    with patch.dict("os.environ", {"HACKAGENT_API_KEY": "storage-token"}, clear=True):
        kwargs = embedding_request_kwargs({"identifier": "text-embedding-3-small"})
        assert "api_key" not in kwargs
        with pytest.raises(ValueError, match="is unset"):
            embedding_request_kwargs(
                {"identifier": "model", "api_key": "${MISSING_KEY}"}
            )


def test_ollama_explicit_auth_and_slash_model_preserved():
    kwargs = embedding_request_kwargs(
        {
            "identifier": "org/embedding-model",
            "agent_type": "OLLAMA",
            "api_key": "ollama-auth",
        }
    )
    assert kwargs["model"] == "org/embedding-model"
    assert kwargs["api_key"] == "ollama-auth"


def test_litellm_provider_prefix_preserved():
    kwargs = embedding_request_kwargs(
        {
            "identifier": "cohere/embed-english-v3.0",
            "agent_type": "LITELLM",
        }
    )
    assert kwargs["model"] == "cohere/embed-english-v3.0"
    assert "custom_llm_provider" not in kwargs


@pytest.mark.parametrize(
    "value",
    [
        None,
        [],
        "signature",
        ["1"],
        [True],
        [[1, 2]],
        [float("nan")],
        [float("inf")],
        [-float("inf")],
        [1e40],
        [1 + 2j],
        [None],
    ],
)
def test_invalid_embedding_vectors(value):
    with pytest.raises(ValueError):
        extract_embedding_vector({"data": [{"embedding": value}]})


@pytest.mark.parametrize(
    "response",
    [
        None,
        {},
        {"data": []},
        {"data": "bad"},
        {"data": [{}, {}]},
        {"embeddings": [[1, 2]]},
    ],
)
def test_malformed_embedding_payload(response):
    with pytest.raises(ValueError):
        extract_embedding_vector(response)


def test_object_response_validation():
    vector = extract_embedding_vector(
        SimpleNamespace(data=[SimpleNamespace(embedding=[0.25, 1])])
    )
    np.testing.assert_array_equal(vector, [0.25, 1])
    assert vector.dtype == np.float32


@pytest.mark.parametrize("suffix", ["", "/v1", "/v1/embeddings", "/api/embed"])
def test_real_litellm_dispatch_uses_compatible_embedding_http_request(
    suffix, embedding_http_transport
):
    """Mock HTTP transport, not LiteLLM: exercise SDK URL construction offline."""
    vector = request_embedding(
        {
            "identifier": "ollama/embeddinggemma:300m",
            "agent_type": "OLLAMA",
            "endpoint": "http://embedding.test" + suffix,
        },
        "text to embed",
    )
    np.testing.assert_array_equal(vector, [0.25, 0.75])
    assert len(embedding_http_transport) == 1
    request = embedding_http_transport[0]
    assert str(request.url) == "http://embedding.test/v1/embeddings"
    payload = json.loads(request.content)
    assert payload["input"] == ["text to embed"]
    assert payload["model"] == "embeddinggemma:300m"
    assert "messages" not in payload


_LITELLM_COST_MAP_URL = (
    "https://raw.githubusercontent.com/BerriAI/litellm/main/"
    "model_prices_and_context_window.json"
)


@pytest.fixture(scope="module")
def local_litellm_cost_map():
    from litellm.litellm_core_utils.get_model_cost_map import GetModelCostMap

    return GetModelCostMap.load_local_model_cost_map()


@pytest.fixture
def embedding_http_transport(monkeypatch, local_litellm_cost_map):
    """Intercept real SDK requests; no provider or embedding function is mocked."""
    monkeypatch.setenv("LITELLM_LOCAL_MODEL_COST_MAP", "True")
    requests = []
    unexpected_requests = []

    def send(_client, request, **kwargs):
        # A refresh started by another test can already be in flight before the
        # environment flag takes effect. Serve bundled prices, never the network.
        if request.method == "GET" and str(request.url) == _LITELLM_COST_MAP_URL:
            return httpx.Response(200, request=request, json=local_litellm_cost_map)
        if request.method != "POST" or not request.url.path.endswith("/embeddings"):
            unexpected_requests.append((request.method, str(request.url)))
            raise AssertionError(
                f"Unexpected network request: {unexpected_requests[-1]}"
            )
        requests.append(request)
        return httpx.Response(
            200,
            request=request,
            json={
                "object": "list",
                "model": json.loads(request.content)["model"],
                "data": [
                    {"object": "embedding", "index": 0, "embedding": [0.25, 0.75]}
                ],
                "usage": {"prompt_tokens": 1, "total_tokens": 1},
            },
        )

    with patch.object(httpx.Client, "send", send):
        yield requests
    assert not unexpected_requests


def test_embedding_transport_isolates_concurrent_cost_map_refresh(
    embedding_http_transport, local_litellm_cost_map
):
    """Reproduce an already-started refresh that bypasses the environment guard."""
    from litellm.litellm_core_utils.get_model_cost_map import GetModelCostMap

    with ThreadPoolExecutor(max_workers=1) as executor:
        refresh = executor.submit(
            GetModelCostMap.fetch_remote_model_cost_map, _LITELLM_COST_MAP_URL
        )
        vector = request_embedding(
            {
                "identifier": "openai/text-embedding-3-small",
                "agent_type": "OPENAI_SDK",
                "endpoint": "https://compatible.test/v1",
                "api_key": "offline-provider-key",
            },
            "text to embed",
        )
        assert refresh.result() == local_litellm_cost_map
    np.testing.assert_array_equal(vector, [0.25, 0.75])
    assert len(embedding_http_transport) == 1
    request = embedding_http_transport[0]
    assert str(request.url) == "https://compatible.test/v1/embeddings"
    assert json.loads(request.content)["model"] == "openai/text-embedding-3-small"


@pytest.mark.parametrize("consumer", ["autodan", "rag", "preflight", "legacy"])
@pytest.mark.parametrize(
    "endpoint", ["https://openrouter.ai/api/v1", "https://compatible.test/custom/v1"]
)
@pytest.mark.parametrize(
    "model",
    [
        "openai/text-embedding-3-small",
        "acme/embedding-model",
        "azure/native-model",
        "ollama/native-model",
    ],
)
def test_compatible_transport_preserves_server_model_names(
    consumer, endpoint, model, embedding_http_transport
):
    from hackagent.attacks.orchestrator import AttackOrchestrator
    from hackagent.attacks.techniques.autodan_turbo.strategy_library import (
        StrategyLibrary,
    )
    from hackagent.attacks.techniques.rag.attack import get_embeddings

    config = {
        "identifier": model,
        "agent_type": "OPENAI_SDK",
        "endpoint": endpoint,
        "api_key": "compatible-provider-key",
    }
    if consumer == "autodan":
        vector = StrategyLibrary(embedder_config=config).embed("text to embed")
        np.testing.assert_array_equal(vector, [0.25, 0.75])
    elif consumer == "rag":
        vectors = get_embeddings(["text to embed"], config, logging.getLogger(__name__))
        np.testing.assert_array_equal(vectors, [[0.25, 0.75]])
    elif consumer == "legacy":
        vector = StrategyLibrary(
            embedding_model=f"openai/{model}",
            embedding_api_base=endpoint,
            embedding_api_key="compatible-provider-key",
        ).embed("text to embed")
        np.testing.assert_array_equal(vector, [0.25, 0.75])
    else:
        orchestrator = object.__new__(AttackOrchestrator)
        assert orchestrator._probe_embedding_target({"config": config}) is None

    assert len(embedding_http_transport) == 1
    request = embedding_http_transport[0]
    assert str(request.url) == f"{endpoint}/embeddings"
    assert json.loads(request.content)["model"] == model
    assert request.headers["Authorization"] == "Bearer compatible-provider-key"


@pytest.mark.parametrize("mode", ["normal", "legacy"])
@pytest.mark.parametrize("path", ["", "/proxy"])
def test_native_azure_transport_preserves_provider_base(
    mode, path, embedding_http_transport
):
    from hackagent.attacks.techniques.autodan_turbo.strategy_library import (
        StrategyLibrary,
    )

    endpoint = f"https://embedding-resource.openai.azure.com{path}"
    if mode == "legacy":
        library = StrategyLibrary(
            embedding_model="azure/embedding-deployment",
            embedding_api_base=endpoint,
            embedding_api_key="azure-provider-key",
        )
    else:
        library = StrategyLibrary(
            embedder_config={
                "identifier": "azure/embedding-deployment",
                "agent_type": "LITELLM",
                "endpoint": endpoint,
                "api_key": "azure-provider-key",
            }
        )
    with patch.dict("os.environ", {"AZURE_API_VERSION": "2024-02-01"}):
        np.testing.assert_array_equal(library.embed("text to embed"), [0.25, 0.75])
    assert len(embedding_http_transport) == 1
    request = embedding_http_transport[0]
    assert (
        request.url.path == f"{path}/openai/deployments/embedding-deployment/embeddings"
    )
    assert request.url.params["api-version"] == "2024-02-01"
    assert json.loads(request.content)["model"] == "embedding-deployment"
    assert request.headers["api-key"] == "azure-provider-key"


@pytest.mark.parametrize(
    "model",
    ["azure/deployment", "cohere/embed-v3", "bedrock/amazon.titan-embed-text-v2:0"],
)
@pytest.mark.parametrize(
    "endpoint", ["https://native.test", "https://native.test/embeddings"]
)
def test_native_litellm_bases_are_not_openai_normalized(model, endpoint):
    kwargs = embedding_request_kwargs(
        {
            "identifier": model,
            "agent_type": "LITELLM",
            "endpoint": endpoint,
            "api_key": "native-key",
        }
    )
    assert kwargs["api_base"] == endpoint
    assert kwargs["model"] == model


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://api.openai.com",
        "https://api.openai.com/v1",
        "https://api.openai.com/v1/embeddings",
    ],
)
@pytest.mark.parametrize("mode", ["normal", "legacy"])
def test_openai_transport_still_removes_only_routing_prefix(
    endpoint, mode, embedding_http_transport
):
    from hackagent.attacks.techniques.autodan_turbo.strategy_library import (
        StrategyLibrary,
    )

    if mode == "legacy":
        library = StrategyLibrary(
            embedding_model="openai/text-embedding-3-small",
            embedding_api_base=endpoint,
            embedding_api_key="openai-provider-key",
        )
    else:
        library = StrategyLibrary(
            embedder_config={
                "identifier": "openai/text-embedding-3-small",
                "agent_type": "OPENAI_SDK",
                "endpoint": endpoint,
                "api_key": "openai-provider-key",
            }
        )
    np.testing.assert_array_equal(library.embed("text to embed"), [0.25, 0.75])
    assert len(embedding_http_transport) == 1
    request = embedding_http_transport[0]
    assert str(request.url) == "https://api.openai.com/v1/embeddings"
    assert json.loads(request.content)["model"] == "text-embedding-3-small"
    assert request.headers["Authorization"] == "Bearer openai-provider-key"
