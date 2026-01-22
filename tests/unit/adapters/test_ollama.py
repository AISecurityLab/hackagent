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
Unit tests for OllamaAgent.

These tests verify the functionality of the Ollama adapter including:
- Initialization with various configurations
- Request handling (generate and chat endpoints)
- Error handling
- Model information retrieval
"""

import logging
import os
import unittest
from unittest.mock import MagicMock, patch

import requests

from hackagent.router.adapters.ollama import (
    OllamaAgent,
    OllamaConfigurationError,
)

# Disable logging for tests to keep output clean
logging.disable(logging.CRITICAL)


class TestOllamaAgentInit(unittest.TestCase):
    """Test initialization of OllamaAgent."""

    def test_init_success_with_minimal_config(self):
        """Test successful initialization with minimum required config."""
        adapter_id = "ollama_test_agent_001"
        config = {
            "name": "llama3",
        }

        adapter = OllamaAgent(id=adapter_id, config=config)

        self.assertEqual(adapter.id, adapter_id)
        self.assertEqual(adapter.model_name, "llama3")
        self.assertEqual(adapter.api_base_url, "http://localhost:11434")
        self.assertEqual(adapter.default_max_new_tokens, 100)
        self.assertEqual(adapter.default_temperature, 0.8)
        self.assertEqual(adapter.default_top_p, 0.95)

    def test_init_with_custom_endpoint(self):
        """Test initialization with custom endpoint."""
        adapter_id = "ollama_test_agent_002"
        config = {
            "name": "mistral",
            "endpoint": "http://192.168.1.100:11434",
        }

        adapter = OllamaAgent(id=adapter_id, config=config)

        self.assertEqual(adapter.api_base_url, "http://192.168.1.100:11434")

    def test_init_with_endpoint_trailing_slash(self):
        """Test that trailing slash is removed from endpoint."""
        adapter_id = "ollama_test_agent_003"
        config = {
            "name": "llama3",
            "endpoint": "http://localhost:11434/",
        }

        adapter = OllamaAgent(id=adapter_id, config=config)

        self.assertEqual(adapter.api_base_url, "http://localhost:11434")

    @patch.dict(os.environ, {"OLLAMA_BASE_URL": "http://env-ollama:11434"})
    def test_init_with_env_var_endpoint(self):
        """Test initialization with endpoint from environment variable."""
        adapter_id = "ollama_test_agent_004"
        config = {
            "name": "llama3",
        }

        adapter = OllamaAgent(id=adapter_id, config=config)

        self.assertEqual(adapter.api_base_url, "http://env-ollama:11434")

    def test_init_with_full_config(self):
        """Test initialization with full configuration."""
        adapter_id = "ollama_test_agent_005"
        config = {
            "name": "codellama",
            "endpoint": "http://localhost:11434",
            "max_new_tokens": 200,
            "temperature": 0.7,
            "top_p": 0.9,
            "top_k": 40,
            "num_ctx": 4096,
            "stream": False,
            "timeout": 60,
        }

        adapter = OllamaAgent(id=adapter_id, config=config)

        self.assertEqual(adapter.model_name, "codellama")
        self.assertEqual(adapter.default_max_new_tokens, 200)
        self.assertEqual(adapter.default_temperature, 0.7)
        self.assertEqual(adapter.default_top_p, 0.9)
        self.assertEqual(adapter.default_top_k, 40)
        self.assertEqual(adapter.default_num_ctx, 4096)
        self.assertEqual(adapter.default_stream, False)
        self.assertEqual(adapter.timeout, 60)

    def test_init_missing_name_raises_error(self):
        """Test that missing 'name' config raises error."""
        with self.assertRaisesRegex(
            OllamaConfigurationError, "Missing required configuration key 'name'"
        ):
            OllamaAgent(id="err_agent_1", config={})


class TestOllamaAgentBuildOptions(unittest.TestCase):
    """Test _build_options method of OllamaAgent."""

    def setUp(self):
        """Set up test fixtures."""
        self.adapter = OllamaAgent(
            id="test_options_adapter",
            config={
                "name": "llama3",
                "max_new_tokens": 100,
                "temperature": 0.8,
                "top_p": 0.95,
            },
        )

    def test_build_options_with_defaults(self):
        """Test building options with default values."""
        options = self.adapter._build_options()

        self.assertEqual(options["num_predict"], 100)
        self.assertEqual(options["temperature"], 0.8)
        self.assertEqual(options["top_p"], 0.95)

    def test_build_options_with_overrides(self):
        """Test building options with override values."""
        options = self.adapter._build_options(
            max_new_tokens=200, temperature=0.5, top_p=0.7
        )

        self.assertEqual(options["num_predict"], 200)
        self.assertEqual(options["temperature"], 0.5)
        self.assertEqual(options["top_p"], 0.7)

    def test_build_options_with_additional_params(self):
        """Test building options with additional Ollama parameters."""
        options = self.adapter._build_options(seed=42, repeat_penalty=1.1, stop=["END"])

        self.assertEqual(options["seed"], 42)
        self.assertEqual(options["repeat_penalty"], 1.1)
        self.assertEqual(options["stop"], ["END"])


class TestOllamaAgentHandleRequest(unittest.TestCase):
    """Test handle_request method of OllamaAgent."""

    def setUp(self):
        """Set up test fixtures."""
        self.adapter_id = "ollama_handle_req_test"
        self.config = {
            "name": "llama3",
            "endpoint": "http://localhost:11434",
            "max_new_tokens": 50,
            "temperature": 0.5,
        }
        self.adapter = OllamaAgent(id=self.adapter_id, config=self.config)

    def test_handle_request_missing_prompt_and_messages(self):
        """Test that missing both prompt and messages returns error."""
        request_data = {"temperature": 0.5}
        response = self.adapter.handle_request(request_data)

        self.assertEqual(response["status_code"], 400)
        self.assertIn(
            "Request data must include either 'messages' or 'prompt'",
            response["error_message"],
        )
        self.assertEqual(response["raw_request"], request_data)

    @patch("hackagent.router.adapters.ollama.requests.post")
    def test_handle_request_with_prompt_success(self, mock_post):
        """Test successful request with prompt text using generate endpoint."""
        # Mock the Ollama API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "model": "llama3",
            "response": "This is a test response from Ollama.",
            "done": True,
            "eval_count": 10,
            "eval_duration": 1000000,
            "prompt_eval_count": 5,
            "total_duration": 2000000,
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        request_data = {"prompt": "Hello, Ollama!"}
        response = self.adapter.handle_request(request_data)

        self.assertEqual(response["status_code"], 200)
        self.assertIsNone(response["error_message"])
        self.assertEqual(
            response["processed_response"], "This is a test response from Ollama."
        )
        self.assertEqual(response["raw_request"], request_data)
        self.assertEqual(response["agent_specific_data"]["model_name"], "llama3")

        # Verify the API was called correctly
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        self.assertIn("/api/generate", call_args[0][0])

    @patch("hackagent.router.adapters.ollama.requests.post")
    def test_handle_request_with_messages_success(self, mock_post):
        """Test successful request with messages using chat endpoint."""
        # Mock the Ollama API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "model": "llama3",
            "message": {"role": "assistant", "content": "Chat response from Ollama."},
            "done": True,
            "eval_count": 15,
            "total_duration": 3000000,
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        request_data = {
            "messages": [
                {"role": "user", "content": "Hello!"},
            ]
        }
        response = self.adapter.handle_request(request_data)

        self.assertEqual(response["status_code"], 200)
        self.assertIsNone(response["error_message"])
        self.assertEqual(response["processed_response"], "Chat response from Ollama.")

        # Verify the chat endpoint was called
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        self.assertIn("/api/chat", call_args[0][0])

    @patch("hackagent.router.adapters.ollama.requests.post")
    def test_handle_request_connection_error(self, mock_post):
        """Test handling of connection error."""
        mock_post.side_effect = requests.exceptions.ConnectionError(
            "Connection refused"
        )

        request_data = {"prompt": "Hello"}
        response = self.adapter.handle_request(request_data)

        self.assertEqual(response["status_code"], 503)
        self.assertIn("connection error", response["error_message"].lower())

    @patch("hackagent.router.adapters.ollama.requests.post")
    def test_handle_request_timeout_error(self, mock_post):
        """Test handling of timeout error."""
        mock_post.side_effect = requests.exceptions.Timeout("Request timed out")

        request_data = {"prompt": "Hello"}
        response = self.adapter.handle_request(request_data)

        self.assertEqual(response["status_code"], 503)
        self.assertIn("timed out", response["error_message"].lower())

    @patch("hackagent.router.adapters.ollama.requests.post")
    def test_handle_request_http_error(self, mock_post):
        """Test handling of HTTP error."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Model not found"
        http_error = requests.exceptions.HTTPError("404 Not Found")
        http_error.response = mock_response
        mock_post.side_effect = http_error

        request_data = {"prompt": "Hello"}
        response = self.adapter.handle_request(request_data)

        self.assertEqual(response["status_code"], 404)
        self.assertIn("HTTP error", response["error_message"])

    @patch("hackagent.router.adapters.ollama.requests.post")
    def test_handle_request_with_system_prompt(self, mock_post):
        """Test request with system prompt."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "model": "llama3",
            "response": "Response with system context.",
            "done": True,
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        request_data = {
            "prompt": "What's the weather?",
            "system": "You are a helpful weather assistant.",
        }
        response = self.adapter.handle_request(request_data)

        self.assertEqual(response["status_code"], 200)

        # Verify system prompt was included in the request
        call_args = mock_post.call_args
        request_body = call_args[1]["json"]
        self.assertEqual(request_body["system"], "You are a helpful weather assistant.")

    @patch("hackagent.router.adapters.ollama.requests.post")
    def test_handle_request_with_custom_parameters(self, mock_post):
        """Test request with custom generation parameters."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "model": "llama3",
            "response": "Custom params response.",
            "done": True,
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        request_data = {
            "prompt": "Hello",
            "max_new_tokens": 200,
            "temperature": 0.3,
            "top_k": 20,
            "seed": 42,
        }
        response = self.adapter.handle_request(request_data)

        self.assertEqual(response["status_code"], 200)

        # Verify options were included in the request
        call_args = mock_post.call_args
        request_body = call_args[1]["json"]
        self.assertEqual(request_body["options"]["num_predict"], 200)
        self.assertEqual(request_body["options"]["temperature"], 0.3)
        self.assertEqual(request_body["options"]["top_k"], 20)
        self.assertEqual(request_body["options"]["seed"], 42)


