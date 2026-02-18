# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Shared router factory for attack modules.

This module provides a unified factory function for creating AgentRouter
instances from configuration dictionaries. It eliminates the duplicated
~30-line router initialization pattern found across:

- advprefix/generate.py  (_initialize_generation_router)
- advprefix/evaluators.py (BaseEvaluator.__init__ router setup)
- pair/attack.py          (_initialize_attacker_router)

All three follow the same pattern: extract endpoint/model_id, handle API
key (env var fallback), build operational_config, create AgentRouter,
validate registry, extract registration key.

Usage:
    from hackagent.attacks.shared.router_factory import create_router

    router, reg_key = create_router(
        client=client,
        config={
            "identifier": "ollama/llama3",
            "endpoint": "http://localhost:11434/v1",
            "max_new_tokens": 500,
            "temperature": 0.7,
        },
        logger=logger,
        router_name="attacker",
    )
"""

import logging
import os
from typing import Any, Dict, Optional, Tuple

from hackagent.client import AuthenticatedClient
from hackagent.router.router import AgentRouter
from hackagent.router.types import AgentTypeEnum

logger = logging.getLogger("hackagent.attacks.shared.router_factory")


def create_router(
    client: AuthenticatedClient,
    config: Dict[str, Any],
    logger: Optional[logging.Logger] = None,
    router_name: Optional[str] = None,
) -> Tuple[AgentRouter, str]:
    """
    Create an AgentRouter from a configuration dictionary.

    This factory extracts endpoint, model identifier, API key, and
    operational parameters from a flat config dict and returns a
    fully-initialized AgentRouter with its registration key.

    Args:
        client: Authenticated client providing the default API key.
        config: Configuration dictionary. Expected keys:
            - identifier (str, required): Model identifier (e.g. "ollama/llama3").
            - endpoint (str, optional): API endpoint URL.
            - agent_type (str, optional): Agent type string, default "OPENAI_SDK".
            - api_key (str, optional): Explicit API key or env var name.
            - max_new_tokens (int, optional): Max tokens to generate.
            - temperature (float, optional): Sampling temperature.
            - top_p (float, optional): Top-p (nucleus) sampling.
            - request_timeout (int, optional): Request timeout in seconds.
            - agent_metadata (dict, optional): Extra metadata for the agent.
            Any additional keys in the dict are merged into agent_metadata.
        logger: Logger instance. Falls back to module-level logger.
        router_name: Human-readable name for logging (e.g. "generator",
            "attacker", "judge-harmbench"). Defaults to the identifier.

    Returns:
        Tuple of (AgentRouter, registration_key).

    Raises:
        ValueError: If ``identifier`` is missing from config.
        RuntimeError: If the AgentRouter fails to register the agent.

    Example:
        >>> router, key = create_router(
        ...     client=my_client,
        ...     config={"identifier": "gpt-4", "endpoint": "https://api.openai.com/v1"},
        ...     logger=my_logger,
        ...     router_name="attacker",
        ... )
        >>> response = router.route_request(registration_key=key, request_data={...})
    """
    log = logger or globals()["logger"]

    model_name = config.get("identifier")
    if not model_name:
        raise ValueError(
            "Router config must include an 'identifier' key "
            f"(e.g. 'ollama/llama3'). Got keys: {list(config.keys())}"
        )

    name = router_name or model_name
    endpoint = config.get("endpoint")

    # ---- API key resolution ----
    # Priority: explicit config key → env var lookup → client token
    api_key = client.token
    api_key_config = config.get("api_key")
    if api_key_config:
        env_key = os.environ.get(api_key_config)
        api_key = env_key if env_key else api_key_config

    # Also check agent_metadata for api_key (used by evaluators)
    agent_metadata = config.get("agent_metadata", {}) or {}
    metadata_api_key = agent_metadata.get("api_key")
    if metadata_api_key and not api_key_config:
        env_key = os.environ.get(metadata_api_key)
        api_key = env_key if env_key else metadata_api_key

    # ---- Operational config ----
    operational_config: Dict[str, Any] = {
        "name": config.get("model", model_name),
        "endpoint": endpoint,
        "api_key": api_key,
        "max_new_tokens": config.get("max_new_tokens"),
        "temperature": config.get("temperature"),
        "request_timeout": config.get("request_timeout"),
    }

    # Optional top_p
    if "top_p" in config:
        operational_config["top_p"] = config["top_p"]

    # Merge remaining metadata
    for key, value in agent_metadata.items():
        if key not in operational_config or operational_config[key] is None:
            operational_config[key] = value

    # ---- Agent type resolution ----
    agent_type_str = config.get("agent_type", "OPENAI_SDK")
    try:
        agent_type = AgentTypeEnum(agent_type_str.upper())
    except ValueError:
        log.warning(
            f"Invalid agent_type '{agent_type_str}' for {name}, "
            "defaulting to OPENAI_SDK"
        )
        agent_type = AgentTypeEnum.OPENAI_SDK

    # ---- Create router ----
    log.debug(f"Creating AgentRouter for '{name}' ({model_name} via {endpoint})")

    router = AgentRouter(
        client=client,
        name=model_name,
        agent_type=agent_type,
        endpoint=endpoint,
        metadata=agent_metadata if agent_metadata else operational_config.copy(),
        adapter_operational_config=operational_config,
        overwrite_metadata=True,
    )

    if not router._agent_registry:  # type: ignore[attr-defined]
        raise RuntimeError(
            f"AgentRouter for '{name}' initialized but no agent was registered. "
            f"Config: identifier={model_name}, endpoint={endpoint}, "
            f"agent_type={agent_type}"
        )

    registration_key = next(iter(router._agent_registry.keys()))  # type: ignore[attr-defined]
    log.debug(f"Router '{name}' ready. Registration key: {registration_key}")

    return router, registration_key
