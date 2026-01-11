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

"""
Attack orchestration layer.

This module provides the AttackOrchestrator base class that coordinates attack execution
with server-side tracking. The orchestrator acts as a bridge between:
- HackAgent (user API)
- HackAgent backend server (tracking/audit)
- Attack technique implementations (algorithms)

Architecture:
    HackAgent.hack() → AttackOrchestrator.execute() → BaseAttack.run()

The orchestrator handles:
- Server record creation (Attack/Run records)
- Configuration validation and preparation
- Delegation to technique implementations
- HTTP response parsing and error handling

Technique implementations remain pure algorithms, unaware of server integration.
"""

import json
import logging
from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple
from uuid import UUID

import httpx

from hackagent.api.attack.attack_create import (
    sync_detailed as attacks_create_sync_detailed,
)
from hackagent.api.run import run_run_tests_create
from hackagent.errors import HackAgentError
from hackagent.models.attack_request import AttackRequest
from hackagent.models.run_request import RunRequest

if TYPE_CHECKING:
    from hackagent.agent import HackAgent

logger = logging.getLogger(__name__)


class AttackOrchestrator:
    """
    Base class for attack orchestrators managing server-tracked execution.

    Orchestrators coordinate attack execution by:
    1. Creating Attack record on server for tracking
    2. Creating Run record on server for this execution
    3. Executing attack locally using BaseAttack implementation
    4. Returning results to caller

    Concrete orchestrators only need to specify:
    - attack_type: String identifier (e.g., "advprefix", "pair")
    - attack_impl_class: BaseAttack subclass to instantiate
    - (Optional) Override methods for custom behavior

    Example:
        class AdvPrefix(AttackOrchestrator):
            attack_type = "advprefix"
            attack_impl_class = AdvPrefixAttack

    Attributes:
        hack_agent: HackAgent instance providing context
        client: Authenticated client for API communication
        attack_type: Attack identifier (must be set by subclass)
        attack_impl_class: Implementation class (must be set by subclass)
    """

    attack_type: str = None  # Must be overridden by subclass
    attack_impl_class: type = None  # Must be overridden by subclass

    def __init__(self, hack_agent: "HackAgent"):
        """
        Initialize orchestrator with HackAgent instance.

        Args:
            hack_agent: HackAgent instance providing client and configuration

        Raises:
            ValueError: If attack_type or attack_impl_class not defined
        """
        self.hack_agent = hack_agent
        self.client = hack_agent.client

        if not self.attack_type:
            raise ValueError(f"{self.__class__.__name__} must define attack_type")
        if not self.attack_impl_class:
            raise ValueError(f"{self.__class__.__name__} must define attack_impl_class")

    def _create_server_attack_record(
        self,
        attack_type: str,
        victim_agent_id: UUID,
        organization_id: UUID,
        attack_config: Dict[str, Any],
    ) -> str:
        """
        Create Attack record on server for tracking.

        Args:
            attack_type: Type of attack (e.g., "advprefix")
            victim_agent_id: UUID of target agent
            organization_id: UUID of organization
            attack_config: Attack configuration dictionary

        Returns:
            Attack record ID

        Raises:
            HackAgentError: If record creation fails
        """
        logger.info(f"Creating {attack_type} Attack record on server")

        payload = {
            "type": attack_type,
            "agent": str(victim_agent_id),
            "organization": str(organization_id),
            "configuration": attack_config,
        }

        try:
            attack_req_obj = AttackRequest.from_dict(payload)
            response = attacks_create_sync_detailed(
                client=self.client, body=attack_req_obj
            )
        except Exception as e:
            logger.error(
                f"Failed to create {attack_type} Attack record: {e}", exc_info=True
            )
            raise HackAgentError(f"Failed to create Attack record: {e}") from e

        attack_id, _ = self._extract_ids_from_response(
            response=response, context=attack_type
        )
        logger.info(f"Attack record created. ID: {attack_id}")
        return attack_id

    def _create_server_run_record(
        self,
        attack_id: str,
        victim_agent_id: str,
        run_config_override: Optional[Dict[str, Any]],
    ) -> str:
        """
        Create Run record on server for this execution.

        Args:
            attack_id: ID of parent attack record
            victim_agent_id: ID of target agent
            run_config_override: Optional configuration overrides

        Returns:
            Run record ID

        Raises:
            HackAgentError: If record creation fails
        """
        logger.info(f"Creating Run record for Attack ID: {attack_id}")

        payload = RunRequest(
            attack=attack_id,
            agent=victim_agent_id,
            run_config=run_config_override or {},
        )

        try:
            response = run_run_tests_create.sync_detailed(
                client=self.client, body=payload
            )
        except Exception as e:
            logger.error(f"Failed to create Run record: {e}", exc_info=True)
            raise HackAgentError(f"Failed to create Run record: {e}") from e

        decoded_content = self._decode_response(response)
        parsed_data = self._parse_response(response, decoded_content, "Run record")

        run_id = parsed_data.get("id")
        if not run_id:
            logger.error(f"Run record missing 'id': {parsed_data}")
            raise HackAgentError("Run record missing 'id' field")

        logger.info(f"Run record created. ID: {run_id}")
        return run_id

    def _prepare_attack_params(self, attack_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract parameters for attack execution.

        Override this method for custom parameter handling.
        Default implementation extracts 'goals' from config.

        Args:
            attack_config: Full attack configuration

        Returns:
            Parameters to pass to technique's run() method

        Raises:
            ValueError: If required parameters are missing
        """
        goals = attack_config.get("goals")
        if not isinstance(goals, list):
            raise ValueError(f"'goals' must be a list for {self.attack_type}")
        return {"goals": goals}

    def _get_attack_impl_kwargs(
        self,
        attack_config: Dict[str, Any],
        run_config_override: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Prepare kwargs for attack implementation instantiation.

        Override this method for special initialization needs
        (e.g., PAIR requires an attacker router).

        Args:
            attack_config: Full attack configuration
            run_config_override: Optional run overrides

        Returns:
            Kwargs for attack_impl_class constructor
        """
        return {
            "config": {**attack_config, **(run_config_override or {})},
            "client": self.client,
            "agent_router": self.hack_agent.agent_router,
        }

    def _execute_local_attack(
        self,
        attack_id: str,
        run_id: str,
        attack_params: Dict[str, Any],
        attack_config: Dict[str, Any],
        run_config_override: Optional[Dict[str, Any]],
    ) -> Any:
        """
        Execute attack locally using technique implementation.

        Args:
            attack_id: Server-side attack record ID
            run_id: Server-side run record ID
            attack_params: Parameters from _prepare_attack_params()
            attack_config: Full attack configuration
            run_config_override: Optional run overrides

        Returns:
            Attack results (format depends on implementation)
        """
        logger.info(
            f"Executing {self.attack_type} attack (Attack: {attack_id}, Run: {run_id})"
        )

        impl_kwargs = self._get_attack_impl_kwargs(attack_config, run_config_override)
        attack_impl = self.attack_impl_class(**impl_kwargs)
        results = attack_impl.run(**attack_params)

        logger.info(f"{self.attack_type} attack completed")
        return results

    def execute(
        self,
        attack_config: Dict[str, Any],
        run_config_override: Optional[Dict[str, Any]],
        fail_on_run_error: bool,
        max_wait_time_seconds: Optional[int] = None,
        poll_interval_seconds: Optional[int] = None,
        _tui_app: Optional[Any] = None,
        _tui_log_callback: Optional[Any] = None,
    ) -> Any:
        """
        Execute attack with server tracking.

        Standard workflow:
        1. Validate and extract attack parameters
        2. Create Attack record on server
        3. Create Run record on server
        4. Execute attack locally via BaseAttack implementation
        5. Return results

        Args:
            attack_config: Attack configuration dictionary
            run_config_override: Optional run configuration overrides
            fail_on_run_error: Whether to raise on errors
            max_wait_time_seconds: Unused for local execution
            poll_interval_seconds: Unused for local execution
            _tui_app: Optional TUI app for logging
            _tui_log_callback: Optional TUI log callback

        Returns:
            Attack results from local execution

        Raises:
            ValueError: If configuration is invalid
            HackAgentError: If server record creation fails
        """
        # 1. Validate parameters
        attack_params = self._prepare_attack_params(attack_config)

        # 2. Create Attack record
        victim_agent_id = self.hack_agent.agent_id
        organization_id = self.hack_agent.organization_id

        attack_id = self._create_server_attack_record(
            attack_type=self.attack_type,
            victim_agent_id=victim_agent_id,
            organization_id=organization_id,
            attack_config=attack_config,
        )

        # 3. Create Run record
        run_id = self._create_server_run_record(
            attack_id=attack_id,
            victim_agent_id=str(victim_agent_id),
            run_config_override=run_config_override,
        )

        # 4. Execute locally
        results = self._execute_local_attack(
            attack_id=attack_id,
            run_id=run_id,
            attack_params=attack_params,
            attack_config=attack_config,
            run_config_override=run_config_override,
        )

        return results

    # ========================================================================
    # HTTP Response Helpers
    # ========================================================================

    def _decode_response(self, response: httpx.Response) -> str:
        """Decode response content to UTF-8 string."""
        return (
            response.content.decode("utf-8", errors="replace")
            if response.content
            else "N/A"
        )

    def _parse_json(
        self,
        response: httpx.Response,
        decoded_content: str,
        context: str,
    ) -> Optional[Dict[str, Any]]:
        """Parse JSON from response with fallback to pre-parsed attributes."""
        parsed_data: Optional[Dict[str, Any]] = None

        if response.content:
            try:
                parsed_data = json.loads(decoded_content)
            except json.JSONDecodeError as jde:
                if response.status_code == 201:
                    logger.error(f"Failed to parse JSON for {context} (201): {jde}")
                    raise HackAgentError(
                        f"Failed to parse 201 response for {context}"
                    ) from jde
                logger.warning(
                    f"Could not parse JSON for {context} (status {response.status_code})",
                    exc_info=False,
                )

        # Fallback to pre-parsed attributes
        if not parsed_data and hasattr(response, "parsed") and response.parsed:
            if hasattr(response.parsed, "additional_properties") and isinstance(
                response.parsed.additional_properties, dict
            ):
                parsed_data = response.parsed.additional_properties
            elif isinstance(response.parsed, dict):
                parsed_data = response.parsed

        return parsed_data

    def _parse_response(
        self,
        response: httpx.Response,
        decoded_content: str,
        context: str,
    ) -> Dict[str, Any]:
        """Parse and validate response data."""
        parsed_data = self._parse_json(response, decoded_content, context)

        if response.status_code == 201:
            if not parsed_data:
                logger.error(f"201 response for {context} but no parseable data")
                raise HackAgentError(f"201 for {context} but no parseable data")
        elif response.status_code >= 300:
            err = f"Failed {context}. Status: {response.status_code}, Body: {decoded_content}"
            logger.error(err)
            raise HackAgentError(err)
        else:
            logger.warning(f"Unexpected status {response.status_code} for {context}")
            if not parsed_data:
                err = f"No parseable data for {context} (status {response.status_code})"
                logger.error(err)
                raise HackAgentError(err)

        if not parsed_data:
            err = f"Failed to parse data for {context} (status {response.status_code})"
            logger.error(err)
            raise HackAgentError(err)

        return parsed_data

    def _extract_ids_from_data(
        self,
        parsed_data: Dict[str, Any],
        context: str,
        original_content: str,
    ) -> Tuple[str, Optional[str]]:
        """Extract attack_id and optional run_id from parsed data."""
        raw_attack_id = parsed_data.get("id")
        attack_id = str(raw_attack_id) if raw_attack_id is not None else None

        if not attack_id:
            err = f"Could not extract attack_id from {context}. Data: {parsed_data}"
            logger.error(err)
            raise HackAgentError(err)

        raw_run_id = parsed_data.get("associated_run_id")
        run_id = str(raw_run_id) if raw_run_id is not None else None

        logger.info(f"Extracted Attack ID: {attack_id}, Run ID: {run_id or 'N/A'}")
        return attack_id, run_id

    def _extract_ids_from_response(
        self, response: httpx.Response, context: str = "attack"
    ) -> Tuple[str, Optional[str]]:
        """Main entry point for extracting IDs from API response."""
        logger.debug(f"Extracting IDs for '{context}' (status: {response.status_code})")
        decoded_content = self._decode_response(response)
        parsed_data = self._parse_response(response, decoded_content, context)
        return self._extract_ids_from_data(parsed_data, context, decoded_content)
