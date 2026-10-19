---
sidebar_label: config
title: hackagent.models.config
---

Model configuration.

:class:`ModelConfig` is the declarative description of a model (name,
transport, sampling) used everywhere a campaign names one: the target, the
attack roles, and the judges. :class:`ModelConnection` and
:class:`ModelGeneration` are the resolved LiteLLM arguments built from it.

## ConnectionSpec Objects

```python
class ConnectionSpec(BaseModel)
```

How to reach a model: which client to use, where it lives, and how to
authenticate.

## GenerationSpec Objects

```python
class GenerationSpec(BaseModel)
```

Sampling settings applied to every request the model receives. All optional:
anything left unset uses the provider&#x27;s own default.

## ModelConfig Objects

```python
class ModelConfig(BaseModel)
```

A model HackAgent talks to: its name, how to reach it, and how to sample from
it.

The same shape describes the target, every attack helper (role), every judge,
every guardrail and the goal classifier.

## ModelGeneration Objects

```python
class ModelGeneration(GenerationSpec)
```

Validated generation defaults shared by model implementations.

#### validate\_extra\_kwargs

```python
@model_validator(mode="after")
def validate_extra_kwargs() -> "ModelGeneration"
```

Keep transport and unsupported streaming options out of generation.

#### to\_kwargs

```python
def to_kwargs() -> Dict[str, Any]
```

Return non-null generation arguments for a completion call.

## ModelConnection Objects

```python
class ModelConnection(BaseModel)
```

Validated LiteLLM provider and transport settings.

#### validate\_api\_key\_source

```python
@model_validator(mode="after")
def validate_api_key_source() -> "ModelConnection"
```

Require an unambiguous API-key source.

#### to\_litellm

```python
def to_litellm() -> Dict[str, Any]
```

Resolve secrets and return LiteLLM connection arguments.

