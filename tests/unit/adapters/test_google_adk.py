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


import unittest
from unittest.mock import patch, MagicMock
import logging
import requests  # Added for requests.exceptions

from hackagent.router.adapters.google_adk import (
    ADKAgentAdapter,
    AgentConfigurationError,
    AgentInteractionError,
)

# Disable logging for tests to keep output clean
logging.disable(logging.CRITICAL)


class TestADKAgentAdapterInit(unittest.TestCase):
    def test_init_success_with_all_required_config(self):
        adapter_id = "adk_test_agent_001"
        config = {
            "name": "multi_tool_agent_app",
            "endpoint": "http://fake-adk-endpoint.com/api",
            "user_id": "test_user_adk",
            "request_timeout": 60,
        }
        try:
            adapter = ADKAgentAdapter(id=adapter_id, config=config)
            self.assertEqual(adapter.id, adapter_id)
            self.assertEqual(adapter.name, config["name"])
            self.assertEqual(adapter.endpoint, config["endpoint"].strip("/"))
            self.assertEqual(adapter.user_id, config["user_id"])
            self.assertEqual(adapter.request_timeout, config["request_timeout"])
        except AgentConfigurationError:
            self.fail(
                "ADKAgentAdapter initialization failed unexpectedly with valid config."
            )

    def test_init_uses_default_timeout_if_not_provided(self):
        adapter_id = "adk_test_agent_002"
        config = {
            "name": "another_agent",
            "endpoint": "http://another-endpoint.com",
            "user_id": "user_abc",
        }
        adapter = ADKAgentAdapter(id=adapter_id, config=config)
        self.assertEqual(adapter.request_timeout, 120)  # Default timeout

    def test_init_missing_name_raises_error(self):
        with self.assertRaisesRegex(
            AgentConfigurationError, "Missing required configuration key 'name'"
        ):
            ADKAgentAdapter(
                id="err_agent_1", config={"endpoint": "ep", "user_id": "uid"}
            )

    def test_init_missing_endpoint_raises_error(self):
        with self.assertRaisesRegex(
            AgentConfigurationError, "Missing required configuration key 'endpoint'"
        ):
            ADKAgentAdapter(
                id="err_agent_2", config={"name": "app_name", "user_id": "uid"}
            )

    def test_init_missing_user_id_raises_error(self):
        with self.assertRaisesRegex(
            AgentConfigurationError, "Missing required configuration key 'user_id'"
        ):
            ADKAgentAdapter(
                id="err_agent_3", config={"name": "app_name", "endpoint": "ep"}
            )

    def test_init_endpoint_gets_stripped(self):
        adapter_id = "adk_strip_test"
        config = {
            "name": "strip_app",
            "endpoint": "http://fake-adk-endpoint.com/api/",  # trailing slash
            "user_id": "strip_user",
        }
        adapter = ADKAgentAdapter(id=adapter_id, config=config)
        self.assertEqual(adapter.endpoint, "http://fake-adk-endpoint.com/api")


class TestADKAgentAdapterCreateSession(unittest.TestCase):
    def setUp(self):
        self.adapter_id = "adk_session_test_agent"
        self.config = {
            "name": "test_app",
            "endpoint": "http://fake-adk.com",
            "user_id": "test_user",
        }
        self.adapter = ADKAgentAdapter(id=self.adapter_id, config=self.config)
        self.session_id = "test_session_123"

    @patch("requests.post")
    def test_create_session_internal_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()  # Does not raise for 200
        mock_post.return_value = mock_response

        result = self.adapter._create_session_internal(session_id=self.session_id)
        self.assertTrue(result)
        expected_url = f"{self.config['endpoint']}/apps/{self.config['name']}/users/{self.config['user_id']}/sessions/{self.session_id}"
        mock_post.assert_called_once_with(
            expected_url, headers=unittest.mock.ANY, json={}, timeout=30
        )

    @patch("requests.post")
    def test_create_session_internal_success_with_initial_state(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response
        initial_state = {"key": "value"}

        result = self.adapter._create_session_internal(
            session_id=self.session_id, initial_state=initial_state
        )
        self.assertTrue(result)
        expected_url = f"{self.config['endpoint']}/apps/{self.config['name']}/users/{self.config['user_id']}/sessions/{self.session_id}"
        mock_post.assert_called_once_with(
            expected_url, headers=unittest.mock.ANY, json=initial_state, timeout=30
        )

    @patch("requests.post")
    def test_create_session_internal_already_exists_409(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 409
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            response=mock_response
        )
        mock_post.return_value = mock_response

        result = self.adapter._create_session_internal(session_id=self.session_id)
        self.assertTrue(result)

    @patch("requests.post")
    def test_create_session_internal_already_exists_400_specific_message(
        self, mock_post
    ):
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Session already exists for this user and app."
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            response=mock_response
        )
        mock_post.return_value = mock_response

        result = self.adapter._create_session_internal(session_id=self.session_id)
        self.assertTrue(result)

    @patch("requests.post")
    def test_create_session_internal_http_error_other(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 500  # Other server error
        mock_response.text = "Internal Server Error"
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            response=mock_response
        )
        mock_post.return_value = mock_response

        with self.assertRaisesRegex(
            AgentInteractionError, "HTTP Error 500 creating session test_session_123"
        ):
            self.adapter._create_session_internal(session_id=self.session_id)

    @patch("requests.post")
    def test_create_session_internal_request_exception_timeout(self, mock_post):
        mock_post.side_effect = requests.exceptions.Timeout("Request timed out")
        with self.assertRaisesRegex(
            AgentInteractionError,
            "Request failed creating session test_session_123: Request timed out",
        ):
            self.adapter._create_session_internal(session_id=self.session_id)

    @patch("requests.post")
    def test_create_session_internal_request_exception_connection(self, mock_post):
        mock_post.side_effect = requests.exceptions.ConnectionError(
            "Connection refused"
        )
        with self.assertRaisesRegex(
            AgentInteractionError,
            "Request failed creating session test_session_123: Connection refused",
        ):
            self.adapter._create_session_internal(session_id=self.session_id)


class TestADKAgentAdapterHandleRequestValidation(unittest.TestCase):
    def setUp(self):
        self.adapter_id = "adk_handle_req_test_agent"
        self.config = {
            "name": "handle_app",
            "endpoint": "http://fake-handle.com",
            "user_id": "handle_user",
        }
        self.adapter = ADKAgentAdapter(id=self.adapter_id, config=self.config)

    def test_handle_request_missing_prompt(self):
        request_data = {"session_id": "sess_abc"}
        response = self.adapter.handle_request(request_data)
        self.assertEqual(response["status_code"], 400)
        self.assertIn(
            "Request data must include a 'prompt' field.", response["error_message"]
        )
        self.assertEqual(response["raw_request"], request_data)

    def test_handle_request_missing_session_id(self):
        # Session ID is optional - adapter uses default if not provided
        # This will fail with 500 when trying to create/verify the session
        request_data = {"prompt": "Hello agent"}
        response = self.adapter.handle_request(request_data)
        self.assertEqual(response["status_code"], 500)
        # Check that error message mentions session creation failure
        self.assertIn(
            "Failed to create/verify ADK session",
            response["error_message"],
        )
        self.assertEqual(response["raw_request"], request_data)


if __name__ == "__main__":
    unittest.main()
