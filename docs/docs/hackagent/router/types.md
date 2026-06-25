---
sidebar_label: types
title: hackagent.router.types
---

SDK-specific types for HackAgent router.

These types are used internally by the SDK and are not part of the API models.
The API uses plain strings for agent_type, but the SDK provides enums for type safety.

## AgentTypeEnum Objects

```python
class AgentTypeEnum(str, Enum)
```

Enumeration of supported agent types in the HackAgent SDK.

These values correspond to the string values used in the API&#x27;s
agent_type field.

Recommended choice for chat-completion targets:
    - **LITELLM** is the general-purpose path. It speaks
      OpenAI, Anthropic, Google Gemini, AWS Bedrock, Azure, Cohere,
      Mistral, Groq, OpenRouter, Together, vLLM, LM Studio,
      Hugging Face Inference, NVIDIA NIM, and ~140 other providers
      out of the box. Pass the model with a provider prefix in
      ``adapter_operational_config[&quot;name&quot;]`` — e.g.
      ``&quot;anthropic/claude-3-5-sonnet-20241022&quot;``,
      ``&quot;gemini/gemini-2.0-flash&quot;``,
      ``&quot;bedrock/anthropic.claude-3-sonnet-20240229-v1:0&quot;``,
      ``&quot;groq/llama-3.1-70b-versatile&quot;``.

Convenience aliases (same behaviour as ``LITELLM`` with the right
provider prefix; kept for ergonomics and back-compat):
    - **OPENAI_SDK**: OpenAI-compatible endpoint (the official API
      or a local server exposing ``/v1/chat/completions``).
    - **OLLAMA**: targets ``ollama_chat/&lt;model&gt;`` via LiteLLM
      (default endpoint ``http://localhost:11434``).
    - **LANGCHAIN**: LangServe endpoints (treated as OpenAI-compat).

Custom protocols (gap-fillers that LiteLLM doesn&#x27;t speak natively):
    - **GOOGLE_ADK**: deployed Google ADK agent server
      (POST /run with session + event protocol). Implemented as a
      per-instance ``litellm.CustomLLM`` provider.
    - **CLAUDE_CODE**: a locally-installed Claude Code CLI, driven in
      headless mode (``claude -p``). Like ADK, implemented as a
      per-instance ``litellm.CustomLLM`` provider that shells out to the
      ``claude`` binary instead of making an HTTP call — no endpoint.
    - **WEB**: a chatbot on a public website, driven through a real browser
      (Playwright). Point it at the site URL and it types each prompt into
      the live chat widget and reads the reply from the page — works on any
      chat UI regardless of transport (WebSocket/SSE/HTTP). Implemented as a
      per-instance ``litellm.CustomLLM`` provider.
    - **MCP**: Model Context Protocol endpoint (placeholder).
    - **A2A**: Agent-to-Agent protocol endpoint (placeholder).

- **UNKNOWN**: fallback used when the agent type can&#x27;t be inferred.

See ``hackagent/examples/litellm_multi_provider/`` for a working
demo that runs the same attack against several providers by only
changing the model string.

#### \_missing\_

```python
@classmethod
def _missing_(cls, value: object) -> "AgentTypeEnum"
```

Allow case-insensitive lookup and common shorthand aliases.

For example ``AgentTypeEnum(&quot;openai&quot;)`` resolves to
``AgentTypeEnum.OPENAI_SDK``.

