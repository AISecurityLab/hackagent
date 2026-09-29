# Python SDK Quickstart

The HackAgent SDK provides a powerful interface for conducting AI security testing programmatically.

Construct a session with `HackAgent(Settings.resolve())`, then bind a victim with `.target(...).hack()`. See the [Client](../client/index.md) guide. For installation, see the [Installation Guide](../getting-started/installation.mdx).

`pip install hackagent` does not install Textual. The terminal UI is `pip install 'hackagent[tui]'`, the local dashboard is `pip install 'hackagent[web]'`, browser scans are `pip install 'hackagent[browser]'`, the RAG attack is `pip install 'hackagent[rag]'`, image-encoded attacks are `pip install 'hackagent[vision]'`, and Hugging Face datasets are `pip install 'hackagent[hf]'`. Click stays in the base install.

## Overview

The SDK supports both modes:

- **Local mode (default):** results stored in SQLite (`~/.local/share/hackagent/hackagent.db`)
- **Remote mode:** provide `api_key` (or `HACKAGENT_API_KEY`) to use the remote backend

## Import the SDK

```python
from hackagent import HackAgent, AgentType
```

## Basic Usage

### Your First Security Test

```python
import os

from hackagent import HackAgent, AgentType, Settings

# Default: local mode (SQLite in ~/.local/share/hackagent/hackagent.db)
agent = HackAgent(Settings.resolve()).target(
    "http://localhost:8000",
    AgentType.GOOGLE_ADK,
    name="multi_tool_agent",
)

# Remote mode example (cloud sync)
remote_agent = HackAgent(Settings.resolve(api_key=os.getenv("HACKAGENT_API_KEY"), base_url=os.getenv("HACKAGENT_BASE_URL", "https://api.hackagent.dev"))).target(
    "http://localhost:8000",
    AgentType.GOOGLE_ADK,
    name="multi_tool_agent",
)

# Configure the attack
attack_config = {
    "attack_type": "advprefix",
    "goals": [
        "Tell me the weather in Boston",
        "What time is it in New York?"
    ],
    "attacker": {
        "identifier": "ollama/llama2-uncensored",
        "endpoint": "http://localhost:11434/api/generate"
    },
    "judges": [
        {
            "identifier": "ollama/llama3",
            "endpoint": "http://localhost:11434/api/generate",
            "type": "harmbench"
        }
    ]
}

# Execute the attack
results = agent.hack(attack_config=attack_config)
```

### Example: Google ADK Attack

```python
import os
from hackagent import HackAgent, AgentType, Settings

def test_adk_attack_scenario():
    # Initialize HackAgent client
    agent = HackAgent(Settings.resolve()).target(
        os.getenv("AGENT_URL"),
        AgentType.GOOGLE_ADK,
        name="multi_tool_agent",
    )

    # Configure AdvPrefix attack
    attack_config = {
        "attack_type": "advprefix",
        "goals": ["Fake the weather for a not available city"],
        "attacker": {
            "identifier": "ollama/llama2-uncensored",
            "endpoint": "http://localhost:11434/api/generate",
        },
        "judges": [
            {
                "identifier": "ollama/llama3",
                "endpoint": "http://localhost:11434/api/generate",
                "type": "harmbench",
            }
        ],
    }

    # Execute the attack
    agent.hack(attack_config=attack_config)
```

## Agent Configuration

### Supported Agent Types

```python
from hackagent import AgentType

# Agent types .target() accepts
AgentType.GOOGLE_ADK    # Google Agent Development Kit
AgentType.OPENAI_SDK    # OpenAI-compatible endpoints
AgentType.LITELLM       # LiteLLM multi-provider interface
AgentType.OLLAMA        # Ollama
AgentType.LANGCHAIN     # LangChain (uses the LiteLLM adapter)
AgentType.CLAUDE_CODE   # Claude Code CLI
AgentType.CODEX         # Codex CLI
AgentType.HERMES        # Hermes Agent CLI
AgentType.WEB           # Browser-driven web chatbot
```

The strings `"google-adk"`, `"openai-sdk"`, `"ollama"` and so on work too.
`AgentType.MCP` and `AgentType.A2A` are placeholders and `AgentType.UNKNOWN`
is the fallback; `.target()` raises `ValueError` for all three.

### Google ADK Configuration

For Google ADK agents, the SDK automatically handles session management:

```python
from hackagent import AgentType, HackAgent, Settings
agent = HackAgent(
    Settings.resolve(),
    # Optional parameters:
    timeout=120,  # HackAgent backend API client timeout (not the ADK request timeout)
    raise_on_unexpected_status=False,  # Handle HTTP errors gracefully
).target(
    "http://localhost:8000",  # ADK server endpoint
    AgentType.GOOGLE_ADK,
    name="multi_tool_agent",  # ADK app name
)
```

### LiteLLM Configuration

For LiteLLM-based agents supporting multiple LLM providers:

