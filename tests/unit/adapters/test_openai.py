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
import unittest
from unittest.mock import MagicMock, patch

from hackagent.router.adapters.openai import (
    OpenAIAgent,
    OpenAIConfigurationError,
)

# Disable logging for tests to keep output clean
logging.disable(logging.CRITICAL)


class TestOpenAIAgentInit(unittest.TestCase):
    """Test initialization of OpenAIAgent."""

    @patch("hackagent.router.adapters.openai.OPENAI_AVAILABLE", True)
    @patch("hackagent.router.adapters.openai.OpenAI")
    def test_init_success_with_required_config(self, mock_openai_class):
        """Test successful initialization with minimum required config."""
        adapter_id = "openai_test_agent_001"
        config = {
            "name": "gpt-4",
        }
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        adapter = OpenAIAgent(id=adapter_id, config=config)

        self.assertEqual(adapter.id, adapter_id)
        self.assertEqual(adapter.model_name, "gpt-4")
        self.assertIsNone(adapter.api_base_url)
        self.assertEqual(adapter.default_temperature, 1.0)
        mock_openai_class.assert_called_once()

    @patch("hackagent.router.adapters.openai.OPENAI_AVAILABLE", True)
    @patch("hackagent.router.adapters.openai.OpenAI")
    @patch.dict("os.environ", {"CUSTOM_API_KEY": "test-key-123"})
    def test_init_with_api_key_from_env(self, mock_openai_class):
        """Test initialization with API key from environment variable."""
        adapter_id = "openai_test_agent_002"
        config = {
            "name": "gpt-3.5-turbo",
            "api_key": "CUSTOM_API_KEY",
        }
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        adapter = OpenAIAgent(id=adapter_id, config=config)

        self.assertEqual(adapter.actual_api_key, "test-key-123")
        mock_openai_class.assert_called_once_with(api_key="test-key-123")

    @patch("hackagent.router.adapters.openai.OPENAI_AVAILABLE", True)
    @patch("hackagent.router.adapters.openai.OpenAI")
    def test_init_with_custom_endpoint(self, mock_openai_class):
        """Test initialization with custom API endpoint."""
        adapter_id = "openai_test_agent_003"
        config = {
            "name": "gpt-4",
            "endpoint": "https://custom.openai.proxy.com/v1",
        }
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        adapter = OpenAIAgent(id=adapter_id, config=config)

        self.assertEqual(adapter.api_base_url, "https://custom.openai.proxy.com/v1")
        # Verify OpenAI was called with the correct base_url (api_key may vary)
        mock_openai_class.assert_called_once()
        call_kwargs = mock_openai_class.call_args.kwargs
        self.assertEqual(
            call_kwargs.get("base_url"), "https://custom.openai.proxy.com/v1"
        )

    @patch("hackagent.router.adapters.openai.OPENAI_AVAILABLE", True)
    @patch("hackagent.router.adapters.openai.OpenAI")
    def test_init_with_generation_parameters(self, mock_openai_class):
        """Test initialization with custom generation parameters."""
        adapter_id = "openai_test_agent_004"
        config = {
            "name": "gpt-4",
            "max_tokens": 500,
            "temperature": 0.7,
            "tools": [{"type": "function", "function": {"name": "test_func"}}],
            "tool_choice": "auto",
        }
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        adapter = OpenAIAgent(id=adapter_id, config=config)

        self.assertEqual(adapter.default_max_tokens, 500)
        self.assertEqual(adapter.default_temperature, 0.7)
        self.assertIsNotNone(adapter.default_tools)
        self.assertEqual(adapter.default_tool_choice, "auto")

    def test_init_missing_name_raises_error(self):
        """Test that missing 'name' config raises error."""
        with self.assertRaisesRegex(
            OpenAIConfigurationError, "Missing required configuration key 'name'"
        ):
            OpenAIAgent(id="err_agent_1", config={})

    @patch("hackagent.router.adapters.openai.OPENAI_AVAILABLE", False)
    def test_init_without_openai_installed_raises_error(self):
        """Test that initialization fails gracefully when OpenAI SDK not installed."""
        with self.assertRaisesRegex(
            OpenAIConfigurationError, "OpenAI SDK is not installed"
        ):
            OpenAIAgent(id="err_agent_2", config={"name": "gpt-4"})


