# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import logging
from typing import Any, Dict, Optional, Type

from hackagent.server.storage.base import AgentRecord, StorageBackend
from hackagent.router.adapters.base import Agent
from hackagent.router.types import AgentTypeEnum

# Adapter imports - these are imported at module level for backwards compatibility
# with test patching (tests patch hackagent.router.router.LiteLLMAgent etc.)
# The actual heavy dependency (litellm) is lazy-loaded within LiteLLMAgent
from hackagent.router.adapters import ADKAgent
from hackagent.router.adapters.litellm import LiteLLMAgent
from hackagent.router.adapters.openai import OpenAIAgent
from hackagent.router.adapters.ollama import OllamaAgent

# Use explicit hierarchical logger name for clarity
logger = logging.getLogger("hackagent.router")

# --- Agent Type to Adapter Mapping ---
AGENT_TYPE_TO_ADAPTER_MAP: Dict[AgentTypeEnum, Type[Agent]] = {
    AgentTypeEnum.GOOGLE_ADK: ADKAgent,
    AgentTypeEnum.LITELLM: LiteLLMAgent,
    AgentTypeEnum.OPENAI_SDK: OpenAIAgent,
    AgentTypeEnum.OLLAMA: OllamaAgent,
    AgentTypeEnum.LANGCHAIN: LiteLLMAgent,  # LangChain agents can use LiteLLM adapter
    # Add other agent types and their corresponding adapters here
}


