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
import os
import unittest
from unittest.mock import MagicMock, patch

import litellm  # Required for litellm.exceptions

from hackagent.router.adapters.litellm import (
    LiteLLMAgent,
    LiteLLMConfigurationError,
)

# Disable logging for tests
logging.disable(logging.CRITICAL)


class TestLiteLLMAgentInit(unittest.TestCase):
    def test_init_success_minimal_config(self):
        adapter_id = "litellm_test_001"
        config = {
            "name": "ollama/llama2"  # Model string
        }
        try:
            adapter = LiteLLMAgent(id=adapter_id, config=config)
            self.assertEqual(adapter.id, adapter_id)
            self.assertEqual(adapter.model_name, config["name"])
            self.assertIsNone(adapter.api_base_url)
            self.assertIsNone(adapter.actual_api_key)
            self.assertEqual(adapter.default_max_new_tokens, 100)
            self.assertEqual(adapter.default_temperature, 0.8)
            self.assertEqual(adapter.default_top_p, 0.95)
        except LiteLLMConfigurationError:
            self.fail("LiteLLMAgent initialization failed with minimal valid config.")

    def test_init_success_full_config_no_api_key_env(self):
        adapter_id = "litellm_test_002"
        config = {
            "name": "gpt-3.5-turbo",
            "endpoint": "https://api.openai.com/v1",
            "api_key": "OPENAI_API_KEY_ENV_VAR_NAME",  # Env var name
            "max_new_tokens": 200,
            "temperature": 0.7,
            "top_p": 0.9,
        }
        with patch.dict(os.environ, {}, clear=True):  # Ensure env var is not set
            adapter = LiteLLMAgent(id=adapter_id, config=config)
            self.assertEqual(adapter.model_name, config["name"])
            self.assertEqual(adapter.api_base_url, config["endpoint"])
            # When env var is not found, the adapter uses the string itself as the key
            self.assertEqual(adapter.actual_api_key, "OPENAI_API_KEY_ENV_VAR_NAME")
            self.assertEqual(adapter.default_max_new_tokens, config["max_new_tokens"])
            self.assertEqual(adapter.default_temperature, config["temperature"])
            self.assertEqual(adapter.default_top_p, config["top_p"])

    @patch.dict(os.environ, {"MY_LLM_API_KEY": "actual_key_from_env"})
    def test_init_success_with_api_key_from_env(self):
        adapter_id = "litellm_test_003"
        config = {
            "name": "claude-2",
            "api_key": "MY_LLM_API_KEY",  # Env var name
        }
        adapter = LiteLLMAgent(id=adapter_id, config=config)
        self.assertEqual(adapter.actual_api_key, "actual_key_from_env")

    def test_init_missing_name_raises_error(self):
        with self.assertRaisesRegex(
            LiteLLMConfigurationError, "Missing required configuration key 'name'"
        ):
            LiteLLMAgent(id="err_litellm_1", config={})

    def test_init_config_without_api_key_field(self):
        # Should not try to get from env if 'api_key' field itself is missing in config
        adapter_id = "litellm_test_004"
        config = {"name": "some-model"}
        with patch.object(
            os.environ, "get"
        ) as mock_os_environ_get:  # More specific patch
            adapter = LiteLLMAgent(id=adapter_id, config=config)
            self.assertIsNone(adapter.actual_api_key)
            mock_os_environ_get.assert_not_called()


