# Copyright 2025 - AI4I. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
from typing import Any, Dict, Optional, Type, Union
from uuid import UUID

from hackagent.api.agent import agent_create, agent_list, agent_partial_update
from hackagent.client import AuthenticatedClient
from hackagent.models import (
    Agent as BackendAgentModel,
)
from hackagent.models import (
    AgentRequest,
    PatchedAgentRequest,
)
from hackagent.router.adapters import ADKAgentAdapter
from hackagent.router.adapters.base import Agent
from hackagent.router.adapters.litellm_adapter import LiteLLMAgentAdapter
from hackagent.router.adapters.openai_adapter import OpenAIAgentAdapter
from hackagent.router.types import AgentTypeEnum

from ..types import UNSET, Unset

# Use explicit hierarchical logger name for clarity
logger = logging.getLogger("hackagent.router")

# --- Agent Type to Adapter Mapping ---
AGENT_TYPE_TO_ADAPTER_MAP: Dict[AgentTypeEnum, Type[Agent]] = {
    AgentTypeEnum.GOOGLE_ADK: ADKAgentAdapter,
    AgentTypeEnum.LITELLM: LiteLLMAgentAdapter,
    AgentTypeEnum.OPENAI_SDK: OpenAIAgentAdapter,
    AgentTypeEnum.LANGCHAIN: LiteLLMAgentAdapter,  # LangChain agents can use LiteLLM adapter
    # Add other agent types and their corresponding adapters here
}