class AgentRouter:
    """
    Manages the configuration and request routing for a single agent instance.

    The `AgentRouter` is responsible for initializing an agent, which includes:
    1.  Resolving organizational context via the storage backend.
    2.  Ensuring the agent is registered in the storage backend.
    3.  Instantiating the appropriate adapter (e.g., `ADKAgent`, `LiteLLMAgent`)
        based on the `agent_type`.
    4.  Storing this adapter for subsequent request routing.

    Attributes:
        backend: The StorageBackend (RemoteBackend or LocalBackend).
        organization_id: The UUID of the organization associated with the backend.
        user_id_str: The string user ID associated with the backend context.
        backend_agent: The `AgentRecord` representing this agent in storage.
        _agent_registry: Dict mapping agent ID → instantiated adapter `Agent` objects.
    """

    def __init__(
        self,
        backend: StorageBackend,
        name: str,
        agent_type: AgentTypeEnum,
        endpoint: str,
        metadata=None,
        adapter_operational_config=None,
        overwrite_metadata: bool = True,
    ):
        """
        Initializes the AgentRouter and configures a single agent.

        Args:
            backend: StorageBackend (RemoteBackend or LocalBackend).
            name: Name for the agent in storage.
            agent_type: The type of agent (e.g., AgentTypeEnum.LITELLM).
            endpoint: API endpoint URL for the agent service.
            metadata: Optional metadata to store with the agent record.
            adapter_operational_config: Runtime config for the adapter.
            overwrite_metadata: If True, update agent metadata when it differs.

        Raises:
            ValueError: If the agent_type is unsupported or adapter init fails.
            RuntimeError: If backend communication fails.
        """
        self.backend = backend
        self._agent_registry: dict = {}

        context = self.backend.get_context()
        self.organization_id = context.org_id
        self.user_id_str = context.user_id
        logger.info(
            f"AgentRouter context: Organization ID={self.organization_id}, "
            f"User ID={self.user_id_str}"
        )

        if agent_type not in AGENT_TYPE_TO_ADAPTER_MAP:
            raise ValueError(
                f"Unsupported agent type: {agent_type}. "
                f"Supported types: {list(AGENT_TYPE_TO_ADAPTER_MAP.keys())}"
            )

        actual_metadata = {k: v for k, v in (metadata or {}).items() if v is not None}

        current_adapter_op_config = (
            adapter_operational_config.copy() if adapter_operational_config else {}
        )

        if agent_type == AgentTypeEnum.GOOGLE_ADK:
            if "user_id" not in current_adapter_op_config:
                current_adapter_op_config["user_id"] = self.user_id_str
                logger.info(
                    f"ADK Agent: Using fetched User ID '{self.user_id_str}' for adapter operational config."
                )
            else:
                logger.warning(
                    f"ADK Agent: 'user_id' was already present in adapter_operational_config "
                    f"('{current_adapter_op_config['user_id']}'). Using that value instead of fetched one."
                )

        self.backend_agent: AgentRecord = self.backend.create_or_update_agent(
            name=name,
            agent_type=agent_type.value,
            endpoint=endpoint,
            metadata=actual_metadata,
            overwrite_metadata=overwrite_metadata,
        )

        registration_key = str(self.backend_agent.id)

        self._configure_and_instantiate_adapter(
            name=name,
            agent_type=agent_type,
            registration_key=registration_key,
            adapter_operational_config=current_adapter_op_config,
        )

    def _configure_and_instantiate_adapter(
        self,
        name: str,
        agent_type: AgentTypeEnum,
        registration_key: str,
        adapter_operational_config: Optional[Dict[str, Any]],
    ) -> None:
        """
        Configures, instantiates, and registers the appropriate agent adapter.

        This method selects the adapter class based on `agent_type`, prepares its
        specific configuration by merging `adapter_operational_config` with details
        from `self.backend_agent` (like name, endpoint, or specific metadata fields
        depending on the agent type), and then creates an instance of the adapter.
        The instantiated adapter is stored in `self._agent_registry` using the
        `registration_key` (backend agent ID).

        Args:
            name: The name of the agent (primarily for logging/identification).
            agent_type: The `AgentTypeEnum` of the agent.
            registration_key: The backend ID of the agent, used as the key for
                storing the adapter in the registry.
            adapter_operational_config: The base operational configuration for the
                adapter, which will be augmented with type-specific details.

        Raises:
            ValueError: If essential configuration for an adapter type is missing
                (e.g., model name for LiteLLM) or if adapter instantiation fails.
        """
        adapter_class = AGENT_TYPE_TO_ADAPTER_MAP[agent_type]

        logger.debug(
            f"ROUTER_DEBUG: adapter_class is: {adapter_class}, type: {type(adapter_class)}, id: {id(adapter_class)}"
        )

        adapter_instance_config = (
            adapter_operational_config.copy() if adapter_operational_config else {}
        )

        if agent_type == AgentTypeEnum.GOOGLE_ADK:
            adapter_instance_config["name"] = self.backend_agent.name
            adapter_instance_config["endpoint"] = str(self.backend_agent.endpoint)
            if "user_id" not in adapter_instance_config:
                logger.error(
                    f"CRITICAL: user_id not found in adapter_instance_config for ADK agent '{self.backend_agent.name}' just before adapter instantiation. This should have been set in __init__."
                )
                adapter_instance_config["user_id"] = self.user_id_str

        elif agent_type in [AgentTypeEnum.LITELLM, AgentTypeEnum.LANGCHAIN]:
            if "name" not in adapter_instance_config:
                if (
                    isinstance(self.backend_agent.metadata, dict)
                    and "name" in self.backend_agent.metadata
                ):
                    adapter_instance_config["name"] = self.backend_agent.metadata[
                        "name"
                    ]
                else:
                    logger.warning(
                        f"Agent '{name}' (Type: {agent_type.value}) missing 'name' (model string) in metadata. "
                        f"Defaulting to agent name '{self.backend_agent.name}'."
                    )
                    adapter_instance_config["name"] = self.backend_agent.name

            # Always use backend agent's endpoint if not already in config
            if (
                "endpoint" not in adapter_instance_config
                and self.backend_agent.endpoint
            ):
                adapter_instance_config["endpoint"] = str(self.backend_agent.endpoint)

            optional_litellm_keys = [
                "api_key",
                "max_new_tokens",
                "temperature",
                "top_p",
            ]
            if isinstance(self.backend_agent.metadata, dict):
                for key in optional_litellm_keys:
                    if (
                        key not in adapter_instance_config
                        and key in self.backend_agent.metadata
                    ):
                        adapter_instance_config[key] = self.backend_agent.metadata[key]

            # For hackagent/* models, pass the HackAgent API key for authentication
            model_name = adapter_instance_config.get("name", "")
            if model_name.startswith("hackagent/"):
                adapter_instance_config["hackagent_api_key"] = (
                    self.backend.get_api_key() or ""
                )

        elif agent_type == AgentTypeEnum.OPENAI_SDK:
            if "name" not in adapter_instance_config:
                if (
                    isinstance(self.backend_agent.metadata, dict)
                    and "name" in self.backend_agent.metadata
                ):
                    adapter_instance_config["name"] = self.backend_agent.metadata[
                        "name"
                    ]
                # For custom endpoints, model name is optional (will default to 'default')
                # Only raise error if no endpoint is configured (i.e., using OpenAI API directly)
                elif (
                    "endpoint" not in adapter_instance_config
                    and not self.backend_agent.endpoint
                ):
                    raise ValueError(
                        f"OpenAI SDK agent '{name}' (ID: {registration_key}) missing "
                        f"'name' (model string) in adapter_operational_config or backend metadata. "
                        f"Cannot configure OpenAIAgent."
                    )
                else:
                    # Fall back to the registered agent name (e.g. full local model path)
                    logger.warning(
                        f"Agent '{name}' (Type: {agent_type.value}) missing 'name' in metadata. "
                        f"Defaulting to agent name '{self.backend_agent.name}'."
                    )
                    adapter_instance_config["name"] = self.backend_agent.name

            # Always use backend agent's endpoint if not already in config
            if (
                "endpoint" not in adapter_instance_config
                and self.backend_agent.endpoint
            ):
                adapter_instance_config["endpoint"] = str(self.backend_agent.endpoint)

            optional_openai_keys = [
                "api_key",
                "max_tokens",
                "temperature",
                "tools",
                "tool_choice",
            ]
            if isinstance(self.backend_agent.metadata, dict):
                for key in optional_openai_keys:
                    if (
                        key not in adapter_instance_config
                        and key in self.backend_agent.metadata
                    ):
                        adapter_instance_config[key] = self.backend_agent.metadata[key]

        elif agent_type == AgentTypeEnum.OLLAMA:
            # Configure Ollama adapter
            if "name" not in adapter_instance_config:
                if (
                    isinstance(self.backend_agent.metadata, dict)
                    and "name" in self.backend_agent.metadata
                ):
                    adapter_instance_config["name"] = self.backend_agent.metadata[
                        "name"
                    ]
                else:
                    logger.warning(
                        f"Agent '{name}' (Type: {agent_type.value}) missing 'name' (model string) in metadata. "
                        f"Defaulting to agent name '{self.backend_agent.name}'."
                    )
                    adapter_instance_config["name"] = self.backend_agent.name

            # Always use backend agent's endpoint if not already in config
            if (
                "endpoint" not in adapter_instance_config
                and self.backend_agent.endpoint
            ):
                adapter_instance_config["endpoint"] = str(self.backend_agent.endpoint)

            optional_ollama_keys = [
                "max_new_tokens",
                "temperature",
                "top_p",
                "top_k",
                "num_ctx",
                "stream",
                "timeout",
            ]
            if isinstance(self.backend_agent.metadata, dict):
                for key in optional_ollama_keys:
                    if (
                        key not in adapter_instance_config
                        and key in self.backend_agent.metadata
                    ):
                        adapter_instance_config[key] = self.backend_agent.metadata[key]

        try:
            logger.debug(
                f"ROUTER_DEBUG: About to call adapter_class(id='{registration_key}', config_keys={list(adapter_instance_config.keys())})"
            )
            adapter_instance = adapter_class(
                id=registration_key, config=adapter_instance_config
            )
            logger.debug(
                f"ROUTER_DEBUG: Called adapter_class. Resulting instance: {adapter_instance}, type: {type(adapter_instance)}"
            )
            self._agent_registry[registration_key] = adapter_instance
            logger.info(
                f"Agent '{name}' (Backend ID: {registration_key}, Type: {agent_type.value}) "
                f"successfully initialized and registered with adapter {adapter_class.__name__}. "
                f"Adapter config keys: {list(adapter_instance_config.keys())}"
            )
        except Exception as e:
            logger.error(
                f"Failed to instantiate adapter for agent '{name}' (Backend ID: {registration_key}): {e}",
                exc_info=True,
            )
            raise ValueError(
                f"Failed to instantiate adapter {adapter_class.__name__}: {e}"
            ) from e

    def get_agent_instance(self, registration_key: str) -> Optional[Agent]:
        """
        Retrieves a registered agent adapter instance by its registration key.

        The registration key is typically the backend ID of the agent.

        Args:
            registration_key: The key (backend ID string) of the registered agent adapter.

        Returns:
            The `Agent` adapter instance if found, otherwise `None`.
        """
        return self._agent_registry.get(registration_key)

    def _build_error_response(
        self,
        error_message: str,
        error_category: str,
        status_code: int,
        raw_request: Optional[Dict[str, Any]] = None,
        registration_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Constructs a standardized error response dictionary for the router.

        This ensures that router-level errors follow the same format as adapter errors,
        providing consistency across the entire request handling pipeline.

        Args:
            error_message: The primary error message string.
            error_category: Category/type of error (e.g., "AgentNotFound", "AdapterException").
            status_code: The HTTP status code associated with the error.
            raw_request: The original request data that led to the error.
            registration_key: The registration key of the agent that failed, if applicable.

        Returns:
            A dictionary representing a standardized error response compatible with adapter responses.
        """
        return {
            "raw_request": raw_request,
            "processed_response": None,
            "generated_text": None,
            "raw_response_status": status_code,
            "raw_response_headers": None,
            "raw_response_body": None,
            "agent_specific_data": None,
            "error_message": error_message,
            "error_category": error_category,
            "agent_id": registration_key,
            "adapter_type": "AgentRouter",
        }

    def route_request(
        self,
        registration_key: str,
        request_data: Dict[str, Any],
        raise_on_error: bool = False,
    ) -> Dict[str, Any]:
        """
        Routes a request to the appropriate agent adapter and returns its response.

        This method now follows a consistent error handling pattern: it returns standardized
        error response dictionaries instead of raising exceptions by default. This ensures
        that all code using the router can handle errors uniformly without try/except blocks.

        Args:
            registration_key: The key (backend ID string) used to register the agent,
                which identifies the target adapter.
            request_data: A dictionary containing the data to be sent to the agent's
                `handle_request` method.
            raise_on_error: If True, raises exceptions for errors (legacy behavior).
                If False (default), returns standardized error response dictionaries.

        Returns:
            A dictionary containing either:
            - The successful response from the agent adapter, or
            - A standardized error response dictionary with error_message field

        Raises:
            ValueError: Only if raise_on_error=True and no agent found for registration_key.
            RuntimeError: Only if raise_on_error=True and agent's handle_request fails.

        Note:
            When raise_on_error=False (default), this method never raises exceptions,
            making it safer to use in pipelines where continuity is important.
        """
        logger.debug(
            f"Routing request for agent key: {registration_key}. Request data keys: {list(request_data.keys())}"
        )
        agent_instance = self.get_agent_instance(registration_key)

        if not agent_instance:
            error_msg = f"Agent not found for key: {registration_key}"
            logger.error(error_msg)

            if raise_on_error:
                raise ValueError(error_msg)

            return self._build_error_response(
                error_message=error_msg,
                error_category="AgentNotFound",
                status_code=404,
                raw_request=request_data,
                registration_key=registration_key,
            )

        try:
            response = agent_instance.handle_request(request_data)
            logger.debug(
                f"Successfully routed request for agent key: {registration_key}"
            )
            return response
        except Exception as e:
            error_msg = f"Agent {registration_key} failed to handle request: {e}"
            logger.error(
                f"Error handling request for agent {registration_key}: {e}",
                exc_info=True,
            )

            if raise_on_error:
                raise RuntimeError(error_msg) from e

            return self._build_error_response(
                error_message=error_msg,
                error_category="AdapterException",
                status_code=500,
                raw_request=request_data,
                registration_key=registration_key,
            )
