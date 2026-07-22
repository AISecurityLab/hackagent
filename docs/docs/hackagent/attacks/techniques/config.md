---
sidebar_label: config
title: hackagent.attacks.techniques.config
---

Shared Pydantic configuration primitives for attack techniques.

This module is the single source of truth for the pieces that are genuinely
standard across attacks:

* attacker routing defaults
* judge routing defaults
* judge-evaluation scalars
* goals/dataset input shape
* run/output bookkeeping

Technique-specific modules should extend these building blocks with their own
algorithm parameters, but they should not redefine the shared defaults.

Victim-model request defaults are still defined here for compatibility and
for callers that want the canonical schema, but the preferred runtime source
for those settings is now `HackAgent(..., target_config=...)`.

Two export styles are intentionally supported:

* Pydantic models such as :class:`AttackerConfig` and :class:`RunConfig`
* plain Python dict helpers such as :func:`default_attacker` and
    :data:`DEFAULT_RUN_CONFIG`

The dict helpers are not a compatibility shim; they are the canonical bridge
for attack modules that still build top-level ``DEFAULT_*_CONFIG`` mappings.

## AttackerConfig Objects

```python
class AttackerConfig(BaseModel)
```

Configuration for the attacker LLM.

Defaults to a local Ollama attacker endpoint using an abliterated 12B model so users
only need to override what is different for their deployment.

## CategoryClassifierConfig Objects

```python
class CategoryClassifierConfig(BaseModel)
```

Configuration for per-goal category classification.

This classifier is queried once per goal when a tracker result record is
created, regardless of the selected attack technique.

## JudgeConfig Objects

```python
class JudgeConfig(BaseModel)
```

Configuration for one judge evaluator.

Defaults to a HarmBench judge routed through local Ollama (abliterated 12B).

## JudgeEvalConfig Objects

```python
class JudgeEvalConfig(BaseModel)
```

Scalar evaluation parameters shared by every attack that uses a judge.

## TargetConfig Objects

```python
class TargetConfig(BaseModel)
```

Default generation parameters for the target (victim) model.

## GoalsDatasetConfig Objects

```python
class GoalsDatasetConfig(BaseModel)
```

Shared input source fields for attacks that accept goals or datasets.

## RunConfig Objects

```python
class RunConfig(BaseModel)
```

Pipeline-level bookkeeping shared by every attack.

## ExecutionConfig Objects

```python
class ExecutionConfig(BaseModel)
```

Shared batching and orchestration defaults used across attacks.

## ConfigBase Objects

```python
class ConfigBase(GoalsDatasetConfig, RunConfig, ExecutionConfig,
                 JudgeEvalConfig, TargetConfig)
```

Base typed config for the shared user-facing attack defaults.

#### default\_attacker

```python
def default_attacker() -> Dict[str, Any]
```

Return a fresh attacker config dict.

#### default\_judge

```python
def default_judge() -> Dict[str, Any]
```

Return a fresh single judge config dict.

#### default\_category\_classifier

```python
def default_category_classifier() -> Dict[str, Any]
```

Return a fresh category-classifier config dict.

#### default\_embedder

```python
def default_embedder() -> Dict[str, Any]
```

Return a fresh embedder config dict (local ``embeddinggemma`` on Ollama).

Used by router-based embedder roles such as AutoDAN-Turbo strategy retrieval.

#### default\_rag\_embedder

```python
def default_rag_embedder() -> Dict[str, Any]
```

Return a fresh RAG embedder config dict (local ``embeddinggemma`` on Ollama).

The RAG Attack embeds through an OpenAI-compatible client, so the endpoint
points at Ollama&#x27;s ``/v1`` base and a placeholder API key is provided.

#### default\_judges

```python
def default_judges() -> List[Dict[str, Any]]
```

Return a fresh default judges list (one HarmBench judge).

#### default\_judge\_eval

```python
def default_judge_eval() -> Dict[str, Any]
```

Return a fresh dict of shared judge-evaluation scalar defaults.

#### default\_target

```python
def default_target() -> Dict[str, Any]
```

Return a fresh dict of shared target-generation defaults.

#### default\_goals\_and\_dataset

```python
def default_goals_and_dataset() -> Dict[str, Any]
```

Return a fresh goals/dataset mapping used by attack default dicts.

#### default\_run

```python
def default_run() -> Dict[str, Any]
```

Return a fresh dict of shared run/output defaults.

#### default\_execution

```python
def default_execution() -> Dict[str, Any]
```

Return a fresh dict of shared execution/batching defaults.

#### default\_config\_base

```python
def default_config_base() -> Dict[str, Any]
```

Return shared attack defaults excluding victim request defaults.