class TestLiteLLMAgentHandleRequest(unittest.TestCase):
    def setUp(self):
        self.adapter_id = "litellm_handle_req_agent"
        self.config = {
            "name": "test-model",
            "endpoint": "http://fake-litellm-api.com",
            "max_new_tokens": 50,
            "temperature": 0.5,
            "top_p": 0.9,
        }
        self.adapter = LiteLLMAgent(id=self.adapter_id, config=self.config)
        self.prompt = "Hello LiteLLM"

    def test_handle_request_missing_prompt(self):
        request_data = {}
        response = self.adapter.handle_request(request_data)
        self.assertEqual(response["status_code"], 400)
        self.assertIn(
            "Request data must include either 'messages' or 'prompt' field.",
            response["error_message"],
        )
        self.assertEqual(response["raw_request"], request_data)

    @patch("litellm.completion")
    def test_handle_request_success(self, mock_litellm_completion):
        mock_choice = MagicMock()
        mock_choice.message = MagicMock()
        mock_choice.message.content = " a successful response."
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_litellm_completion.return_value = mock_response

        request_data = {"prompt": self.prompt, "max_new_tokens": 150}
        response = self.adapter.handle_request(request_data)

        self.assertEqual(response["status_code"], 200)
        self.assertIsNone(response["error_message"])
        self.assertEqual(response["processed_response"], " a successful response.")
        self.assertEqual(response["raw_request"], request_data)
        self.assertEqual(
            response["agent_specific_data"]["model_name"], self.config["name"]
        )
        # ChatCompletionsAgent base class normalizes to max_tokens
        self.assertEqual(
            response["agent_specific_data"]["invoked_parameters"]["max_tokens"], 150
        )  # Overridden
        self.assertEqual(
            response["agent_specific_data"]["invoked_parameters"]["temperature"],
            self.config["temperature"],
        )  # Default

        mock_litellm_completion.assert_called_once_with(
            model=self.config["name"],
            messages=[{"role": "user", "content": self.prompt}],
            max_tokens=150,
            temperature=self.config["temperature"],
            top_p=self.config["top_p"],
            api_base=self.config["endpoint"],
            custom_llm_provider="openai",
            extra_headers={"User-Agent": "HackAgent/0.1.0"},
        )

    @patch("litellm.completion")
    def test_handle_request_litellm_api_error(self, mock_litellm_completion):
        # Simulate an API error from LiteLLM (e.g. litellm.exceptions.APIError)
        mock_litellm_completion.side_effect = litellm.exceptions.APIError(
            "LiteLLM API Error from test",  # message (positional)
            503,  # status_code (positional)
            llm_provider="test_provider",  # llm_provider (keyword)
            model="test_model",  # model (keyword)
        )

        request_data = {"prompt": self.prompt}
        response = self.adapter.handle_request(request_data)

        self.assertEqual(response["status_code"], 500)
        # The ChatCompletionsAgent base class formats errors differently
        self.assertIn("APIError", response["error_message"])
        self.assertEqual(response["raw_request"], request_data)

    @patch("litellm.completion")
    def test_handle_request_unexpected_response_structure_no_choices(
        self, mock_litellm_completion
    ):
        mock_response = MagicMock()
        mock_response.choices = []  # Empty choices
        mock_litellm_completion.return_value = mock_response

        request_data = {"prompt": self.prompt}
        response = self.adapter.handle_request(request_data)
        self.assertEqual(response["status_code"], 500)
        # The ChatCompletionsAgent base class uses ADAPTER_TYPE in error messages
        self.assertIn("generation error", response["error_message"])
        self.assertIn(
            "[GENERATION_ERROR: UNEXPECTED_RESPONSE]", response["error_message"]
        )

    @patch("litellm.completion")
    def test_handle_request_unexpected_response_structure_no_message_content(
        self, mock_litellm_completion
    ):
        # Create a proper mock that returns None for all reasoning fields
        mock_choice = MagicMock()
        mock_message = MagicMock(spec=["content"])  # Only spec content attribute
        mock_message.content = None  # No content
        mock_message.configure_mock(reasoning_content=None, reasoning=None)
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_litellm_completion.return_value = mock_response

        request_data = {"prompt": self.prompt}
        response = self.adapter.handle_request(request_data)

        # Implementation returns 500 error when content is empty/None
        self.assertEqual(response["status_code"], 500)
        self.assertIn("generation error", response["error_message"])
        self.assertIn("[GENERATION_ERROR: EMPTY_RESPONSE]", response["error_message"])

    @patch("litellm.completion")
    def test_handle_request_reasoning_model_with_reasoning_field(
        self, mock_litellm_completion
    ):
        """Test that reasoning models (e.g., o1, kimi-k2-thinking) work correctly."""
        mock_choice = MagicMock()
        mock_choice.message = MagicMock()
        mock_choice.message.content = ""  # Empty content (typical for reasoning models)
        mock_choice.message.reasoning_content = (
            "This is the reasoning output from the model"
        )
        mock_choice.message.reasoning = None
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_litellm_completion.return_value = mock_response

        request_data = {"prompt": self.prompt}
        response = self.adapter.handle_request(request_data)

        self.assertEqual(response["status_code"], 200)
        self.assertEqual(
            response["processed_response"],
            "This is the reasoning output from the model",
        )
        self.assertIsNone(response["error_message"])

    @patch("litellm.completion")
    def test_handle_request_empty_completions_list_from_execute(
        self, mock_litellm_completion
    ):
        # This simulates the _execute_completion returning an empty/None content,
        # which should result in an error response.
        # The ChatCompletionsAgent base class handle_request checks for None content.

        # Mock _execute_completion to return success but with None content
        with patch.object(
            self.adapter,
            "_execute_completion",
            return_value={"success": True, "content": None},
        ) as mock_execute:
            request_data = {"prompt": self.prompt}
            response = self.adapter.handle_request(request_data)
            self.assertEqual(response["status_code"], 500)
            self.assertIn("returned empty result", response["error_message"])
            mock_execute.assert_called_once()

    def test_handle_request_passes_additional_kwargs_to_litellm(self):
        with patch("litellm.completion") as mock_litellm_completion:
            mock_choice = MagicMock()
            mock_choice.message = MagicMock()
            mock_choice.message.content = " response with custom params."
            mock_response = MagicMock()
            mock_response.choices = [mock_choice]
            mock_litellm_completion.return_value = mock_response

            request_data = {
                "prompt": self.prompt,
                "custom_param": "value123",
                "another_param": 42,
            }
            self.adapter.handle_request(request_data)

            called_kwargs = mock_litellm_completion.call_args[1]
            self.assertEqual(called_kwargs.get("custom_param"), "value123")
            self.assertEqual(called_kwargs.get("another_param"), 42)


if __name__ == "__main__":
    unittest.main()
