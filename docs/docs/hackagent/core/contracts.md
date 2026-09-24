---
sidebar_label: contracts
title: hackagent.core.contracts
---

Shared vocabulary: the values that cross package boundaries.

Every package may import this module. It holds data definitions and
protocols only, no behaviour beyond validation and small properties.

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

## RawExchange Objects

```python
class RawExchange(BaseModel)
```

The provider-level request and response, for callers that need them.

## LLMError Objects

```python
class LLMError(BaseModel)
```

Why a call failed. Calls return errors as values.

## GuardrailInfo Objects

```python
class GuardrailInfo(BaseModel)
```

A guardrail blocked the prompt (`before`) or the response (`after`).

## Completion Objects

```python
class Completion(BaseModel)
```

The result of one model call.

Replaces the response dict: `generated_text` / `processed_response`
become `text`; `error_message` / `error_category` become `error`;
`agent_specific_data` usage, finish reason, model and invoked
parameters become typed fields; `raw_response_*` and `raw_request`
become `raw`; a guardrail envelope becomes `guardrail`.

#### ok

```python
@property
def ok() -> bool
```

True when the call produced a usable response.

#### blocked

```python
@property
def blocked() -> bool
```

True when a guardrail blocked or censored the call.

#### guardrail\_info

```python
@property
def guardrail_info() -> Dict[str, Any]
```

Guardrail metadata as a plain dict (empty when not blocked).

## ModelSpec Objects

```python
class ModelSpec(BaseModel)
```

How to reach one model: the target or any role model.

## JudgeSpec Objects

```python
class JudgeSpec(ModelSpec)
```

A judge model and how to read its verdicts.

## Goal Objects

```python
class Goal(BaseModel)
```

One goal to attack, with its position in the run.

## Sample Objects

```python
class Sample(BaseModel)
```

One exchange to judge.

## JudgeVote Objects

```python
class JudgeVote(BaseModel)
```

One judge&#x27;s score for a sample, on the judge&#x27;s native scale.

`error` is set when the judge gave no usable answer: the call failed or
the reply could not be parsed. That vote is an abstention. Its `score`
and `success` are `None` and aggregation leaves it out.

#### abstained

```python
@property
def abstained() -> bool
```

True when this judge gave no usable answer.

#### NORMALIZED\_SCORE\_MAX

Every verdict score is normalised onto 0..NORMALIZED_SCORE_MAX.

## Verdict Objects

```python
class Verdict(BaseModel)
```

The combined judgement of a sample.

`error` is set when every judge abstained. The sample was then not
judged: `success` is false and `score` is 0, but neither is a finding.
Report it as unjudged, not as a failed attack.

## LLM Objects

```python
@runtime_checkable
class LLM(Protocol)
```

A callable model. Calls never raise for provider errors.

## LLMFactory Objects

```python
@runtime_checkable
class LLMFactory(Protocol)
```

Builds the LLM for a role model.

