# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import logging
from typing import Any, Dict, List, Optional, Tuple, Type

from hackagent.server.storage.base import AgentRecord, StorageBackend
from hackagent.router import envelope as _envelope
from hackagent.router import tracking_logger as _tracking_logger
from hackagent.router._chat_registration import _ChatRegistration
from hackagent.router.adapters.base import Agent
from hackagent.router.provider_config import ProviderConfig, get_provider_config
from hackagent.router.types import AgentTypeEnum

# Adapter imports - these stay at module level for tests that still patch
# ``hackagent.router.router.LiteLLMAgent`` etc. As of Phase E.2 chat
# AgentTypes no longer instantiate these classes — they build a
# ``_ChatRegistration`` instead. ADK still uses ``ADKAgent`` because its
# CustomLLM registration is per-instance.
from hackagent.router.adapters import ADKAgent
from hackagent.router.adapters.litellm import LiteLLMAgent, _get_litellm
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
        backend: The StorageBackend.
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
            backend: StorageBackend.
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
        # Tracks the AgentTypeEnum each registration was created under, so
        # ``route_request`` can pick the right dispatch path (chat
        # AgentTypes go through ``_dispatch_via_litellm`` directly;
        # everything else still calls ``adapter.handle_request``).
        self._agent_types: Dict[str, AgentTypeEnum] = {}

        # Phase D: register the LiteLLM CustomLogger that captures input
        # and output for every HackAgent-owned call. Idempotent.
        _tracking_logger.ensure_registered()

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

        # Every adapter now subclasses LiteLLMAgent, so the same set of
        # config fields applies (with ADK adding a required user_id).
        # ``name`` is the model string, ``endpoint`` is the API base URL.
        if "name" not in adapter_instance_config:
            metadata = self.backend_agent.metadata
            if isinstance(metadata, dict) and "name" in metadata:
                adapter_instance_config["name"] = metadata["name"]
            else:
                logger.warning(
                    f"Agent '{name}' (Type: {agent_type.value}) missing 'name' "
                    f"(model string) in metadata. Defaulting to agent name "
                    f"'{self.backend_agent.name}'."
                )
                adapter_instance_config["name"] = self.backend_agent.name

        if "endpoint" not in adapter_instance_config and self.backend_agent.endpoint:
            adapter_instance_config["endpoint"] = str(self.backend_agent.endpoint)

        # Merge through any optional generation/provider knobs stored on
        # the backend agent's metadata so adapter subclasses see them.
        optional_passthrough_keys = (
            "api_key",
            "max_tokens",
            "temperature",
            "top_p",
            "top_k",
            "num_ctx",
            "stream",
            "timeout",
            "thinking",
            "tools",
            "tool_choice",
            "extra_body",
            "reasoning_effort",
        )
        if isinstance(self.backend_agent.metadata, dict):
            for key in optional_passthrough_keys:
                if (
                    key not in adapter_instance_config
                    and key in self.backend_agent.metadata
                ):
                    adapter_instance_config[key] = self.backend_agent.metadata[key]

        if agent_type == AgentTypeEnum.GOOGLE_ADK:
            # ADK uses the agent name as the app_name in its run payload.
            adapter_instance_config["name"] = self.backend_agent.name
            if "user_id" not in adapter_instance_config:
                logger.error(
                    f"CRITICAL: user_id not found in adapter_instance_config "
                    f"for ADK agent '{self.backend_agent.name}'. Defaulting "
                    f"to context user_id."
                )
                adapter_instance_config["user_id"] = self.user_id_str

        provider_config = get_provider_config(agent_type)

        try:
            if provider_config is not None:
                # Phase E.2b — chat AgentTypes no longer go through the
                # heavy adapter classes; the router stores a lightweight
                # ``_ChatRegistration`` that ``_dispatch_via_litellm`` reads
                # off. Adapter classes remain importable for back-compat.
                logger.debug(
                    f"ROUTER_DEBUG: Building _ChatRegistration for "
                    f"'{registration_key}' (Type: {agent_type.value}), "
                    f"config_keys={list(adapter_instance_config.keys())}"
                )
                adapter_instance: Any = _ChatRegistration(
                    id=registration_key,
                    agent_type=agent_type,
                    provider_config=provider_config,
                    config=adapter_instance_config,
                )
            else:
                logger.debug(
                    f"ROUTER_DEBUG: About to call adapter_class(id='{registration_key}', config_keys={list(adapter_instance_config.keys())})"
                )
                adapter_instance = adapter_class(
                    id=registration_key, config=adapter_instance_config
                )
            logger.debug(
                f"ROUTER_DEBUG: Resulting instance: {adapter_instance}, type: {type(adapter_instance)}"
            )
            self._agent_registry[registration_key] = adapter_instance
            self._agent_types[registration_key] = agent_type
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
            # Phase F.1 — ``status_code`` is the canonical field used by
            # the new chat-dispatch envelope; ``raw_response_status`` is
            # kept as an alias for legacy callers that read it.
            "status_code": status_code,
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

        agent_type = self._agent_types.get(registration_key)
        provider_config = (
            get_provider_config(agent_type) if agent_type is not None else None
        )

        try:
            if provider_config is not None:
                # Chat-completion AgentType: drive LiteLLM directly via the
                # router instead of going through the adapter's
                # ``handle_request``. Phase C of #379.
                response = self._dispatch_via_litellm(
                    registration_key=registration_key,
                    agent_instance=agent_instance,
                    provider_config=provider_config,
                    request_data=request_data,
                )
            else:
                # ADK and other gap-filler AgentTypes still use the
                # adapter path.
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

    # ------------------------------------------------------------------ #
    # Phase C: LiteLLM dispatch path
    # ------------------------------------------------------------------ #

    @staticmethod
    def _extract_messages(
        request_data: Dict[str, Any],
    ) -> Tuple[Optional[List[Dict[str, str]]], Optional[str]]:
        """Return ``(messages, error_msg)`` for a chat-completion request."""
        messages = request_data.get("messages")
        prompt = request_data.get("prompt")
        if messages:
            return messages, None
        if prompt:
            return [{"role": "user", "content": prompt}], None
        return (
            None,
            "Request data must include either 'messages' or 'prompt' field.",
        )

    def _dispatch_via_litellm(
        self,
        *,
        registration_key: str,
        agent_instance: Agent,
        provider_config: ProviderConfig,
        request_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Route a chat-completion request through ``litellm.completion``.

        Reads the model string, endpoint, API key, and generation
        defaults off the already-configured adapter instance, looks up
        the provider-specific thinking translator from
        ``provider_config``, then calls LiteLLM directly. The response
        is shaped via :mod:`hackagent.router.envelope` so downstream
        consumers see exactly the same dict as the adapter-driven path.
        """
        adapter_label = provider_config.adapter_label or agent_instance.ADAPTER_TYPE
        model_name = getattr(agent_instance, "litellm_model", None) or getattr(
            agent_instance, "model_name", None
        )
        if model_name is None:
            return _envelope.build_error_envelope(
                agent_id=registration_key,
                adapter_type=adapter_label,
                error_message=(
                    f"Adapter for '{registration_key}' has no model name; "
                    "cannot dispatch via LiteLLM."
                ),
                status_code=500,
                raw_request=request_data,
            )

        messages, validation_error = self._extract_messages(request_data)
        if validation_error:
            return _envelope.build_error_envelope(
                agent_id=registration_key,
                adapter_type=adapter_label,
                error_message=validation_error,
                status_code=400,
                raw_request=request_data,
            )

        # Generation defaults come from the adapter instance.
        max_tokens = request_data.get(
            "max_tokens", getattr(agent_instance, "default_max_tokens", 100)
        )
        temperature = request_data.get(
            "temperature", getattr(agent_instance, "default_temperature", 0.8)
        )
        top_p = request_data.get(
            "top_p", getattr(agent_instance, "default_top_p", 0.95)
        )

        # Translate the unified thinking knob via the provider config.
        thinking = request_data.get(
            "thinking", getattr(agent_instance, "default_thinking", None)
        )
        thinking_payload = provider_config.thinking_translator(
            thinking, model_name=model_name
        )

        # Provider-specific pass-throughs (tools, extras, …) plus any
        # adapter-specific extra knobs (top_k, num_ctx for Ollama, etc.).
        tools = request_data.get(
            "tools", getattr(agent_instance, "default_tools", None)
        )
        tool_choice = request_data.get(
            "tool_choice", getattr(agent_instance, "default_tool_choice", None)
        )
        extra_body = request_data.get(
            "extra_body", getattr(agent_instance, "default_extra_body", None)
        )

        excluded_keys = {
            "prompt",
            "messages",
            "max_tokens",
            "temperature",
            "top_p",
            "tools",
            "tool_choice",
            "thinking",
            "extra_body",
            "metadata",
        }
        extra_kwargs: Dict[str, Any] = {
            k: v for k, v in request_data.items() if k not in excluded_keys
        }
        # Add adapter-instance defaults for the extra passthrough keys.
        for key in provider_config.extra_passthrough_keys:
            if key in request_data or key in extra_kwargs:
                continue
            default = getattr(agent_instance, f"default_{key}", None)
            if default is not None:
                extra_kwargs[key] = default

        # Phase D: attach correlation metadata so the registered
        # HackAgentTrackingLogger can join input ↔ output ↔ cost. Any
        # ``metadata`` already in ``request_data`` is preserved and
        # augmented (caller-supplied keys win on collision so user
        # tracing identifiers aren't overwritten).
        caller_metadata = request_data.get("metadata")
        merged_metadata: Dict[str, Any] = {
            _tracking_logger.HACKAGENT_AGENT_ID_KEY: registration_key,
            _tracking_logger.HACKAGENT_ADAPTER_TYPE_KEY: adapter_label,
        }
        if isinstance(caller_metadata, dict):
            merged_metadata.update(caller_metadata)
        extra_kwargs["metadata"] = merged_metadata

        kwargs = _envelope.build_litellm_kwargs(
            model=model_name,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            api_base=getattr(agent_instance, "api_base_url", None),
            api_key=getattr(agent_instance, "actual_api_key", None),
            tools=tools,
            tool_choice=tool_choice,
            extra_body=extra_body,
            thinking_payload=thinking_payload,
            extra_kwargs=extra_kwargs,
        )

        litellm, available = _get_litellm()
        if not available:
            return _envelope.build_error_envelope(
                agent_id=registration_key,
                adapter_type=adapter_label,
                error_message="litellm is not installed",
                status_code=500,
                raw_request=request_data,
                model_name=model_name,
            )

        try:
            response = litellm.completion(**kwargs)
        except Exception as exc:
            logger.exception(
                f"LiteLLM dispatch failed for agent {registration_key} "
                f"(model={model_name}): {exc}"
            )
            return _envelope.build_error_envelope(
                agent_id=registration_key,
                adapter_type=adapter_label,
                error_message=f"{adapter_label} error ({type(exc).__name__}): {exc}",
                status_code=500,
                raw_request=request_data,
                model_name=model_name,
            )

        text = _envelope.extract_text_from_response(response, model_name=model_name)
        if isinstance(text, str) and text.startswith("[GENERATION_ERROR:"):
            return _envelope.build_error_envelope(
                agent_id=registration_key,
                adapter_type=adapter_label,
                error_message=f"{adapter_label} generation error: {text}",
                status_code=500,
                raw_request=request_data,
                model_name=model_name,
            )

        # Build completion_result + agent_specific_data the same way
        # ChatCompletionsAgent did, so the envelope dict matches byte
        # for byte.
        invoked_parameters: Dict[str, Any] = {
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
        }
        invoked_parameters.update(extra_kwargs)
        if tools is not None:
            invoked_parameters["tools"] = tools
        if tool_choice is not None:
            invoked_parameters["tool_choice"] = tool_choice

        completion_result: Dict[str, Any] = {
            "success": True,
            "content": text,
            "raw_response": response,
        }
        tool_calls = _envelope.extract_tool_calls(response)
        if tool_calls is not None:
            completion_result["tool_calls"] = tool_calls
        try:
            completion_result["finish_reason"] = response.choices[0].finish_reason
        except (AttributeError, IndexError, TypeError):
            pass
        try:
            if response.usage is not None:
                completion_result["usage"] = response.usage.model_dump()
        except AttributeError:
            pass
        try:
            completion_result["provider_model"] = response.model
        except AttributeError:
            pass
        # Phase F.1 — surface LiteLLM's response_cost and call_id so
        # downstream traces can join input ↔ output ↔ spend without
        # poking at private attributes on the raw response object.
        response_cost = _envelope.extract_response_cost(response)
        if response_cost is not None:
            completion_result["response_cost"] = response_cost
        call_id = _envelope.extract_litellm_call_id(response)
        if call_id is not None:
            completion_result["litellm_call_id"] = call_id

        agent_specific_data = _envelope.build_agent_specific_data(
            model_name=model_name,
            invoked_parameters=invoked_parameters,
            completion_result=completion_result,
        )

        return _envelope.build_success_envelope(
            agent_id=registration_key,
            adapter_type=adapter_label,
            processed_response=text,
            raw_request=request_data,
            raw_response_body=response,
            agent_specific_data=agent_specific_data,
            model_name=model_name,
        )