class TestOllamaAgentUtilityMethods(unittest.TestCase):
    """Test utility methods of OllamaAgent."""

    def setUp(self):
        """Set up test fixtures."""
        self.adapter = OllamaAgent(
            id="test_utility_adapter",
            config={
                "name": "llama3",
                "endpoint": "http://localhost:11434",
            },
        )

    @patch("hackagent.router.adapters.ollama.requests.get")
    def test_list_models_success(self, mock_get):
        """Test successful model listing."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [
                {"name": "llama3:latest", "size": 4000000000},
                {"name": "mistral:latest", "size": 3500000000},
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        models = self.adapter.list_models()

        self.assertEqual(len(models), 2)
        self.assertEqual(models[0]["name"], "llama3:latest")

    @patch("hackagent.router.adapters.ollama.requests.get")
    def test_list_models_error(self, mock_get):
        """Test model listing with error."""
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection refused")

        models = self.adapter.list_models()

        self.assertEqual(models, [])

    @patch("hackagent.router.adapters.ollama.requests.post")
    def test_model_info_success(self, mock_post):
        """Test successful model info retrieval."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "modelfile": "FROM llama3...",
            "parameters": "temperature 0.8",
            "template": "...",
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        info = self.adapter.model_info()

        self.assertIn("modelfile", info)

    @patch("hackagent.router.adapters.ollama.requests.post")
    def test_model_info_error(self, mock_post):
        """Test model info with error."""
        mock_post.side_effect = requests.exceptions.ConnectionError(
            "Connection refused"
        )

        info = self.adapter.model_info()

        self.assertEqual(info, {})

    @patch("hackagent.router.adapters.ollama.requests.get")
    def test_is_available_true(self, mock_get):
        """Test is_available returns True when model exists."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [
                {"name": "llama3:latest"},
                {"name": "mistral:latest"},
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        self.assertTrue(self.adapter.is_available())

    @patch("hackagent.router.adapters.ollama.requests.get")
    def test_is_available_false(self, mock_get):
        """Test is_available returns False when model doesn't exist."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [
                {"name": "other-model:latest"},
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        self.assertFalse(self.adapter.is_available())

    @patch("hackagent.router.adapters.ollama.requests.get")
    def test_is_available_connection_error(self, mock_get):
        """Test is_available returns False on connection error."""
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection refused")

        self.assertFalse(self.adapter.is_available())


class TestOllamaAgentIntegration(unittest.TestCase):
    """Integration-style tests for OllamaAgent."""

    def test_adapter_identifier(self):
        """Test that adapter returns correct identifier."""
        adapter = OllamaAgent(
            id="integration_test_adapter",
            config={"name": "llama3"},
        )

        self.assertEqual(adapter.get_identifier(), "integration_test_adapter")

    def test_adapter_with_model_tag(self):
        """Test adapter with model name including tag."""
        adapter = OllamaAgent(
            id="tagged_model_adapter",
            config={"name": "llama3:8b-instruct-q4_0"},
        )

        self.assertEqual(adapter.model_name, "llama3:8b-instruct-q4_0")


if __name__ == "__main__":
    unittest.main()
