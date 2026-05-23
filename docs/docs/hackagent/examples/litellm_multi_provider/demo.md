---
sidebar_label: demo
title: hackagent.examples.litellm_multi_provider.demo
---

Multi-provider HackAgent demo via LiteLLM.

The same HackAgent attack configuration works against any of the
~140 providers LiteLLM understands. The only thing that changes
between providers is:

  1. The ``model`` string (prefixed with the LiteLLM provider name).
  2. The provider&#x27;s API key environment variable.

This script picks a provider by ``--provider`` flag (or
``HACKAGENT_PROVIDER`` env var, default ``anthropic``) and runs a
short TAP attack against it. Use it as a starting point for adapting
the existing ``examples/openai_sdk`` or ``examples/ollama`` demos to
a different cloud LLM.

Usage:
    # Anthropic Claude
    ANTHROPIC_API_KEY=… python demo.py --provider anthropic

    # Google Gemini
    GEMINI_API_KEY=… python demo.py --provider gemini

    # AWS Bedrock (also needs AWS_REGION + AWS creds)
    AWS_REGION=us-east-1 python demo.py --provider bedrock

    # Groq
    GROQ_API_KEY=… python demo.py --provider groq

    # OpenAI (for completeness)
    OPENAI_API_KEY=… python demo.py --provider openai

    # Mistral
    MISTRAL_API_KEY=… python demo.py --provider mistral

    # Together
    TOGETHER_API_KEY=… python demo.py --provider together

    # OpenRouter (proxy in front of many providers)
    OPENROUTER_API_KEY=… python demo.py --provider openrouter

Reference:
    LiteLLM provider catalogue: https://docs.litellm.ai/docs/providers

#### build\_demo\_config

```python
def build_demo_config(provider: str) -> dict
```

Return the HackAgent config for the chosen provider.

The structure is identical to ``examples/ollama/demo.py``; only the
``agent_type`` becomes ``AgentTypeEnum.LITELLM`` and the model
strings carry a provider prefix (``anthropic/…``, ``gemini/…``…).

#### run\_demo

```python
def run_demo(provider: str) -> object
```

Build the config for ``provider`` and execute the attack.

