---
sidebar_label: enums
title: hackagent.core.contracts.enums
---

Enums. Wire values are persisted and must not change.

## AgentType Objects

```python
class AgentType(str, Enum)
```

How HackAgent talks to a model or agent.

Chat-completion types (`LITELLM`, `OPENAI_SDK`, `OLLAMA`,
`LANGCHAIN`) are driven through LiteLLM. `GOOGLE_ADK`,
`CLAUDE_CODE`, `CODEX`, `HERMES` and `WEB` use dedicated adapters.
`MCP` and `A2A` are placeholders. `UNKNOWN` is the fallback when a
type cannot be inferred.

#### \_missing\_

```python
@classmethod
def _missing_(cls, value: object) -> Optional["AgentType"]
```

Accept any case and the aliases in `_AGENT_TYPE_ALIASES`.

#### parse

```python
@classmethod
def parse(cls, value: Union["AgentType", str, None]) -> "AgentType"
```

Parse leniently: an unrecognised value becomes `UNKNOWN`.

## RunStatus Objects

```python
class RunStatus(str, Enum)
```

Lifecycle of a run.

## StepKind Objects

```python
class StepKind(str, Enum)
```

Kind of a recorded trace step.

## EvalStatus Objects

```python
class EvalStatus(str, Enum)
```

Evaluation outcome of a result.

