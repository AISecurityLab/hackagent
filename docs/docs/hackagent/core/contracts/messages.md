---
sidebar_label: messages
title: hackagent.core.contracts.messages
---

Chat messages and tool calls.

## ToolCall Objects

```python
class ToolCall(BaseModel)
```

A tool invocation requested by a model.

## Message Objects

```python
class Message(BaseModel)
```

One chat message. `content` is text or OpenAI-style content parts.

