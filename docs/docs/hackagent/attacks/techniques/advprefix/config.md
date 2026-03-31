---
sidebar_label: config
title: hackagent.attacks.techniques.advprefix.config
---

Configuration settings for AdvPrefix attacks.

This module contains default configuration parameters and settings used throughout
the AdvPrefix attack pipeline. These settings control various aspects of the attack
including model parameters, generation settings, evaluation criteria, and output
formatting.

The configuration is designed to be easily customizable while providing sensible
defaults for most use cases.

## PrefixGenerationConfig Objects

```python
@dataclass
class PrefixGenerationConfig()
```

Unified configuration for the entire prefix generation pipeline.

Consolidates all configuration parameters into a single, well-structured
dataclass that can be easily validated and passed around.

#### from\_dict

```python
@classmethod
def from_dict(cls, config_dict: Dict[str, Any]) -> "PrefixGenerationConfig"
```

Create config from dictionary, extracting only known fields.

## EvaluationPipelineConfig Objects

```python
@dataclass
class EvaluationPipelineConfig()
```

Unified configuration for the Evaluation stage of the AdvPrefix pipeline.

Consolidates all configuration parameters for judge evaluation, result aggregation,
and prefix selection into a single, well-structured dataclass.

#### from\_dict

```python
@classmethod
def from_dict(cls, config_dict: Dict[str, Any]) -> "EvaluationPipelineConfig"
```

Create config from dictionary, extracting only known fields.

## EvaluatorConfig Objects

```python
@dataclass
class EvaluatorConfig()
```

Configuration class for response evaluators using AgentRouter framework.

This dataclass encapsulates all configuration parameters needed to set up
and operate different types of judge evaluators for assessing adversarial
attack success. It supports various agent types and provides comprehensive
configuration for both local and remote evaluation setups.

**Attributes**:

- `agent_name` - Unique identifier for this judge agent configuration.
- `agent_type` - Type of agent backend (e.g., AgentTypeEnum.LITELLM).
- `model_id` - Model identifier string (e.g., &quot;ollama/llama3&quot;, &quot;gpt-4&quot;).
- `agent_endpoint` - Optional API endpoint URL for the agent service.
- `organization_id` - Optional organization identifier for backend agent.
- `agent_metadata` - Optional dictionary containing agent-specific metadata.
- `batch_size` - Number of evaluation requests to process in batches.
- `max_tokens_eval` - Maximum tokens to generate per evaluation.
- `filter_len` - Minimum response length threshold for pre-filtering.
- `timeout` - Timeout in seconds for individual evaluation requests.
- `agent_type`0 - Sampling temperature for judge model responses (0.0 for deterministic).

#### agent\_type

AgentTypeEnum from hackagent.server.api.models

#### \_\_post\_init\_\_

```python
def __post_init__()
```

Coerce agent_type strings to AgentTypeEnum on construction.