class TestOpenAIAgentHandleRequest(unittest.TestCase):
    """Test handle_request method of OpenAIAgent."""

    def setUp(self):
        """Set up test fixtures."""
        self.adapter_id = "openai_handle_req_test"
        self.config = {
            "name": "gpt-4",
            "max_tokens": 100,
            "temperature": 0.8,
        }

        # Patch at module level
        self.openai_patch = patch(
            "hackagent.router.adapters.openai.OPENAI_AVAILABLE", True
        )
        self.openai_class_patch = patch("hackagent.router.adapters.openai.OpenAI")

        self.openai_patch.start()
        self.mock_openai_class = self.openai_class_patch.start()

        self.mock_client = MagicMock()
        self.mock_openai_class.return_value = self.mock_client

        self.adapter = OpenAIAgent(id=self.adapter_id, config=self.config)

    def tearDown(self):
        """Clean up patches."""
        self.openai_patch.stop()
        self.openai_class_patch.stop()

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

    def test_handle_request_with_prompt_success(self):
        """Test successful request with prompt text."""
        # Mock the OpenAI API response
        mock_message = MagicMock()
        mock_message.content = "This is a test response"
        mock_message.tool_calls = None

        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_choice.finish_reason = "stop"

        mock_usage = MagicMock()
        mock_usage.model_dump.return_value = {
            "prompt_tokens": 10,
            "completion_tokens": 20,
            "total_tokens": 30,
        }

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = mock_usage
        mock_response.model = "gpt-4"

        self.mock_client.chat.completions.create.return_value = mock_response

        request_data = {"prompt": "Hello, how are you?"}
        response = self.adapter.handle_request(request_data)

        # Verify response structure
        self.assertEqual(response["status_code"], 200)
        self.assertIsNone(response["error_message"])
        self.assertEqual(response["generated_text"], "This is a test response")
        self.assertEqual(response["agent_id"], self.adapter_id)
        self.assertEqual(response["adapter_type"], "OpenAIAgent")

        # Verify agent specific data
        self.assertEqual(response["agent_specific_data"]["model_name"], "gpt-4")
        self.assertEqual(response["agent_specific_data"]["finish_reason"], "stop")
        self.assertIsNotNone(response["agent_specific_data"]["usage"])

        # Verify the API was called correctly
        self.mock_client.chat.completions.create.assert_called_once()
        call_kwargs = self.mock_client.chat.completions.create.call_args[1]
        self.assertEqual(call_kwargs["model"], "gpt-4")
        self.assertEqual(
            call_kwargs["messages"],
            [{"role": "user", "content": "Hello, how are you?"}],
        )

    def test_handle_request_with_messages_success(self):
        """Test successful request with pre-formatted messages."""
        # Mock the OpenAI API response
        mock_message = MagicMock()
        mock_message.content = "Response to conversation"
        mock_message.tool_calls = None

        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_choice.finish_reason = "stop"

        mock_usage = MagicMock()
        mock_usage.model_dump.return_value = {
            "prompt_tokens": 15,
            "completion_tokens": 25,
            "total_tokens": 40,
        }

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = mock_usage
        mock_response.model = "gpt-4"

        self.mock_client.chat.completions.create.return_value = mock_response

        request_data = {
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Hello!"},
            ]
        }
        response = self.adapter.handle_request(request_data)

        self.assertEqual(response["status_code"], 200)
        self.assertIsNone(response["error_message"])
        self.assertEqual(response["generated_text"], "Response to conversation")

        # Verify messages were passed correctly
        call_kwargs = self.mock_client.chat.completions.create.call_args[1]
        self.assertEqual(len(call_kwargs["messages"]), 2)
        self.assertEqual(call_kwargs["messages"][0]["role"], "system")

    def test_handle_request_with_tool_calls(self):
        """Test request that returns tool calls."""
        # Mock a tool call response
        mock_tool_call = MagicMock()
        mock_tool_call.id = "call_123"
        mock_tool_call.type = "function"
        mock_tool_call.function.name = "get_weather"
        mock_tool_call.function.arguments = '{"location": "San Francisco"}'

        mock_message = MagicMock()
        mock_message.content = None
        mock_message.tool_calls = [mock_tool_call]

        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_choice.finish_reason = "tool_calls"

        mock_usage = MagicMock()
        mock_usage.model_dump.return_value = {
            "prompt_tokens": 50,
            "completion_tokens": 30,
            "total_tokens": 80,
        }

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = mock_usage
        mock_response.model = "gpt-4"

        self.mock_client.chat.completions.create.return_value = mock_response

        tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "Get weather for a location",
                    "parameters": {
                        "type": "object",
                        "properties": {"location": {"type": "string"}},
                    },
                },
            }
        ]

        request_data = {
            "prompt": "What's the weather in San Francisco?",
            "tools": tools,
            "tool_choice": "auto",
        }
        response = self.adapter.handle_request(request_data)

        self.assertEqual(response["status_code"], 200)
        self.assertIsNone(response["error_message"])
        self.assertEqual(response["agent_specific_data"]["finish_reason"], "tool_calls")

        # Verify tool calls in response
        tool_calls = response["agent_specific_data"]["tool_calls"]
        self.assertIsNotNone(tool_calls)
        self.assertEqual(len(tool_calls), 1)
        self.assertEqual(tool_calls[0]["id"], "call_123")
        self.assertEqual(tool_calls[0]["function"]["name"], "get_weather")

    def test_handle_request_api_timeout_error(self):
        """Test handling of API timeout errors."""
        import openai

        self.mock_client.chat.completions.create.side_effect = openai.APITimeoutError(
            "Request timed out"
        )

        request_data = {"prompt": "Hello"}
        response = self.adapter.handle_request(request_data)

        self.assertEqual(response["status_code"], 500)
        self.assertIn("timeout", response["error_message"])
        self.assertIn("Request timed out", response["error_message"])

    def test_handle_request_rate_limit_error(self):
        """Test handling of rate limit errors."""
        import openai

        # Create mock response and body for RateLimitError
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_body = {"error": {"message": "Rate limit exceeded"}}

        error = openai.RateLimitError(
            "Rate limit exceeded", response=mock_response, body=mock_body
        )
        self.mock_client.chat.completions.create.side_effect = error

        request_data = {"prompt": "Hello"}
        response = self.adapter.handle_request(request_data)

        self.assertEqual(response["status_code"], 500)
        self.assertIn("rate_limit", response["error_message"])

    def test_handle_request_connection_error(self):
        """Test handling of connection errors."""
        import openai

        # APIConnectionError requires a request parameter
        mock_request = MagicMock()
        error = openai.APIConnectionError(
            message="Connection failed", request=mock_request
        )
        self.mock_client.chat.completions.create.side_effect = error

        request_data = {"prompt": "Hello"}
        response = self.adapter.handle_request(request_data)

        self.assertEqual(response["status_code"], 500)
        self.assertIn("connection", response["error_message"])

    def test_handle_request_with_parameter_overrides(self):
        """Test that request parameters override defaults."""
        mock_message = MagicMock()
        mock_message.content = "Response"
        mock_message.tool_calls = None

        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_choice.finish_reason = "stop"

        mock_usage = MagicMock()
        mock_usage.model_dump.return_value = {}

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = mock_usage
        mock_response.model = "gpt-4"

        self.mock_client.chat.completions.create.return_value = mock_response

        request_data = {
            "prompt": "Test",
            "max_tokens": 200,  # Override default of 100
            "temperature": 0.5,  # Override default of 0.8
        }
        response = self.adapter.handle_request(request_data)

        self.assertEqual(response["status_code"], 200)

        # Verify overridden parameters were used
        call_kwargs = self.mock_client.chat.completions.create.call_args[1]
        self.assertEqual(call_kwargs["max_tokens"], 200)
        self.assertEqual(call_kwargs["temperature"], 0.5)


