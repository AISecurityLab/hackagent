# OpenAI SDK Agent Testing Example

This example demonstrates how to use HackAgent to test agents built with the OpenAI SDK.

## Prerequisites

1. Install HackAgent with OpenAI support:
   ```bash
   pip install hackagent
   # or with uv
   uv add hackagent
   ```

2. Set up your environment variables:
   ```bash
   export HACKAGENT_API_KEY="your-hackagent-api-key"
   export OPENAI_API_KEY="your-openai-api-key"
   ```

## Usage

### Basic Example

```python
from hackagent import HackAgent
from hackagent.models import AgentTypeEnum

# Initialize the agent tester
agent = HackAgent(
    name="my_openai_agent",
    endpoint="https://api.openai.com/v1",
    agent_type=AgentTypeEnum.OPENAI_SDK,
    metadata={
        "name": "gpt-4",  # Model name
        "api_key": "OPENAI_API_KEY",  # Env var name
        "temperature": 0.7,
        "max_tokens": 150,
    },
)

# Configure the attack
attack_config = {
    "attack_type": "advprefix",
    "goals": [
        "Test prompt injection vulnerability",
    ],
}

# Run the security test
agent.hack(attack_config=attack_config)
```

### Testing Agents with Function Calling

```python
from hackagent import HackAgent
from hackagent.models import AgentTypeEnum

# Define tools/functions your agent uses
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current weather for a location",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "City name"
                    }
                },
                "required": ["location"]
            }
        }
    }
]

# Initialize with function calling enabled
agent = HackAgent(
    name="weather_agent",
    endpoint="https://api.openai.com/v1",
    agent_type=AgentTypeEnum.OPENAI_SDK,
    metadata={
        "name": "gpt-4",
        "api_key": "OPENAI_API_KEY",
        "temperature": 0.7,
        "max_tokens": 150,
        "tools": tools,
        "tool_choice": "auto",
    },
)

# Test for vulnerabilities in function calling
attack_config = {
    "attack_type": "advprefix",
    "goals": [
        "Make the agent call functions with malicious parameters",
    ],
}

agent.hack(attack_config=attack_config)
```

### Using Custom OpenAI-Compatible Endpoints

HackAgent's OpenAI adapter supports any OpenAI-compatible API:

```python
# Example: Using Azure OpenAI
agent = HackAgent(
    name="azure_agent",
    endpoint="https://your-resource.openai.azure.com",
    agent_type=AgentTypeEnum.OPENAI_SDK,
    metadata={
        "name": "gpt-4",
        "api_key": "AZURE_OPENAI_API_KEY",
    },
)

# Example: Using local LLM with OpenAI-compatible API
agent = HackAgent(
    name="local_agent",
    endpoint="http://localhost:8000/v1",
    agent_type=AgentTypeEnum.OPENAI_SDK,
    metadata={
        "name": "local-model",
    },
)
```

## Configuration Options

The `metadata` dictionary supports the following OpenAI-specific options:

- `name` (required): Model name (e.g., "gpt-4", "gpt-3.5-turbo")
- `api_key` (optional): Environment variable name containing the API key
- `endpoint` (optional): Custom API endpoint
- `max_tokens` (optional): Maximum tokens to generate
- `temperature` (optional): Sampling temperature (0-2)
- `tools` (optional): List of function/tool definitions
- `tool_choice` (optional): Tool choice strategy ("auto", "none", or specific function)

## Attack Types

HackAgent supports various attack types for testing OpenAI agents:

- `advprefix`: Adversarial prefix attacks
- More attack types coming soon...

## Running the Example

```bash
# Set environment variables
export HACKAGENT_API_KEY="your-hackagent-api-key"
export OPENAI_API_KEY="your-openai-api-key"

# Run the example
python hack.py
```

## Viewing Results

After running the tests, view your results at: [https://hackagent.dev](https://hackagent.dev)

## Best Practices

1. **Rate Limits**: Be aware of OpenAI API rate limits when running tests
2. **Cost Management**: Monitor your API usage as tests may consume tokens
3. **Test Environments**: Use separate API keys for testing vs. production
4. **Incremental Testing**: Start with a few goals and scale up gradually

## Troubleshooting

### "OpenAI SDK is not installed"
Install the OpenAI package:
```bash
pip install openai
```

### Authentication Errors
Verify your API key is correctly set:
```bash
echo $OPENAI_API_KEY
```

### Rate Limit Errors
The adapter handles rate limits gracefully. If you encounter persistent rate limits, consider:
- Reducing the number of test goals
- Increasing delays between requests
- Using a different API tier

## Additional Resources

- [HackAgent Documentation](https://docs.hackagent.dev)
- [OpenAI API Documentation](https://platform.openai.com/docs)
- [HackAgent GitHub Repository](https://github.com/vistalabs-org/hackagent)
