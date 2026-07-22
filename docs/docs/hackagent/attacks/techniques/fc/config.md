---
sidebar_label: config
title: hackagent.attacks.techniques.fc.config
---

Configuration for FC-Attack.

Provides both the plain-dict ``DEFAULT_FC_CONFIG`` (used internally by
:class:`~hackagent.attacks.techniques.fc.attack.FCAttack`) and
typed Pydantic models for structured configuration.

Layout Modes
------------
vertical
    Steps flow top-to-bottom in a single vertical column.
horizontal
    Steps flow left-to-right in a single horizontal row.
s_shaped
    Steps flow in an S-shaped (serpentine/tortuous) path, alternating
    direction on each row for compact display.

## StepGeneratorConfig Objects

```python
class StepGeneratorConfig(BaseModel)
```

Configuration for the step generator LLM.

Used to decompose harmful goals into numbered step descriptions
before rendering them as flowcharts.

**Attributes**:

- `identifier` - Model identifier (e.g. ``&quot;gpt-4&quot;``).
- `endpoint` - API endpoint URL.
- `agent_type` - Agent adapter type (e.g. ``&quot;OPENAI_SDK&quot;``, ``&quot;OLLAMA&quot;``).
- `api_key` - Optional API key for the model provider.
- `max_tokens` - Maximum output tokens for step generation.
- `temperature` - Sampling temperature.

## FCParams Objects

```python
class FCParams(BaseModel)
```

Hyperparameters controlling the FC-Attack flowchart image generation.

**Attributes**:

- `layout` - Flowchart layout mode. One of ``&quot;vertical&quot;`` (top-to-bottom),
  ``&quot;horizontal&quot;`` (left-to-right), or ``&quot;tortuous&quot;`` (S-shaped).
  ``&quot;s_shaped&quot;`` is accepted as an alias for ``&quot;tortuous&quot;``.
- `dpi` - Resolution (dots-per-inch) for Graphviz rendering.
- `num_steps` - Number of steps to decompose the goal into.
- `truncate_last_step` - Whether to truncate the last step to induce
  the target model to complete the harmful content.

## tFCParams Objects

```python
class tFCParams(BaseModel)
```

Hyperparameters controlling the text-only flowchart attack.

**Attributes**:

- `layout` - Flowchart layout mode (affects text serialization structure).
- `text_format` - Graph description format to use.
- `num_steps` - Number of steps to decompose the goal into.
- `truncate_last_step` - Whether to truncate the last step to induce
  the target model to complete the harmful content.

## FCConfig Objects

```python
class FCConfig(ConfigBase)
```

Complete FC-Attack configuration for use with :meth:`HackAgent.hack`.

**Attributes**:

- `attack_type` - Always ``&quot;fc&quot;`` (required by the orchestrator).
- `fc_params` - Flowchart generation hyperparameters.
- `step_generator` - Optional step generator model config. When ``None``,
  a built-in heuristic decomposition is used instead of an LLM.

#### from\_dict

```python
@classmethod
def from_dict(cls, config_dict: Dict[str, Any]) -> "FCConfig"
```

Create a :class:`FCConfig` from a plain dictionary.

#### to\_dict

```python
def to_dict() -> Dict[str, Any]
```

Convert to dictionary.

## tFCConfig Objects

```python
class tFCConfig(ConfigBase)
```

Configuration for the text-only flowchart attack.

**Attributes**:

- `attack_type` - Always ``&quot;tFC&quot;`` (required by the orchestrator).
- `tfc_params` - Text flowchart generation hyperparameters.
- `step_generator` - Optional step generator model config. When ``None``,
  a built-in heuristic decomposition is used instead of an LLM.

#### from\_dict

```python
@classmethod
def from_dict(cls, config_dict: Dict[str, Any]) -> "tFCConfig"
```

Create a :class:`tFCConfig` from a plain dictionary.

#### to\_dict

```python
def to_dict() -> Dict[str, Any]
```

Convert to dictionary.

