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
class PrefixGenerationConfig(BaseModel)
```

Unified configuration for the entire prefix generation pipeline.

#### from\_dict

```python
@classmethod
def from_dict(cls, config_dict: Dict[str, Any]) -> "PrefixGenerationConfig"
```

Create config from dictionary, extracting only known fields.

## EvaluationPipelineConfig Objects

```python
class EvaluationPipelineConfig(BaseModel)
```

Unified configuration for the Evaluation stage of the AdvPrefix pipeline.

#### from\_dict

```python
@classmethod
def from_dict(cls, config_dict: Dict[str, Any]) -> "EvaluationPipelineConfig"
```

Create config from dictionary, extracting only known fields.

## EvaluatorConfig Objects

```python
class EvaluatorConfig(BaseModel)
```

Configuration class for response evaluators using AgentRouter framework.

#### agent\_type

AgentTypeEnum from hackagent.router.types

#### coerce\_agent\_type

```python
@model_validator(mode="before")
@classmethod
def coerce_agent_type(cls, values: Any) -> Any
```

Coerce agent_type strings to AgentTypeEnum on construction.

