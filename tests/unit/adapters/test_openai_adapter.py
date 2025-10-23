import unittest
from unittest.mock import patch, MagicMock
import logging

from hackagent.router.adapters.openai_adapter import (
    OpenAIAgentAdapter,
    OpenAIConfigurationError,
)

# Disable logging for tests to keep output clean
logging.disable(logging.CRITICAL)


class TestOpenAIAgentAdapterInit(unittest.TestCase):
    """Test initialization of OpenAIAgentAdapter."""

    @patch("hackagent.router.adapters.openai_adapter.OPENAI_AVAILABLE", True)
    @patch("hackagent.router.adapters.openai_adapter.OpenAI")
    def test_init_success_with_required_config(self, mock_openai_class):
        """Test successful initialization with minimum required config."""
        adapter_id = "openai_test_agent_001"
        config = {
            "name": "gpt-4",
        }
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        adapter = OpenAIAgentAdapter(id=adapter_id, config=config)

        self.assertEqual(adapter.id, adapter_id)
        self.assertEqual(adapter.model_name, "gpt-4")
        self.assertIsNone(adapter.api_base_url)
        self.assertEqual(adapter.default_temperature, 1.0)
        mock_openai_class.assert_called_once()

    @patch("hackagent.router.adapters.openai_adapter.OPENAI_AVAILABLE", True)
    @patch("hackagent.router.adapters.openai_adapter.OpenAI")
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

        adapter = OpenAIAgentAdapter(id=adapter_id, config=config)

        self.assertEqual(adapter.actual_api_key, "test-key-123")
        mock_openai_class.assert_called_once_with(api_key="test-key-123")

    @patch("hackagent.router.adapters.openai_adapter.OPENAI_AVAILABLE", True)
    @patch("hackagent.router.adapters.openai_adapter.OpenAI")
    def test_init_with_custom_endpoint(self, mock_openai_class):
        """Test initialization with custom API endpoint."""
        adapter_id = "openai_test_agent_003"
        config = {
            "name": "gpt-4",
            "endpoint": "https://custom.openai.proxy.com/v1",
        }
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        adapter = OpenAIAgentAdapter(id=adapter_id, config=config)

        self.assertEqual(adapter.api_base_url, "https://custom.openai.proxy.com/v1")
        mock_openai_class.assert_called_once_with(
            base_url="https://custom.openai.proxy.com/v1"
        )

    @patch("hackagent.router.adapters.openai_adapter.OPENAI_AVAILABLE", True)
    @patch("hackagent.router.adapters.openai_adapter.OpenAI")
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

        adapter = OpenAIAgentAdapter(id=adapter_id, config=config)

        self.assertEqual(adapter.default_max_tokens, 500)
        self.assertEqual(adapter.default_temperature, 0.7)
        self.assertIsNotNone(adapter.default_tools)
        self.assertEqual(adapter.default_tool_choice, "auto")

    def test_init_missing_name_raises_error(self):
        """Test that missing 'name' config raises error."""
        with self.assertRaisesRegex(
            OpenAIConfigurationError, "Missing required configuration key 'name'"
        ):
            OpenAIAgentAdapter(id="err_agent_1", config={})

    @patch("hackagent.router.adapters.openai_adapter.OPENAI_AVAILABLE", False)
    def test_init_without_openai_installed_raises_error(self):
        """Test that initialization fails gracefully when OpenAI SDK not installed."""
        with self.assertRaisesRegex(
            OpenAIConfigurationError, "OpenAI SDK is not installed"
        ):
            OpenAIAgentAdapter(id="err_agent_2", config={"name": "gpt-4"})


class TestOpenAIAgentAdapterHandleRequest(unittest.TestCase):
    """Test handle_request method of OpenAIAgentAdapter."""

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
            "hackagent.router.adapters.openai_adapter.OPENAI_AVAILABLE", True
        )
        self.openai_class_patch = patch(
            "hackagent.router.adapters.openai_adapter.OpenAI"
        )

        self.openai_patch.start()
        self.mock_openai_class = self.openai_class_patch.start()

        self.mock_client = MagicMock()
        self.mock_openai_class.return_value = self.mock_client

        self.adapter = OpenAIAgentAdapter(id=self.adapter_id, config=self.config)

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
        self.assertEqual(response["adapter_type"], "OpenAIAgentAdapter")

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
        from hackagent.router.adapters.openai_adapter import APITimeoutError

        self.mock_client.chat.completions.create.side_effect = APITimeoutError(
            "Request timed out"
        )

        request_data = {"prompt": "Hello"}
        response = self.adapter.handle_request(request_data)

        self.assertEqual(response["status_code"], 500)
        self.assertIn("timeout", response["error_message"])
        self.assertIn("Request timed out", response["error_message"])

    def test_handle_request_rate_limit_error(self):
        """Test handling of rate limit errors."""
        from hackagent.router.adapters.openai_adapter import RateLimitError

        # Create mock response and body for RateLimitError
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_body = {"error": {"message": "Rate limit exceeded"}}

        error = RateLimitError(
            "Rate limit exceeded", response=mock_response, body=mock_body
        )
        self.mock_client.chat.completions.create.side_effect = error

        request_data = {"prompt": "Hello"}
        response = self.adapter.handle_request(request_data)

        self.assertEqual(response["status_code"], 500)
        self.assertIn("rate_limit", response["error_message"])

    def test_handle_request_connection_error(self):
        """Test handling of connection errors."""
        from hackagent.router.adapters.openai_adapter import APIConnectionError

        # APIConnectionError requires a request parameter
        mock_request = MagicMock()
        error = APIConnectionError(message="Connection failed", request=mock_request)
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


class TestOpenAIAgentAdapterIntegration(unittest.TestCase):
    """Integration-style tests for OpenAIAgentAdapter."""

    @patch("hackagent.router.adapters.openai_adapter.OPENAI_AVAILABLE", True)
    @patch("hackagent.router.adapters.openai_adapter.OpenAI")
    def test_full_conversation_flow(self, mock_openai_class):
        """Test a full conversation flow with multiple messages."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        adapter = OpenAIAgentAdapter(
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


if __name__ == "__main__":
    unittest.main()
