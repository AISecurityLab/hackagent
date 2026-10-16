# Multi-provider LiteLLM demo

Since [#379](https://github.com/AISecurityLab/hackagent/issues/379)
every chat-completion AgentType goes through LiteLLM, so HackAgent
transparently supports the ~140 providers LiteLLM speaks. Picking a
different provider is a model-string change, not a different adapter.

## Quick run

```sh
# Anthropic Claude
ANTHROPIC_API_KEY=sk-…  hackagent campaign run tap-any-provider.yaml --provider anthropic

# Google Gemini
GEMINI_API_KEY=…        hackagent campaign run tap-any-provider.yaml --provider gemini

# AWS Bedrock
AWS_REGION=us-east-1    hackagent campaign run tap-any-provider.yaml --provider bedrock

# Groq
GROQ_API_KEY=…          hackagent campaign run tap-any-provider.yaml --provider groq

# OpenRouter
OPENROUTER_API_KEY=…    hackagent campaign run tap-any-provider.yaml --provider openrouter
```

`anthropic`, `gemini`, `bedrock`, `groq`, `mistral`, `together`,
`openrouter`, `openai` are wired up out of the box. Add more by
editing the `_PROVIDERS` table in [tap-any-provider.yaml](tap-any-provider.yaml).

## Why this works

```python
HackAgent(
    name="my-target",
    agent_type=AgentType.LITELLM,
    endpoint="",
    adapter_operational_config={
        # LiteLLM's model-string convention: "<provider>/<model>"
        "name": "anthropic/claude-3-5-sonnet-20241022",
        # API key resolution: either an env-var name or the raw value.
        "api_key": "ANTHROPIC_API_KEY",
    },
)
```

The full LiteLLM provider catalogue (with the exact prefix for each
provider) is at <https://docs.litellm.ai/docs/providers>.

For protocols LiteLLM can't speak natively (Google ADK servers, MCP,
A2A), HackAgent registers a per-instance `litellm.CustomLLM` provider;
those keep their own AgentType entries (`GOOGLE_ADK` today).
