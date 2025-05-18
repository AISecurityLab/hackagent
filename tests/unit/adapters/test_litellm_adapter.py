import unittest
from unittest.mock import patch, MagicMock
import logging
import os

from hackagent.router.adapters.litellm_adapter import (
    LiteLLMAgentAdapter,
    LiteLLMConfigurationError,
)
import litellm  # Required for litellm.exceptions

# Disable logging for tests
logging.disable(logging.CRITICAL)


class TestLiteLLMAgentAdapterInit(unittest.TestCase):
    def test_init_success_minimal_config(self):
        adapter_id = "litellm_test_001"
        config = {
            "name": "ollama/llama2"  # Model string
        }
        try:
            adapter = LiteLLMAgentAdapter(id=adapter_id, config=config)
            self.assertEqual(adapter.id, adapter_id)
            self.assertEqual(adapter.model_name, config["name"])
            self.assertIsNone(adapter.api_base_url)
            self.assertIsNone(adapter.actual_api_key)
            self.assertEqual(adapter.default_max_new_tokens, 100)
            self.assertEqual(adapter.default_temperature, 0.8)
            self.assertEqual(adapter.default_top_p, 0.95)
        except LiteLLMConfigurationError:
            self.fail(
                "LiteLLMAgentAdapter initialization failed with minimal valid config."
            )

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
            adapter = LiteLLMAgentAdapter(id=adapter_id, config=config)
            self.assertEqual(adapter.model_name, config["name"])
            self.assertEqual(adapter.api_base_url, config["endpoint"])
            self.assertIsNone(adapter.actual_api_key)  # Not set in env
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
        adapter = LiteLLMAgentAdapter(id=adapter_id, config=config)
        self.assertEqual(adapter.actual_api_key, "actual_key_from_env")

    def test_init_missing_name_raises_error(self):
        with self.assertRaisesRegex(
            LiteLLMConfigurationError, "Missing required configuration key 'name'"
        ):
            LiteLLMAgentAdapter(id="err_litellm_1", config={})

    def test_init_config_without_api_key_field(self):
        # Should not try to get from env if 'api_key' field itself is missing in config
        adapter_id = "litellm_test_004"
        config = {"name": "some-model"}
        with patch.object(
            os.environ, "get"
        ) as mock_os_environ_get:  # More specific patch
            adapter = LiteLLMAgentAdapter(id=adapter_id, config=config)
            self.assertIsNone(adapter.actual_api_key)
            mock_os_environ_get.assert_not_called()


class TestLiteLLMAgentAdapterHandleRequest(unittest.TestCase):
    def setUp(self):
        self.adapter_id = "litellm_handle_req_agent"
        self.config = {
            "name": "test-model",
            "endpoint": "http://fake-litellm-api.com",
            "max_new_tokens": 50,
            "temperature": 0.5,
            "top_p": 0.9,
        }
        self.adapter = LiteLLMAgentAdapter(id=self.adapter_id, config=self.config)
        self.prompt = "Hello LiteLLM"

    def test_handle_request_missing_prompt(self):
        request_data = {}
        response = self.adapter.handle_request(request_data)
        self.assertEqual(response["status_code"], 400)
        self.assertIn(
            "Request data must include a 'prompt' field.", response["error_message"]
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
        self.assertEqual(
            response["processed_response"], self.prompt + " a successful response."
        )
        self.assertEqual(response["raw_request"], request_data)
        self.assertEqual(
            response["agent_specific_data"]["model_name"], self.config["name"]
        )
        self.assertEqual(
            response["agent_specific_data"]["invoked_parameters"]["max_new_tokens"], 150
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
            api_key=None,  # As no api_key in config for this test
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
        self.assertIn(
            "LiteLLM generation error: [GENERATION_ERROR: APIError]",
            response["error_message"],
        )
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
        self.assertIn(
            "LiteLLM generation error: [GENERATION_ERROR: UNEXPECTED_RESPONSE]",
            response["error_message"],
        )

    @patch("litellm.completion")
    def test_handle_request_unexpected_response_structure_no_message_content(
        self, mock_litellm_completion
    ):
        mock_choice = MagicMock()
        mock_choice.message = MagicMock()
        mock_choice.message.content = None  # No content
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_litellm_completion.return_value = mock_response

        request_data = {"prompt": self.prompt}
        response = self.adapter.handle_request(request_data)

        self.assertEqual(response["status_code"], 500)
        self.assertIn(
            "LiteLLM generation error: [GENERATION_ERROR: UNEXPECTED_RESPONSE]",
            response["error_message"],
        )

    @patch("litellm.completion")
    def test_handle_request_empty_completions_list_from_execute(
        self, mock_litellm_completion
    ):
        # This simulates the _execute_litellm_completion returning an empty list,
        # though it's less likely with current _execute_litellm_completion logic which appends errors.
        # To properly test this, we might need to patch _execute_litellm_completion itself.
        # For now, let's assume litellm.completion directly causes such a state that leads to empty completions.
        # The method _execute_litellm_completion itself ensures a list of the same length as input texts.
        # So this tests the outer handle_request logic if completions was somehow empty.

        # Let's mock _execute_litellm_completion directly for this specific scenario
        with patch.object(
            self.adapter, "_execute_litellm_completion", return_value=[]
        ) as mock_execute:
            request_data = {"prompt": self.prompt}
            response = self.adapter.handle_request(request_data)
            self.assertEqual(response["status_code"], 500)
            self.assertIn(
                "LiteLLM returned empty or invalid result.", response["error_message"]
            )
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