class TestOpenAIAgentIntegration(unittest.TestCase):
    """Integration-style tests for OpenAIAgent."""

    @patch("hackagent.router.adapters.openai.OPENAI_AVAILABLE", True)
    @patch("hackagent.router.adapters.openai.OpenAI")
    def test_full_conversation_flow(self, mock_openai_class):
        """Test a full conversation flow with multiple messages."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        adapter = OpenAIAgent(
            id="conversation_test", config={"name": "gpt-4", "temperature": 0.7}
        )

        # Mock response
        mock_message = MagicMock()
        mock_message.content = "I'm doing great, thank you!"
        mock_message.tool_calls = None

        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_choice.finish_reason = "stop"

        mock_usage = MagicMock()
        mock_usage.model_dump.return_value = {"total_tokens": 50}

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = mock_usage
        mock_response.model = "gpt-4"

        mock_client.chat.completions.create.return_value = mock_response

        # Simulate a conversation
        messages = [
            {"role": "system", "content": "You are a friendly assistant."},
            {"role": "user", "content": "Hello!"},
            {"role": "assistant", "content": "Hi! How can I help you?"},
            {"role": "user", "content": "How are you?"},
        ]

        request_data = {"messages": messages}
        response = adapter.handle_request(request_data)

        self.assertEqual(response["status_code"], 200)
        self.assertEqual(response["generated_text"], "I'm doing great, thank you!")
        self.assertEqual(response["agent_specific_data"]["model_name"], "gpt-4")


class TestOpenAIAgentReasoningModels(unittest.TestCase):
    """Test reasoning model support (e.g., o1-preview, o1-mini)."""

    def setUp(self):
        """Set up test fixtures."""
        self.adapter_id = "openai_reasoning_test"
        self.config = {
            "name": "o1-preview",
            "temperature": 1.0,
        }

        # Patch at module level
        self.openai_patch = patch(
            "hackagent.router.adapters.openai.OPENAI_AVAILABLE", True
        )
        self.openai_class_patch = patch("hackagent.router.adapters.openai.OpenAI")

        self.openai_patch.start()
        self.mock_openai_class = self.openai_class_patch.start()

        self.mock_client = MagicMock()
        self.mock_openai_class.return_value = self.mock_client

        self.adapter = OpenAIAgent(id=self.adapter_id, config=self.config)

    def tearDown(self):
        """Clean up patches."""
        self.openai_patch.stop()
        self.openai_class_patch.stop()

    def test_handle_request_with_reasoning_field(self):
        """Test that reasoning field is extracted when content is empty."""
        # Mock a reasoning model response with reasoning field
        mock_message = MagicMock()
        mock_message.content = None  # Reasoning models may have no content
        mock_message.reasoning = "Let me think through this step by step..."
        mock_message.tool_calls = None

        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_choice.finish_reason = "stop"

        mock_usage = MagicMock()
        mock_usage.model_dump.return_value = {
            "prompt_tokens": 20,
            "completion_tokens": 50,
            "total_tokens": 70,
        }

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = mock_usage
        mock_response.model = "o1-preview"

        self.mock_client.chat.completions.create.return_value = mock_response

        request_data = {"prompt": "What is 2+2?"}
        response = self.adapter.handle_request(request_data)

        # Verify reasoning field was extracted
        self.assertEqual(response["status_code"], 200)
        self.assertEqual(
            response["generated_text"], "Let me think through this step by step..."
        )
        self.assertEqual(
            response["processed_response"], "Let me think through this step by step..."
        )
        self.assertEqual(response["agent_specific_data"]["model_name"], "o1-preview")

    def test_handle_request_with_empty_content_and_reasoning(self):
        """Test extraction when content is empty string but reasoning exists."""
        mock_message = MagicMock()
        mock_message.content = ""  # Empty content
        mock_message.reasoning = "First, I need to analyze the problem..."
        mock_message.tool_calls = None

        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_choice.finish_reason = "stop"

        mock_usage = MagicMock()
        mock_usage.model_dump.return_value = {"total_tokens": 100}

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = mock_usage
        mock_response.model = "o1-mini"

        self.mock_client.chat.completions.create.return_value = mock_response

        request_data = {"prompt": "Solve this problem"}
        response = self.adapter.handle_request(request_data)

        self.assertEqual(response["status_code"], 200)
        self.assertEqual(
            response["generated_text"], "First, I need to analyze the problem..."
        )

    def test_handle_request_without_reasoning_attribute(self):
        """Test handling when message has no reasoning attribute (non-reasoning model)."""
        mock_message = MagicMock()
        mock_message.content = "Regular response"
        # Don't set reasoning attribute at all
        mock_message.tool_calls = None
        # Ensure hasattr returns False
        del mock_message.reasoning

        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_choice.finish_reason = "stop"

        mock_usage = MagicMock()
        mock_usage.model_dump.return_value = {"total_tokens": 50}

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = mock_usage
        mock_response.model = "gpt-4"

        self.mock_client.chat.completions.create.return_value = mock_response

        request_data = {"prompt": "Hello"}
        response = self.adapter.handle_request(request_data)

        # Should use content, not reasoning
        self.assertEqual(response["status_code"], 200)
        self.assertEqual(response["generated_text"], "Regular response")

    def test_handle_request_content_takes_precedence_over_reasoning(self):
        """Test that non-empty content takes precedence over reasoning field."""
        mock_message = MagicMock()
        mock_message.content = "This is the actual response"
        mock_message.reasoning = "This is the reasoning"
        mock_message.tool_calls = None

        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_choice.finish_reason = "stop"

        mock_usage = MagicMock()
        mock_usage.model_dump.return_value = {"total_tokens": 60}

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = mock_usage
        mock_response.model = "o1-preview"

        self.mock_client.chat.completions.create.return_value = mock_response

        request_data = {"prompt": "Test"}
        response = self.adapter.handle_request(request_data)

        # Content should be used, not reasoning
        self.assertEqual(response["status_code"], 200)
        self.assertEqual(response["generated_text"], "This is the actual response")

    def test_handle_request_reasoning_with_messages(self):
        """Test reasoning model with pre-formatted messages."""
        mock_message = MagicMock()
        mock_message.content = None
        mock_message.reasoning = "Analyzing the conversation context..."
        mock_message.tool_calls = None

        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_choice.finish_reason = "stop"

        mock_usage = MagicMock()
        mock_usage.model_dump.return_value = {"total_tokens": 150}

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = mock_usage
        mock_response.model = "o1-mini"

        self.mock_client.chat.completions.create.return_value = mock_response

        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Help me solve this."},
        ]
        request_data = {"messages": messages}
        response = self.adapter.handle_request(request_data)

        self.assertEqual(response["status_code"], 200)
        self.assertEqual(
            response["generated_text"], "Analyzing the conversation context..."
        )
        self.assertIsNone(response["error_message"])

    def test_handle_request_reasoning_none_and_content_none(self):
        """Test when both reasoning and content are None (edge case)."""
        mock_message = MagicMock()
        mock_message.content = None
        mock_message.reasoning = None
        mock_message.tool_calls = None

        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_choice.finish_reason = "stop"

        mock_usage = MagicMock()
        mock_usage.model_dump.return_value = {"total_tokens": 10}

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = mock_usage
        mock_response.model = "o1-preview"

        self.mock_client.chat.completions.create.return_value = mock_response

        request_data = {"prompt": "Test"}
        response = self.adapter.handle_request(request_data)

        # Should return empty string
        self.assertEqual(response["status_code"], 200)
        self.assertEqual(response["generated_text"], "")


if __name__ == "__main__":
    unittest.main()
