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


import json
import logging
from typing import Any, Dict, Optional, Tuple

import requests
from requests.structures import CaseInsensitiveDict

from hackagent.router.adapters.base import Agent

# Global logger for this module, can be used by utility functions too
logger = logging.getLogger(__name__)


# --- Custom Exceptions (moved from api.utils.py) ---
class AgentConfigurationError(Exception):
    """Custom exception for agent configuration issues."""

    pass


class AgentInteractionError(Exception):
    """Custom exception for errors during interaction with the agent API."""

    pass


class ResponseParsingError(Exception):
    """Custom exception for errors parsing the agent's response."""

    pass


class ADKAgentAdapter(Agent):
    """
    Adapter for interacting with ADK (Agent Development Kit) based agents.

    This class implements the common `Agent` interface. It translates requests
    and responses between the router's standard format and the specific format
    required by ADK agents. It encapsulates all logic for ADK communication,
    including session management (optional), request formatting, execution,
    response parsing, and error handling.

    Attributes:
        name (str): The name of the ADK application (used for router registration AND as ADK app identifier).
        endpoint (str): The base API endpoint for the ADK agent.
        user_id (str): The user identifier for ADK sessions.
        request_timeout (int): Timeout in seconds for requests to the ADK agent.
        logger (logging.Logger): Logger instance for this adapter.
    """

    def __init__(self, id: str, config: Dict[str, Any]):
        """
        Initializes the ADKAgentAdapter.

        Args:
            id: The unique identifier for this ADK agent instance.
            config: Configuration dictionary for the ADK agent.
                          Expected keys include:
                          - 'name': Name of the ADK application (e.g., 'multi_tool_agent').
                          - 'endpoint': Base URL of the ADK agent.
                          - 'user_id': User ID for the ADK session.
                          - 'request_timeout' (optional): Request timeout in seconds
                            (defaults to 120).

        Raises:
            AgentConfigurationError: If any required configuration key (name, endpoint, user_id) is missing.
        """
        super().__init__(id, config)
        required_keys = ["name", "endpoint", "user_id"]
        for key in required_keys:
            if key not in self.config:
                msg = f"Missing required configuration key '{key}' for ADKAgentAdapter: {self.id}"
                raise AgentConfigurationError(msg)

        self.name: str = self.config["name"]
        self.endpoint: str = self.config["endpoint"].strip("/")
        self.user_id: str = self.config["user_id"]
        self.request_timeout: int = self.config.get("request_timeout", 120)

        # Generate a unique session ID for this adapter instance
        # This keeps session state persistent across multiple requests to the same agent
        import uuid

        self.session_id: str = self.config.get("session_id", str(uuid.uuid4()))

        # Use hierarchical logger name for TUI handler inheritance
        self.logger = logging.getLogger(
            f"hackagent.router.adapters.ADKAgentAdapter.{self.id}"
        )
        self.logger.info(
            f"ADKAgentAdapter initialized with session_id: {self.session_id}"
        )

    def _initialize_session(
        self, session_id_to_init: str, initial_state: Optional[dict] = None
    ) -> bool:
        """
        (Optional) Creates or ensures a specific ADK session exists.

        Args:
            session_id_to_init: The specific session ID to initialize.
            initial_state: An optional dictionary to provide initial state when
                           creating the ADK session.
        Returns:
            True if the session was created successfully or already existed.
        Raises:
            AgentInteractionError: If there's an issue.
        """
        self.logger.info(f"Explicitly initializing ADK session: {session_id_to_init}.")
        try:
            return self._create_session_internal(
                session_id=session_id_to_init, initial_state=initial_state
            )
        except AgentInteractionError as e:
            self.logger.error(
                f"Failed to initialize ADK session {session_id_to_init}: {e}"
            )
            raise

    def _create_session_internal(
        self, session_id: str, initial_state: Optional[dict] = None
    ) -> bool:
        """
        Internal helper to create a session on the ADK server.

        Sends a POST request to the ADK session creation endpoint.

        Args:
            session_id: The specific session ID to create.
            initial_state: An optional dictionary to provide initial state for the session.

        Returns:
            True if the session was successfully created or if it already existed (HTTP 409, or HTTP 400 with specific message).

        Raises:
            AgentInteractionError: If the HTTP request fails or the server returns
                                   an unexpected error status.
        """
        target_url = f"{self.endpoint}/apps/{self.name}/users/{self.user_id}/sessions/{session_id}"
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        payload = initial_state or {}
        self.logger.info(f"Attempting to create ADK session: {target_url}")
        try:
            response = requests.post(
                target_url, headers=headers, json=payload, timeout=30
            )
            response.raise_for_status()
            self.logger.info(f"Successfully created ADK session {session_id}")
            return True
        except requests.exceptions.HTTPError as http_err:
            if http_err.response is not None:
                status_code = http_err.response.status_code
                response_text_lower = ""
                original_response_text = "[Could not read body]"
                try:
                    original_response_text = http_err.response.text
                    response_text_lower = original_response_text.lower()
                except Exception as e_text:
                    self.logger.warning(
                        f"Could not get text from error response (status {status_code}) for session {session_id}: {e_text}"
                    )

                # Condition 1: HTTP 409 Conflict (standard "already exists")
                if status_code == 409:
                    self.logger.warning(
                        f"ADK session {session_id} already exists (HTTP 409). Proceeding."
                    )
                    return True

                # Condition 2: HTTP 400 Bad Request + specific message (ADK server's current behavior)
                if (
                    status_code == 400
                    and "session already exists" in response_text_lower
                ):
                    self.logger.warning(
                        f"ADK session {session_id} already exists (HTTP 400 with 'session already exists' in body). "
                        f"Proceeding. Body: {original_response_text}"
                    )
                    return True

            # If neither of the above conditions met, then it's a genuine error
            err_msg_detail_base = f"HTTP error creating ADK session {session_id}"
            err_msg_detail_extended = ""
            current_status_for_exc = "Unknown"

            if http_err.response is not None:
                try:
                    current_status_for_exc = http_err.response.status_code
                    # Ensure response_text is defined for logging if it wasn't fetched successfully above
                    body_for_log = (
                        original_response_text
                        if "original_response_text" in locals()
                        else "[Could not read body during logging]"
                    )
                    err_msg_detail_extended = f": {http_err} - Status {current_status_for_exc} - Body: {body_for_log}"
                except Exception as e_resp_attrs:
                    self.logger.warning(
                        f"Could not get all attributes from error response for session {session_id}: {e_resp_attrs}"
                    )
                    err_msg_detail_extended = (
                        f": {http_err} (Error response attributes inaccessible)"
                    )
            else:  # http_err.response is None
                err_msg_detail_extended = f": {http_err}"

            self.logger.error(f"{err_msg_detail_base}{err_msg_detail_extended}")
            raise AgentInteractionError(
                f"HTTP Error {current_status_for_exc} creating session {session_id}"
            ) from http_err
        except requests.exceptions.RequestException as e:
            self.logger.error(
                f"Request exception creating ADK session {session_id}: {e}"
            )
            raise AgentInteractionError(
                f"Request failed creating session {session_id}: {e}"
            ) from e

    def _prepare_request_payload(
        self, prompt_text: str, session_id: str
    ) -> Tuple[dict, dict]:
        """
        Prepares the HTTP headers and JSON payload for an ADK agent request.

        Args:
            prompt_text: The user's prompt text to be sent to the agent.
            session_id: The session identifier for this specific ADK interaction.

        Returns:
            A tuple containing two dictionaries: the headers and the payload.
        """
        payload = {
            "app_name": self.name,
            "user_id": self.user_id,
            "session_id": session_id,
            "new_message": {"role": "user", "parts": [{"text": prompt_text}]},
        }
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        return headers, payload

    def _execute_http_post(
        self, url: str, headers: dict, payload: dict
    ) -> requests.Response:
        """
        Executes an HTTP POST request.

        Args:
            url: The URL to send the POST request to.
            headers: A dictionary of HTTP headers.
            payload: A dictionary to be sent as the JSON payload.

        Returns:
            A `requests.Response` object.

        Raises:
            AgentInteractionError: If the request times out or another request-related
                                   exception occurs.
        """
        try:
            # Log agent interaction for TUI visibility
            self.logger.info(f"🌐 Sending request to agent endpoint: {url}")
            if "message" in payload:
                msg_preview = str(payload["message"])[:100]
                self.logger.debug(f"   Message preview: {msg_preview}...")

            response = requests.post(
                url, headers=headers, json=payload, timeout=self.request_timeout
            )

            # Log response status
            self.logger.info(f"✅ Agent responded with status {response.status_code}")
            self.logger.debug(
                f"Request to {url} completed with status {response.status_code}"
            )
            return response
        except requests.exceptions.Timeout as e:
            self.logger.warning(f"Request timed out accessing {url}: {e}")
            raise AgentInteractionError(f"Request timed out: {e}") from e
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Request exception accessing {url}: {e}")
            raise AgentInteractionError(f"Request failed: {e}") from e

    def _parse_response_json(
        self, response: requests.Response
    ) -> Tuple[Optional[str], Optional[list], str, Optional[CaseInsensitiveDict]]:
        """
        Parses the JSON response from an ADK agent.

        It checks for HTTP errors first. Then, it attempts to parse the JSON body,
        expecting a list of events. It iterates through these events (in reverse)
        to find the agent's final text response or an escalation message.

        Args:
            response: The `requests.Response` object from the ADK agent.

        Returns:
            A tuple containing:
            - final_response_text (Optional[str]): The extracted text response.
            - events (Optional[list]): The full list of ADK events.
            - response_body_str (str): The raw response body as a string.
            - http_headers (Optional[CaseInsensitiveDict]): The response headers.

        Raises:
            AgentInteractionError: If an HTTP error status (4xx or 5xx) is encountered.
            ResponseParsingError: If the response body is not valid JSON, not in the
                                  expected list format, or if a non-event detail message
                                  is returned instead of events.
        """
        response_body_str = response.text
        http_headers = response.headers
        self.logger.debug(
            f"ADK Response Body for parsing: {response_body_str[:1000]}"
        )  # Log more of the body

        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as http_err:
            status = http_err.response.status_code if http_err.response else "Unknown"
            self.logger.error(
                f"HTTP error {status} from {response.url}: {response_body_str}"
            )
            raise AgentInteractionError(f"HTTP Error: {status}") from http_err

        final_response_text = None
        events = None
        try:
            events = response.json()
            if not isinstance(events, list):
                self.logger.warning(
                    f"ADK response was not a JSON list. Type: {type(events)}. Body: {response_body_str[:500]}"
                )
                if isinstance(events, dict) and "detail" in events:
                    detail_message = events["detail"]
                    self.logger.warning(
                        f"ADK returned non-event detail message: {detail_message}"
                    )
                    raise ResponseParsingError(
                        f"ADK returned detail message: {detail_message}"
                    )
                self.logger.warning(
                    f"ADK response not a JSON list or recognized detail. Body: {response_body_str[:500]}"
                )
                raise ResponseParsingError(
                    "ADK response format unrecognized (not a list)."
                )

            self.logger.debug(f"Received {len(events)} events from ADK for parsing.")

            for i, event in enumerate(reversed(events)):
                self.logger.debug(
                    f"Parsing event {len(events) - 1 - i} (reversed index {i}): {str(event)[:200]}..."
                )
                actions = event.get("actions")
                if actions and isinstance(actions, dict) and actions.get("escalate"):
                    error_msg = event.get(
                        "error_message",
                        "No specific message provided by agent for escalation.",
                    )
                    final_response_text = f"Agent escalated: {error_msg}"
                    self.logger.debug(
                        f"Escalation event found as final response: {final_response_text}"
                    )
                    break  # Found escalation, stop parsing

                content = event.get("content")
                if not content or not isinstance(content, dict):
                    self.logger.debug(
                        f"Event {len(events) - 1 - i} has no content or content is not a dict. Skipping for text."
                    )
                    continue

                parts = content.get("parts")
                if not parts or not isinstance(parts, list) or len(parts) == 0:
                    self.logger.debug(
                        f"Event {len(events) - 1 - i} content has no parts, parts is not a list, or parts is empty. Skipping for text."
                    )
                    continue

                # Check the first part for text
                first_part = parts[0]
                if not isinstance(first_part, dict):
                    self.logger.debug(
                        f"Event {len(events) - 1 - i} first part is not a dict: {type(first_part)}. Skipping for text."
                    )
                    continue

                part_text = first_part.get("text")
                if (
                    part_text is None
                ):  # Explicitly check for None, as empty string is fine if stripped later
                    self.logger.debug(
                        f"Event {len(events) - 1 - i} first part has no 'text' key. Skipping for text."
                    )
                    continue

                if not isinstance(part_text, str):
                    self.logger.debug(
                        f"Event {len(events) - 1 - i} first part 'text' is not a string: {type(part_text)}. Skipping for text."
                    )
                    continue

                # At this point, part_text is a string (could be empty)
                # The original code also checks `part_text.strip()` to ensure it's not just whitespace.
                # Let's keep that check.
                if part_text.strip():
                    final_response_text = part_text  # Store the original text, stripping is for check only
                    self.logger.debug(
                        f"Found text in event {len(events) - 1 - i}, part 0, as final response: '{final_response_text[:100]}...'"
                    )
                    break  # Found usable text, stop parsing
                else:
                    self.logger.debug(
                        f"Event {len(events) - 1 - i} first part text is empty or whitespace after strip. Skipping for text."
                    )

            if final_response_text is None:
                self.logger.warning(
                    f"No final response text could be extracted from any of the {len(events)} ADK events from {response.url}."
                )
            return final_response_text, events, response_body_str, http_headers
        except (
            json.JSONDecodeError,
            ValueError,
        ) as parse_err:  # Catch ValueError too for broader JSON issues
            self.logger.warning(
                f"Failed to parse ADK JSON from {response.url}: {parse_err}. Body: {response_body_str[:500]}"
            )
            raise ResponseParsingError(f"JSON parse failed: {parse_err}") from parse_err

    def _process_agent_interaction(self, prompt_text: str, session_id: str) -> dict:
        """
        Manages a single interaction (turn) with the ADK agent for a given prompt.

        This involves preparing the payload, executing the HTTP POST request to the
        correct ADK :runTurn endpoint, and parsing the response.

        Args:
            prompt_text: The prompt text to send to the ADK agent.
            session_id: The ADK session ID for this interaction.

        Returns:
            A dictionary containing detailed results of the interaction, including:
            - 'generated_text': The agent's final response text.
            - 'adapter_specific_events': Full list of ADK events.
            - 'raw_request': The payload sent to the agent.
            - 'raw_response_status': HTTP status code of the agent's response.
            - 'raw_response_headers': HTTP headers from the agent's response.
            - 'raw_response_body': Raw body of the agent's response.
            - 'error_message': Any error message if an issue occurred.
        """
        interaction_result: Dict[str, Any] = {
            "generated_text": None,
            "adapter_specific_events": None,
            "raw_request": None,
            "raw_response_status": None,
            "raw_response_headers": None,
            "raw_response_body": None,
            "error_message": None,
        }

        try:
            headers, payload = self._prepare_request_payload(prompt_text, session_id)
            interaction_result["raw_request"] = payload

            # Reverting to the simple /run endpoint as per general ADK docs
            run_turn_url = f"{self.endpoint}/run"
            self.logger.debug(
                f"Sending ADK request to: {run_turn_url} with payload app_name: {payload.get('app_name')}"
            )

            response = self._execute_http_post(run_turn_url, headers, payload)
            interaction_result["raw_response_status"] = response.status_code
            # interaction_result["raw_response_headers"] is set in _parse_response_json
            # interaction_result["raw_response_body"] is set in _parse_response_json

            (
                final_text,
                events,
                response_body_str,
                resp_headers,
            ) = self._parse_response_json(response)

            interaction_result["generated_text"] = final_text
            interaction_result["adapter_specific_events"] = events
            interaction_result["raw_response_body"] = response_body_str
            interaction_result["raw_response_headers"] = (
                dict(resp_headers) if resp_headers else None
            )

        except AgentInteractionError as aie:
            self.logger.error(f"AgentInteractionError processing prompt: {aie}")
            interaction_result["error_message"] = f"ADK Error: {aie}"
        except ResponseParsingError as rpe:
            self.logger.error(f"ResponseParsingError processing prompt: {rpe}")
            interaction_result["error_message"] = f"ADK Response Parse Error: {rpe}"
        except Exception as e:
            self.logger.exception(f"Unexpected error during ADK agent interaction: {e}")
            interaction_result["error_message"] = f"Unexpected ADK Adapter Error: {e}"

        return interaction_result

    def _build_error_response(
        self,
        error_message: str,
        status_code: Optional[int],
        raw_request: Optional[Dict[str, Any]] = None,
        interaction_details: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Constructs a standardized error response dictionary for the adapter.

        Args:
            error_message: The primary error message string.
            status_code: The HTTP status code associated with the error, if applicable.
            raw_request: The original request data that led to the error.
            interaction_details: A dictionary containing details from
                                 `_process_agent_interaction` if the error occurred
                                 during ADK processing.

        Returns:
            A dictionary representing a standardized error response.
        """
        raw_response_headers = None
        raw_response_body = None
        actual_status_code = status_code
        adk_events = None

        if interaction_details:
            raw_response_headers = interaction_details.get("response_headers")
            raw_response_body = interaction_details.get("response_body_raw")
            adk_events = interaction_details.get("adk_events_list")
            if interaction_details.get("response_status_code") is not None:
                actual_status_code = interaction_details.get("response_status_code")
            if raw_request is None:
                raw_request = interaction_details.get("request_payload")

        return {
            "raw_request": raw_request,
            "processed_response": None,
            "status_code": (
                actual_status_code if actual_status_code is not None else 500
            ),
            "raw_response_headers": raw_response_headers,
            "raw_response_body": raw_response_body,
            "agent_specific_data": {"adk_events_list": adk_events},
            "error_message": error_message,
            "agent_id": self.id,
            "adapter_type": "ADKAgentAdapter",
        }

    def handle_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handles an incoming request by creating an ADK session (if not existing)
        and then processing the request through the ADK agent.

        Args:
            request_data: A dictionary containing the request data. Must include
                          a 'prompt' key with the text to send to the agent.
                          Optional keys:
                          - 'session_id': Override the adapter's default session_id (advanced usage)
                          - 'initial_session_state': Initial state dict for new sessions
                          - 'adk_session_id': Deprecated, use 'session_id' instead
                          - 'adk_user_id': Deprecated, adapter manages user_id

        Returns:
            A dictionary representing the agent's response or an error.
        """
        prompt_text = request_data.get("prompt")

        # Support both new 'session_id' and legacy 'adk_session_id' for backward compatibility
        session_id_from_request = request_data.get(
            "session_id", request_data.get("adk_session_id")
        )

        # Use adapter's instance session_id if not provided in request
        session_id_to_use = (
            session_id_from_request if session_id_from_request else self.session_id
        )

        initial_session_state = request_data.get("initial_session_state")  # Optional

        if not prompt_text:
            self.logger.warning("No 'prompt' found in request_data.")
            return self._build_error_response(
                error_message="Request data must include a 'prompt' field.",
                status_code=400,
                raw_request=request_data,
            )

        self.logger.info(
            f"Handling request for agent {self.id} with prompt: '{prompt_text[:75]}...' (Session: {session_id_to_use})"
        )

        try:
            # Step 1: Ensure ADK session exists
            self.logger.info(
                f"Ensuring ADK session '{session_id_to_use}' exists before running turn."
            )
            self._create_session_internal(
                session_id=session_id_to_use, initial_state=initial_session_state
            )
            # If _create_session_internal raises, it will be caught by the outer try-except
            self.logger.info(f"Session '{session_id_to_use}' confirmed/created.")

            # Step 2: Process the agent interaction (send to /run)
            interaction_details = self._process_agent_interaction(
                prompt_text, session_id=session_id_to_use
            )

            if interaction_details.get("error_message"):
                self.logger.warning(
                    f"ADK interaction for agent {self.id} (session {session_id_to_use}) processed with error: "
                    f"{interaction_details['error_message']}"
                )
                # Pass full interaction_details to enrich the error response
                return self._build_error_response(
                    error_message=interaction_details["error_message"],
                    status_code=interaction_details.get("raw_response_status"),
                    interaction_details=interaction_details,
                )

            # Success case
            return {
                "raw_request": interaction_details.get(
                    "raw_request"
                ),  # Changed from request_payload
                "generated_text": interaction_details.get("generated_text"),
                "status_code": interaction_details.get("raw_response_status"),
                "raw_response_headers": interaction_details.get("raw_response_headers"),
                "raw_response_body": interaction_details.get("raw_response_body"),
                "agent_specific_data": {
                    "adk_events_list": interaction_details.get(
                        "adapter_specific_events"
                    )
                },
                "error_message": None,
                "agent_id": self.id,
                "adapter_type": "ADKAgentAdapter",
            }
        except AgentInteractionError as aie_session:  # Specific catch for session errors from _create_session_internal
            self.logger.error(
                f"Failed to ensure ADK session '{session_id_to_use}': {aie_session}"
            )
            return self._build_error_response(
                error_message=f"Failed to create/verify ADK session '{session_id_to_use}': {aie_session}",
                status_code=500,  # Or a more specific code if available from aie_session
                raw_request=request_data,
            )
        except Exception as e:
            self.logger.exception(
                f"Unexpected error in handle_request for agent {self.id} (session {session_id_to_use}): {e}"
            )
            return self._build_error_response(
                error_message=f"Unexpected adapter error: {type(e).__name__} - {str(e)}",
                status_code=500,
                raw_request=request_data,
            )
