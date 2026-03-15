---
sidebar_label: registry
title: hackagent.datasets.registry
---

Registry and factory functions for dataset providers.

This module provides the main entry point for loading goals from various sources.

#### register\_provider

```python
def register_provider(name: str,
                      provider_class: Type[DatasetProvider]) -> None
```

Register a dataset provider.

**Arguments**:

- `name` - The provider name.
- `provider_class` - The provider class.

#### get\_provider

```python
def get_provider(name: str, config: Dict[str, Any]) -> DatasetProvider
```

Get a dataset provider instance by name.

**Arguments**:

- `name` - The provider name (e.g., &quot;huggingface&quot;, &quot;file&quot;).
- `config` - Provider configuration dictionary.
  

**Returns**:

  Configured DatasetProvider instance.
  

**Raises**:

- `ValueError` - If the provider is not found.

#### load\_goals

```python
def load_goals(preset: Optional[str] = None,
               provider: Optional[str] = None,
               path: Optional[str] = None,
               goal_field: Optional[str] = None,
               split: Optional[str] = None,
               name: Optional[str] = None,
               limit: Optional[int] = None,
               shuffle: bool = False,
               seed: Optional[int] = None,
               **kwargs) -> List[str]
```

Load attack goals from a dataset source.

This is the main entry point for loading goals. It supports three modes:
1. Preset mode: Use a pre-configured dataset by name
2. Provider mode: Directly specify provider and dataset details
3. Config mode: Pass a full configuration dictionary

**Arguments**:

- `preset` - Name of a pre-configured dataset preset (e.g., &quot;agentharm&quot;, &quot;strongreject&quot;).
- `provider` - Provider type (&quot;huggingface&quot; or &quot;file&quot;).
- `path` - Dataset path (HuggingFace dataset ID or file path).
- `goal_field` - Field name containing the goal text.
- `split` - Dataset split to use (for HuggingFace).
- `name` - Dataset configuration name (for HuggingFace datasets with multiple configs).
- `limit` - Maximum number of goals to return.
- `shuffle` - Whether to shuffle before selecting.
- `seed` - Random seed for shuffling.
- `**kwargs` - Additional provider-specific configuration.
  

**Returns**:

  List of goal strings.
  

**Examples**:

  # Using a preset
  goals = load_goals(preset=&quot;agentharm&quot;, limit=50)
  
  # Using HuggingFace directly
  goals = load_goals(
  provider=&quot;huggingface&quot;,
  path=&quot;ai-safety-institute/AgentHarm&quot;,
  name=&quot;harmful&quot;,
  goal_field=&quot;prompt&quot;,
  split=&quot;test_public&quot;,
  limit=100
  )
  
  # Using a local file
  goals = load_goals(
  provider=&quot;file&quot;,
  path=&quot;./my_goals.json&quot;,
  goal_field=&quot;objective&quot;
  )
  

**Raises**:

- `provider`0 - If neither preset nor provider is specified.

#### load\_goals\_from\_config

```python
def load_goals_from_config(config: Dict[str, Any]) -> List[str]
```

Load goals from a configuration dictionary.

This function is designed to be called from the AttackOrchestrator
when a &#x27;dataset&#x27; key is present in the attack configuration.

**Arguments**:

- `config` - Dataset configuration dictionary with keys:
  - preset (str, optional): Preset name
  - provider (str, optional): Provider type
  - path (str, optional): Dataset path
  - goal_field (str, optional): Field containing goals
  - split (str, optional): Dataset split
  - name (str, optional): Dataset config name
  - limit (int, optional): Max goals to load
  - shuffle (bool, optional): Shuffle before selecting
  - seed (int, optional): Random seed
  

**Returns**:

  List of goal strings.
  
  Example config:
  &#123;
- `"preset"` - &quot;agentharm&quot;,
- `"limit"` - 100,
- `"shuffle"` - True
  &#125;
  
  Or:
  
  &#123;
- `"provider"` - &quot;huggingface&quot;,
- `"path"` - &quot;ai-safety-institute/AgentHarm&quot;,
- `"goal_field"` - &quot;prompt&quot;,
- `"split"` - &quot;test_public&quot;,
- `"limit"` - 50
  &#125;

