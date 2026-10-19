# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unified model execution."""

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