class AgentRouter:
    """
    Manages the configuration and request routing for a single agent instance.

    The `AgentRouter` is responsible for initializing an agent, which includes:
    1.  Fetching necessary contextual information like Organization ID and User ID
        based on the provided authenticated client's API key.
    2.  Ensuring the agent is registered in the HackAgent backend. This involves
        checking if an agent with the specified name, type, and organization
        already exists. If not, it creates a new agent. If it exists, it may
        update its metadata based on the `overwrite_metadata` flag.
    3.  Instantiating the appropriate adapter (e.g., `ADKAgentAdapter`,
        `LiteLLMAgentAdapter`) based on the `agent_type`.
    4.  Storing this adapter for subsequent request routing.

    Once initialized, the router uses the adapter to handle requests directed
    to the managed agent.

    Attributes:
        client: An `AuthenticatedClient` instance for API communication.
        organization_id: The UUID of the organization associated with the API key.
        user_id_str: The string representation of the user ID associated with the API key.
        backend_agent: The `BackendAgentModel` instance representing the agent
            in the HackAgent backend (after creation or retrieval).
        _agent_registry: A dictionary mapping agent registration keys (backend ID)
            to their instantiated adapter `Agent` objects.
    """

    def _fetch_organization_id(self) -> UUID:
        """
        Fetches the organization ID (UUID) associated with the API key.

        This method lists agents accessible by the current client's token and
        extracts the organization ID from any agent. All agents for a given API key
        belong to the same organization, so we can use any agent's organization field.

        Note: We use the /agent endpoint instead of /key because /key is Auth0-only
        for security reasons (prevents API keys from managing other API keys).

        Returns:
            The UUID of the organization.

        Raises:
            RuntimeError: If the organization ID cannot be determined (e.g., no agents
                exist, organization field missing, or API call fails).
        """
        try:
            logger.debug(
                "AgentRouter: Attempting to retrieve Organization ID by listing agents..."
            )
            agents_response = agent_list.sync_detailed(client=self.client)

            if (
                agents_response.status_code == 200
                and agents_response.parsed
                and agents_response.parsed.results
            ):
                first_agent = agents_response.parsed.results[0]
                if hasattr(first_agent, "organization") and isinstance(
                    first_agent.organization, UUID
                ):
                    logger.info(
                        f"AgentRouter: Successfully determined Organization ID: {first_agent.organization} from agent '{first_agent.name}'."
                    )
                    return first_agent.organization
                else:
                    org_type = (
                        type(first_agent.organization).__name__
                        if hasattr(first_agent, "organization")
                        else "Missing"
                    )
                    logger.error(
                        f"AgentRouter: Agent '{first_agent.name}' has invalid organization field (type: {org_type})."
                    )
                    raise RuntimeError(
                        f"AgentRouter: Could not determine Organization ID (invalid type: {org_type})."
                    )
            elif agents_response.parsed and not agents_response.parsed.results:
                logger.error(
                    "AgentRouter: No agents found. Cannot determine Organization ID."
                )
                raise RuntimeError(
                    "AgentRouter: No agents exist for Organization ID retrieval. Create an agent first."
                )
            else:
                content = (
                    agents_response.content.decode()
                    if agents_response.content
                    else "N/A"
                )
                logger.error(
                    f"AgentRouter: Failed to list agents for Org ID. Status: {agents_response.status_code}, Body: {content}"
                )
                raise RuntimeError(
                    f"AgentRouter: Agent list failed for Organization ID (status {agents_response.status_code})."
                )
        except RuntimeError:
            raise
        except Exception as e:
            logger.error(
                f"AgentRouter: Exception fetching Organization ID: {e}", exc_info=True
            )
            raise RuntimeError(f"AgentRouter: Exception fetching Organization ID: {e}")

    def _fetch_user_id_str(self) -> str:
        """
        Fetches the user ID associated with the API key and returns it as a string.

        This method lists agents accessible by the current client's token and
        extracts the owner (user ID) from any agent. All agents for a given API key
        belong to the same user, so we can use any agent's owner field.

        Note: We use the /agent endpoint instead of /key because /key is Auth0-only
        for security reasons (prevents API keys from managing other API keys).

        Returns:
            The string representation of the user ID.

        Raises:
            RuntimeError: If the user ID cannot be determined (e.g., no agents
                exist, owner field missing/null, or API call fails).
        """
        try:
            logger.debug(
                "AgentRouter: Attempting to retrieve User ID by listing agents..."
            )
            agents_response = agent_list.sync_detailed(client=self.client)

            if (
                agents_response.status_code == 200
                and agents_response.parsed
                and agents_response.parsed.results
            ):
                first_agent = agents_response.parsed.results[0]
                if hasattr(first_agent, "owner") and isinstance(first_agent.owner, int):
                    user_id_as_str = str(first_agent.owner)
                    logger.info(
                        f"AgentRouter: Successfully determined User ID (str): {user_id_as_str} from agent '{first_agent.name}'."
                    )
                    return user_id_as_str
                else:
                    owner_type = (
                        type(first_agent.owner).__name__
                        if hasattr(first_agent, "owner")
                        else "Missing"
                    )
                    logger.error(
                        f"AgentRouter: Agent '{first_agent.name}' has invalid owner field (type: {owner_type})."
                    )
                    raise RuntimeError(
                        f"AgentRouter: Could not determine User ID (invalid type: {owner_type})."
                    )
            elif agents_response.parsed and not agents_response.parsed.results:
                logger.error("AgentRouter: No agents found. Cannot determine User ID.")
                raise RuntimeError(
                    "AgentRouter: No agents exist for User ID retrieval. Create an agent first."
                )
            else:
                content = (
                    agents_response.content.decode()
                    if agents_response.content
                    else "N/A"
                )
                logger.error(
                    f"AgentRouter: Failed to list agents for User ID. Status: {agents_response.status_code}, Body: {content}"
                )
                raise RuntimeError(
                    f"AgentRouter: Agent list failed for User ID (status {agents_response.status_code})."
                )
        except RuntimeError:
            raise
        except Exception as e:
            logger.error(f"AgentRouter: Exception fetching User ID: {e}", exc_info=True)
            raise RuntimeError(f"AgentRouter: Exception fetching User ID: {e}")

    def __init__(
        self,
        client: AuthenticatedClient,
        name: str,
        agent_type: AgentTypeEnum,
        endpoint: str,
        metadata: Optional[Dict[str, Any]] = None,
        adapter_operational_config: Optional[Dict[str, Any]] = None,
        overwrite_metadata: bool = True,
    ):
        """
        Initializes the AgentRouter and configures a single agent.

        This constructor performs several key setup steps:
        1. Fetches the organization and user IDs using the provided client.
        2. Validates the `agent_type` against supported adapters.
        3. Prepares metadata and operational configurations for the agent and its adapter.
           For `AgentTypeEnum.GOOGLE_ADK`, it ensures `user_id` is set in the
           adapter's operational config, using the fetched User ID if not provided.
        4. Calls `ensure_agent_in_backend` to create or update the agent's record
           in the HackAgent backend.
        5. Calls `_configure_and_instantiate_adapter` to set up the specific adapter
           for the agent type.

        Args:
            client: An `AuthenticatedClient` for backend API interactions.
            name: The desired name for the agent in the backend.
            agent_type: The type of the agent (e.g., `AgentTypeEnum.GOOGLE_ADK`).
            endpoint: The API endpoint URL for the agent service itself. This is used
                for backend registration and can also be used by the adapter.
            metadata: Optional. Metadata to be stored with the agent's record in the
                backend. Structure can vary by agent type. For example, for
                `AgentTypeEnum.LITELLM`, this might include `{'model_name': ..., 'api_key_env_var': ...}`.
            adapter_operational_config: Optional. Runtime configuration specific to the
                adapter instance. This can override or augment values derived from
                the backend agent's metadata. For `AgentTypeEnum.GOOGLE_ADK`, this might
                include `{'user_id': ..., 'session_id': ...}`. For `AgentTypeEnum.LITELLM`,
                it must provide the model string ('name') if not in backend metadata.
            overwrite_metadata: If `True` (default), and an agent with the same name,
                type, and organization already exists in the backend, its metadata
                will be updated with the provided `metadata`. If `False`, existing
                metadata is preserved.

        Raises:
            ValueError: If the `agent_type` is unsupported, if adapter instantiation fails,
                or if critical configuration for an adapter type (e.g., model name for LiteLLM)
                is missing.
            RuntimeError: If backend communication (e.g., fetching org/user ID, creating/
                updating agent) fails.
        """
        self.client = client
        self._agent_registry: Dict[str, Agent] = {}

        self.organization_id = self._fetch_organization_id()
        self.user_id_str = self._fetch_user_id_str()
        logger.info(
            f"AgentRouter initialized with Organization ID (UUID): {self.organization_id} and User ID (str): {self.user_id_str}"
        )

        if agent_type not in AGENT_TYPE_TO_ADAPTER_MAP:
            raise ValueError(
                f"Unsupported agent type: {agent_type}. Supported types: {list(AGENT_TYPE_TO_ADAPTER_MAP.keys())}"
            )

        actual_metadata = metadata.copy() if metadata is not None else {}

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
                    f"ADK Agent: 'user_id' was already present in adapter_operational_config ('{current_adapter_op_config['user_id']}'). Using that value instead of fetched one."
                )

        self.backend_agent = self.ensure_agent_in_backend(
            name=name,
            agent_type=agent_type,
            endpoint_for_backend=endpoint,
            metadata_for_backend=actual_metadata,
            update_metadata_if_exists=overwrite_metadata,
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
            adapter_instance_config["endpoint"] = self.backend_agent.endpoint
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
                adapter_instance_config["endpoint"] = self.backend_agent.endpoint

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
                adapter_instance_config["hackagent_api_key"] = self.client.token

        elif agent_type == AgentTypeEnum.OPENAI_SDK:
            if "name" not in adapter_instance_config:
                if (
                    isinstance(self.backend_agent.metadata, dict)
                    and "name" in self.backend_agent.metadata
                ):
                    adapter_instance_config["name"] = self.backend_agent.metadata[
                        "name"
                    ]
                else:
                    raise ValueError(
                        f"OpenAI SDK agent '{name}' (ID: {registration_key}) missing "
                        f"'name' (model string) in adapter_operational_config or backend metadata. "
                        f"Cannot configure OpenAIAgentAdapter."
                    )

            # Always use backend agent's endpoint if not already in config
            if (
                "endpoint" not in adapter_instance_config
                and self.backend_agent.endpoint
            ):
                adapter_instance_config["endpoint"] = self.backend_agent.endpoint

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

    def _find_existing_agent(
        self,
        name: str,
    ) -> Optional[BackendAgentModel]:
        """
        Finds an existing agent in the backend by its name and organization.

        This method paginates through the list of all agents accessible via the
        client's API key. It matches agents based on the provided `name`
        and the `self.organization_id` (UUID) of the router instance.
        The organization ID match is crucial for ensuring the correct agent is
        identified in a multi-tenant environment.

        The method checks both `agent_model.organization` (expected to be a UUID)
        and falls back to `agent_model.organization_detail.id` if necessary.

        Args:
            name: The name of the agent to find.

        Returns:
            A `BackendAgentModel` instance if a matching agent is found, otherwise `None`.
        """
        logger.debug(
            f"SYNC_DEBUG: Entered _find_existing_agent for Name='{name}', OrgID='{self.organization_id}' (UUID)"
        )

        current_page: Union[Unset, int] = UNSET
        agents_processed_count = 0

        while True:
            list_response = None
            try:
                list_response = agent_list.sync_detailed(
                    client=self.client, page=current_page
                )
                logger.debug(
                    f"SYNC_DEBUG: Fetched page of agents. Status: {list_response.status_code if list_response else 'N/A'}"
                )

            except Exception as e:
                logger.error(
                    f"SYNC_DEBUG: An unexpected error occurred during 'agents_list.sync_detailed' while fetching page {current_page if not isinstance(current_page, Unset) else 'initial'}: {e}",
                    exc_info=True,
                )
                return None

            if (
                list_response
                and list_response.status_code == 200
                and list_response.parsed
            ):
                paginated_result = list_response.parsed
                results_list = getattr(paginated_result, "results", [])
                logger.debug(
                    f"SYNC_DEBUG: Page {current_page if not isinstance(current_page, Unset) else 'initial'} - Number of results on page: {len(results_list) if results_list else 0}"
                )
                if not isinstance(results_list, list):
                    logger.warning(
                        f"SYNC_DEBUG: Expected 'results' to be a list, but got {type(results_list)}. Full parsed response: {paginated_result}"
                    )
                    results_list = []

                for agent_model in results_list:
                    agents_processed_count += 1
                    logger.debug(
                        f"SYNC_DEBUG: Checking agent: ID={agent_model.id}, Name={getattr(agent_model, 'name', 'N/A')}, Type={getattr(agent_model, 'agent_type', getattr(agent_model, 'type', 'N/A'))}, Org={getattr(agent_model, 'organization', 'N/A')}"
                    )

                    name_matches = (
                        hasattr(agent_model, "name") and agent_model.name == name
                    )

                    org_matches = False
                    if hasattr(agent_model, "organization") and isinstance(
                        agent_model.organization, UUID
                    ):
                        if agent_model.organization == self.organization_id:
                            org_matches = True
                    elif (
                        hasattr(agent_model, "organization_detail")
                        and hasattr(agent_model.organization_detail, "id")
                        and isinstance(agent_model.organization_detail.id, UUID)
                    ):
                        if agent_model.organization_detail.id == self.organization_id:
                            org_matches = True
                            logger.debug(
                                f"SYNC_DEBUG: Matched OrgID via organization_detail.id for agent '{agent_model.name}'"
                            )
                    elif hasattr(agent_model, "organization") and isinstance(
                        agent_model.organization, int
                    ):
                        logger.warning(
                            f"SYNC_DEBUG: agent_model.organization is an int ('{agent_model.organization}') for agent '{agent_model.name}'. Schema mismatch with expected UUID ('{self.organization_id}')."
                        )

                    if not name_matches:
                        logger.debug(
                            f"SYNC_DEBUG: Agent ID '{agent_model.id}' ('{agent_model.name}') failed name match (expected '{name}')"
                        )
                    elif not org_matches:
                        logger.debug(
                            f"SYNC_DEBUG: Agent ID '{agent_model.id}' ('{agent_model.name}') failed organization match (expected UUID '{self.organization_id}', found '{getattr(agent_model, 'organization', 'N/A')}' or detail '{getattr(agent_model.organization_detail, 'id', 'N/A') if hasattr(agent_model, 'organization_detail') else 'N/A'}')"
                        )

                    if name_matches and org_matches:
                        logger.info(
                            f"SYNC_DEBUG: Found existing backend agent '{name}' (OrgID: {self.organization_id}) "
                            f"with ID {agent_model.id} on page {current_page if not isinstance(current_page, Unset) else 'initial'}. Processed {agents_processed_count} agents total so far."
                        )
                        return agent_model

                if (
                    hasattr(paginated_result, "next_")
                    and paginated_result.next_
                    and not isinstance(paginated_result.next_, Unset)
                ):
                    next_page_url = paginated_result.next_
                    try:
                        if isinstance(next_page_url, str) and "page=" in next_page_url:
                            current_page = int(
                                next_page_url.split("page=")[-1].split("&")[0]
                            )
                        elif isinstance(next_page_url, int):
                            current_page = next_page_url
                        else:
                            current_page = (
                                current_page if isinstance(current_page, int) else 1
                            ) + 1
                    except ValueError:
                        logger.warning(
                            f"Could not parse next page number from URL: {next_page_url}. Using simple increment."
                        )
                        current_page = (
                            current_page if isinstance(current_page, int) else 1
                        ) + 1

                    logger.debug(
                        f"SYNC_DEBUG: Moving to next page of agents: {current_page}"
                    )
                else:
                    logger.debug(
                        f"SYNC_DEBUG: No more pages of agents to fetch. Processed {agents_processed_count} agents in total."
                    )
                    break

            elif list_response and list_response.status_code != 200:
                logger.error(
                    f"SYNC_DEBUG: Failed to list agents on page {current_page if not isinstance(current_page, Unset) else 'initial'}. Status: {list_response.status_code}, "
                    f"Body: {list_response.content.decode() if list_response.content else 'N/A'}"
                )
                return None
            elif not list_response:
                logger.error(
                    f"SYNC_DEBUG: Failed to get any response from agents_list API for page {current_page if not isinstance(current_page, Unset) else 'initial'}."
                )
                return None
            else:
                logger.warning(
                    f"SYNC_DEBUG: Unexpected state after trying to fetch page {current_page if not isinstance(current_page, Unset) else 'initial'}. list_response: {list_response}"
                )
                return None

        logger.debug(
            f"SYNC_DEBUG: No existing backend agent found matching Name='{name}', OrgID='{self.organization_id}' after searching all pages."
        )
        return None

    def _update_agent(self, agent_id: UUID, **kwargs) -> BackendAgentModel:
        """
        Updates an existing agent in the backend.

        Args:
            agent_id: The UUID of the agent to update.
            **kwargs: Fields to update (e.g., metadata, agent_type).
        """
        logger.info(
            f"Attempting to update backend agent ID: {agent_id} with fields: {list(kwargs.keys())}"
        )
        patch_body = PatchedAgentRequest(**kwargs)
        try:
            update_response = agent_partial_update.sync_detailed(
                client=self.client, id=agent_id, body=patch_body
            )
            if update_response.status_code == 200 and update_response.parsed:
                logger.info(f"Successfully updated backend agent ID: {agent_id}.")
                return update_response.parsed
            else:
                err_msg = (
                    f"Failed to update backend agent ID: {agent_id}. "
                    f"Status: {update_response.status_code}, "
                    f"Body: {update_response.content.decode() if update_response.content else 'N/A'}"
                )
                logger.error(err_msg)
                raise RuntimeError(err_msg)
        except Exception as e:
            err_msg_ex = (
                f"Exception during backend agent update for ID: {agent_id}: {e}"
            )
            logger.error(err_msg_ex, exc_info=True)
            raise RuntimeError(err_msg_ex) from e

    def _create_new_agent(
        self,
        name: str,
        agent_type: AgentTypeEnum,
        endpoint: str,
        metadata: Dict[str, Any],
        description: str,
    ) -> BackendAgentModel:
        """
        Creates a new agent in the backend.

        The new agent is associated with the `self.organization_id` (UUID) of the router.

        Args:
            name: The name for the new agent.
            agent_type: The `AgentTypeEnum` for the new agent.
            endpoint: The endpoint URL for the new agent.
            metadata: A dictionary of metadata for the new agent.
            description: A descriptive string for the new agent.

        Returns:
            The created `BackendAgentModel` instance.

        Raises:
            RuntimeError: If the API call to create the agent fails.
        """
        logger.info(
            f"Creating new backend agent: Name='{name}', Type='{agent_type.value}', OrgID='{self.organization_id}' (UUID)"
        )

        agent_req_body = AgentRequest(
            name=name,
            endpoint=endpoint,
            agent_type=agent_type.value,
            metadata=metadata,
            description=description,
        )

        try:
            create_response = agent_create.sync_detailed(
                client=self.client, body=agent_req_body
            )
            if create_response.status_code == 201 and create_response.parsed:
                logger.info(
                    f"Created backend agent '{name}' (Type: {agent_type.value}) with ID {create_response.parsed.id}."
                )
                return create_response.parsed
            else:
                body_content = (
                    create_response.content.decode()
                    if create_response.content
                    else "N/A"
                )
                err_msg = (
                    f"Failed to create backend agent '{name}'. Status: {create_response.status_code}, "
                    f"Body: {body_content}"
                )
                logger.error(err_msg)
                raise RuntimeError(err_msg)
        except Exception as e:
            err_msg_ex = (
                f"Exception during backend agent creation for Name='{name}': {e}"
            )
            logger.error(err_msg_ex, exc_info=True)
            raise RuntimeError(err_msg_ex) from e

    def ensure_agent_in_backend(
        self,
        name: str,
        agent_type: AgentTypeEnum,
        endpoint_for_backend: str,
        metadata_for_backend: Dict[str, Any],
        description_prefix: str = "Agent managed by router",
        update_metadata_if_exists: bool = True,
    ) -> BackendAgentModel:
        """
        Ensures an agent with the given specifications exists in the backend.

        This method first attempts to find an existing agent matching the name,
        type, and the router's `self.organization_id`. If found, it checks if its
        metadata needs updating based on `metadata_for_backend`. If an update is
        needed and `update_metadata_if_exists` is `True`, it performs the update.
        If the agent is not found, a new one is created.

        Args:
            name: The name of the agent.
            agent_type: The `AgentTypeEnum` of the agent.
            endpoint_for_backend: The endpoint URL for the agent.
            metadata_for_backend: The desired metadata for the agent in the backend.
            description_prefix: A prefix for the description of a newly created agent.
                The agent's name will be appended to this prefix.
            update_metadata_if_exists: If `True` and the agent exists, its metadata
                will be updated if it differs from `metadata_for_backend`.

        Returns:
            The `BackendAgentModel` of the existing (possibly updated) or newly
            created agent.
        """
        logger.info(
            f"Ensuring backend agent presence: Name='{name}', Type='{agent_type.value}', OrgID='{self.organization_id}' (UUID)"
        )

        existing_agent = self._find_existing_agent(name=name)

        if existing_agent:
            needs_update = False
            patch_kwargs: Dict[str, Any] = {}

            # Check metadata
            current_metadata = (
                existing_agent.metadata
                if isinstance(existing_agent.metadata, dict)
                else {}
            )
            metadata_to_patch = {}

            for key, value_for_backend in metadata_for_backend.items():
                if current_metadata.get(key) != value_for_backend:
                    metadata_to_patch[key] = value_for_backend
                    needs_update = True

            if metadata_to_patch:
                final_metadata = current_metadata.copy()
                final_metadata.update(metadata_to_patch)
                patch_kwargs["metadata"] = final_metadata

            # Check agent_type
            current_type_val = None
            if isinstance(existing_agent.agent_type, AgentTypeEnum):
                current_type_val = existing_agent.agent_type.value
            elif isinstance(existing_agent.agent_type, str):
                current_type_val = existing_agent.agent_type

            if current_type_val != agent_type.value:
                logger.info(
                    f"Backend agent '{name}' exists but type differs. Current: '{current_type_val}', Requested: '{agent_type.value}'. Will update."
                )
                patch_kwargs["agent_type"] = agent_type.value
                needs_update = True

            if needs_update and update_metadata_if_exists:
                logger.info(
                    f"Backend agent '{name}' exists and needs update. Proceeding with update."
                )
                return self._update_agent(agent_id=existing_agent.id, **patch_kwargs)
            else:
                if needs_update and not update_metadata_if_exists:
                    logger.info(
                        f"Backend agent '{name}' exists and differs, but update_metadata_if_exists is False. Skipping update."
                    )
                else:
                    logger.info(
                        f"Backend agent '{name}' exists and is current or update is skipped."
                    )
                return existing_agent

        description = f"{description_prefix}: {name}"
        return self._create_new_agent(
            name=name,
            agent_type=agent_type,
            endpoint=endpoint_for_backend,
            metadata=metadata_for_backend,
            description=description,
        )

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
