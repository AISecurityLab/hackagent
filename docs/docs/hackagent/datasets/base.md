---
sidebar_label: base
title: hackagent.datasets.base
---

Base class for dataset providers.

## DatasetProvider Objects

```python
class DatasetProvider(abc.ABC)
```

Abstract base class for dataset providers.

Dataset providers are responsible for loading samples from various sources
and converting them to goal strings that can be used in HackAgent attacks.

#### \_\_init\_\_

```python
def __init__(config: Dict[str, Any])
```

Initialize the dataset provider.

**Arguments**:

- `config` - Provider-specific configuration dictionary.

#### load\_goals

```python
@abc.abstractmethod
def load_goals(limit: Optional[int] = None, **kwargs) -> List[str]
```

Load samples and convert them to goal strings.

**Arguments**:

- `limit` - Maximum number of goals to return. None means all.
- `**kwargs` - Additional provider-specific arguments.
  

**Returns**:

  List of goal strings for use in attacks.

#### get\_metadata

```python
@abc.abstractmethod
def get_metadata() -> Dict[str, Any]
```

Return metadata about the loaded dataset.

**Returns**:

  Dictionary containing metadata like source, total samples, etc.