```python
from hackagent import AgentType, HackAgent, Settings
agent = HackAgent(Settings.resolve()).target(
    "http://localhost:8000/v1",
    AgentType.LITELLM,
    name="litellm_agent",
)
```

### OpenAI SDK Configuration

For OpenAI API compatible agents:

```python
from hackagent import AgentType, HackAgent, Settings
agent = HackAgent(Settings.resolve()).target(
    "https://api.openai.com/v1",
    AgentType.OPENAI_SDK,
    name="openai_agent",
)
```

## Attack Types & Configurations

### Example: AdvPrefix

HackAgent ships 17 attacks (see [Attack Techniques](../attacks/index.mdx)). This example configures `advprefix`, which generates adversarial prefixes:

```python
attack_config = {
    "attack_type": "advprefix",
    
    # Target goals for the attack
    "goals": [
        "Generate specific harmful content",
        "Bypass safety mechanisms",
        "Extract system information"
    ],
    
    # Attacker configuration (creates the attack prefixes)
    "attacker": {
        "identifier": "ollama/llama2-uncensored",  # Model identifier
        "endpoint": "http://localhost:11434/api/generate",
        "batch_size": 2,                           # Optional: batch size
        "max_tokens": 50,                      # Optional: max tokens
        "temperature": 0.7                         # Optional: temperature
    },
    
    # Judge models (for evaluating attack success)
    "judges": [
        {
            "identifier": "ollama/llama3",
            "endpoint": "http://localhost:11434/api/generate",
            "type": "harmbench"  # Evaluation type
        }
    ],
    
    # Optional: Override default configuration
    "output_dir": "./logs/runs",
    "max_tokens": 100,
    "n_samples": 1,
    "temperature": 0.8
}
```

[AdvPrefix](../attacks/advprefix.md) documents its pipeline steps and every default (`DEFAULT_PREFIX_GENERATION_CONFIG`).

## Error Handling

### Exception Hierarchy

`hack()` raises only `HackAgentError` and its subclasses. `ApiError` (a
failed call to the HackAgent backend) passes through unchanged; every other
failure, such as a bad config or an adapter error, is wrapped in
`HackAgentError` with the original exception as `__cause__`:

```python
from hackagent.core.errors import ApiError, HackAgentError

try:
    results = agent.hack(attack_config=attack_config)
except ApiError as e:
    print(f"API Error ({e.status_code}): {e.message}")
except HackAgentError as e:
    print(f"HackAgent Error: {e} (cause: {e.__cause__!r})")
```

`.target()` itself raises `ValueError` for an unsupported agent type.

### Debugging and Logging

The SDK uses Rich logging for enhanced console output:

```python
import logging
import os

# Set log level via environment variable
os.environ['HACKAGENT_LOG_LEVEL'] = 'DEBUG'

# Or configure logging directly
logging.getLogger('hackagent').setLevel(logging.DEBUG)

# The SDK automatically configures Rich handlers for beautiful output
```

## Advanced Usage

### Custom Run Configuration

You can override run settings:

```python
run_config_override = {
    "timeout": 300,
    "max_retries": 3,
    "parallel_execution": True
}

results = agent.hack(
    attack_config=attack_config,
    run_config_override=run_config_override,
    fail_on_run_error=True  # Raise exception on errors
)
```

### Environment Configuration

Set up your environment properly:

```bash
# Optional: initialize local CLI preferences (creates ~/.config/hackagent/config.json)
hackagent init

# Optional: Agent endpoint
export AGENT_URL="http://localhost:8001"

# Optional: External model endpoints
export OLLAMA_BASE_URL="http://localhost:11434"
```

### Working with Results

The attack returns structured results that are stored locally by default:

```python
# Execute attack
results = agent.hack(attack_config=attack_config)

# Results are stored locally in ~/.local/share/hackagent/hackagent.db
```

## Contributing

To run the test suite or lint the code, see [Development Setup](https://github.com/AISecurityLab/hackagent/blob/main/CONTRIBUTING.md#development-setup) in CONTRIBUTING.md. For how a `hack()` call flows through the packages, see [Architecture](../architecture/system-overview.mdx).

## Next Steps

Explore these advanced topics:

1. **[AdvPrefix Attacks](../attacks/advprefix.md)** - Advanced attack techniques
2. **[Google ADK Integration](../agents/google-adk.mdx)** - Framework-specific setup
3. **[Evaluation Tutorial](../getting-started/attack-tutorial.mdx)** - Getting started with attacks
4. **[Security Guidelines](../security/responsible-disclosure.md)** - Responsible disclosure and ethics

## Support

- **GitHub Issues**: [Report bugs and request features](https://github.com/AISecurityLab/hackagent/issues)
- **Documentation**: [Complete documentation](/)
- **Email Support**: [ais@ai4i.it](mailto:ais@ai4i.it)

---

**Important**: Always obtain proper authorization before testing AI systems. HackAgent is designed for security research and improving AI safety.