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

These values correspond to the string values used in the API&#x27;s agent_type field.

Endpoint Requirements by Type:
- GOOGLE_ADK: Google Agent Development Kit endpoint (custom protocol)
- LITELLM: Any LLM endpoint via LiteLLM (multi-provider support)
- OPENAI_SDK: OpenAI-compatible endpoint (should end with /v1 base path)
- LANGCHAIN: LangServe endpoint (typically /invoke or /stream)
- MCP: Model Context Protocol endpoint (MCP-specific protocol)
- A2A: Agent-to-Agent protocol endpoint (A2A-specific protocol)
- UNKNOWN: Unknown agent type (fallback)

Note: For OpenAI-compatible endpoints (OPENAI_SDK, LITELLM with custom endpoints),
provide the base URL ending in /v1 (e.g., http://localhost:8000/v1).
The OpenAI client will automatically append /chat/completions.

