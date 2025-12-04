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
from typing import Any, Dict, Optional, Union

from hackagent import utils
from hackagent.attacks.strategies import AdvPrefix, AttackStrategy
from hackagent.client import AuthenticatedClient
from hackagent.errors import HackAgentError
from hackagent.router import AgentRouter
from hackagent.router.types import AgentTypeEnum
from hackagent.vulnerabilities.prompts import DEFAULT_PROMPTS

logger = logging.getLogger(__name__)


class HackAgent:
    """
    The primary client for orchestrating security assessments with HackAgent.

    This class serves as the main entry point to the HackAgent library, providing
    a high-level interface for:
    - Configuring victim agents that will be assessed.
    - Defining and selecting attack strategies.
    - Executing automated security tests against the configured agents.
    - Retrieving and handling test results.

    It encapsulates complexities such as API authentication, agent registration
    with the backend (via `AgentRouter`), and the dynamic dispatch of various
    attack methodologies.

    Attributes:
        client: An `AuthenticatedClient` instance for API communication.
        prompts: A dictionary of default prompts. This dictionary is a copy of
            `DEFAULT_PROMPTS` and can be modified after instantiation if needed,
            though the primary mechanism for custom prompts is usually via attack
            configurations.
        router: An `AgentRouter` instance managing the agent's representation
            in the HackAgent backend.
        attack_strategies: A dictionary mapping strategy names to their
            `AttackStrategy` implementations.
    """

    def __init__(
        self,
        endpoint: str,
        name: Optional[str] = None,
        agent_type: Union[AgentTypeEnum, str] = AgentTypeEnum.UNKNOWN,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        raise_on_unexpected_status: bool = False,
        timeout: Optional[float] = None,
        env_file_path: Optional[str] = None,
    ):
        """
        Initializes the HackAgent client and prepares it for interaction.

        This constructor sets up the authenticated API client, loads default
        prompts, resolves the agent type, and initializes the agent router
        to ensure the agent is known to the backend. It also prepares available
        attack strategies.

        Args:
            endpoint: The target application's endpoint URL. This is the primary
                interface that the configured agent will interact with or represent
                during security tests.
            name: An optional descriptive name for the agent being configured.
                If not provided, a default name might be assigned or behavior might
                depend on the specific backend agent management policies.
            agent_type: Specifies the type of the agent. This can be provided
                as an `AgentTypeEnum` member (e.g., `AgentTypeEnum.GOOGLE_ADK`) or
                as a string identifier (e.g., "google-adk", "litellm").
                String values are automatically converted to the corresponding
                `AgentTypeEnum` member. Defaults to `AgentTypeEnum.UNKNOWN` if
                not specified or if an invalid string is provided.
            base_url: The base URL for the HackAgent API service.
            api_key: The API key for authenticating with the HackAgent API.
                If omitted, the client will attempt to retrieve it from the
                `HACKAGENT_API_KEY` environment variable. The `env_file_path`
                parameter can specify a .env file to load this variable from.
            raise_on_unexpected_status: If set to `True`, the API client will
                raise an exception for any HTTP status codes that are not typically
                expected for a successful operation. Defaults to `False`.
            timeout: The timeout duration in seconds for API requests made by the
                authenticated client. Defaults to `None` (which might mean a
                default timeout from the underlying HTTP library is used).
            env_file_path: An optional path to a .env file. If provided, environment
                variables (such as `HACKAGENT_API_KEY`) will be loaded from this
                file if not already present in the environment.
        """

        resolved_auth_token = utils.resolve_api_token(
            direct_api_key_param=api_key, env_file_path=env_file_path
        )

        self.client = AuthenticatedClient(
            base_url=base_url,
            token=resolved_auth_token,
            prefix="Bearer",
            raise_on_unexpected_status=raise_on_unexpected_status,
            timeout=timeout,
        )

        self.prompts = DEFAULT_PROMPTS.copy()

        processed_agent_type = utils.resolve_agent_type(agent_type)

        self.router = AgentRouter(
            client=self.client,
            name=name,
            agent_type=processed_agent_type,
            endpoint=endpoint,
        )

        self.attack_strategies: Dict[str, AttackStrategy] = {
            "advprefix": AdvPrefix(hack_agent=self),
        }

    def hack(
        self,
        attack_config: Dict[str, Any],
        run_config_override: Optional[Dict[str, Any]] = None,
        fail_on_run_error: bool = True,
        _tui_app: Optional[Any] = None,
        _tui_log_callback: Optional[Any] = None,
    ) -> Any:
        """
        Executes a specified attack strategy against the configured victim agent.

        This method serves as the primary action command for initiating an attack.
        It identifies the appropriate attack strategy based on `attack_config`,
        ensures the victim agent (managed by `self.router`) is ready, and then
        delegates the execution to the chosen strategy.

        Args:
            attack_config: A dictionary containing parameters specific to the
                chosen attack type. Must include an 'attack_type' key that maps
                to a registered strategy (e.g., "advprefix"). Other keys provide
                configuration for that strategy (e.g., 'category', 'prompt_text').
            run_config_override: An optional dictionary that can override default
                run configurations. The specifics depend on the attack strategy
                and backend capabilities.
            fail_on_run_error: If `True` (the default), an exception will be
                raised if the attack run encounters an error and fails. If `False`,
                errors might be suppressed or handled differently by the strategy.

        Returns:
            The result returned by the `execute` method of the chosen attack
            strategy. The nature of this result is strategy-dependent.

        Raises:
            ValueError: If the 'attack_type' is missing from `attack_config` or
                if the specified 'attack_type' is not a supported/registered
                strategy.
            HackAgentError: For issues during API interaction, problems with backend
                agent operations, or other unexpected errors during the attack process.
        """
        try:
            attack_type = attack_config.get("attack_type")
            if not attack_type:
                raise ValueError("'attack_type' must be provided in attack_config.")

            strategy = self.attack_strategies.get(attack_type)
            if not strategy:
                supported_types = list(self.attack_strategies.keys())
                raise ValueError(
                    f"Unsupported attack_type: {attack_type}. Supported types: {supported_types}."
                )

            backend_agent = self.router.backend_agent

            logger.info(
                f"Preparing to attack agent '{backend_agent.name}' "
                f"(ID: {backend_agent.id}, Type: {backend_agent.agent_type}) "
                f"configured in this HackAgent instance, using strategy '{attack_type}'."
            )

            return strategy.execute(
                attack_config=attack_config,
                run_config_override=run_config_override,
                fail_on_run_error=fail_on_run_error,
                _tui_app=_tui_app,
                _tui_log_callback=_tui_log_callback,
            )

        except HackAgentError:
            raise
        except ValueError as ve:
            logger.error(f"Configuration error in HackAgent.hack: {ve}", exc_info=True)
            raise HackAgentError(f"Configuration error: {ve}") from ve
        except RuntimeError as re:
            logger.error(f"Runtime error during HackAgent.hack: {re}", exc_info=True)
            if "Failed to create backend agent" in str(
                re
            ) or "Failed to update metadata" in str(re):
                raise HackAgentError(f"Backend agent operation failed: {re}") from re
            raise HackAgentError(f"An unexpected runtime error occurred: {re}") from re
        except Exception as e:
            logger.error(f"Unexpected error in HackAgent.hack: {e}", exc_info=True)
            raise HackAgentError(
                f"An unexpected error occurred during attack: {e}"
            ) from e
