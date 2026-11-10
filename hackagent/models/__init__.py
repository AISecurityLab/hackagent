# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unified model execution: one interface for every target and role model.

A :class:`ModelConfig` (from a campaign file or the API) is turned into a
:class:`Model` by :func:`build_model`; every backend (LiteLLM providers,
Google ADK, CLI agents, live web chatbots) answers ``complete`` /
``acomplete`` with a :class:`ModelResponse` and returns provider failures as
values instead of raising. :class:`GuardedModel` and the retry wrapper add
guardrails and retries around any backend, and :class:`ModelFactory` builds
role models with the platform gateway's credentials.
"""

from .build import (
    ModelCallError,
    as_completion,
    build_embedder,
    build_model,
    embedder_is_reachable,
)
from .config import (
    ConnectionSpec,
    GenerationSpec,
    ModelConfig,
    ModelConnection,
    ModelGeneration,
)
from .connect import check_supported, connect
from .factory import ModelFactory
from .guardrail import GuardedModel
from .model import Model, Reachability
from .response import ModelResponse

__all__ = [
    "ConnectionSpec",
    "GenerationSpec",
    "GuardedModel",
    "Model",
    "ModelCallError",
    "ModelConfig",
    "ModelConnection",
    "ModelFactory",
    "ModelGeneration",
    "ModelResponse",
    "Reachability",
    "as_completion",
    "build_embedder",
    "build_model",
    "embedder_is_reachable",
    "check_supported",
    "connect",
]
