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
Attack strategy implementations using the Strategy pattern.

This module provides different attack strategies that can be executed against victim agents.
The Strategy pattern allows for dynamic selection and execution of various attack methodologies,
each with their own specific configurations and execution logic.

The module includes:
- Abstract base class `AttackStrategy` defining the interface
- Concrete implementations like `AdvPrefix` for adversarial prefix attacks
- Helper methods for HTTP response handling and data parsing
- Integration with the HackAgent backend API for attack execution and result tracking
"""

import abc
import json  # For ManagedAttackStrategy
import logging
import os  # Added for path joining
from http import HTTPStatus  # Added for checking 201 status
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple
from uuid import UUID  # Added import

import httpx  # Added for manual HTTP call in AdvPrefix
import pandas as pd  # For AdvPrefix

# Imports for specific strategies, moved from agent.py or direct_test_executor.py
from hackagent import errors  # Import the errors module
from hackagent.api.attack.attack_create import (
    sync_detailed as attacks_create_sync_detailed,
)
from hackagent.api.run import run_run_tests_create
from hackagent.attacks.advprefix import (
    AdvPrefixAttack,
)  # Used by LocalPrefix
from hackagent.errors import HackAgentError
from hackagent.models import Run
from hackagent.models.attack_request import (
    AttackRequest,
)  # For creating attacks via attacks_create API
from hackagent.models.run_request import RunRequest

if TYPE_CHECKING:
    from hackagent.agent import HackAgent

logger = logging.getLogger(__name__)

# --- Strategy Pattern for Attacks ---


class AttackStrategy(abc.ABC):
    """
    Abstract base class for implementing attack strategies using the Strategy pattern.

    This class provides the foundational interface for all attack strategy implementations.
    It handles common functionality such as HTTP response processing, data parsing,
    and interaction with the HackAgent backend API.

    Attributes:
        hack_agent: Reference to the HackAgent instance that owns this strategy.
        client: Authenticated client for API communication.
    """

    def __init__(self, hack_agent: "HackAgent"):
        """
        Initialize the attack strategy with a reference to the parent HackAgent.

        Args:
            hack_agent: The HackAgent instance that will use this strategy.
                Provides access to the authenticated client and agent configuration.
        """
        self.hack_agent = hack_agent
        self.client = hack_agent.client

    @abc.abstractmethod
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
        Execute the attack strategy with the provided configuration.

        This abstract method must be implemented by all concrete strategy classes
        to define their specific attack execution logic.

        Args:
            attack_config: Configuration dictionary containing attack-specific parameters.
                Must include 'attack_type' and other parameters specific to the strategy.
            run_config_override: Optional configuration overrides for the attack run.
                Can be used to modify default run parameters.
            fail_on_run_error: Whether to raise an exception if the attack run fails.
                If False, errors may be handled gracefully depending on the strategy.
            max_wait_time_seconds: Maximum time to wait for attack completion.
                Not used by all strategies.
            poll_interval_seconds: Interval for polling attack status.
                Not used by all strategies.
            _tui_app: Optional Textual App instance for TUI logging integration.
                Internal parameter used when running attacks from the TUI.
            _tui_log_callback: Optional callback function for TUI log handling.
                Internal parameter used when running attacks from the TUI.

        Returns:
            Strategy-specific results. The format varies by implementation but
            typically includes attack results, success metrics, or result data.

        Raises:
            NotImplementedError: If not implemented by a concrete strategy class.
            HackAgentError: For various attack execution failures.
            ValueError: For invalid configuration parameters.
        """
        pass

    def _decode_response_content(self, response: httpx.Response) -> str:
        """
        Decode HTTP response content to a UTF-8 string with error handling.

        Args:
            response: The httpx.Response object containing the response data.

        Returns:
            The decoded content as a UTF-8 string, or 'N/A' if content is None or empty.
            Uses 'replace' error handling to avoid decoding exceptions.
        """
        return (
            response.content.decode("utf-8", errors="replace")
            if response.content
            else "N/A"
        )

    def _parse_json_from_response_data(
        self,
        response: httpx.Response,
        decoded_content: str,
        attack_type_for_error_msg: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Parse JSON data from an HTTP response with comprehensive error handling.

        This method attempts to parse JSON from response content and falls back
        to pre-parsed attributes if direct parsing fails. It handles various
        edge cases and provides detailed error logging.

        Args:
            response: The httpx.Response object to parse.
            decoded_content: The already decoded string content of the response.
            attack_type_for_error_msg: Descriptive string for error messages,
                typically the attack type being processed.

        Returns:
            A dictionary containing the parsed JSON data if successful,
            None if parsing fails for non-critical cases.

        Raises:
            HackAgentError: If response status is 201 (Created) but JSON parsing
                fails critically, indicating a server-side issue.
        """
        parsed_data_dict: Optional[Dict[str, Any]] = None
        if response.content:
            try:
                parsed_data_dict = json.loads(decoded_content)
            except json.JSONDecodeError as jde:
                if (
                    response.status_code == 201
                ):  # Critical for 201 if body exists but is bad JSON
                    logger.error(
                        f"Failed to parse JSON for {attack_type_for_error_msg} (201 response with content): {jde}. Content: {decoded_content}"
                    )
                    raise HackAgentError(
                        f"Failed to parse 201 response JSON for {attack_type_for_error_msg} (content present): {jde}"
                    ) from jde
                logger.warning(
                    f"Could not parse JSON from response body for {attack_type_for_error_msg} (status {response.status_code}). Content: {decoded_content}",
                    exc_info=False,
                )  # exc_info=False to avoid verbose log for non-critical parse fail
                # Do not return None yet, try pre-parsed attributes next

        # Try pre-parsed attributes, especially if content parsing failed or content was empty
        if not parsed_data_dict and hasattr(response, "parsed") and response.parsed:
            logger.debug(
                f"Attempting to use pre-parsed attribute for {attack_type_for_error_msg}"
            )
            if hasattr(response.parsed, "additional_properties") and isinstance(
                response.parsed.additional_properties, dict
            ):
                parsed_data_dict = response.parsed.additional_properties
            elif isinstance(response.parsed, dict):
                parsed_data_dict = response.parsed
            else:
                logger.warning(
                    f"Response has 'parsed' attribute but it's not a usable dict for {attack_type_for_error_msg}. Type: {type(response.parsed)}"
                )

        return parsed_data_dict

    def _get_parsed_data_from_initiate_response(
        self,
        response: httpx.Response,
        decoded_content: str,
        attack_type_for_error_msg: str,
    ) -> Dict[str, Any]:
        """
        Process an attack initiation response and extract parsed data.

        This method handles different HTTP status codes and ensures that
        the response contains valid, parseable data for further processing.
        It provides comprehensive error handling for various failure scenarios.

        Args:
            response: The httpx.Response object from an attack initiation request.
            decoded_content: Pre-decoded string content of the response.
            attack_type_for_error_msg: Descriptive string for error messages.

        Returns:
            A dictionary containing the parsed response data.

        Raises:
            HackAgentError: If the response indicates failure (status >= 300),
                if a 201 response lacks parseable data, or if unexpected
                status codes are received without valid data.
        """
        parsed_data_dict = self._parse_json_from_response_data(
            response, decoded_content, attack_type_for_error_msg
        )

        if response.status_code == 201:
            if not parsed_data_dict:
                # This case implies that _parse_json_from_response_data returned None for a 201, which means
                # either no content, or content that wasn't JSON, or pre-parsed attributes also failed.
                # If content was present but bad JSON, _parse_json_from_response_data would have raised.
                logger.error(
                    f"201 for {attack_type_for_error_msg} but no parsable dictionary body was found. Decoded content: '{decoded_content}', Pre-parsed type: {type(response.parsed if hasattr(response, 'parsed') else None)}"
                )
                raise HackAgentError(
                    f"201 for {attack_type_for_error_msg} but no parsable dictionary body was found."
                )

        elif response.status_code >= 300:
            err_text = f"Failed to initiate {attack_type_for_error_msg}. Status: {response.status_code}, Body: {decoded_content}"
            logger.error(err_text)
            raise HackAgentError(err_text)

        else:  # Unexpected success status codes (e.g., 200 OK instead of 201 Created, or other 2xx)
            logger.warning(
                f"Unexpected success status {response.status_code} from initiate_{attack_type_for_error_msg}. Content: {decoded_content}"
            )
            if (
                not parsed_data_dict
            ):  # If still no data after trying for an unexpected success status
                err_text = (
                    f"Could not obtain parsable data from initiate_{attack_type_for_error_msg} response with unexpected status {response.status_code}. "
                    f"Content: {decoded_content}"
                )
                logger.error(err_text)
                raise HackAgentError(err_text)

        if (
            not parsed_data_dict
        ):  # Should be caught by earlier checks, but as a final safeguard
            logger.error(
                f"Internal logic error: Parsed data dictionary is None for {attack_type_for_error_msg} status {response.status_code} without raising earlier. Content: {decoded_content}"
            )
            raise HackAgentError(
                f"Failed to obtain parsed data for {attack_type_for_error_msg} (status {response.status_code}). Check logs for parsing attempts."
            )
        return parsed_data_dict

    def _extract_ids_from_data_dict(
        self,
        parsed_data_dict: Dict[str, Any],
        attack_type_for_error_msg: str,
        original_content: str,
    ) -> Tuple[str, Optional[str]]:
        """
        Extract attack ID and optional run ID from a parsed response dictionary.

        This method extracts the mandatory 'id' field (attack_id) and optional
        'associated_run_id' field from API response data.

        Args:
            parsed_data_dict: Dictionary containing parsed response data.
            attack_type_for_error_msg: Descriptive string for error messages.
            original_content: Original response content string for error reporting.

        Returns:
            A tuple containing (attack_id, run_id). The attack_id is always a string,
            while run_id may be None if not present in the response.

        Raises:
            HackAgentError: If the mandatory attack_id cannot be extracted or
                is invalid.
        """
        raw_attack_id = parsed_data_dict.get("id")
        attack_id_str = str(raw_attack_id) if raw_attack_id is not None else None

        if attack_id_str is None:
            err_detail = (
                f"Could not extract mandatory attack_id ('{attack_id_str}') "
                f"from initiate_{attack_type_for_error_msg} response. "
                f"Source dict: {parsed_data_dict}, Original Decoded Content: '{original_content}'"
            )
            logger.error(err_detail)
            raise HackAgentError(err_detail)

        raw_run_id = parsed_data_dict.get("associated_run_id")
        run_id_str = str(raw_run_id) if raw_run_id is not None else None

        logger.info(
            f"Extracted Attack ID: {attack_id_str} and optional server-associated Run ID: {run_id_str if run_id_str else 'Not Provided'} for {attack_type_for_error_msg}."
        )
        return attack_id_str, run_id_str

    def extract_attack_and_run_ids_from_initiate_response(
        self, response: httpx.Response, attack_type_for_error_msg: str = "attack"
    ) -> Tuple[str, Optional[str]]:
        """
        Orchestrate the extraction of attack and run IDs from an attack creation response.

        This is the main entry point for extracting IDs from API responses. It coordinates
        the decoding, parsing, and extraction process using the helper methods.

        Args:
            response: The httpx.Response object from an attack creation API call.
            attack_type_for_error_msg: Descriptive string for error messages,
                defaults to "attack".

        Returns:
            A tuple containing (attack_id, run_id). The attack_id is always present
            as a string, while run_id may be None if not provided in the response.

        Raises:
            HackAgentError: If the attack_id cannot be extracted or if the response
                indicates an error condition.
        """
        logger.debug(
            f"Attempting to extract Attack/Run IDs for '{attack_type_for_error_msg}' from response (status: {response.status_code})"
        )
        decoded_content = self._decode_response_content(response)
        parsed_data_dict = self._get_parsed_data_from_initiate_response(
            response, decoded_content, attack_type_for_error_msg
        )
        return self._extract_ids_from_data_dict(
            parsed_data_dict, attack_type_for_error_msg, decoded_content
        )


class AdvPrefix(AttackStrategy):
    """
    Strategy implementation for AdvPrefix (Adversarial Prefix) attacks.

    This strategy implements adversarial prefix generation attacks that use
    uncensored models to generate prefixes that can elicit harmful responses
    from target models. The attack follows a multi-stage pipeline including
    prefix generation, cross-entropy computation, completion generation,
    evaluation, and final selection.

    The strategy integrates with the HackAgent backend to track attack
    progress and results while executing the local AdvPrefix pipeline.
    """

    def _prepare_and_validate_attack_params(
        self,
        attack_config: Dict[str, Any],
    ) -> List[Any]:
        """
        Validate and extract necessary parameters from the attack configuration.

        This method ensures that the attack configuration contains all required
        parameters for the AdvPrefix attack execution.

        Args:
            attack_config: Dictionary containing attack configuration parameters.
                Must include a 'goals' key with a list of target goals.

        Returns:
            A list of goals extracted from the attack configuration.

        Raises:
            ValueError: If the 'goals' key is missing or is not a list.
        """
        goals = attack_config.get("goals")
        if not isinstance(goals, list):
            raise ValueError(
                "'attack_config' must contain 'goals' list for AdvPrefixAttack."
            )

        return goals

    def _create_server_attack_record(
        self,
        victim_agent_id: UUID,
        organization_id: UUID,
        attack_config: Dict[str, Any],  # Used for summary
    ) -> str:
        """
        Create an Attack record on the HackAgent server.

        This method creates a new attack record in the backend system to track
        the AdvPrefix attack execution and results.

        Args:
            victim_agent_id: UUID of the target agent being attacked.
            organization_id: UUID of the organization running the attack.
            attack_config: Configuration dictionary for the attack, stored
                as metadata in the attack record.

        Returns:
            The string ID of the created attack record.

        Raises:
            HackAgentError: If the attack record creation fails or if the
                response cannot be parsed to extract the attack ID.
        """
        logger.info("Creating Attack record on the server.")
        attack_type = "advprefix"

        payload = {
            "type": attack_type,
            "agent": str(victim_agent_id),  # Convert UUID to string
            "organization": str(organization_id),  # Convert UUID to string
            "configuration": attack_config,
        }
        try:
            attack_req_obj = AttackRequest.from_dict(payload)
            logger.debug(
                f"Attempting to create Attack record with payload: {attack_req_obj.to_dict()}"
            )
            response = attacks_create_sync_detailed(
                client=self.client, body=attack_req_obj
            )
        except Exception as e:
            logger.error(
                f"Failed to construct/send AttackRequest for {attack_type} record: {e}",
                exc_info=True,
            )
            raise HackAgentError(
                f"Failed to send AttackRequest for {attack_type} record: {e}"
            ) from e

        attack_id, _ = self.extract_attack_and_run_ids_from_initiate_response(
            response=response, attack_type_for_error_msg=attack_type
        )
        logger.info(f"Attack record created on server. Attack ID: {attack_id}.")
        return attack_id

    def _create_server_run_record(
        self,
        attack_id: str,
        victim_agent_id: str,
        run_config_override: Optional[Dict[str, Any]],
    ) -> str:
        """
        Create a Run record on the HackAgent server for tracking attack execution.

        This method creates a new run record associated with the attack to track
        the specific execution instance and its results.

        Args:
            attack_id: String ID of the attack record this run belongs to.
            victim_agent_id: String ID of the target agent being attacked.
            run_config_override: Optional configuration overrides for this
                specific run instance.

        Returns:
            The string ID of the created run record.

        Raises:
            HackAgentError: If the run record creation fails, if the response
                cannot be parsed, or if the run ID cannot be extracted.
        """
        logger.info(
            f"Attempting to explicitly create a Run record for Attack ID: {attack_id}"
        )
        payload = RunRequest(
            attack=attack_id,
            agent=victim_agent_id,
            run_config=run_config_override if run_config_override else {},
        )
        try:
            # response_obj is the custom hackagent.types.Response[Run]
            response_obj = run_run_tests_create.sync_detailed(
                client=self.client, body=payload
            )

            created_run: Optional[Run] = response_obj.parsed

            # If the auto-generated client didn't parse for 201, but it's a success, try manual parsing.
            if created_run is None and response_obj.status_code == HTTPStatus.CREATED:
                logger.info(
                    f"Run creation returned 201 (CREATED), attempting to manually parse response content for Attack ID: {attack_id}"
                )
                if response_obj.content:
                    try:
                        created_run_data = json.loads(
                            response_obj.content.decode("utf-8")
                        )
                        created_run = Run.from_dict(
                            created_run_data
                        )  # Use the Run model's from_dict
                        logger.info(
                            f"Manually parsed Run object from 201 response for Attack ID {attack_id}. Run ID: {created_run.id if created_run and hasattr(created_run, 'id') else 'Parse_Failed_Or_No_ID'}"
                        )
                    except json.JSONDecodeError as jde:
                        logger.error(
                            f"Failed to manually parse JSON from 201 response content for Attack ID {attack_id}: {jde}. Content: {response_obj.content.decode('utf-8', errors='replace')}",
                            exc_info=True,
                        )
                        # created_run remains None, will be caught by the check below
                    except Exception as e:
                        logger.error(
                            f"Unexpected error manually parsing 201 response content for Attack ID {attack_id}: {e}",
                            exc_info=True,
                        )
                        # created_run remains None, will be caught by the check below
                else:
                    logger.warning(
                        f"Run creation returned 201 (CREATED) but response content was empty for Attack ID: {attack_id}. Cannot manually parse."
                    )

            if not created_run or not hasattr(created_run, "id") or not created_run.id:
                status_code_val = (
                    response_obj.status_code
                    if hasattr(response_obj, "status_code")
                    else "Unknown Status"
                )
                content_val = (
                    response_obj.content.decode("utf-8", errors="replace")
                    if hasattr(response_obj, "content") and response_obj.content
                    else "No content"
                )

                logger.error(
                    f"Failed to get valid Run ID from run creation for Attack {attack_id}. "
                    f"Status: {status_code_val}, Parsed: {created_run}, Content: {content_val}"
                )
                raise HackAgentError(
                    f"Server API for Run creation returned status {status_code_val} "
                    f"but response parsing failed, lacked Run ID, or an error occurred. Content: {content_val}"
                )

            run_id = str(created_run.id)
            logger.info(
                f"Successfully created Run ID: {run_id} for Attack ID: {attack_id}"
            )
            return run_id

        except errors.UnexpectedStatus as use:
            # This is caught if client.raise_on_unexpected_status is True and server returns non-200
            error_content = (
                use.content.decode("utf-8", errors="replace")
                if use.content
                else "No content"
            )
            logger.error(
                f"API error (UnexpectedStatus {use.status_code}) creating Run for Attack {attack_id}: {error_content}",
                exc_info=True,
            )
            raise HackAgentError(
                f"Failed to create Run for Attack {attack_id} (API status {use.status_code}): {error_content}"
            ) from use
        except Exception as e:
            logger.error(
                f"Error creating Run for Attack {attack_id}: {e}", exc_info=True
            )
            raise HackAgentError(
                f"Failed to create Run for Attack {attack_id}: {e}"
            ) from e

    def _prepare_attack_config(
        self,
        attack_config: Dict[str, Any],
        run_id: str,
        attack_id: str,
    ) -> Dict[str, Any]:
        """
        Prepare the configuration dictionary for the local AdvPrefixAttack execution.

        This method processes the user-provided attack configuration and adds
        necessary parameters for the AdvPrefix attack execution, including
        server-generated IDs and client objects.

        Args:
            attack_config: Original attack configuration provided by the user.
            run_id: Server-generated run ID for tracking this execution.
            attack_id: Server-generated attack ID for this attack instance.

        Returns:
            A dictionary containing the prepared configuration with all necessary
            parameters for AdvPrefixAttack execution, including client references
            and execution metadata.
        """
        logger.debug(f"Preparing local attack config for Run ID: {run_id}")
        # Deep copy the user-provided attack_config to avoid modifying it directly.
        prepared_config = json.loads(json.dumps(attack_config))

        # Explicitly set/override 'run_id' with the server-generated run_id.
        # This 'run_id' will be used by AdvPrefixAttack to initialize its self.run_id.
        original_config_run_id = prepared_config.get("run_id")
        prepared_config["run_id"] = run_id
        if original_config_run_id and original_config_run_id != run_id:
            logger.info(
                f"Overriding 'run_id' in attack_config from '{original_config_run_id}' to server Run ID '{run_id}' for AdvPrefixAttack."
            )
        elif not original_config_run_id:
            logger.info(
                f"Set 'run_id' in attack_config to server Run ID '{run_id}' for AdvPrefixAttack."
            )

        # Update with other necessary parameters for AdvPrefixAttack
        prepared_config.update(
            {
                "hackagent_client": self.client,
                "agent_router": self.hack_agent.router,
                # "initial_run_id": run_id, # This is no longer needed as AdvPrefixAttack.run will use self.run_id
                "attack_id": attack_id,
            }
        )

        # Ensure 'output_dir' is present, defaulting if necessary.
        # AdvPrefixAttack uses this as the final output directory (no nested run_id subdirectory).
        if "output_dir" not in prepared_config:
            # Create timestamp-based directory structure for better organization
            # Format: ./logs/runs/YYYY-MM-DD/HH-MM-SS_attack-id-prefix
            from datetime import datetime

            now = datetime.now()
            date_dir = now.strftime("%Y-%m-%d")
            time_prefix = now.strftime("%H-%M-%S")
            attack_id_short = attack_id[:8] if len(attack_id) > 8 else attack_id
            prepared_config["output_dir"] = (
                f"./logs/runs/{date_dir}/{time_prefix}_{attack_id_short}"
            )
            logger.warning(
                f"'output_dir' not in attack_config for AdvPrefixAttack, defaulting to {prepared_config['output_dir']}"
            )

        return prepared_config

    def _execute_local_prefix_attack(
        self,
        attack_config: Dict[str, Any],
        goals: List[Any],
        run_id: str,  # Server run_id
        attack_id: str,
        _tui_app: Optional[Any] = None,
        _tui_log_callback: Optional[Any] = None,
    ) -> Optional[pd.DataFrame]:
        """
        Execute the local AdvPrefix attack using the configured pipeline.

        This method instantiates and runs the AdvPrefixAttack with the prepared
        configuration and target goals. It handles the execution of the complete
        adversarial prefix generation pipeline.

        Args:
            attack_config: Attack configuration dictionary containing pipeline parameters.
            goals: List of target goals for the adversarial prefix generation.
            run_id: Server-generated run ID for tracking this execution.
            attack_id: Server-generated attack ID for this attack instance.

        Returns:
            A pandas DataFrame containing the attack results if successful,
            None if the attack execution fails.

        Note:
            This method handles exceptions internally and returns None on failure
            rather than raising exceptions, allowing the calling code to handle
            failures gracefully.
        """
        logger.info(
            f"Executing local prefix attack for Attack ID {attack_id}, Server Run ID {run_id}."
        )
        try:
            # runner_config from _prepare_attack_config is a flat dictionary
            # containing pipeline params, client object, and router object.
            flat_prepared_config = self._prepare_attack_config(
                attack_config, run_id, attack_id
            )

            # Extract the client and router objects that AdvPrefixAttack expects as direct arguments.
            # The key for the client object in flat_prepared_config is "hackagent_client".
            adv_prefix_client = flat_prepared_config.pop("hackagent_client")
            adv_prefix_router = flat_prepared_config.pop("agent_router")

            # Remove other keys that are not part of AdvPrefixAttack's 'config' dictionary
            # or were passed for strategy-level logic but not for AdvPrefixAttack.__init__.
            flat_prepared_config.pop(
                "attack_type", None
            )  # Already handled if in original attack_config
            flat_prepared_config.pop(
                "goals", None
            )  # Already handled if in original attack_config

            # The remaining flat_prepared_config is now the dictionary
            # that AdvPrefixAttack expects for its 'config' parameter.
            # This dictionary includes user's settings, run_id, attack_id, output_dir etc.

            runner = AdvPrefixAttack(
                config=flat_prepared_config,
                client=adv_prefix_client,
                agent_router=adv_prefix_router,
            )

            # Attach TUI log handler if TUI context is provided
            if _tui_app and _tui_log_callback:
                try:
                    from hackagent.cli.tui.logger import attach_tui_handler

                    attach_tui_handler(
                        attack_instance=runner,
                        app=_tui_app,
                        callback=_tui_log_callback,
                    )
                    logger.info("TUI log handler attached to attack instance")
                except ImportError:
                    logger.warning(
                        "Failed to import TUI logger, logs will not be shown in TUI"
                    )

            # AdvPrefixAttack.run will use its self.run_id, which is initialized from runner_config["run_id"].
            results_df = runner.run(goals=goals)  # No longer pass initial_run_id
            logger.info(
                f"Local prefix attack completed for Attack ID {attack_id}, Server Run ID {run_id}."
            )
            return results_df
        except Exception as e:
            logger.error(
                f"Error during local prefix attack execution for Attack ID {attack_id}, Server Run ID {run_id}: {e}",
                exc_info=True,
            )
            return None  # Or re-raise if appropriate for the calling context

    def _log_local_run_persistence_info(
        self,
        attack_config: Dict[str, Any],
        attack_id: str,
        run_id: str,
        fail_on_run_error: bool,  # To decide if error during this info step is critical
    ):
        """
        Log information about local run data persistence and file locations.

        This method logs details about where local attack execution data
        (such as intermediate CSV files) are stored for debugging and
        result retrieval purposes.

        Args:
            attack_config: Attack configuration containing output directory settings.
            attack_id: String ID of the attack record.
            run_id: String ID of the run record.
            fail_on_run_error: Whether errors in this step should be treated as
                critical. Currently unused as this method only logs information.

        Note:
            This method currently only performs logging operations. If actual
            file operations were performed, error handling would be more critical
            based on the fail_on_run_error parameter.
        """
        # This method currently only logs. If actual operations were done, error handling would be more critical.
        try:
            base_output_dir = attack_config.get(
                "output_dir", f"./hackagent_local_runs/{attack_id}"
            )
            actual_run_output_dir = os.path.join(base_output_dir, f"run_{run_id}")
            input_csv_hint = attack_config.get(
                "input_csv_for_model_persistence", "step9_output.csv"
            )
            logger.info(
                f"Local run data (for potential Pydantic model persistence/Step10): Dir='{actual_run_output_dir}', CSV hint='{input_csv_hint}'."
            )
        except Exception as e:
            logger.error(
                f"Error preparing local run persistence info for Attack {attack_id}: {e}",
                exc_info=True,
            )
            if fail_on_run_error:
                # This is just logging info, so might not be fatal unless other operations depend on it.
                # For now, just log and continue, but could raise if this setup was critical.
                pass

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
        Execute the complete AdvPrefix attack workflow.

        This method orchestrates the full AdvPrefix attack execution, including
        server-side record creation, local attack execution, and result processing.
        It follows a structured workflow:

        1. Create an Attack record on the HackAgent server for tracking
        2. Create a Run record associated with the Attack for this execution
        3. Execute the local AdvPrefix pipeline with the target goals
        4. Log persistence information for results and intermediate data

        Args:
            attack_config: Configuration dictionary containing attack parameters.
                Must include 'goals' key with a list of target goals for the attack.
                May include 'output_dir' and other AdvPrefix pipeline parameters.
            run_config_override: Optional configuration overrides for this specific
                run. Can be used to modify default run parameters without affecting
                the main attack configuration.
            fail_on_run_error: Whether to raise an exception if the local attack
                execution fails. If False, the method will return None for failed
                executions instead of raising an exception.

        Returns:
            A pandas DataFrame containing the attack results from the local AdvPrefix
            execution if successful. Returns None if the attack fails and
            fail_on_run_error is False.

        Raises:
            HackAgentError: If victim agent ID or organization ID is not available,
                if server record creation fails, or if local execution fails and
                fail_on_run_error is True.
            ValueError: If the 'goals' key is missing from attack_config.

        Note:
            This method creates server-side records for tracking and audit purposes
            but the actual attack execution happens locally. Future versions may
            include server-side result uploading and status updates.
        """
        victim_agent_id: UUID = self.hack_agent.router.backend_agent.id
        organization_id: UUID = self.hack_agent.router.organization_id

        if not victim_agent_id or not organization_id:
            raise HackAgentError(
                "Victim agent ID or Organization ID is not available. Ensure agent is initialized."
            )

        # 1. Create Attack record on the server
        attack_id = self._create_server_attack_record(
            victim_agent_id=victim_agent_id,
            organization_id=organization_id,
            attack_config=attack_config,  # Pass for summary or details
        )
        logger.info(f"AdvPrefix server Attack record created with ID: {attack_id}")

        # 2. Create Run record on the server
        run_id = self._create_server_run_record(
            attack_id=attack_id,
            victim_agent_id=victim_agent_id,
            run_config_override=run_config_override,
        )
        logger.info(
            f"AdvPrefix server Run record created with ID: {run_id} for Attack ID: {attack_id}"
        )

        # 3. Execute the local AdvPrefix attack logic
        goals = attack_config.get("goals")
        if not goals:
            raise ValueError("AdvPrefix attack requires 'goals' in attack_config.")

        # Assuming _execute_local_prefix_attack is now synchronous
        local_results_df = self._execute_local_prefix_attack(
            attack_config=attack_config,
            goals=goals,
            run_id=run_id,
            attack_id=attack_id,
            _tui_app=_tui_app,
            _tui_log_callback=_tui_log_callback,
        )

        # 4. Log persistence info (which internally might update server records)
        # This step might be expanded to explicitly update server records if needed.
        self._log_local_run_persistence_info(
            attack_config, attack_id, run_id, fail_on_run_error
        )

        if local_results_df is None and fail_on_run_error:
            raise HackAgentError(
                f"AdvPrefix local execution failed for Attack ID {attack_id} and Run ID {run_id}."
            )

        logger.info(f"AdvPrefix attack execution completed for Attack ID {attack_id}.")
        # Return the DataFrame from the local execution as the primary result for now.
        # Future: Might return a more comprehensive result object or the server Run object.
        return local_results_df


# --- End Strategy Pattern ---
