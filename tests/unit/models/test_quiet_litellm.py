# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""LiteLLM's stdout banner is off, and an embedder that fails says so."""

from __future__ import annotations

import logging

import pytest

from hackagent.models._litellm import litellm


def test_litellm_prints_no_banner_when_it_raises():
    assert litellm().suppress_debug_info is True


def _failing_embedder(monkeypatch, embedding):
    from hackagent.models import build
    from hackagent.models.config import ModelConfig

    monkeypatch.setattr(litellm(), "embedding", embedding)
    config = ModelConfig.model_validate(
        {
            "name": "mini",
            "connection": {
                "provider": "vllm",
                "type": "OPENAI",
                "endpoint": "http://127.0.0.1:9/v1",
            },
        }
    )
    return build.build_embedder(config)


def _warnings_when_embedding(embed, caplog):
    from hackagent.models import build

    logger = logging.getLogger("hackagent")
    propagate, logger.propagate = logger.propagate, True
    try:
        with caplog.at_level(logging.WARNING, logger="hackagent.models.build"):
            with pytest.raises(Exception):
                build.asyncio.run(embed(["a long text"]))
    finally:
        logger.propagate = propagate
    return caplog.text


def test_a_failing_embedder_logs_why(monkeypatch, caplog):
    def refuse(**_):
        raise RuntimeError("maximum context length is 256 tokens\nlong tail")

    text = _warnings_when_embedding(_failing_embedder(monkeypatch, refuse), caplog)
    assert (
        "embedder mini failed: RuntimeError: maximum context length is 256 tokens"
        in text
    )
    assert "long tail" not in text


def test_a_reply_without_a_usable_vector_logs_why(monkeypatch, caplog):
    def empty(**_):
        return {"data": [{"embedding": []}]}

    text = _warnings_when_embedding(_failing_embedder(monkeypatch, empty), caplog)
    assert "embedder mini failed" in text
